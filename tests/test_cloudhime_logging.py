import importlib
import logging
import os
import sys
from unittest.mock import mock_open, patch

import pytest

MODULE_NAME = "cloudhime_logging"
LOGGER_NAME = "CloudHime"


class DummyFileHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        super().__init__()

    def emit(self, record):
        pass


def reset_logging_module_state():
    sys.modules.pop(MODULE_NAME, None)
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    logger.setLevel(logging.NOTSET)


@pytest.fixture(autouse=True)
def clean_logging_module_state():
    reset_logging_module_state()
    yield
    reset_logging_module_state()


def import_cloudhime_logging():
    return importlib.import_module(MODULE_NAME)


def test_import_succeeds_when_file_handler_is_unavailable(monkeypatch):
    def raising_file_handler(*args, **kwargs):
        raise PermissionError("log path is not writable")

    monkeypatch.setattr(logging, "FileHandler", raising_file_handler)

    module = import_cloudhime_logging()

    assert module.logger is logging.getLogger(LOGGER_NAME)
    assert any(isinstance(handler, logging.StreamHandler) for handler in module.logger.handlers)


def test_log_ai_debug_writes_only_to_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(logging, "FileHandler", DummyFileHandler)
    module = import_cloudhime_logging()

    with patch.object(module.os, "makedirs") as mock_makedirs, patch("builtins.open", new_callable=mock_open) as mock_file:
        test_msg = "test_ai_debug_msg_123"
        module.log_ai_debug(test_msg)

    mock_file.assert_called_once()
    log_path = mock_file.call_args.args[0]
    assert log_path == os.path.join(str(tmp_path), "CloudHime", "cloudhime_ai_debug.log")
    assert os.path.dirname(module.__file__) not in log_path
    assert test_msg in mock_file().write.call_args.args[0]
    mock_makedirs.assert_called_once_with(os.path.dirname(log_path), exist_ok=True)

def test_log_translation_debug_delegates_to_ai_debug(monkeypatch):
    monkeypatch.setattr(logging, "FileHandler", DummyFileHandler)
    module = import_cloudhime_logging()

    with patch.object(module, "log_ai_debug") as mock_log_ai_debug:
        test_msg = "test_trans_msg"
        module.log_translation_debug(test_msg)

    mock_log_ai_debug.assert_called_with(f"[TRANSLATION] {test_msg}")
