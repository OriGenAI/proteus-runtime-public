import os
from dataclasses import dataclass
from typing import Optional

from envclasses import load_env, envclass
import hashlib


@envclass
@dataclass
class Config:
    client_secret: Optional[str] = None

    log_loc: Optional[str] = None
    promt: bool = True
    auth_host: str = "https://auth.dev.origen.ai"
    api_host: str = "https://proteus-test.dev.origen.ai"
    api_host_v2: Optional[str] = None
    vault_host: str = "https://vault.dev.origen.ai"
    vault_username: Optional[str] = None
    vault_password: Optional[str] = None
    username: Optional[str] = ""
    password: Optional[str] = ""
    realm: str = "origen"
    client_id: str = "proteus-front"
    refresh_gap: int = 10  # Seconds
    ignore_worker_status: bool = False
    upload_presigned: bool = True
    ssl_verify: bool = True
    default_retry_times: int = 5
    default_retry_wait: float = 0.5  # s
    default_timeout = 30  # s
    worker_uuid: Optional[str] = None

    safely_enabled: Optional[bool] = False
    safely_path: Optional[str] = "private"
    safely_image: Optional[str] = None
    safely_key: Optional[str] = None
    safely_key_type: Optional[str] = "aes256"

    mqtt_broker_url: Optional[str] = None
    mqtt_broker_port: Optional[int] = None
    mqtt_keep_alive: Optional[int] = 60
    mqtt_token: Optional[str] = None

    @property
    def mqtt_id(self):
        combined = f"{self.mqtt_broker_url}-{self.safely_image}-{self.safely_key}-{self.username}-{self.password}"
        return hashlib.sha256(combined.encode()).hexdigest()

    @classmethod
    def auto(cls, *args, **kwargs):
        to_remove_from_environ = set()

        for alternate_name, final_name in (
            ("API_SSL_VERIFY", "SSL_VERIFY"),
            ("WORKER_USERNAME", "USERNAME"),
            ("WORKER_USERNAME", "PASSWORD"),
            ("PROTEUS_USERNAME", "USERNAME"),
            ("PROTEUS_PASSWORD", "PASSWORD"),
            ("VAULT_ADDR", "VAULT_HOST"),
            ("API_V2_HOST", "API_HOST_V2"),
            ("CLIENT_ID", "OIDC_CLIENT_ID"),
            ("AUTH_HOST", "OIDC_HOST"),
            ("OIDC_WORKERS_REALM", "REALM"),
            ("OIDC_REALM", "REALM"),
            ("CURRENT_IMAGE", "SAFELY_IMAGE"),
            ("SAFETY_PATH", "SAFELY_PATH"),
            ("MQTT_BROKER_URL", "MQTT_BROKER_URL"),
            ("MQTT_BROKER_PORT", "MQTT_BROKER_PORT"),
            ("MQTT_KEEP_ALIVE", "MQTT_KEEP_ALIVE"),
        ):
            if final_name not in os.environ and alternate_name in os.environ:
                os.environ[final_name] = os.environ[alternate_name]
                to_remove_from_environ.add(final_name)

        config = cls(*args, **kwargs)
        load_env(config, prefix="")

        for to_remove_env in to_remove_from_environ:
            os.environ.pop(to_remove_env)

        return config
