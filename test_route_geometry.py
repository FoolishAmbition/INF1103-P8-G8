"""Offline geometry checks with synthetic coordinates, never personal locations."""

import unittest

from src.route_geometry import decode_route_geometry


class TestRouteGeometry(unittest.TestCase):
    def test_decodes_singapore_route_with_positive_and_negative_deltas(self):
        self.assertEqual(decode_route_geometry('_||F_mpxRgEoKgEfE'),
                         [[1.3, 103.8], [1.301, 103.802], [1.302, 103.801]])

    def test_invalid_incomplete_or_out_of_region_geometry_is_unknown(self):
        for value in (None, 123, '', '?', '??', '_||F_mpxR', '_||F_mpxRg',
                      '\n', '\u00e9', '~' * 40, '?' * 200001,
                      '_p~iF~ps|U_ulLnnqC_mqNvxq`@'):
            with self.subTest(value_type=type(value).__name__):
                self.assertIsNone(decode_route_geometry(value))

    def test_results_are_independent(self):
        first = decode_route_geometry('_||F_mpxRgEoKgEfE')
        first[0][0] = 0
        self.assertEqual(decode_route_geometry('_||F_mpxRgEoKgEfE')[0], [1.3, 103.8])


if __name__ == '__main__':
    unittest.main()
