import json
import typing
from base64 import b64decode
from base64 import b64encode
from contextlib import contextmanager

from Crypto import Random
from Crypto.Cipher import AES

if typing.TYPE_CHECKING:
    from .. import Proteus


def random_bytes(size):
    return Random.new().read(size)


def generate_aes_cipher(key_size=32):
    return {
        "type": "aes256",
        "key": b64encode(random_bytes(key_size)).decode("utf-8", "ignore"),
    }


class SafelyCommonBase:
    def __init__(self, proteus: "Proteus"):
        self.proteus = proteus
        self.config = None

    def _init_auto(self):
        return self._init(**self._safely_kwargs())

    def _init(self, image_ref=None, key=None, key_type=None):
        if key and key_type:
            self.config = {"cipher": {"key": key, "type": key_type}}
        elif image_ref:
            with self._maybe_login_to_vault(ensure_login=True):
                self.config = self.proteus.vault.get_config(image_ref)
        else:
            raise RuntimeError(
                "Missing config for safely. Please provide either image_ref "
                "(SAFELY_IMAGE  conf params) with Vault credentials or "
                "key/key_type(SAFELY_KEY/SAFELY_KEY_TYPE conf params)"
            )

    def arrange_keys(self, create_key=False, replace_key=False, save_to_vault=False):
        if replace_key or self.config is None and create_key:
            self.config = dict(cipher=generate_aes_cipher())
            self.proteus.logger.info(f"Generated new key: {json.dumps(self.config, indent=2)}")

            self.proteus.config.safely_key = self.config["cipher"]["key"]
            self.proteus.config.safely_key_type = self.config["cipher"]["type"]

            self.proteus.logger.info(
                f"proteus.safely is now using SAFELY_KEY={self.proteus.config.safely_key} and "
                f"SAFELY_KEY_TYPE={self.proteus.config.safely_key_type} globally! This config "
                f"will be gone when leaving the exiting this process."
            )

        if save_to_vault:
            with self._maybe_login_to_vault(ensure_login=True):
                self.proteus.vault.save_config(self.proteus.config.safely_image, self.config)
            self.proteus.logger.info(f"Stored new key in vault with key {self.proteus.config.safely_image}")

    def get_cipher(self, iv):
        config = self.config
        cipher = config.get("cipher", {})
        cipher_type = cipher.get("type")
        if cipher_type == "aes256":
            key = b64decode(cipher.get("key"))
            return AES.new(key, AES.MODE_CBC, iv)
        raise Exception(f"Unknown encryption type {cipher_type}")

    @contextmanager
    def _maybe_login_to_vault(self, ensure_login=True):
        _, method_auth_vault_enabled = self._check_safely_config()

        (
            method_auth_vault_client_proteus_username,
            method_auth_vault_client_vault_username,
        ) = self._check_safely_config_vault_credentials()

        if method_auth_vault_enabled:
            if method_auth_vault_client_vault_username:
                self.proteus.logger.info("Logging in into Vault using VAULT_USERNAME/VAULT_PASSWORD")
                self.proteus.vault.authenticate_with_userpass(
                    self.proteus.config.vault_username, self.proteus.config.vault_password
                )

            if not self.proteus.vault.is_logged_in and method_auth_vault_client_proteus_username:
                self.proteus.logger.info("Logging in into Vault using Proteus USERNAME/PASSWORD")
                with self.proteus.runs_authentified(
                    user=self.proteus.config.username, password=self.proteus.config.password
                ):
                    self.proteus.vault.authenticate_with_jwt(self.proteus.auth)

        if ensure_login and not self.proteus.vault.is_logged_in:
            raise RuntimeError(
                "Could not login into the vault, please provide configuration paramaters: "
                "VAULT_HOST, SAFELY_IMAGE and <USERNAME, PASSWORD> pair or <VAULT_USERNAME, "
                "VAULT_PASSWORD>."
            )

        yield

    def _safely_kwargs(self):

        method_auth_explicit_key, method_auth_vault_enabled = self._check_safely_config()

        kwargs = {}

        if method_auth_vault_enabled:
            kwargs.update(dict(image_ref=self.proteus.config.safely_image))

        if method_auth_explicit_key:
            kwargs.update(dict(key=self.proteus.config.safely_key, key_type=self.proteus.config.safely_key_type))

        return kwargs

    def _check_safely_config(self):

        (
            method_auth_vault_client_proteus_username,
            method_auth_vault_client_vault_username,
        ) = self._check_safely_config_vault_credentials()

        method_auth_vault_enabled = (
            (method_auth_vault_client_proteus_username or method_auth_vault_client_vault_username)
            and self.proteus.config.vault_host
            and self.proteus.config.safely_image
        )

        # In this authentication method, the user directly provides the cyphering key. If no
        # vault credentials are provided, no key sync is stored in the vault
        method_auth_explicit_key = self.proteus.config.safely_key and self.proteus.config.safely_key_type

        if not method_auth_explicit_key and not method_auth_vault_enabled:
            raise RuntimeError(
                """Not enough information to run safely. Please either provide:
* Proteus config with SAFELY_KEY and SAFELY_KEY_TYPE(optional).
* Proteus config with VAULT_HOST, SAFELY_IMAGE and <USERNAME, PASSWORD> pair or <VAULT_USERNAME, VAULT_PASSWORD>.
"""
            )

        return bool(method_auth_explicit_key), bool(method_auth_vault_enabled)

    def _check_safely_config_vault_credentials(self):
        # It is possible to log in into the vault:
        # a) With a proteus/keycloak username/password. Normally these have only readonly permission
        #    or no permission at all
        # b) With a direct vault username/password. Normally these have write permissions
        method_auth_vault_client_proteus_username = (
            self.proteus.config.vault_host and self.proteus.config.username and self.proteus.config.password
        )

        method_auth_vault_client_vault_username = (
            self.proteus.config.vault_host and self.proteus.config.vault_username and self.proteus.config.vault_password
        )

        return bool(method_auth_vault_client_proteus_username), bool(method_auth_vault_client_vault_username)
