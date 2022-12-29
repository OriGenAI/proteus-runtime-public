from dataclasses import dataclass


@dataclass
class Config:
    client_secret: str = None

    log_loc: str = "logs"
    promt: bool = True
    auth_host: str = "https://auth.dev.origen.ai"
    api_host: str = "https://proteus-test.dev.origen.ai"
    username: str = "user-not-configured"
    password: str = "password-not-configured"
    realm: str = "origen"
    client_id: str = "proteus-front"
    refresh_gap: int = 10  # Seconds
    ignore_worker_status: bool = False
