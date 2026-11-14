"""Offline regression tests for web profile updates."""

import unittest
from unittest.mock import Mock, patch

from src.models import EventRecord, StudentProfile
from web_app import app


class TestWebProfileUpdates(unittest.TestCase):
    def setUp(self):
        self.storage = Mock()
        self.db = Mock()
        backend_patch = patch("web_app.get_backend")
        backend = backend_patch.start()
        self.addCleanup(backend_patch.stop)
        backend.return_value = (
            self.storage, self.db, Mock(), Mock(), StudentProfile, EventRecord
        )
        self.client = app.test_client()
        self.update = {
            "field_of_study": " Computing ",
            "interests": [" Python ", "", "Testing"],
        }

    def assert_update_preserves_postal(self, stored, expected_postal):
        self.db.load_profile.return_value = stored
        response = self.client.post("/api/profile", json=self.update)
        expected = {
            "field_of_study": "Computing",
            "interests": ["Python", "Testing"],
            "home_postal_code": expected_postal,
        }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["profile"], expected)
        self.db.save_profile.assert_called_once_with(expected)
        self.storage.close.assert_called_once_with()

    def test_update_preserves_saved_postal_and_leading_zero(self):
        stored = StudentProfile("Engineering", ["Robotics"], "012345").to_dict()
        original = dict(stored)
        self.assert_update_preserves_postal(stored, "012345")
        self.assertEqual(stored, original)

    def test_update_preserves_empty_postal(self):
        stored = StudentProfile("Engineering", ["Robotics"]).to_dict()
        self.assert_update_preserves_postal(stored, "")

    def test_update_accepts_legacy_profile_without_postal(self):
        stored = {"field_of_study": "Engineering", "interests": ["Robotics"]}
        self.assert_update_preserves_postal(stored, "")

    def test_update_creates_profile_when_none_is_saved(self):
        self.assert_update_preserves_postal(None, "")

    def test_update_accepts_stored_profile_object(self):
        stored = StudentProfile("Engineering", ["Robotics"], "012345")
        self.assert_update_preserves_postal(stored, "012345")
        self.assertEqual(stored.field_of_study, "Engineering")
        self.assertEqual(stored.interests, ["Robotics"])

    def test_invalid_update_does_not_save(self):
        response = self.client.post("/api/profile", json={
            "field_of_study": "Computing", "interests": "Python"
        })
        self.assertEqual(response.status_code, 400)
        self.db.save_profile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
