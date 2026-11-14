"""Offline checks for event travel prompts, routing and the summary display."""

import io
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from rich.console import Console

from main import EventWiseApp
from src.geolocation import GeoLocationError, SINGAPORE_TIMEZONE, TransitRoute
from src.io_manager import IOManager
from src.models import StudentProfile
from src.travel_assessment import TravelEvaluator


class TestEventTravelPrompts(unittest.TestCase):
    def setUp(self):
        self.manager = IOManager(console=Console(file=io.StringIO()))
        self.manager._ask_text = Mock()
        self.manager.display_error = Mock()
        self.future_start = datetime.now(SINGAPORE_TIMEZONE) + timedelta(days=10)

    def test_collects_postal_with_leading_zero_and_singapore_time(self):
        self.manager._ask_text.side_effect = [
            "012345", self.future_start.strftime("%Y-%m-%d %H:%M")
        ]
        destination, event_start = self.manager.collect_event_travel_info()
        self.assertEqual(destination, "012345")
        self.assertEqual(event_start.tzinfo, SINGAPORE_TIMEZONE)
        self.assertEqual(event_start.minute, self.future_start.minute)

    def test_retries_invalid_postal_date_and_past_start(self):
        self.manager._ask_text.side_effect = [
            "ABC123", "012345", "2030-02-30 09:00", "2000-01-01 09:00",
            self.future_start.strftime("%Y-%m-%d %H:%M"),
        ]
        destination, event_start = self.manager.collect_event_travel_info()
        self.assertEqual(destination, "012345")
        self.assertGreater(event_start, datetime.now(SINGAPORE_TIMEZONE))
        self.assertEqual(self.manager.display_error.call_count, 3)

    def test_cancellation_at_either_prompt_returns_none(self):
        for answers in ([None], ["012345", None]):
            with self.subTest(answers=answers):
                self.manager._ask_text.side_effect = answers
                self.assertIsNone(self.manager.collect_event_travel_info())

    @patch("src.io_manager.questionary.select")
    def test_home_choice_is_only_available_with_saved_home(self, select_prompt):
        select_prompt.return_value.ask.return_value = "home"
        self.assertEqual(self.manager.choose_event_travel_origin("012345"), "012345")
        choices = select_prompt.call_args.kwargs["choices"]
        self.assertIn("home", [choice.value for choice in choices])
        select_prompt.return_value.ask.return_value = "skip"
        self.assertEqual(self.manager.choose_event_travel_origin(""), "")
        choices = select_prompt.call_args.kwargs["choices"]
        self.assertNotIn("home", [choice.value for choice in choices])

    @patch("src.io_manager.questionary.select")
    def test_skip_and_cancel_do_not_ask_for_origin(self, select_prompt):
        for choice, expected in (("skip", ""), ("cancel", None), (None, None)):
            with self.subTest(choice=choice):
                select_prompt.return_value.ask.return_value = choice
                self.assertEqual(self.manager.choose_event_travel_origin("012345"), expected)
                self.manager._ask_text.assert_not_called()

    @patch("src.io_manager.questionary.select")
    def test_alternate_origin_retries_invalid_input_and_preserves_zero(self, select_prompt):
        select_prompt.return_value.ask.return_value = "alternate"
        self.manager._ask_text.side_effect = ["ABC123", "12345", "012345"]
        self.assertEqual(self.manager.choose_event_travel_origin(""), "012345")
        self.assertEqual(self.manager.display_error.call_count, 2)

    @patch("src.io_manager.questionary.select")
    def test_alternate_origin_can_be_cancelled(self, select_prompt):
        select_prompt.return_value.ask.return_value = "alternate"
        self.manager._ask_text.return_value = None
        self.assertIsNone(self.manager.choose_event_travel_origin("012345"))


class TestEventTravelWorkflow(unittest.TestCase):
    def setUp(self):
        # The application constructs MongoStorage before its mocked DataManager.
        mongo_patch = patch("main.MongoStorage")
        mongo_patch.start()
        self.addCleanup(mongo_patch.stop)
        storage_patch = patch("main.DataManager")
        data_manager = storage_patch.start()
        self.addCleanup(storage_patch.stop)
        data_manager.return_value.load_profile.return_value = StudentProfile(
            "Software Engineering", ["Python"], "012345"
        ).to_dict()
        data_manager.return_value.load_events.return_value = []
        self.app = EventWiseApp()
        self.app._io_manager = Mock()
        self.app._io_manager.choose_event_travel_origin.side_effect = (
            lambda home_postal_code: home_postal_code
        )
        self.app._ai_manager = Mock()
        self.app._geolocation_service = Mock()
        self.event_start = (datetime.now(SINGAPORE_TIMEZONE) + timedelta(days=10)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        self.app._io_manager.collect_event_info.return_value = (
            "Workshop", "Learn Python", "Low"
        )
        self.app._io_manager.collect_event_travel_info.return_value = (
            "654321", self.event_start
        )
        self.app._ai_manager.analyze_event.return_value = ({
            "career_relevance": 5,
            "learning_value": 5,
            "networking_value": 5,
            "event_category": "Workshop",
            "ai_reasoning": "Relevant to Software Engineering.",
        }, None)
        self.first_route = TransitRoute(
            10, 32, self.event_start - timedelta(hours=1),
            self.event_start - timedelta(minutes=28)
        )
        self.proposed_departure = self.event_start - timedelta(minutes=47)
        self.checked_route = TransitRoute(
            12, 35, self.proposed_departure,
            self.event_start - timedelta(minutes=12)
        )
        self.app._geolocation_service.get_transit_route.side_effect = [
            self.first_route, self.checked_route
        ]

    def test_rechecks_departure_and_displays_the_matching_arrival(self):
        self.app._handle_analyse_event()

        requests = self.app._geolocation_service.get_transit_route.call_args_list
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].args, (
            "012345", "654321", self.event_start - timedelta(minutes=75)
        ))
        self.assertEqual(requests[1].args, ("012345", "654321", self.proposed_departure))
        display = self.app._io_manager.display_event_summary.call_args
        assessment = display.kwargs["travel_assessment"]
        self.assertEqual(assessment.recommended_departure, self.proposed_departure)
        self.assertEqual(assessment.estimated_arrival, self.checked_route.estimated_arrival)
        self.assertEqual(assessment.duration_minutes, 35)
        self.assertEqual(assessment.distance_km, 12)
        self.assertEqual(assessment.feasibility, "WITHIN_LIMIT")
        self.assertEqual(len(self.app.events), 1)
        self.assertEqual(self.app.events[0].recommendation, "ATTEND")
        self.assertNotIn("destination_postal_code", self.app.events[0].to_dict())
        self.app._ai_manager.analyze_event.assert_called_once_with(
            {"field_of_study": "Software Engineering", "interests": ["Python"]},
            "Workshop", "Learn Python"
        )

    def test_long_journey_keeps_ai_recommendation(self):
        self.checked_route.duration_minutes = 90
        self.checked_route.estimated_arrival = self.proposed_departure + timedelta(minutes=90)
        self.app._handle_analyse_event()
        assessment = self.app._io_manager.display_event_summary.call_args.kwargs["travel_assessment"]
        self.assertEqual(assessment.feasibility, "LONG_JOURNEY")
        self.assertEqual(self.app.events[0].recommendation, "ATTEND")

    def test_missing_home_postal_still_adds_event_without_route_requests(self):
        self.app.profile.home_postal_code = ""
        self.app._handle_analyse_event()
        self.app._geolocation_service.get_transit_route.assert_not_called()
        assessment = self.app._io_manager.display_event_summary.call_args.kwargs["travel_assessment"]
        self.assertIsNone(assessment)
        self.app._io_manager.collect_event_travel_info.assert_not_called()
        self.assertEqual(self.app.events[0].recommendation, "ATTEND")

    def test_provider_failures_at_either_request_preserve_event(self):
        for code in ("TIMEOUT", "NO_ROUTE", "AUTHENTICATION_ERROR", "QUOTA_EXCEEDED"):
            for fail_on_second_request in (False, True):
                with self.subTest(code=code, second_request=fail_on_second_request):
                    error = GeoLocationError(code, "Safe provider failure.")
                    responses = [error]
                    if fail_on_second_request:
                        responses = [self.first_route, error]
                    self.app._geolocation_service.get_transit_route.side_effect = responses
                    self.app._handle_analyse_event()
                    assessment = self.app._io_manager.display_event_summary.call_args.kwargs["travel_assessment"]
                    self.assertEqual(assessment.status, "UNAVAILABLE")
                    self.assertIsNone(assessment.estimated_arrival)
                    self.assertEqual(assessment.error_message, "Safe provider failure.")
                    self.assertEqual(self.app.events[-1].recommendation, "ATTEND")

    def test_skip_preserves_ai_event_without_any_geolocation_calls(self):
        for home in ("012345", ""):
            with self.subTest(home=home):
                self.app.profile.home_postal_code = home
                self.app._io_manager.choose_event_travel_origin.side_effect = None
                self.app._io_manager.choose_event_travel_origin.return_value = ""
                self.app._handle_analyse_event()
                self.app._io_manager.collect_event_travel_info.assert_not_called()
                self.assertEqual(self.app._geolocation_service.mock_calls, [])
                self.assertEqual(self.app.events[-1].recommendation, "ATTEND")
                self.assertEqual(self.app.profile.home_postal_code, home)

    def test_alternate_origin_is_used_for_both_requests_without_changing_profile(self):
        for home in ("012345", ""):
            with self.subTest(home=home):
                self.app.profile.home_postal_code = home
                self.app._io_manager.choose_event_travel_origin.side_effect = None
                self.app._io_manager.choose_event_travel_origin.return_value = "023456"
                self.app._geolocation_service.get_transit_route.reset_mock()
                self.app._geolocation_service.get_transit_route.side_effect = [
                    self.first_route, self.checked_route
                ]
                self.app._handle_analyse_event()
                requests = self.app._geolocation_service.get_transit_route.call_args_list
                self.assertEqual(len(requests), 2)
                self.assertEqual([call.args[0] for call in requests], ["023456", "023456"])
                self.assertEqual(self.app.profile.home_postal_code, home)
                self.app._data_manager.save_profile.assert_not_called()
                self.assertEqual(self.app.events[-1].recommendation, "ATTEND")

    def test_cancel_at_origin_choice_stops_event_submission(self):
        self.app._io_manager.choose_event_travel_origin.side_effect = None
        self.app._io_manager.choose_event_travel_origin.return_value = None
        self.app._handle_analyse_event()
        self.app._io_manager.collect_event_travel_info.assert_not_called()
        self.app._ai_manager.analyze_event.assert_not_called()
        self.assertEqual(self.app._geolocation_service.mock_calls, [])
        self.assertEqual(self.app.events, [])

    def test_invalid_route_becomes_unavailable(self):
        self.first_route.duration_minutes = -1
        self.app._handle_analyse_event()
        assessment = self.app._io_manager.display_event_summary.call_args.kwargs["travel_assessment"]
        self.assertEqual(assessment.status, "UNAVAILABLE")
        self.assertEqual(len(self.app.events), 1)

    def test_past_departure_stops_before_second_request(self):
        self.first_route.duration_minutes = 60 * 24 * 20
        self.app._handle_analyse_event()
        self.assertEqual(self.app._geolocation_service.get_transit_route.call_count, 1)
        assessment = self.app._io_manager.display_event_summary.call_args.kwargs["travel_assessment"]
        self.assertIn("already passed", assessment.error_message)

    def test_past_event_sends_no_route_requests(self):
        assessment = self.app._assess_event_travel(
            "654321", datetime.now(SINGAPORE_TIMEZONE) - timedelta(minutes=1)
        )
        self.assertEqual(assessment.status, "UNAVAILABLE")
        self.app._geolocation_service.get_transit_route.assert_not_called()

    def test_cancelled_event_or_travel_prompts_stop_analysis(self):
        for cancel_event in (True, False):
            with self.subTest(cancel_event=cancel_event):
                self.app._io_manager.collect_event_info.return_value = (
                    "Workshop", "Learn Python", "Low"
                )
                self.app._io_manager.collect_event_travel_info.return_value = None
                if cancel_event:
                    self.app._io_manager.collect_event_info.return_value = None
                self.app._handle_analyse_event()
                self.app._ai_manager.analyze_event.assert_not_called()
                self.app._geolocation_service.get_transit_route.assert_not_called()
                self.assertEqual(self.app.events, [])

    def test_ai_failure_stops_before_routing(self):
        self.app._ai_manager.analyze_event.return_value = (None, "AI unavailable")
        self.app._handle_analyse_event()
        self.app._geolocation_service.get_transit_route.assert_not_called()
        self.assertEqual(self.app.events, [])

    def test_invalid_ai_scores_stop_before_routing(self):
        self.app._ai_manager.analyze_event.return_value = ({
            "career_relevance": 99,
            "learning_value": 5,
            "networking_value": 5,
            "event_category": "Workshop",
            "ai_reasoning": "Invalid score example.",
        }, None)
        self.app._handle_analyse_event()
        self.app._geolocation_service.get_transit_route.assert_not_called()
        self.assertEqual(self.app.events, [])

    def test_rechecked_departure_can_be_on_previous_day(self):
        midnight_start = self.event_start.replace(hour=0, minute=15)
        expected_departure = midnight_start - timedelta(minutes=47)
        self.first_route.departure_time = midnight_start - timedelta(minutes=75)
        self.first_route.estimated_arrival = midnight_start - timedelta(minutes=43)
        self.checked_route.departure_time = expected_departure
        self.checked_route.estimated_arrival = midnight_start - timedelta(minutes=12)
        assessment = self.app._assess_event_travel("654321", midnight_start)
        second_request = self.app._geolocation_service.get_transit_route.call_args_list[1]
        self.assertEqual(second_request.args[2], expected_departure)
        self.assertLess(expected_departure.date(), midnight_start.date())
        self.assertEqual(assessment.recommended_departure, expected_departure)


class TestEventTravelDisplay(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.manager = IOManager(console=Console(file=self.output, width=120))
        self.event_start = datetime(2030, 1, 2, 9, tzinfo=SINGAPORE_TIMEZONE)

    def test_arrival_buffer_and_late_arrival_messages(self):
        cases = (
            (15, "meets the 15-minute buffer"),
            (5, "misses the requested arrival buffer"),
            (-5, "after the event starts"),
        )
        for minutes_before_event, expected_message in cases:
            with self.subTest(minutes_before_event=minutes_before_event):
                self.output.seek(0)
                self.output.truncate(0)
                route = TransitRoute(
                    10, 32, self.event_start - timedelta(hours=1),
                    self.event_start - timedelta(minutes=minutes_before_event)
                )
                assessment = TravelEvaluator().evaluate(self.event_start, route)
                self.manager._display_travel_assessment(assessment, self.event_start)
                text = self.output.getvalue()
                self.assertIn(expected_message, text)
                self.assertIn("SGT", text)
                self.assertIn("Schedules can change", text)

    def test_unavailable_display_has_no_fabricated_journey_values(self):
        assessment = TravelEvaluator().evaluate(self.event_start)
        self.manager._display_travel_assessment(assessment, self.event_start)
        text = self.output.getvalue()
        self.assertIn("UNAVAILABLE", text)
        self.assertNotIn("Distance:", text)
        self.assertNotIn("Journey duration:", text)

    @patch("src.io_manager.questionary.select")
    def test_summary_displays_ai_and_travel_before_back_prompt(self, select_prompt):
        assessment = TravelEvaluator().evaluate(self.event_start)
        self.manager.display_event_summary({
            "event_name": "Workshop", "recommendation": "ATTEND",
            "career_relevance": 5, "learning_value": 5, "networking_value": 5,
        }, travel_assessment=assessment, event_start=self.event_start)
        text = self.output.getvalue()
        self.assertIn("ATTEND", text)
        self.assertIn("Public transport estimate", text)
        self.assertIn("UNAVAILABLE", text)
        select_prompt.assert_called_once()

    @patch("src.io_manager.questionary.select")
    def test_saved_event_summary_supports_existing_callers(self, select_prompt):
        self.manager.display_event_summary({
            "event_name": "Old workshop", "recommendation": "ATTEND",
            "career_relevance": 5, "learning_value": 5, "networking_value": 5,
        }, back_label="Return to event table")
        self.assertIn("Old workshop", self.output.getvalue())
        select_prompt.assert_called_once_with("Return to event table", choices=["Back"])


if __name__ == "__main__":
    unittest.main()
