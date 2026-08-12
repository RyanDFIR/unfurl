from unfurl.core import Unfurl
from unfurl.parsers import parse_timestamp
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


def parse_value(value):
    test = Unfurl()
    test.add_to_queue(data_type='url', key=None, value=value)
    test.parse_queue()
    return test


class TestTimestampDecoders(unittest.TestCase):
    """Tests of the individual timestamp decoding functions."""

    def test_decode_epoch_seconds(self):
        result = parse_timestamp.decode_epoch_seconds(1735689600)
        self.assertEqual(result['data_type'], 'timestamp.epoch-seconds')
        self.assertEqual(result['timestamp_value'], '2025-01-01 00:00:00+00:00')

    def test_decode_epoch_milliseconds(self):
        result = parse_timestamp.decode_epoch_milliseconds(1593122074675)
        self.assertEqual(result['data_type'], 'timestamp.epoch-milliseconds')
        self.assertEqual(result['timestamp_value'], '2020-06-25 21:54:34.675+00:00')

    def test_decode_epoch_ten_microseconds(self):
        result = parse_timestamp.decode_epoch_ten_microseconds(170000000000000)
        self.assertEqual(result['data_type'], 'timestamp.epoch-ten-microseconds')
        self.assertEqual(result['timestamp_value'], '2023-11-14 22:13:20+00:00')

    def test_decode_epoch_nanoseconds(self):
        result = parse_timestamp.decode_epoch_nanoseconds(1735689600123456789)
        self.assertEqual(result['data_type'], 'timestamp.epoch-nanoseconds')
        # Full nanosecond precision is preserved in the rendered string
        self.assertEqual(result['timestamp_value'], '2025-01-01 00:00:00.123456789+00:00')

        result = parse_timestamp.decode_epoch_nanoseconds(1735689600000000000)
        self.assertEqual(result['timestamp_value'], '2025-01-01 00:00:00+00:00')

    def test_decode_mac_absolute_time_nanoseconds(self):
        result = parse_timestamp.decode_mac_absolute_time_nanoseconds(757382400000000000)
        self.assertEqual(result['data_type'], 'timestamp.mac-absolute-time-nanoseconds')
        self.assertEqual(result['timestamp_value'], '2025-01-01 00:00:00+00:00')

        result = parse_timestamp.decode_mac_absolute_time_nanoseconds(757382400123456789)
        self.assertEqual(result['timestamp_value'], '2025-01-01 00:00:00.123456789+00:00')

    def test_decode_postgresql(self):
        result = parse_timestamp.decode_postgresql(789004800000000)
        self.assertEqual(result['data_type'], 'timestamp.postgresql')
        self.assertEqual(result['timestamp_value'], '2025-01-01 00:00:00+00:00')

        result = parse_timestamp.decode_postgresql(789004800123456)
        self.assertEqual(result['timestamp_value'], '2025-01-01 00:00:00.123456+00:00')


class TestTimestampDetection(unittest.TestCase):
    """Tests of the automatic timestamp detection on parsed values."""

    def assert_detected_as(self, value, expected_data_type, expected_timestamp):
        test = parse_value(value)
        matches = get_nodes_by_type(test, expected_data_type)
        self.assertEqual(len(matches), 1, f'expected one {expected_data_type} node for {value}')
        self.assertEqual(matches[0].value, expected_timestamp)

    def test_detects_epoch_nanoseconds(self):
        self.assert_detected_as(
            '1735689600123456789', 'timestamp.epoch-nanoseconds', '2025-01-01 00:00:00.123456789+00:00')

    def test_epoch_nanoseconds_suppressed_for_snowflake_domains(self):
        # Modern (2021-2025) snowflake IDs are 19-digit values inside the plausible
        # nanoseconds range; under snowflake domains only the snowflake decode should
        # appear, not a second (wrong) nanoseconds timestamp.
        test = parse_value('https://x.com/someuser/status/1750000000000000000')
        self.assertEqual(get_nodes_by_type(test, 'timestamp.epoch-nanoseconds'), [])

        # The correct interpretation (via the Twitter snowflake parser) is still present
        snowflake_timestamps = get_nodes_by_type(test, 'timestamp.epoch-milliseconds')
        self.assertEqual(len(snowflake_timestamps), 1)
        self.assertEqual(snowflake_timestamps[0].value, '2024-01-24 03:38:08.084+00:00')

    def test_mac_absolute_time_nanoseconds_not_blindly_detected(self):
        # Mac Absolute Time nanoseconds is intentionally excluded from magnitude-based
        # detection: 2018-2021 era snowflake IDs (Discord, Twitter, etc.) fall inside its
        # entire plausible range, so blind detection would mislabel them.
        test = parse_value('757382400000000000')
        self.assertEqual(get_nodes_by_type(test, 'timestamp.mac-absolute-time-nanoseconds'), [])

    def test_mac_absolute_time_nanoseconds_explicit_data_type(self):
        # Parsers with context can opt in by classifying a node with this data_type
        test = Unfurl()
        test.add_to_queue(
            data_type='mac-absolute-time-nanoseconds', key=None, value='757382400123456789')
        test.parse_queue()

        matches = get_nodes_by_type(test, 'timestamp.mac-absolute-time-nanoseconds')
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].value, '2025-01-01 00:00:00.123456789+00:00')

    def test_detects_datetime_ticks(self):
        self.assert_detected_as(
            '638712864000000000', 'timestamp.datetime-ticks', '2025-01-01 00:00:00+00:00')

    def test_detects_postgresql(self):
        self.assert_detected_as(
            '789004800000000', 'timestamp.postgresql', '2025-01-01 00:00:00+00:00')

    def test_detects_epoch_ten_microseconds(self):
        # Regression test: this branch previously decoded as epoch microseconds,
        # yielding a bogus 1975-era date.
        self.assert_detected_as(
            '170000000000000', 'timestamp.epoch-ten-microseconds', '2023-11-14 22:13:20+00:00')

    def test_detects_epoch_seconds(self):
        self.assert_detected_as(
            '1735689600', 'timestamp.epoch-seconds', '2025-01-01 00:00:00+00:00')

    def test_detects_filetime_hex(self):
        """ Test a bare conversion of Windows FileTime (Hex) timestamp """
        test = parse_value('01d15614cbaee92c')

        matches = get_nodes_by_type(test, 'timestamp.windows-filetime-hex')
        self.assertEqual(len(matches), 1)
        self.assertIn('2016-01-23 19:32:28.702751', matches[0].label)
        self.assertIn('Windows FileTime (hex)', matches[0].hover)

    def test_detects_webkit_milliseconds(self):
        """ Test a bare conversion of Webkit milliseconds timestamp """
        test = parse_value('13317004800000')

        matches = get_nodes_by_type(test, 'timestamp.webkit-milliseconds')
        self.assertEqual(len(matches), 1)
        self.assertIn('2023-01-01 00:00:00', matches[0].label)
        self.assertIn('Webkit milliseconds', matches[0].hover)

    def test_detects_epoch_seconds_hex(self):
        """ Test a bare conversion of Epoch Seconds (Hex) timestamp """
        test = parse_value('54A48E00')

        matches = get_nodes_by_type(test, 'timestamp.epoch-seconds-hex')
        self.assertEqual(len(matches), 1)
        self.assertIn('2015-01-01 00', matches[0].label)
        self.assertIn('Epoch seconds (hex)', matches[0].hover)


if __name__ == '__main__':
    unittest.main()
