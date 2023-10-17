import glob
import os
import py_compile
import shutil
import sys
import typing
from base64 import b64decode, b64encode
from functools import wraps
from importlib.abc import PathEntryFinder
from importlib.machinery import FileFinder, SourcelessFileLoader
from pathlib import Path

from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Util import Padding

if typing.TYPE_CHECKING:
    from . import Proteus


def random_bytes(size):
    return Random.new().read(size)


def generate_aes_cipher(key_size=32):
    return {
        "type": "aes256",
        "key": b64encode(random_bytes(key_size)).decode("utf-8", "ignore"),
    }


def create_folder(path, source_root, target_root):
    target_file = path.replace(source_root, target_root)
    target_folder = "/".join(target_file.split("/")[:-1])
    Path(target_folder).mkdir(parents=True, exist_ok=True)


def protect_source_file(safely, source_file, source_root, target_root):
    target_file = source_file.replace(source_root, target_root).replace(".py", ".epyc")
    compiled = py_compile.compile(source_file)
    with open(compiled, "rb") as source:
        safely.store(source, target_file)
        print(f"{source_file} --> {target_file}")


def copy_to_path_protected(safely, source_root, target_root):
    entries = glob.glob(source_root + "/**", recursive=True)
    for path in entries:
        create_folder(path, source_root, target_root)
        if os.path.isfile(path):
            filepath = path
            if filepath.endswith(".py"):
                protect_source_file(safely, filepath, source_root, target_root)
            else:
                target_filepath = path.replace(source_root, target_root)
                shutil.copy2(filepath, target_filepath)
        continue


def EPyCLoaderWithContext(safely: "Safely"):
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
    def install(cls, safely: "Safely", basepath=None):
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


class Safely:
    def __init__(self, proteus: "Proteus"):
        self.proteus = proteus
        self.config = None

    def init(self, auth=None, image_ref=None, key=None, key_type=None):
        if key and key_type:
            self.config = {"cipher": {"key": key, "type": key_type}}
        elif auth and image_ref:
            self.config = self.proteus.vault.authenticate_with_jwt(auth).get_config(image_ref)
        else:
            raise RuntimeError("Missing config for safely. Please provide either auth/image_ref or key/key_type")

    def get_cipher(self, iv):
        config = self.config
        cipher = config.get("cipher", {})
        cipher_type = cipher.get("type")
        if cipher_type == "aes256":
            key = b64decode(cipher.get("key"))
            return AES.new(key, AES.MODE_CBC, iv)
        raise Exception(f"Unknown encryption type {cipher_type}")

    def store(self, stream, path):
        with open(path, "wb") as output:
            iv = random_bytes(AES.block_size)
            output.write(iv)
            cipher = self.get_cipher(iv)
            ciphered_text = cipher.encrypt(Padding.pad(stream.read(), AES.block_size))
            output.write(ciphered_text)

    def retrieve(self, path):
        with open(path, "rb") as stream:
            iv = stream.read(AES.block_size)
            cipher = self.get_cipher(iv)
            cleartext = cipher.decrypt(stream.read())

            if cleartext == b"":
                return cleartext

            return Padding.unpad(cleartext, AES.block_size)

    def protected(self, basepath="private"):
        MetaFileFinder.install(self, basepath)
        return self

    def runs_safely(self, func):
        """Decorator obtains key to perform critic code safely."""

        if not self.proteus.config.safety_enabled:
            self.proteus.logger.warning("Warning. Safety is disabled")
            return func

        @wraps(func)
        def wrapper(*args, **kwargs):

            if self.config is None:
                if not self.proteus.config.safely_path:
                    raise RuntimeError("SAFELY_PATH proteus config is not set")

                method_auth_explicit_key = self.proteus.config.safely_key and self.proteus.config.safely_key_type
                method_auth_vault_enabled = (
                    method_auth_explicit_key
                    or self.proteus.config.vault_host
                    and self.proteus.config.vault_username
                    and self.proteus.config.vault_password
                    and self.proteus.config.safely_image
                )

                if not method_auth_explicit_key and not method_auth_vault_enabled:
                    raise RuntimeError(
                        """Not enough information to run safely. Please either provide:
  * Proteus SAFELY_KEY and SAFELY_KEY_TYPE(optional) config
  * Proteus USERNAME, PASSWORD, VAULT_HOST, VAULT_USERNAME, VAULT_PASSWORD and SAFELY_IMAGE config
"""
                    )

                def _init():
                    kwargs = {}

                    if method_auth_vault_enabled:
                        kwargs.update(dict(auth=self.proteus.auth, image_ref=self.proteus.config.safely_image))

                    if method_auth_explicit_key:
                        kwargs.update(
                            dict(key=self.proteus.config.safely_key, key_type=self.proteus.config.safely_key_type)
                        )

                    self.proteus.safely.init(**kwargs)
                    self.proteus.safely.protected(basepath=self.proteus.config.safely_path)

                if method_auth_vault_enabled and not self.proteus.auth.who:
                    _init = self.proteus.runs_authentified(_init)

                _init()

            return func(*args, **kwargs)

        return wrapper
