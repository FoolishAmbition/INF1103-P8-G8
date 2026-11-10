"""Offline tests for GeoLocation input validation."""

import unittest

from src.exceptions import ValidationError
from src.geolocation import validate_singapore_postal_code


class TestSingaporePostalCodeValidation(unittest.TestCase):
    def test_accepts_six_digit_postal_code(self):
        self.assertEqual(validate_singapore_postal_code("828761"), "828761")

    def test_preserves_leading_zero(self):
        self.assertEqual(validate_singapore_postal_code("012345"), "012345")

    def test_rejects_invalid_postal_codes(self):
        invalid_values = ("", "12345", "1234567", "ABC123", "12 456", "１２３４５６")
        for postal_code in invalid_values:
            with self.subTest(postal_code=postal_code):
                with self.assertRaises(ValidationError):
                    validate_singapore_postal_code(postal_code)

    def test_rejects_non_string_postal_code(self):
        with self.assertRaises(ValidationError):
            validate_singapore_postal_code(123456)


if __name__ == "__main__":
    unittest.main()
