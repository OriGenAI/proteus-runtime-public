import logging
import logging.config
import logging.handlers
import os
import shutil

from pathlib import Path

FALLBACK_LOGGING_PATH = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "logging.ini")


def initialize_logger(log_loc=None):
    # Discover logging.ini path
    if log_loc:
        logging_path = log_loc if os.path.isabs(log_loc) else os.path.abspath(os.path.join(os.curdir, log_loc))

        if not logging_path.endswith("logging.ini"):
            logging_path = os.path.join(logging_path, "logging.ini")
            if not os.path.exists(logging_path):
                shutil.copy(FALLBACK_LOGGING_PATH, logging_path)
        elif not os.path.exists(logging_path):
            raise FileNotFoundError(f"Proteus runtime - log_log path not found: {logging_path}")
    else:
        # Fallback to runtime logger
        logging_path = FALLBACK_LOGGING_PATH

    # Create logs folder. See logging.ini
    Path(os.path.join(os.path.dirname(logging_path), "logs")).mkdir(parents=True, exist_ok=True)

    # Init logger
    logging.config.fileConfig(logging_path, disable_existing_loggers=False)

    # Disable known noisy loggers
    azure_logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
    azure_logger.setLevel(logging.WARNING)

    return logging.getLogger(__name__)
