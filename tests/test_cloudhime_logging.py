import os
import unittest
from unittest.mock import patch, mock_open
import cloudhime_logging

class TestCloudhimeLogging(unittest.TestCase):
    @patch("cloudhime_logging.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    @patch("builtins.print")
    def test_log_ai_debug(self, mock_print, mock_file, mock_makedirs):
        test_msg = "test_ai_debug_msg_123"
        cloudhime_logging.log_ai_debug(test_msg)
        
        self.assertEqual(mock_file.call_count, 2)
        
        calls = mock_file.call_args_list
        path1 = calls[0][0][0]
        path2 = calls[1][0][0]
        
        self.assertIn("cloudhime_ai_debug.log", path1)
        self.assertIn("cloudhime_ai_debug.log", path2)
        
        # Check that script dir and appdata dir are in the paths
        script_dir = os.path.dirname(cloudhime_logging.__file__)
        appdata_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "CloudHime")
        
        paths = [path1, path2]
        self.assertTrue(any(script_dir in p for p in paths))
        self.assertTrue(any("CloudHime" in p for p in paths))
        
        write_calls = mock_file().write.call_args_list
        self.assertTrue(any(test_msg in call[0][0] for call in write_calls))

    @patch("cloudhime_logging.log_ai_debug")
    def test_log_translation_debug(self, mock_log_ai_debug):
        test_msg = "test_trans_msg"
        cloudhime_logging.log_translation_debug(test_msg)
        mock_log_ai_debug.assert_called_with(f"[TRANSLATION] {test_msg}")

if __name__ == "__main__":
    unittest.main()
