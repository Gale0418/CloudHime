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


def test_log_ai_debug_writes_to_script_and_appdata_logs(monkeypatch):
    monkeypatch.setattr(logging, "FileHandler", DummyFileHandler)
    module = import_cloudhime_logging()

    with patch.object(module.os, "makedirs") as mock_makedirs, patch("builtins.open", new_callable=mock_open) as mock_file:
        test_msg = "test_ai_debug_msg_123"
        module.log_ai_debug(test_msg)

    assert mock_file.call_count == 2

    calls = mock_file.call_args_list
    path1 = calls[0][0][0]
    path2 = calls[1][0][0]

    assert "cloudhime_ai_debug.log" in path1
    assert "cloudhime_ai_debug.log" in path2

    script_dir = os.path.dirname(module.__file__)
    paths = [path1, path2]
    assert any(script_dir in path for path in paths)
    assert any("CloudHime" in path for path in paths)

    write_calls = mock_file().write.call_args_list
    assert any(test_msg in call[0][0] for call in write_calls)
    assert mock_makedirs.call_count == 2


def test_log_translation_debug_delegates_to_ai_debug(monkeypatch):
    monkeypatch.setattr(logging, "FileHandler", DummyFileHandler)
    module = import_cloudhime_logging()

    with patch.object(module, "log_ai_debug") as mock_log_ai_debug:
        test_msg = "test_trans_msg"
        module.log_translation_debug(test_msg)

    mock_log_ai_debug.assert_called_with(f"[TRANSLATION] {test_msg}")
