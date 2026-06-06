import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import logging_config


class LoggingConfigTest(unittest.TestCase):
    def test_configures_timed_rotating_file_handler(self):
        old_handlers = logging.getLogger().handlers[:]
        old_level = logging.getLogger().level
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                log_file = Path(temp_dir) / "faceapp.log"
                with (
                    patch.object(logging_config, "LOG_FILE", log_file),
                    patch.object(logging_config, "log_level", return_value="DEBUG"),
                    patch.object(logging_config, "log_retention_days", return_value=3),
                ):
                    logging_config.configure_logging()

                handlers = logging.getLogger().handlers
                file_handlers = [handler for handler in handlers if handler.__class__.__name__ == "TimedRotatingFileHandler"]

                self.assertEqual(logging.getLogger().level, logging.DEBUG)
                self.assertEqual(len(file_handlers), 1)
                self.assertEqual(file_handlers[0].backupCount, 3)
                self.assertTrue(log_file.parent.exists())
            finally:
                for handler in logging.getLogger().handlers:
                    handler.close()
                logging.getLogger().handlers = old_handlers
                logging.getLogger().setLevel(old_level)


if __name__ == "__main__":
    unittest.main()
