import os
import time
import logging

def setup_logger():
    logger = logging.getLogger("CloudHime")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # File handler
        log_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "CloudHime")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "cloudhime.log")
        
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
        file_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(file_formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger

# Global logger instance
logger = setup_logger()

def log_ai_debug(message):
    try:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] {message}\n\n"
        log_paths = [
            os.path.join(os.path.dirname(__file__), "cloudhime_ai_debug.log"),
            os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "CloudHime", "cloudhime_ai_debug.log"),
        ]
        for log_path in log_paths:
            try:
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as fp:
                    fp.write(log_line)
            except Exception:
                pass
        logger.debug(f"[AI-DEBUG] {message}")
    except Exception:
        pass

def log_translation_debug(message):
    try:
        log_ai_debug(f"[TRANSLATION] {message}")
    except Exception:
        pass
