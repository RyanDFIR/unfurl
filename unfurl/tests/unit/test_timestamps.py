from unfurl.core import Unfurl
from unfurl.parsers import parse_gmail, parse_timestamp
import datetime
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


class TestDetectionWindowsHaveNotExpired(unittest.TestCase):
    """A tripwire on the hardcoded plausibility windows in parse_timestamp.py.

    Blind detection is by magnitude: a bare number is a timestamp if it lands inside a
    hardcoded window, and nearly every window in the ladder ends at 2030-01-01. On that
    date those branches stop matching current values and the parser goes quiet -- no
    error, no descriptor, just no timestamp where there used to be one. Two seconds is
    the whole cliff: 1893455999 decodes, 1893456001 produces nothing at all.

    Nothing else in the suite would notice. Every other test here asserts on a fixed
    historical value, so they stay green straight through the expiry and CI never
    mentions it; the failure surfaces when someone points Unfurl at a fresh artifact and
    wonders why timestamps stopped parsing.

    So this test works from the clock instead: it encodes a time DETECTION_LEAD from now
    into each format and requires it to still be detected. Each case also checks the
    decoded date, so a green run means the format was really round-tripped and not just
    that something, somewhere, decoded.

    When it fails, nothing is broken yet -- there is DETECTION_LEAD of runway. Widen the
    upper bound of the named branch in parse_timestamp.py, and the "Useful values for
    ranges" table in that decoder's docstring, which documents the same numbers.
    """

    # How much warning to give. Long enough that the fix is never urgent, short enough
    # that the bounds are not being widened years before anyone needs it.
    DETECTION_LEAD = datetime.timedelta(days=548)  # ~18 months

    # Seconds to add to a Unix timestamp to get each format's own count. Kept here rather
    # than imported so that a wrong constant in the parser cannot quietly validate itself.
    FROM_1601 = 11644473600   # Windows FileTime, WebKit
    FROM_0001 = 62135596800   # .NET DateTime ticks
    FROM_2000 = -946684800    # PostgreSQL
    FROM_2001 = -978307200    # Mac Absolute Time

    def cases(self, unix):
        """(label, the value as it would appear in evidence, expected data_type).

        Integer arithmetic throughout: a float multiply loses precision above ~2**53,
        which is well below the FileTime and ticks magnitudes.
        """
        return [
            ('Epoch seconds',
             f'{unix}', 'timestamp.epoch-seconds'),
            ('Epoch milliseconds',
             f'{unix * 10 ** 3}', 'timestamp.epoch-milliseconds'),
            ('Epoch ten-microseconds',
             f'{unix * 10 ** 5}', 'timestamp.epoch-ten-microseconds'),
            ('Epoch microseconds',
             f'{unix * 10 ** 6}', 'timestamp.epoch-microseconds'),
            ('Epoch nanoseconds',
             f'{unix * 10 ** 9}', 'timestamp.epoch-nanoseconds'),
            ('WebKit',
             f'{(unix + self.FROM_1601) * 10 ** 6}', 'timestamp.webkit'),
            ('WebKit milliseconds',
             f'{(unix + self.FROM_1601) * 10 ** 3}', 'timestamp.webkit-milliseconds'),
            ('Windows FileTime',
             f'{(unix + self.FROM_1601) * 10 ** 7}', 'timestamp.windows-filetime'),
            ('.NET DateTime ticks',
             f'{(unix + self.FROM_0001) * 10 ** 7}', 'timestamp.datetime-ticks'),
            ('PostgreSQL',
             f'{(unix + self.FROM_2000) * 10 ** 6}', 'timestamp.postgresql'),
            ('Mac Absolute Time',
             f'{unix + self.FROM_2001}', 'timestamp.mac-absolute-time'),
            ('Epoch seconds (float)',
             f'{unix}.5', 'timestamp.epoch-seconds'),
            ('Mac Absolute Time (float)',
             f'{unix + self.FROM_2001}.5', 'timestamp.mac-absolute-time'),
            ('Epoch seconds (hex)',
             f'{unix:08X}', 'timestamp.epoch-seconds-hex'),
            ('Windows FileTime (hex)',
             f'{(unix + self.FROM_1601) * 10 ** 7:016X}', 'timestamp.windows-filetime-hex'),
        ]

    def test_a_current_timestamp_is_still_detected(self):
        target = datetime.datetime.now(datetime.timezone.utc) + self.DETECTION_LEAD
        unix = int(target.timestamp())
        expected_date = target.strftime('%Y-%m-%d')
        lead_days = self.DETECTION_LEAD.days

        for label, value, data_type in self.cases(unix):
            with self.subTest(format=label):
                test = parse_value(value)
                matches = get_nodes_by_type(test, data_type)

                self.assertEqual(
                    1, len(matches),
                    f'{label} no longer detects a timestamp {lead_days} days out '
                    f'({expected_date}). Its plausibility window in parse_timestamp.py is '
                    f'about to expire, and when it does, values of this format will stop '
                    f'being decoded with no error and no other failing test. Widen the '
                    f'upper bound of the {label} branch and the "Useful values for ranges" '
                    f'table in its decoder docstring.')

                self.assertTrue(
                    matches[0].value.startswith(expected_date),
                    f'{label} decoded {value} as {matches[0].value}, but it was encoded as '
                    f'{expected_date}. The window is intact; what is wrong is the '
                    f'encoding this test uses for the format.')

    def test_gmail_id_bounds_have_not_expired(self):
        """parse_gmail applies the same kind of window to the timestamp inside an ID.

        It caps at 2035 rather than 2030, so it expires later than the ladder above, but
        silently and in the same way: an ID minted past the bound is judged implausible
        and left undecoded.
        """
        target = datetime.datetime.now(datetime.timezone.utc) + self.DETECTION_LEAD

        self.assertLess(
            int(target.timestamp() * 1000), parse_gmail.max_reasonable_ms,
            f'parse_gmail.max_reasonable_ms is within {self.DETECTION_LEAD.days} days of '
            f'now, so Gmail IDs minted after it will be treated as implausible and left '
            f'undecoded. Raise it, along with the date in the comment above it.')


if __name__ == '__main__':
    unittest.main()
