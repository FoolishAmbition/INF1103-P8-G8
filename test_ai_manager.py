"""Offline coverage for safe diagnostics of malformed AI responses."""

import json
import unittest
from unittest.mock import Mock

from src.ai_manager import AIManager
from src.exceptions import ResponseValidationError


class TestAIResponseDiagnostics(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.is_available.return_value = True
        self.manager = AIManager(client=self.client)
        self.valid = {
            "event_category": "Workshop",
            "career_relevance": 5,
            "learning_value": 4,
            "networking_value": 3,
            "ai_reasoning": "Relevant workshop.",
        }

    def capture_invalid(self, raw):
        with self.assertLogs("src.ai_manager", level="WARNING") as logs:
            with self.assertRaises(ResponseValidationError):
                self.manager.parse_response(raw)
        self.assertEqual(len(logs.records), 1)
        self.assertIsNone(logs.records[0].exc_info)
        return logs.output[0]

    def test_empty_responses_record_shape_and_parse_position(self):
        for raw in ("", "   ", "\n\t"):
            with self.subTest(raw=raw):
                diagnostic = self.capture_invalid(raw)
                self.assertIn("response_type=str", diagnostic)
                self.assertIn(f"length={len(raw)}", diagnostic)
                self.assertIn("empty=True fenced=False", diagnostic)
                self.assertIn(f"position={len(raw)}", diagnostic)

    def test_fenced_json_is_identified_without_logging_content(self):
        raw = " \n```json\n" + json.dumps(self.valid) + "\n```"
        diagnostic = self.capture_invalid(raw)
        self.assertIn("empty=False fenced=True", diagnostic)
        self.assertIn("line=2 column=1 position=2", diagnostic)
        self.assertNotIn("Relevant workshop", diagnostic)
        self.assertNotIn("career_relevance", diagnostic)

    def test_prose_records_only_shape_without_response_text(self):
        diagnostic = self.capture_invalid("Private response text before JSON")
        self.assertIn("empty=False fenced=False", diagnostic)
        self.assertIn("line=1 column=1 position=0", diagnostic)
        self.assertNotIn("Private response text", diagnostic)

    def test_nontext_responses_fail_safely_without_logging_values(self):
        for raw in (None, 123, {"private": "hidden-value"}, ["hidden-value"]):
            with self.subTest(response_type=type(raw).__name__):
                diagnostic = self.capture_invalid(raw)
                self.assertIn(f"response_type={type(raw).__name__}", diagnostic)
                self.assertIn("length=None empty=None fenced=None", diagnostic)
                self.assertIn("line=None column=None position=None", diagnostic)
                self.assertNotIn("hidden-value", diagnostic)

    def test_invalid_bytes_do_not_leak_decoder_details(self):
        diagnostic = self.capture_invalid(b"\xffprivate-response")
        self.assertIn("response_type=bytes length=17", diagnostic)
        self.assertNotIn("private-response", diagnostic)

    def test_valid_json_keeps_existing_schema_and_bytes_support(self):
        text = json.dumps(self.valid)
        for raw in (text, text.encode("utf-8")):
            with self.subTest(response_type=type(raw).__name__), self.assertNoLogs("src.ai_manager"):
                self.assertEqual(self.manager.parse_response(raw), self.valid)
        with self.assertNoLogs("src.ai_manager"), self.assertRaises(ResponseValidationError):
            self.manager.parse_response('{"event_category": "Workshop"}')

    def test_failure_keeps_existing_attempt_count_and_diagnostics_private(self):
        self.client.call.side_effect = ["PRIVATE_RESPONSE_SENTINEL", json.dumps(self.valid)]
        with self.assertLogs("src.ai_manager", level="WARNING") as logs:
            result, error = self.manager.analyze_event(
                {"field_of_study": "PRIVATE_PROFILE_SENTINEL", "interests": []},
                "PRIVATE_EVENT_SENTINEL", "PRIVATE_DESCRIPTION_SENTINEL",
            )
        self.assertIsNone(result)
        self.assertTrue(error.startswith("Non-JSON response:"))
        self.assertEqual(self.client.call.call_count, 1)
        for sentinel in ("PRIVATE_RESPONSE", "PRIVATE_PROFILE", "PRIVATE_EVENT", "PRIVATE_DESCRIPTION"):
            self.assertNotIn(sentinel, " ".join(logs.output))
            self.assertNotIn(sentinel, error)
        result, error = self.manager.analyze_event({}, "Workshop", "Description")
        self.assertEqual(result, self.valid)
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
