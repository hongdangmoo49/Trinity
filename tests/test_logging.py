"""Tests for trinity.logging — logging setup."""

import logging
import pytest
from pathlib import Path

from trinity.logging import get_logger, setup_logging


@pytest.fixture
def log_file(tmp_path):
    return tmp_path / "logs" / "test.log"


class TestSetupLogging:
    def test_returns_logger(self):
        logger = setup_logging(level="WARNING", console_output=False)
        assert isinstance(logger, logging.Logger)
        assert logger.name == "trinity"

    def test_sets_log_level(self):
        logger = setup_logging(level="DEBUG", console_output=False)
        assert logger.level == logging.DEBUG

    def test_creates_file_handler(self, log_file):
        logger = setup_logging(log_file=log_file, console_output=False)
        logger.info("test message")

        # Flush handlers
        for handler in logger.handlers:
            handler.flush()

        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "test message" in content

    def test_file_handler_format(self, log_file):
        logger = setup_logging(log_file=log_file, console_output=False)
        logger.info("format check")

        for handler in logger.handlers:
            handler.flush()

        content = log_file.read_text(encoding="utf-8")
        # Should have timestamp | level | name | message format
        assert "|" in content
        assert "INFO" in content
        assert "trinity" in content

    def test_creates_log_directory(self, tmp_path):
        log_path = tmp_path / "deep" / "nested" / "test.log"
        logger = setup_logging(log_file=log_path, console_output=False)
        logger.info("dir creation test")

        for handler in logger.handlers:
            handler.flush()

        assert log_path.exists()

    def test_no_file_handler_when_none(self):
        logger = setup_logging(log_file=None, console_output=False)
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 0

    def test_console_handler_with_rich(self):
        logger = setup_logging(console_output=True, log_file=None)
        # RichHandler should be added
        assert len(logger.handlers) > 0

    def test_clears_existing_handlers(self):
        logger1 = setup_logging(console_output=False, log_file=None)
        count1 = len(logger1.handlers)
        logger2 = setup_logging(console_output=False, log_file=None)
        # Handlers should be replaced, not accumulated
        assert len(logger2.handlers) == count1


class TestGetLogger:
    def test_returns_child_logger(self):
        logger = get_logger("test_module")
        assert logger.name == "trinity.test_module"

    def test_inherits_level(self):
        setup_logging(level="ERROR", console_output=False)
        logger = get_logger("child")
        # Child logger effective level should be ERROR (inherited)
        assert logger.getEffectiveLevel() == logging.ERROR
