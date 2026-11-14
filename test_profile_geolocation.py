"""Offline tests for home postal codes in profiles, editing and JSON storage."""

import io
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from rich.console import Console

from main import EventWiseApp, main
from src.ai_client import GeminiClient
from src.exceptions import ValidationError
from src.io_manager import IOManager
from src.models import StudentProfile
from src.storage import JsonStorage


class TestProfilePostalCode(unittest.TestCase):
    def test_old_constructor_remains_supported(self):
        profile = StudentProfile("Software Engineering", ["Python"])
        self.assertEqual(profile.home_postal_code, "")
        self.assertEqual(profile.field_of_study, "Software Engineering")
        self.assertEqual(profile.interests, ["Python"])

    def test_older_saved_profile_loads_without_postal(self):
        profile = StudentProfile.from_dict({
            "field_of_study": "Software Engineering",
            "interests": ["Python"],
        })
        self.assertEqual(profile.home_postal_code, "")
        self.assertFalse(profile.is_empty())

    def test_missing_profile_loads_empty(self):
        for data in (None, {}):
            with self.subTest(data=data):
                profile = StudentProfile.from_dict(data)
                self.assertEqual(profile.home_postal_code, "")
                self.assertTrue(profile.is_empty())

    def test_postal_string_preserves_leading_zero(self):
        profile = StudentProfile("Software Engineering", ["Python"], "012345")
        self.assertEqual(profile.home_postal_code, "012345")
        self.assertEqual(profile.to_dict()["home_postal_code"], "012345")

    def test_empty_or_null_postal_is_optional(self):
        for postal_code in ("", None):
            with self.subTest(postal_code=postal_code):
                profile = StudentProfile.from_dict({"home_postal_code": postal_code})
                self.assertEqual(profile.home_postal_code, "")

    def test_invalid_postals_are_rejected_during_construction_and_loading(self):
        invalid_postals = (123456, True, "12345", "1234567", "ABC123", "１２３４５６", " 012345 ")
        for postal_code in invalid_postals:
            with self.subTest(postal_code=postal_code):
                with self.assertRaises(ValidationError):
                    StudentProfile(home_postal_code=postal_code)
                with self.assertRaises(ValidationError):
                    StudentProfile.from_dict({"home_postal_code": postal_code})

    def test_profile_dictionary_round_trip(self):
        original = StudentProfile("Software Engineering", ["Python"], "012345")
        restored = StudentProfile.from_dict(original.to_dict())
        self.assertEqual(restored, original)
        self.assertEqual(restored.home_postal_code, "012345")

    def test_postal_survives_actual_json_save_and_reload(self):
        original = StudentProfile("Software Engineering", ["Python"], "012345")
        with TemporaryDirectory(prefix="eventwise-profile-test-") as directory:
            storage = JsonStorage(directory)
            storage.save("profile", original.to_dict())
            reloaded_storage = JsonStorage(directory)
            restored = StudentProfile.from_dict(reloaded_storage.load("profile"))
        self.assertEqual(restored, original)
        self.assertEqual(restored.home_postal_code, "012345")

    def test_older_json_profile_can_be_loaded_and_saved(self):
        with TemporaryDirectory(prefix="eventwise-profile-test-") as directory:
            storage = JsonStorage(directory)
            storage.save("profile", {"field_of_study": "Software Engineering", "interests": ["Python"]})
            profile = StudentProfile.from_dict(storage.load("profile"))
            storage.save("profile", profile.to_dict())
            restored = StudentProfile.from_dict(storage.load("profile"))
        self.assertEqual(restored.field_of_study, "Software Engineering")
        self.assertEqual(restored.interests, ["Python"])
        self.assertEqual(restored.home_postal_code, "")

    def test_postal_does_not_replace_existing_profile_fields(self):
        profile = StudentProfile(home_postal_code="012345")
        self.assertTrue(profile.is_empty())
        complete_profile = StudentProfile("Software Engineering", ["Python"])
        self.assertFalse(complete_profile.is_empty())

    def test_dictionary_copy_keeps_postal_and_separate_interests(self):
        original = StudentProfile("Software Engineering", ["Python"], "012345").to_dict()
        draft = IOManager._copy_profile(original)
        draft["interests"].append("Testing")
        draft["home_postal_code"] = "654321"
        self.assertEqual(original["interests"], ["Python"])
        self.assertEqual(original["home_postal_code"], "012345")

    def test_entity_copy_keeps_postal_and_separate_interests(self):
        original = StudentProfile("Software Engineering", ["Python"], "012345")
        draft = IOManager._copy_profile(original)
        self.assertEqual(draft["home_postal_code"], "012345")
        draft["interests"].append("Testing")
        self.assertEqual(original.interests, ["Python"])

    def test_empty_and_old_dictionary_copies_have_postal_field(self):
        for profile in (None, {}, {"field_of_study": "Software Engineering", "interests": ["Python"]}):
            with self.subTest(profile=profile):
                self.assertEqual(IOManager._copy_profile(profile)["home_postal_code"], "")


class TestProfilePostalEditor(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.manager = IOManager(console=Console(file=self.output))
        self.manager.refresh_screen = Mock()
        self.profile = StudentProfile("Software Engineering", ["Python"], "012345")

    def test_prompt_validation_accepts_optional_and_valid_postals(self):
        for value in ("", "   ", "012345", " 012345 "):
            with self.subTest(value=value):
                self.assertIs(self.manager._validate_home_postal_code(value), True)
        for value in ("12345", "ABC123", "１２３４５６"):
            with self.subTest(value=value):
                result = self.manager._validate_home_postal_code(value)
                self.assertIsInstance(result, str)
                self.assertNotIn(value, result)

    @patch("src.io_manager.questionary.text")
    def test_postal_prompt_uses_validator_and_preserves_zero(self, text_prompt):
        text_prompt.return_value.ask.return_value = " 012345 "
        self.assertEqual(self.manager._ask_home_postal_code("654321"), "012345")
        arguments = text_prompt.call_args.kwargs
        self.assertEqual(arguments["default"], "654321")
        self.assertEqual(arguments["validate"], self.manager._validate_home_postal_code)

    @patch("src.io_manager.questionary.text")
    def test_cancelled_postal_prompt_returns_none(self, text_prompt):
        text_prompt.return_value.ask.return_value = None
        self.assertIsNone(self.manager._ask_home_postal_code("012345"))

    @patch("src.io_manager.questionary.text")
    @patch("src.io_manager.questionary.select")
    def test_save_changed_postal(self, select_prompt, text_prompt):
        select_prompt.return_value.ask.side_effect = ["Home postal code: 012345", "Save"]
        text_prompt.return_value.ask.return_value = "654321"
        updated = self.manager.collect_profile(self.profile)
        restored = StudentProfile.from_dict(updated)
        self.assertEqual(restored.home_postal_code, "654321")
        self.assertEqual(self.profile.home_postal_code, "012345")
        self.assertEqual(restored.field_of_study, self.profile.field_of_study)
        self.assertEqual(restored.interests, self.profile.interests)

    @patch("src.io_manager.questionary.text")
    @patch("src.io_manager.questionary.select")
    def test_blank_input_clears_postal(self, select_prompt, text_prompt):
        select_prompt.return_value.ask.side_effect = ["Home postal code: 012345", "Save"]
        text_prompt.return_value.ask.return_value = ""
        updated = self.manager.collect_profile(self.profile)
        self.assertEqual(StudentProfile.from_dict(updated).home_postal_code, "")

    @patch("src.io_manager.questionary.text")
    @patch("src.io_manager.questionary.select")
    def test_cancelled_input_keeps_postal(self, select_prompt, text_prompt):
        select_prompt.return_value.ask.side_effect = ["Home postal code: 012345", "Save"]
        text_prompt.return_value.ask.return_value = None
        updated = self.manager.collect_profile(self.profile)
        self.assertEqual(updated["home_postal_code"], "012345")

    @patch("src.io_manager.questionary.text")
    @patch("src.io_manager.questionary.select")
    def test_cancel_edit_discards_draft(self, select_prompt, text_prompt):
        for cancel_choice in ("Cancel", None):
            with self.subTest(cancel_choice=cancel_choice):
                select_prompt.return_value.ask.side_effect = ["Home postal code: 012345", cancel_choice]
                text_prompt.return_value.ask.return_value = "654321"
                result = self.manager.collect_profile(self.profile)
                self.assertIs(result, self.profile)
                self.assertEqual(self.profile.home_postal_code, "012345")

    @patch("src.io_manager.questionary.select")
    def test_old_profile_can_save_without_postal(self, select_prompt):
        select_prompt.return_value.ask.return_value = "Save"
        old_profile = {"field_of_study": "Software Engineering", "interests": ["Python"]}
        updated = self.manager.collect_profile(old_profile)
        self.assertEqual(updated["home_postal_code"], "")

    @patch("src.io_manager.questionary.select")
    def test_existing_save_requirements_are_enforced(self, select_prompt):
        select_prompt.return_value.ask.side_effect = ["Save", "Cancel"]
        empty_profile = StudentProfile(home_postal_code="012345")
        result = self.manager.collect_profile(empty_profile)
        self.assertIs(result, empty_profile)
        self.manager.refresh_screen.assert_called_with(
            "Field of study and at least one interest are required.", True
        )


class TestProfilePostalAppFlow(unittest.TestCase):
    @patch("main.DataManager")
    def test_invalid_saved_postal_recovers_study_and_interests_and_saves(self, data_manager):
        invalid_postals = ("12345", "ABC123", 123456, True, [], {})
        for postal_code in invalid_postals:
            with self.subTest(postal_code=postal_code):
                saved = {
                    "field_of_study": "Software Engineering",
                    "interests": ["Python"],
                    "home_postal_code": postal_code,
                }
                data_manager.return_value.reset_mock()
                data_manager.return_value.load_profile.return_value = saved
                data_manager.return_value.load_events.return_value = []
                app = EventWiseApp()
                app._io_manager = Mock()

                self.assertEqual(app.profile.field_of_study, "Software Engineering")
                self.assertEqual(app.profile.interests, ["Python"])
                self.assertEqual(app.profile.home_postal_code, "")
                self.assertEqual(saved["home_postal_code"], postal_code)
                data_manager.return_value.save_profile.assert_not_called()

                app._handle_exit()

                data_manager.return_value.save_profile.assert_called_once_with({
                    "field_of_study": "Software Engineering",
                    "interests": ["Python"],
                    "home_postal_code": "",
                })

    @patch("main.DataManager")
    def test_invalid_required_fields_still_load_an_empty_profile(self, data_manager):
        for invalid_fields in ({"field_of_study": 123}, {"interests": "Python"}):
            with self.subTest(invalid_fields=invalid_fields):
                saved = {
                    "field_of_study": "Software Engineering",
                    "interests": ["Python"],
                    "home_postal_code": "12345",
                }
                saved.update(invalid_fields)
                data_manager.return_value.load_profile.return_value = saved
                data_manager.return_value.load_events.return_value = []

                app = EventWiseApp()

                self.assertEqual(app.profile, StudentProfile())

    @patch("main.DataManager")
    def test_analysis_receives_only_study_and_interests(self, data_manager):
        profile = StudentProfile("Software Engineering", ["Python"], "012345")
        data_manager.return_value.load_profile.return_value = profile.to_dict()
        data_manager.return_value.load_events.return_value = []
        app = EventWiseApp()
        app._io_manager = Mock()
        app._io_manager.collect_event_info.return_value = ("Workshop", "Learn Python", "Low")
        app._ai_manager = Mock()
        app._ai_manager.analyze_event.return_value = (None, "Offline test")

        app._handle_analyse_event()

        app._ai_manager.analyze_event.assert_called_once_with(
            {"field_of_study": "Software Engineering", "interests": ["Python"]},
            "Workshop",
            "Learn Python",
        )
        self.assertEqual(app.profile.home_postal_code, "012345")

    @patch("main.DataManager")
    def test_app_profile_save_and_exit_keep_postal(self, data_manager):
        data_manager.return_value.load_profile.return_value = {
            "field_of_study": "Software Engineering",
            "interests": ["Python"],
        }
        data_manager.return_value.load_events.return_value = []
        app = EventWiseApp()
        app._io_manager = Mock()
        updated = StudentProfile("Software Engineering", ["Python"], "012345").to_dict()
        app._io_manager.collect_profile.return_value = updated

        app._handle_profile()
        app._handle_exit()

        self.assertEqual(app.profile.home_postal_code, "012345")
        data_manager.return_value.save_profile.assert_called_once_with(updated)
        self.assertEqual(app._status, "Profile saved!")


class TestAppCredentialLoading(unittest.TestCase):
    @patch("main.EventWiseApp")
    def test_startup_loads_dotenv_before_creating_app(self, app_class):
        # Use fake credentials in a temporary directory for this offline test.
        with TemporaryDirectory(prefix="eventwise-startup-test-") as directory:
            project_directory = Path(directory)
            env_file = project_directory / ".env"
            env_file.write_text("API_KEY=fake-gemini-key\nONEMAP_ACCESS_TOKEN=fake-onemap-token\n")

            def create_app():
                self.assertTrue(GeminiClient().is_available())
                self.assertEqual(os.environ.get("API_KEY"), "fake-gemini-key")
                self.assertEqual(os.environ.get("ONEMAP_ACCESS_TOKEN"), "fake-onemap-token")
                return Mock()

            app_class.side_effect = create_app
            with patch.dict(os.environ, {}, clear=True):
                with patch("main.__file__", str(project_directory / "main.py")):
                    main()
            app_class.assert_called_once_with()

    @patch("main.EventWiseApp")
    def test_startup_preserves_existing_environment_key(self, app_class):
        with TemporaryDirectory(prefix="eventwise-startup-test-") as directory:
            project_directory = Path(directory)
            (project_directory / ".env").write_text("API_KEY=fake-file-key\n")
            with patch.dict(os.environ, {"API_KEY": "fake-environment-key"}):
                with patch("main.__file__", str(project_directory / "main.py")):
                    main()
                self.assertEqual(os.environ["API_KEY"], "fake-environment-key")
            app_class.return_value.run.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
