# Copyright 2024 Ryan Benson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import re

from unfurl import utils

timestamp_edge = {
    'color': {
        'color': 'blue'
    },
    'title': 'Date & Time Parsing Functions',
    'label': '🕓'
}


def trim_zero_fractional_seconds(timestamp_string, number_to_trim):
    """Timestamp formats have different levels of precision; trim off extra 0s.

    Different formats may have less precision that the microseconds datetime returns.
    Trim off the appropriate number of trailing zeros from a value to not add extra,
    incorrect precision to it.

    """
    m = re.search(
        rf'\.\d{{{6 - number_to_trim}}}0{{{number_to_trim}}}(?P<tz_offset>\+\d\d:\d\d)?$', timestamp_string)
    if m and m.group('tz_offset'):
        return f"{timestamp_string[:-(number_to_trim + 6)]}{m.group('tz_offset')}"
    elif m:
        return timestamp_string[:-number_to_trim]
    return timestamp_string


def decode_epoch_seconds(seconds):
    """Decode a numeric timestamp in Epoch seconds format to a human-readable timestamp.

    An Epoch timestamp (1-10 digits) is an integer that counts the number of seconds since Jan 1 1970.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 0
      2015: 1420070400
      2025: 1735689600
      2030: 1893456000

    """
    return {
        'data_type': 'timestamp.epoch-seconds',
        'display_type': 'Epoch seconds',
        'timestamp_value': str(datetime.datetime.fromtimestamp(float(seconds), tz=datetime.UTC))
    }


def decode_epoch_centiseconds(centiseconds):
    """Decode a numeric timestamp in Epoch centiseconds (10 ms) format to a human-readable timestamp.

    An Epoch centisecond timestamp (1-12 digits) is an integer that counts the number of centiseconds (10 ms)
    since Jan 1 1970.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 0
      2015: 142007040000
      2025: 173568960000
      2030: 189345600000

    """
    # Trim off the 4 trailing 0s (don't add precision that wasn't in the timestamp)
    converted_ts = trim_zero_fractional_seconds(
        str(datetime.datetime.fromtimestamp(float(centiseconds) / 100, tz=datetime.UTC)), 4)

    return {
        'data_type': 'timestamp.epoch-centiseconds',
        'display_type': 'Epoch centiseconds',
        'timestamp_value': converted_ts
    }

def decode_epoch_milliseconds(milliseconds):
    """Decode a numeric timestamp in Epoch milliseconds format to a human-readable timestamp.

    An Epoch millisecond timestamp (1-13 digits) is an integer that counts the number of milliseconds since Jan 1 1970.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 0
      2015: 1420070400000
      2025: 1735689600000
      2030: 1893456000000

    """
    converted_dt = datetime.datetime(1970, 1, 1, tzinfo=datetime.UTC) + datetime.timedelta(milliseconds=float(milliseconds))
    # Trim off the 3 trailing 0s (don't add precision that wasn't in the timestamp)
    converted_ts = trim_zero_fractional_seconds(str(converted_dt), 3)

    return {
        'data_type': 'timestamp.epoch-milliseconds',
        'display_type': 'Epoch milliseconds',
        'timestamp_value': converted_ts
    }


def decode_epoch_ten_microseconds(ten_microseconds):
    """Decode a numeric timestamp in Epoch ten-millisecond increments to a human-readable timestamp.

    An Epoch ten-microsecond increments timestamp (1-15 digits) is an integer that counts the number of ten-microsecond
    increments since Jan 1 1970.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 0
      2015: 142007040000000
      2025: 173568960000000
      2030: 189345600000000

    """
    # Trim off the trailing 0 (don't add precision that wasn't in the timestamp)
    converted_ts = trim_zero_fractional_seconds(
        str(datetime.datetime.fromtimestamp(float(ten_microseconds) / 100000, tz=datetime.UTC)), 1)

    return {
        'data_type': 'timestamp.epoch-ten-microseconds',
        'display_type': 'Epoch ten-microsecond increments',
        'timestamp_value': converted_ts
    }

def decode_epoch_microseconds(microseconds):
    """Decode a numeric timestamp in Epoch microseconds format to a human-readable timestamp.

    An Epoch millisecond timestamp (1-16 digits) is an integer that counts the number of milliseconds since Jan 1 1970.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 0
      2015: 1420070400000000
      2025: 1735689600000000
      2030: 1893456000000000

    """
    converted_ts = datetime.datetime.fromtimestamp(float(microseconds) / 1000000, tz=datetime.UTC)

    return {
        'data_type': 'timestamp.epoch-microseconds',
        'display_type': 'Epoch microseconds',
        'timestamp_value': str(converted_ts)
    }


def decode_webkit(microseconds):
    """Decode a numeric timestamp in Webkit format to a human-readable timestamp.

    A Webkit timestamp (17 digits) is an integer that counts the number of microseconds since 12:00AM Jan 1 1601 UTC.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 11644473600000000
      2015: 13064544000000000
      2025: 13380163200000000
      2030: 13537929600000000

    """
    converted_ts = datetime.datetime.fromtimestamp((float(microseconds) / 1000000) - 11644473600, tz=datetime.UTC)

    return {
        'data_type': 'timestamp.webkit',
        'display_type': 'Webkit',
        'timestamp_value': str(converted_ts)
    }

def decode_webkit_milliseconds(milliseconds):
    """Decode a numeric timestamp in Webkit milliseconds format to a human-readable timestamp.

    A Webkit milliseconds timestamp (14 digits) is an integer that counts the number of milliseconds since
    12:00AM Jan 1 1601 UTC.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 11644473600000
      2015: 13064544000000
      2025: 13380163200000
      2030: 13537929600000

    """
    converted_ts = datetime.datetime.fromtimestamp((float(milliseconds) / 1000) - 11644473600, tz=datetime.UTC)

    return {
        'data_type': 'timestamp.webkit-milliseconds',
        'display_type': 'Webkit milliseconds',
        'timestamp_value': str(converted_ts)
    }


def decode_windows_filetime(intervals):
    """Decode a numeric timestamp in Windows FileTime format to a human-readable timestamp.

    A Windows FileTime timestamp (18 digits) is a 64-bit value that represents the number of 100-nanosecond intervals
    since 12:00AM Jan 1 1601 UTC.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 116444736000000000
      2015: 130645440000000000
      2025: 133801632000000000
      2030: 135379296000000000
      2065: 146424672000000000

    """
    converted_ts =  datetime.datetime.fromtimestamp((float(intervals) / 10000000) - 11644473600, tz=datetime.UTC)

    return {
        'data_type': 'timestamp.windows-filetime',
        'display_type': 'Windows FileTime',
        'timestamp_value': str(converted_ts)
    }

def decode_datetime_ticks(ticks):
    """Decode a numeric timestamp in .Net/C# DateTime ticks format to a human-readable timestamp.

    A .Net/C# DateTime ticks timestamp (18 digits) is the number of 100-nanosecond intervals that have elapsed since
    12:00:00 midnight, January 1, 0001 (0:00:00 UTC on January 1, 0001, in the Gregorian calendar), which represents
    DateTime.MinValue. It does not include the number of ticks that are attributable to leap seconds.

    A single tick represents one hundred nanoseconds or one ten-millionth of a second. There are 10,000 ticks in a
    millisecond, or 10 million ticks in a second.

    (^ from https://docs.microsoft.com/en-us/dotnet/api/system.datetime.ticks?view=netframework-4.8)

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 621355968000000000
      2015: 635556672000000000
      2025: 638712864000000000
      2030: 640290528000000000
      2038: 642815136000000000

    """
    ticks = int(ticks)
    seconds = (ticks - 621355968000000000) / 10000000
    converted_ts = datetime.datetime.fromtimestamp(seconds, tz=datetime.UTC)

    return {
        'data_type': 'timestamp.datetime-ticks',
        'display_type': 'DateTime ticks',
        'timestamp_value': str(converted_ts)
    }


def decode_mac_absolute_time(seconds):
    """Decode a numeric timestamp in Mac Absolute Time format to a human-readable timestamp.

    A Mac Absolute Time timestamp (9 digits typically) is the number of seconds since 2001-01-01. This time format is
    also known as CFAbsoluteTime, Core Data timestamp, or Cocoa Core Data timestamp. Negative values are allowed and
    denote timestamps before the reference date.

    ref: https://developer.apple.com/documentation/corefoundation/cfabsolutetime

    Useful values for ranges (all Jan-1 00:00:00):
      1970: -978307200
      2015: 441763200
      2025: 757382400
      2030: 915148800
      2035: 1072915200

    """
    converted_ts = datetime.datetime.fromtimestamp(float(seconds) + 978307200, tz=datetime.UTC)

    return {
        'data_type': 'timestamp.mac-absolute-time',
        'display_type': 'Mac Absolute Time / Cocoa',
        'timestamp_value': str(converted_ts)
    }


def decode_epoch_hex(seconds):
    """Decode a hex string (big endian) of an Epoch seconds integer to a human-readable timestamp.

    An Epoch timestamp (1-10 digits) is an integer that counts the number of seconds since Jan 1 1970.

    Useful values for ranges (all Jan-1 00:00:00):
      2015: 54A48E00
      2025: 67748580
      2030: 713FB300

    """
    timestamp = decode_epoch_seconds(int(seconds, 16))

    return {
        'data_type': 'timestamp.epoch-seconds-hex',
        'display_type': 'Epoch seconds (hex)',
        'timestamp_value': timestamp['timestamp_value']
    }


def decode_windows_filetime_hex(intervals):
    """Decode a hex timestamp in Windows FileTime format to a human-readable timestamp.

    A Windows FileTime timestamp (18 digits) is a 64-bit value that represents the number of 100-nanosecond intervals
    since 12:00AM Jan 1 1601 UTC.

    Useful values for ranges (all Jan-1 00:00:00):
      1970: 19DB1DED53E8000
      2015: 1D02555E2B98000
      2025: 1DB5BE019BA4000
      2065: 2083476A0E9C000

    """
    int_right = int(intervals, 16)
    timestamp = decode_windows_filetime(int_right)

    return {
        'data_type': 'timestamp.windows-filetime-hex',
        'display_type': 'Windows FileTime (hex)',
        'timestamp_value': timestamp['timestamp_value']
    }


def run(unfurl, node):
    new_timestamp = (None, 'unknown')

    # There are some known cases where we want to suppress a timestamp conversion; put them here.
    if node.data_type in ('description', 'google.ei'):
        return

    # If the node is explicitly classified as a raw timestamp, use that type for the conversion
    elif node.data_type == 'epoch-seconds':
        new_timestamp = decode_epoch_seconds(node.value)

    elif node.data_type == 'epoch-centiseconds':
        new_timestamp = decode_epoch_centiseconds(node.value)

    elif node.data_type == 'epoch-milliseconds':
        new_timestamp = decode_epoch_milliseconds(node.value)

    elif node.data_type == 'epoch-ten-microseconds':
        new_timestamp = decode_epoch_ten_microseconds(node.value)

    elif node.data_type == 'epoch-microseconds':
        new_timestamp = decode_epoch_microseconds(node.value)

    elif node.data_type == 'windows-filetime':
        new_timestamp = decode_windows_filetime(node.value)

    elif node.data_type == 'webkit':
        new_timestamp = decode_webkit(node.value)

    elif node.data_type == 'webkit-milliseconds':
        new_timestamp = decode_webkit_milliseconds(node.value)

    elif node.data_type == 'datetime-ticks':
        new_timestamp = decode_datetime_ticks(node.value)

    elif node.data_type == 'mac-absolute-time':
        new_timestamp = decode_mac_absolute_time(node.value)

    elif node.data_type == 'epoch-hex-seconds':
        new_timestamp = decode_epoch_hex(node.value)

    # Otherwise, examine the value of the node and see if we can detect a reasonable timestamp
    else:
        matches_digits = utils.digits_re.fullmatch(str(node.value))
        matches_float = utils.float_re.fullmatch(str(node.value))
        matches_hex = utils.hex_re.fullmatch(str(node.value))

        if matches_digits:
            timestamp = int(node.value)

            # Windows FileTime (18 digits)
            if 130645440000000000 <= timestamp <= 135379296000000000:  # 2015 <= ts <= 2030
                new_timestamp = decode_windows_filetime(timestamp)

            # .Net/C# DateTime ticks (18 digits)
            elif 635556672000000000 <= timestamp <= 640290528000000000:  # 2015 <= ts <= 2030
                new_timestamp = decode_datetime_ticks(timestamp)

            # WebKit (17 digits)
            elif 13064544000000000 <= timestamp <= 13537929600000000:  # 2015 <= ts <= 2030
                new_timestamp = decode_webkit(timestamp)

            # Epoch microseconds (16 digits)
            elif 1420070400000000 <= timestamp <= 1893456000000000:  # 2015 <= ts <= 2030
                new_timestamp = decode_epoch_microseconds(timestamp)

            # Epoch ten microsecond increments (15 digits)
            elif 142007040000000 <= timestamp <= 189345600000000:  # 2015 <= ts <= 2030
                new_timestamp = decode_epoch_microseconds(timestamp)

            # Webkit milliseconds (14 digits)
            elif 12906777600000 < timestamp < 15000000000000:  # 2009 < ts < 2076
                new_timestamp = decode_webkit_milliseconds(timestamp)

            # Epoch milliseconds (13 digits)
            elif 1420070400000 <= timestamp <= 1893456000000:  # 2015 <= ts <= 2030
                new_timestamp = decode_epoch_milliseconds(timestamp)

            # Epoch seconds (10 digits)
            elif 1262304000 <= timestamp <= 1893456000:  # 2010 <= ts <= 2030
                new_timestamp = decode_epoch_seconds(timestamp)

            # Mac Absolute Time (9 digits)
            elif 441763200 <= timestamp <= 915148800:  # 2015 <= ts <= 2030
                new_timestamp = decode_mac_absolute_time(timestamp)

        elif matches_float:
            timestamp = float(node.value)

            # Epoch seconds (10 digits)
            if 1420070400.0 <= timestamp <= 1893456000.0:  # 2015 <= ts <= 2030
                new_timestamp = decode_epoch_seconds(timestamp)

            # Mac Absolute Time (9 digits)
            elif 441763200.0 <= timestamp <= 915148800.0:  # 2015 <= ts <= 2030
                new_timestamp = decode_mac_absolute_time(timestamp)

        elif matches_hex:
            timestamp = node.value.replace(':', '')

            # Epoch hex seconds (8 hex chars)
            if 1420070400 <= int(timestamp, 16) <= 1893456000:  # 2015 <= ts <= 2030
                new_timestamp = decode_epoch_hex(timestamp)

            # Windows FileTime hex (16 hex digits)
            elif 130645440000000000 <= int(timestamp, 16) <= 135379296000000000:  # 2015 <= ts <= 2030
                new_timestamp = decode_windows_filetime_hex(timestamp)

    if new_timestamp != (None, 'unknown'):
        unfurl.add_to_queue(
            data_type=new_timestamp['data_type'], key=None, value=new_timestamp['timestamp_value'],
            hover=f'Converted as {new_timestamp["display_type"]}', parent_id=node.node_id,
            incoming_edge_config=timestamp_edge)
