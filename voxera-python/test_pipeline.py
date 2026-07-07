import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import requests

# Add parent directory to path so imports work
sys.path.append(str(Path(__file__).resolve().parent))

import config
import storage
import formatter
import retell
import telegram
import main

# Check if timezone is available on this system
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    ZoneInfo("Asia/Kolkata")
    HAS_TZ = True
    EXPECTED_TIME_STR = "4:43 PM IST"
    # 22 May 2026 16:43:00 IST (UTC+5:30)
    dt1 = datetime(2026, 5, 22, 16, 43, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    dt2 = datetime(2026, 5, 22, 16, 44, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
except Exception:
    HAS_TZ = False
    EXPECTED_TIME_STR = "11:13 AM UTC"
    # Fallback to UTC equivalent: 22 May 2026 11:13:00 UTC
    dt1 = datetime(2026, 5, 22, 11, 13, 0, tzinfo=ZoneInfo("UTC"))
    dt2 = datetime(2026, 5, 22, 11, 14, 0, tzinfo=ZoneInfo("UTC"))

MOCK_START_TIMESTAMP_1 = int(dt1.timestamp() * 1000)
MOCK_START_TIMESTAMP_2 = int(dt2.timestamp() * 1000)

# Mock call data representing Retell API responses
MOCK_CALL_1 = {
    "call_id": "call_12345_inbound",
    "call_status": "ended",
    "direction": "inbound",
    "from_number": "+919876543210",
    "to_number": "+1234567890",
    "duration_ms": 25000,
    "start_timestamp": MOCK_START_TIMESTAMP_1,
    "disconnection_reason": "user_hangup",
    "call_analysis": {
        "call_successful": True,
        "user_sentiment": "Neutral",
        "call_summary": "The customer called to inquire about the service activation status. Agent explained it takes 24 hours. The customer was satisfied and hung up."
    }
}

MOCK_CALL_2 = {
    "call_id": "call_67890_outbound",
    "call_status": "ended",
    "direction": "outbound",
    "from_number": "+1234567890",
    "to_number": "+918888888888",
    "duration_ms": 125000,
    "start_timestamp": MOCK_START_TIMESTAMP_2,
    "disconnection_reason": "agent_hangup",
    "call_analysis": {
        "call_successful": True,
        "user_sentiment": "Positive",
        "call_summary": "Follow up call regarding feedback. User expressed great satisfaction and thanked the agent."
    }
}

MOCK_CALL_CORRUPT_OR_MISSING = {
    "call_id": "call_error_missing_fields",
    "call_status": "error",
    "direction": "inbound",
    "from_number": None,
    "to_number": None,
    "duration_ms": None,
    "start_timestamp": None,
    "disconnection_reason": None,
    "call_analysis": None
}

class TestVoxeraPipeline(unittest.TestCase):
    
    def setUp(self):
        # Override config storage path for testing to avoid overwriting production data
        self.test_storage_file = Path(__file__).resolve().parent / "test_processed_calls.json"
        
        # Explicitly patch all references to the storage path
        config.PROCESSED_CALLS_FILE = self.test_storage_file
        storage.config.PROCESSED_CALLS_FILE = self.test_storage_file
        main.config.PROCESSED_CALLS_FILE = self.test_storage_file

        # Reset config properties to ensure test isolation
        config.START_FETCH_DATE = None
        main.config.START_FETCH_DATE = None
        config.TARGET_AGENT_ID = ""
        main.config.TARGET_AGENT_ID = ""

        # Reset storage files
        for suffix in ["", ".corrupted"]:
            path = self.test_storage_file.with_name(self.test_storage_file.name + suffix)
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass

    def tearDown(self):
        # Clean up test file and backup corrupted file
        for suffix in ["", ".corrupted"]:
            path = self.test_storage_file.with_name(self.test_storage_file.name + suffix)
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass

    def test_storage_operations(self):
        """
        Tests loading, saving, and duplicate prevention in storage.py.
        """
        # Ensure file auto-creation and empty load works
        calls = storage.load_processed_calls()
        self.assertEqual(len(calls), 0)
        self.assertTrue(self.test_storage_file.exists())
        
        # Test is_processed
        self.assertFalse(storage.is_processed("call_1"))
        
        # Save a call and check
        storage.save_processed_call("call_1")
        self.assertTrue(storage.is_processed("call_1"))
        self.assertEqual(storage.load_processed_calls(), {"call_1"})
        
        # Test corruption recovery
        with open(self.test_storage_file, "w") as f:
            f.write("{invalid_json: true}")
            
        # Should recover and return empty set rather than raising error
        calls_after_corruption = storage.load_processed_calls()
        self.assertEqual(len(calls_after_corruption), 0)

    def test_message_formatting(self):
        """
        Tests message formatting matches requirements exactly.
        """
        # If timezone isn't available, we configure formatter to use UTC to match test expectations
        if not HAS_TZ:
            formatter.TIMEZONE = "UTC"

        formatted = formatter.format_call_message(MOCK_CALL_1)
        
        # Check specific expected lines
        self.assertIn("📞 New Call Summary", formatted)
        self.assertIn("👤 Caller: +919876543210", formatted)
        self.assertIn("⏱ Duration: 25s", formatted)
        self.assertIn(f"📅 22 May 2026 • {EXPECTED_TIME_STR}", formatted)
        self.assertIn("• Call Status: Successful", formatted)
        self.assertIn("• User Sentiment: Neutral", formatted)
        self.assertIn("• Disconnection: User Hangup", formatted)
        self.assertIn("The customer called to inquire", formatted)

        # Test with missing/corrupted fields
        formatted_corrupt = formatter.format_call_message(MOCK_CALL_CORRUPT_OR_MISSING)
        self.assertIn("👤 Caller: Web Call / Call", formatted_corrupt)
        self.assertIn("⏱ Duration: 0s", formatted_corrupt)
        self.assertIn("• Call Status: Failed", formatted_corrupt)
        self.assertIn("• User Sentiment: Neutral", formatted_corrupt)
        self.assertIn("• Disconnection: Unknown", formatted_corrupt)
        self.assertIn("No summary available.", formatted_corrupt)

    def test_telegram_chunking(self):
        """
        Tests that Telegram integration correctly chunks long messages.
        """
        short_msg = "Hello World"
        chunks = telegram.chunk_message(short_msg, limit=20)
        self.assertEqual(chunks, ["Hello World"])
        
        # Test long message chunking at space or newline
        long_msg = "Line 1\nLine 2\nLine 3\nLine 4"
        chunks = telegram.chunk_message(long_msg, limit=15)
        # Should split by newlines where possible
        self.assertEqual(chunks, ["Line 1\nLine 2", "Line 3\nLine 4"])

    @patch("requests.post")
    def test_retell_fetching_and_retry(self, mock_post):
        """
        Tests Retell fetching calls and retrying on failure.
        """
        # Mock success response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [MOCK_CALL_1, MOCK_CALL_2]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Set API key directly on retell.config
        retell.config.RETELL_API_KEY = "test_key"
        
        calls = retell.fetch_latest_calls()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["call_id"], "call_12345_inbound")
            
        # Test retry logic on exception
        mock_post.reset_mock()
        mock_post.side_effect = [requests.exceptions.ConnectionError("Connection timeout"), mock_response]
        
        with patch("time.sleep", return_value=None):
            calls = retell.fetch_latest_calls()
            self.assertEqual(len(calls), 2)
            # Ensure post was called twice due to retry
            self.assertEqual(mock_post.call_count, 2)

    @patch("requests.post")
    def test_telegram_sending_and_retry(self, mock_post):
        """
        Tests Telegram sending and retrying on failure.
        """
        # Mock success response
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Set config directly on telegram.config
        telegram.config.TELEGRAM_BOT_TOKEN = "test_bot"
        telegram.config.TELEGRAM_CHAT_ID = "test_chat"

        success = telegram.send_telegram_message("Test message")
        self.assertTrue(success)
                
        # Test retry logic on exception
        mock_post.reset_mock()
        mock_post.side_effect = [requests.exceptions.ConnectionError("Timeout"), mock_response]
        
        with patch("time.sleep", return_value=None):
            success = telegram.send_telegram_message("Test message")
            self.assertTrue(success)
            self.assertEqual(mock_post.call_count, 2)

    @patch("retell.fetch_latest_calls")
    @patch("telegram.send_telegram_message")
    def test_main_polling_loop_integration(self, mock_send_telegram, mock_fetch_calls):
        """
        Tests the integration of main.py polling job, including duplicate prevention.
        """
        # Setup mocks
        mock_fetch_calls.return_value = [MOCK_CALL_2, MOCK_CALL_1]  # Mock API returns these 2 calls
        mock_send_telegram.return_value = True

        # Ensure correct key setup
        main.config.RETELL_API_KEY = "test_key"
        main.config.TELEGRAM_BOT_TOKEN = "test_bot"
        main.config.TELEGRAM_CHAT_ID = "test_chat"

        # Run poll job (first run) - should detect 2 calls, format and send them
        main.poll_job()
        
        # Ensure telegram send was called twice (for call_1 and call_2)
        self.assertEqual(mock_send_telegram.call_count, 2)
        
        # Check that both calls are now processed
        self.assertTrue(storage.is_processed("call_12345_inbound"))
        self.assertTrue(storage.is_processed("call_67890_outbound"))
        
        # Run poll job again (second run) - should process nothing because of duplicate prevention
        mock_send_telegram.reset_mock()
        main.poll_job()
        self.assertEqual(mock_send_telegram.call_count, 0)

    @patch("retell.fetch_latest_calls")
    @patch("telegram.send_telegram_message")
    def test_date_filtering(self, mock_send_telegram, mock_fetch_calls):
        """
        Verify the implementation with:
        - one old mock call
        - one new mock call
        - confirm only new call gets sent to Telegram
        We test both created_at (as ISO string and ms timestamp) and start_timestamp fallback.
        """
        from datetime import datetime
        
        # 1. Define the threshold date: 23 May 2026, 8:00 AM IST
        threshold_str = "2026-05-23T08:00:00+05:30"
        threshold_dt = datetime.fromisoformat(threshold_str)
        
        # Configure config properties
        config.START_FETCH_DATE = threshold_dt
        main.config.START_FETCH_DATE = threshold_dt
        
        # 2. Create one old mock call with created_at as ISO string (e.g. 23 May 2026, 7:59 AM IST)
        old_call = {
            "call_id": "call_old_ignored_iso",
            "call_status": "ended",
            "direction": "inbound",
            "from_number": "+911111111111",
            "duration_ms": 10000,
            "created_at": "2026-05-23T07:59:00+05:30",
            "disconnection_reason": "user_hangup",
            "call_analysis": {
                "call_successful": True,
                "user_sentiment": "Neutral",
                "call_summary": "Old call that should be ignored."
            }
        }
        
        # 3. Create one new mock call with created_at as ISO string (e.g. 23 May 2026, 8:01 AM IST)
        new_call = {
            "call_id": "call_new_processed_iso",
            "call_status": "ended",
            "direction": "inbound",
            "from_number": "+912222222222",
            "duration_ms": 20000,
            "created_at": "2026-05-23T08:01:00+05:30",
            "disconnection_reason": "user_hangup",
            "call_analysis": {
                "call_successful": True,
                "user_sentiment": "Positive",
                "call_summary": "New call that should be processed."
            }
        }
        
        # Setup mock returns
        mock_fetch_calls.return_value = [new_call, old_call]
        mock_send_telegram.return_value = True
        
        # Run main polling job
        main.config.RETELL_API_KEY = "test_key"
        main.config.TELEGRAM_BOT_TOKEN = "test_bot"
        main.config.TELEGRAM_CHAT_ID = "test_chat"
        
        main.poll_job()
        
        # Verify that send_telegram_message was only called ONCE
        self.assertEqual(mock_send_telegram.call_count, 1)
        
        # Verify only the new call ID is processed and stored in storage
        self.assertTrue(storage.is_processed("call_new_processed_iso"))
        self.assertFalse(storage.is_processed("call_old_ignored_iso"))
        
        # Reset storage and mocks for second check: using millisecond timestamps in created_at
        mock_send_telegram.reset_mock()
        if self.test_storage_file.exists():
            self.test_storage_file.unlink()
        storage.load_processed_calls()
        
        old_call_ms_dt = datetime.fromisoformat("2026-05-23T07:59:00+05:30")
        new_call_ms_dt = datetime.fromisoformat("2026-05-23T08:01:00+05:30")
        
        old_call_ms = {
            "call_id": "call_old_ignored_ms",
            "call_status": "ended",
            "direction": "inbound",
            "from_number": "+911111111111",
            "duration_ms": 10000,
            "created_at": int(old_call_ms_dt.timestamp() * 1000),
            "disconnection_reason": "user_hangup",
            "call_analysis": {
                "call_successful": True,
                "user_sentiment": "Neutral",
                "call_summary": "Old call that should be ignored."
            }
        }
        
        new_call_ms = {
            "call_id": "call_new_processed_ms",
            "call_status": "ended",
            "direction": "inbound",
            "from_number": "+912222222222",
            "duration_ms": 20000,
            "created_at": int(new_call_ms_dt.timestamp() * 1000),
            "disconnection_reason": "user_hangup",
            "call_analysis": {
                "call_successful": True,
                "user_sentiment": "Positive",
                "call_summary": "New call that should be processed."
            }
        }
        
        mock_fetch_calls.return_value = [new_call_ms, old_call_ms]
        main.poll_job()
        
        self.assertEqual(mock_send_telegram.call_count, 1)
        self.assertTrue(storage.is_processed("call_new_processed_ms"))
        self.assertFalse(storage.is_processed("call_old_ignored_ms"))
        
        # Clean up
        config.START_FETCH_DATE = None
        main.config.START_FETCH_DATE = None

    @patch("retell.fetch_latest_calls")
    @patch("telegram.send_telegram_message")
    def test_agent_filtering(self, mock_send_telegram, mock_fetch_calls):
        """
        Verify the implementation of agent-level filtering:
        - only calls from TARGET_AGENT_ID are processed
        - exact matching works for agent IDs
        - calls from other agents or missing agent_id are ignored
        """
        # Set target agent ID
        config.TARGET_AGENT_ID = "agent_123"
        main.config.TARGET_AGENT_ID = "agent_123"

        # Mock calls
        call_target_match = {
            "call_id": "call_agent_match",
            "call_status": "ended",
            "direction": "inbound",
            "agent_id": "agent_123",
            "from_number": "+912222222222",
            "duration_ms": 20000,
            "call_analysis": {"call_successful": True, "call_summary": "Match"}
        }

        call_different_agent = {
            "call_id": "call_different_agent",
            "call_status": "ended",
            "direction": "inbound",
            "agent_id": "agent_999",
            "from_number": "+911111111111",
            "duration_ms": 15000,
            "call_analysis": {"call_successful": True, "call_summary": "No match"}
        }

        call_missing_agent = {
            "call_id": "call_missing_agent",
            "call_status": "ended",
            "direction": "inbound",
            "agent_id": None,
            "from_number": "+913333333333",
            "duration_ms": 10000,
            "call_analysis": {"call_successful": True, "call_summary": "Missing"}
        }

        # Setup mocks
        mock_fetch_calls.return_value = [call_target_match, call_different_agent, call_missing_agent]
        mock_send_telegram.return_value = True

        main.config.RETELL_API_KEY = "test_key"
        main.config.TELEGRAM_BOT_TOKEN = "test_bot"
        main.config.TELEGRAM_CHAT_ID = "test_chat"

        # Run poll job
        main.poll_job()

        # Only one telegram message (the matching one) should be sent
        self.assertEqual(mock_send_telegram.call_count, 1)
        self.assertTrue(storage.is_processed("call_agent_match"))
        self.assertFalse(storage.is_processed("call_different_agent"))
        self.assertFalse(storage.is_processed("call_missing_agent"))

        # Reset storage and mocks for checking when target agent name is NOT set
        mock_send_telegram.reset_mock()
        if self.test_storage_file.exists():
            self.test_storage_file.unlink()
        storage.load_processed_calls()

        config.TARGET_AGENT_ID = ""
        main.config.TARGET_AGENT_ID = ""

        # Should process all calls now (as it defaults to processing all calls)
        mock_fetch_calls.return_value = [call_target_match, call_different_agent, call_missing_agent]
        main.poll_job()
        self.assertEqual(mock_send_telegram.call_count, 3)
        self.assertTrue(storage.is_processed("call_agent_match"))
        self.assertTrue(storage.is_processed("call_different_agent"))
        self.assertTrue(storage.is_processed("call_missing_agent"))

        # Clean up
        config.TARGET_AGENT_ID = ""
        main.config.TARGET_AGENT_ID = ""


if __name__ == "__main__":
    unittest.main()
