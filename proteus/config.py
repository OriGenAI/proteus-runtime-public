import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    DEBUG = False
    TESTING = False
    DEVELOPMENT = False

    OUTPUT_LOC = "output"
    TEMPLATE_NAME = "case_template"
    INPUT_LOC = "input"
    LOG_LOC = "logs"

    SLEEP_TIME = 30
    PROMPT = True
    AUTH_HOST = os.getenv("AUTH_HOST", "https://auth.dev.origen.ai")
    API_HOST = os.getenv(
        "API_HOST", "https://proteus-test.dev.origen.ai"
    )

    PROTEUS_USERNAME = os.getenv("PROTEUS_USERNAME")
    WORKER_USERNAME = os.getenv("WORKER_USERNAME", "user-not-configured")
    USERNAME = PROTEUS_USERNAME or WORKER_USERNAME

    PROTEUS_PASSWORD = os.getenv("PROTEUS_PASSWORD")
    WORKER_PASSWORD = os.getenv("WORKER_PASSWORD", "password-not-configured")
    PASSWORD = PROTEUS_PASSWORD or WORKER_PASSWORD

    REALM = os.getenv("REALM", "origen")
    CLIENT_ID = os.getenv("CLIENT_ID", "proteus-front")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET", None)

    RETRY_INTERVAL = 25  # Seconds
    REFRESH_GAP = 10  # Seconds
    S3_REGION = "eu-west-3"
    WORKERS_COUNT = 5
    AZURE_STORAGE_CONNECTION_STRING = os.getenv(
        "AZURE_STORAGE_CONNECTION_STRING"
    )

    STRESS_ITERATIONS = 10


class ProductionConfig(Config):
    pass


class StagingConfig(Config):
    pass


class DevelopmentConfig(Config):
    pass


configs = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "staging": StagingConfig,
    "default": ProductionConfig,
}

config_name = os.getenv("ENVIRONMENT") or "default"

config = configs[config_name]
