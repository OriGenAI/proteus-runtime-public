import os
import sys
from functools import wraps
from importlib.abc import PathEntryFinder
from importlib.machinery import FileFinder, SourcelessFileLoader

from Crypto.Cipher import AES
from Crypto.Util import Padding

from .common import SafelyCommonBase


def EPyCLoaderWithContext(safely: "SafelyDecipherMixin"):
    class _EPyCLoader(SourcelessFileLoader):
        def __init__(self, fullname, path):
            self.fullname = fullname
            self.path = path

        def get_filename(self, fullname):
            return self.path

        def get_data(self, filename):
            """exec_module is already defined for us, we just have to provide a way
            of getting the source code of the module"""
            return safely.retrieve(filename)

    return _EPyCLoader


@PathEntryFinder.register
class MetaFileFinder:
    """
    A 'middleware', if you will, between the PathFinder sys.meta_path hook,
    and sys.path_hooks hooks--particularly FileFinder.

    The hook returned by FileFinder.path_hook is rather 'promiscuous' in that
    it will handle *any* directory.  So if one wants to insert another
    FileFinder.path_hook into sys.path_hooks, that will totally take over
    importing for any directory, and previous path hooks will be ignored.

    This class provides its own sys.path_hooks hook as follows: If inserted
    on sys.path_hooks (it should be inserted early so that it can supersede
    anything else).  Its find_spec method then calls each hook on
    sys.path_hooks after itself and, for each hook that can handle the given
    sys.path entry, it calls the hook to create a finder, and calls that
    finder's find_spec.  So each sys.path_hooks entry is tried until a spec is
    found or all finders are exhausted.
    """

    class hook:
        """
        Use this little internal class rather than a function with a closure
        or a classmethod or anything like that so that it's easier to
        identify our hook and skip over it while processing sys.path_hooks.
        """

        def __init__(self, basepath=None):
            self.basepath = os.path.abspath(basepath)

        def __call__(self, path):
            if not os.path.isdir(path):
                raise ImportError("only directories are supported", path=path)
            elif not self.handles(path):
                raise ImportError(
                    "only directories under {} are supported".format(self.basepath),
                    path=path,
                )

            return MetaFileFinder(path)

        def handles(self, path):
            """
            Return whether this hook will handle the given path, depending on
            what its basepath is.
            """

            path = os.path.abspath(path)
            return self.basepath is None or os.path.commonpath([self.basepath, path]) == self.basepath

    def __init__(self, path):
        self.path = path
        self._finder_cache = {}

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self.path)

    def find_spec(self, fullname, target=None):
        if not sys.path_hooks:
            return None

        last = len(sys.path_hooks) - 1

        for idx, hook in enumerate(sys.path_hooks):
            if isinstance(hook, self.__class__.hook):
                continue

            finder = None
            try:
                if hook in self._finder_cache:
                    finder = self._finder_cache[hook]
                    if finder is None:
                        # We've tried this finder before and got an ImportError
                        continue
            except TypeError:
                # The hook is unhashable
                pass

            if finder is None:
                try:
                    finder = hook(self.path)
                    self._finder_cache[hook] = finder
                except ImportError:
                    pass
                except TypeError:
                    # The hook is unhashable for some reason so we don't bother
                    # caching it
                    pass

            if finder is not None:
                spec = finder.find_spec(fullname, target)
                if spec is not None and (spec.loader is not None or idx == last):
                    # If no __init__.<suffix> was found by any Finder,
                    # we may be importing a namespace package (which
                    # FileFinder.find_spec returns in this case).  But we
                    # only want to return the namespace ModuleSpec if we've
                    # exhausted every other finder first.
                    return spec

        # Module spec not found through any of the finders
        return None

    def find_module(self, fullname, path=None):
        return None

    def invalidate_caches(self):
        for finder in self._finder_cache.values():
            finder.invalidate_caches()

    @classmethod
    def install(cls, safely: "SafelyDecipherMixin", basepath=None):
        """
        Install the MetaFileFinder in the front sys.path_hooks, so that
        it can support any existing sys.path_hooks and any that might
        be appended later.

        If given, only support paths under and including basepath.  In this
        case it's not necessary to invalidate the entire
        sys.path_importer_cache, but only any existing entries under basepath.
        """

        if basepath is not None:
            basepath = os.path.abspath(basepath)

        EPyCLoader = EPyCLoaderWithContext(safely)
        hook = cls.hook(basepath)
        sys.path_hooks.insert(0, hook)
        loader_details = (EPyCLoader, [".epyc"])
        sys.path_hooks.append(FileFinder.path_hook(loader_details))
        if basepath is None:
            sys.path_importer_cache.clear()
        else:
            for path in list(sys.path_importer_cache):
                if hook.handles(path):
                    del sys.path_importer_cache[path]


class SafelyDecipherMixin(SafelyCommonBase):

    PROTECTED_READ_PATHS = {}

    def retrieve(self, path):
        with open(path, "rb") as stream:
            iv = stream.read(AES.block_size)
            cipher = self.get_cipher(iv)
            cleartext = cipher.decrypt(stream.read())

            if cleartext == b"":
                return cleartext

            return Padding.unpad(cleartext, AES.block_size)

    def enable_protected_read(self, basepath):
        MetaFileFinder.install(self, basepath)
        self.PROTECTED_READ_PATHS = basepath
        return self

    def runs_safely(self, func):
        """Decorator obtains key to perform critic code safely."""

        if not self.proteus.config.safely_enabled:
            self.proteus.logger.warning("Warning. Safety is disabled")
            return func

        @wraps(func)
        def wrapper(*args, **kwargs):

            if not self.proteus.config.safely_path:
                raise RuntimeError("SAFELY_PATH proteus config is not set")

            if self.config is None:
                self._init_auto()

            if self.proteus.config.safely_path not in self.PROTECTED_READ_PATHS:
                self.proteus.safely.enable_protected_read(basepath=self.proteus.config.safely_path)

            return func(*args, **kwargs)

        return wrapper
