import os
import logging
import logging.config
import logging.handlers
from proteus.config import config


def _setup_logging():
    os.makedirs(config.LOG_LOC, exist_ok=True)
    loggin_path = os.path.abspath(os.path.join(os.path.abspath(os.curdir), "logging.ini"))
    if os.path.exists(loggin_path):
        logging.config.fileConfig(loggin_path, disable_existing_loggers=False)
    else:
        loggin_path = os.path.abspath("logging.ini")
        logging.config.fileConfig(loggin_path, disable_existing_loggers=False)

    azure_logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
    azure_logger.setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger(__name__)
