import os
import logging


def setup_logger():
    logger = logging.getLogger("CloudHime")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')

        log_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "CloudHime")
        log_path = os.path.join(log_dir, "cloudhime.log")
        try:
            from logging.handlers import RotatingFileHandler
            os.makedirs(log_dir, exist_ok=True)
            file_handler = RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception:
            pass

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(file_formatter)
        logger.addHandler(console_handler)

    return logger


# Global logger instance
logger = setup_logger()


def log_ai_debug(message):
    try:
        logger.debug(f"[AI-DEBUG] {message}")
    except Exception:
        pass


def log_translation_debug(message):
    try:
        log_ai_debug(f"[TRANSLATION] {message}")
    except Exception:
        pass
