import glob
import os
import py_compile
import shutil
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Util import Padding

from proteus.safe.common import SafelyCommonBase, random_bytes


def create_folder(path, source_root, target_root):
    target_file = path.replace(source_root, target_root)
    target_folder = "/".join(target_file.split("/")[:-1])
    Path(target_folder).mkdir(parents=True, exist_ok=True)


class SafelyCypherMixin(SafelyCommonBase):
    def protect_source_file(self, source_file, source_root, target_root):
        target_file = source_file.replace(source_root, target_root).replace(".py", ".epyc")
        compiled = py_compile.compile(source_file)
        with open(compiled, "rb") as source:
            self.store(source, target_file)
            self.proteus.logger.info(f"{source_file} --> {target_file}")

    def copy_to_path_protected(self, source_root, target_root):
        new_source_root = None
        old_source_root = None
        if source_root == target_root:
            base_source_root = "_" + source_root
            new_source_root = base_source_root
            idx = 1
            while os.path.exists(new_source_root):
                new_source_root = f"{base_source_root}_{idx}"
                idx += 1

            shutil.move(source_root, new_source_root)
            old_source_root = source_root
            source_root = new_source_root
            self.proteus.logger.info(
                f"Origin/Destination paths are the same. We have preserved the old source path "
                f'by renaming it from "{old_source_root}" to "{new_source_root}"'
            )

        if os.path.exists(target_root):
            raise RuntimeError(f"Cannot protect {source_root}, target {target_root} already exists!")

        try:
            entries = glob.glob(source_root + "/**", recursive=True)
            for path in entries:
                create_folder(path, source_root, target_root)
                if os.path.isfile(path):
                    filepath = path
                    if filepath.endswith(".py"):
                        self.protect_source_file(filepath, source_root, target_root)
                    else:
                        target_filepath = path.replace(source_root, target_root)
                        shutil.copy2(filepath, target_filepath)
                continue
        except BaseException:
            shutil.rmtree(target_root)
            if new_source_root and old_source_root:
                shutil.move(new_source_root, old_source_root)
            raise

    def store(self, stream, path):
        with open(path, "wb") as output:
            iv = random_bytes(AES.block_size)
            output.write(iv)
            cipher = self.get_cipher(iv)
            ciphered_text = cipher.encrypt(Padding.pad(stream.read(), AES.block_size))
            output.write(ciphered_text)

    def protect(self, path=None, output=None, create_key=True, replace_key=False, save_to_vault=False):
        if path is None:
            if not self.proteus.config.safely_path:
                raise RuntimeError("SAFELY_PATH proteus config is not set")

            path = self.proteus.config.safely_path

        if output is None:
            output = path

        if self.config is None:
            self._init_auto()
            self.arrange_keys(create_key=create_key, replace_key=replace_key, save_to_vault=save_to_vault)

        if self.config is None:
            raise RuntimeError(f'No cyphering key to protect "{path}". Maybe you should use replace_key/create_key?')

        self.copy_to_path_protected(path, output)
