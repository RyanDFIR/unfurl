# Copyright 2026 Ryan Benson
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

import re
import time

timeflake_edge = {
    'color': {
        'color': 'orange'
    },
    'title': 'Timeflake Parsing Functions',
    'label': 'TF'
}

# A Timeflake is 128 bits: a 48-bit Unix timestamp in milliseconds, then 80 random bits. It is
# written as 32 hex characters, 22 base62 characters, or in dashed UUID form. A ULID converted
# to a UUID has the same bits, so the two cannot be told apart in the hex and UUID forms.
#
# Ref: https://github.com/anthonynsimon/timeflake
#
# There are no version or marker bits, so the only check available is whether the first 48 bits
# are a plausible time. The window opens at Timeflake's first release and closes a year ahead.
# A random 128-bit value lands in a seven-year window about 0.08% of the time in hex form; a
# random 22-character alphanumeric string does about 0.01% of the time.
TIMESTAMP_MIN_MS = 1577836800000  # 2020-01-01
RANDOM_BITS = 80
BASE62_ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
BASE62_VALUES = {char: index for index, char in enumerate(BASE62_ALPHABET)}

hex_re = re.compile(r'[0-9A-F]{32}', re.IGNORECASE)
dashed_re = re.compile(r'[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}', re.IGNORECASE)
base62_re = re.compile(r'0[0-9A-Za-z]{21}')

LAYOUT_HOVER = (
    'A Timeflake is a 128-bit identifier: a 48-bit Unix timestamp in milliseconds followed by 80 random bits. '
    '<a href="https://github.com/anthonynsimon/timeflake" target="_blank">[ref]</a>')

CAVEAT_HOVER = (
    '<br><br>Timeflakes have no version or marker bits. Unfurl recognized this one only by its length and '
    'because its first 48 bits are a plausible time, so an unrelated value of the same shape '
    'can match by chance.')


def timestamp_is_plausible(milliseconds):
    return TIMESTAMP_MIN_MS <= milliseconds < (time.time() + 365 * 86400) * 1000


def has_rfc_uuid_bits(hex_id):
    """True if the version and variant positions hold values an RFC 9562 UUID (v1-v8) would have."""
    return hex_id[12] in '12345678' and hex_id[16] in '89ab'


def has_timeflake_layout(hex_id):
    """True if 32 hex characters start with a plausible time and are not marked as an RFC UUID."""
    return not has_rfc_uuid_bits(hex_id) and timestamp_is_plausible(int(hex_id[:12], 16))


def decode_base62(value):
    number = 0
    for char in value:
        number = number * 62 + BASE62_VALUES[char]
    return number


def to_hex(value):
    """The 32 lowercase hex characters of a value in any Timeflake form, or None if it is not one."""
    if hex_re.fullmatch(value):
        return value.lower()

    if dashed_re.fullmatch(value):
        return value.replace('-', '').lower()

    # Real base62 Timeflakes mix cases: 80 random bits almost never encode to digits and one
    # case only. Requiring both drops the all-digit and lowercase file names and counters that
    # are the usual 22-character lookalikes.
    if base62_re.fullmatch(value) and not value.isupper() and not value.islower() and not value.isdigit():
        number = decode_base62(value)
        if number < 2 ** 128:
            return f'{number:032x}'

    return None


def claims_uuid(unfurl, node):
    """True if this parser decodes the given 'uuid' node (so parse_uuid can skip its generic notes).

    parse_uuid picks up anything shaped like a UUID with 1-8 in the version position. If the
    variant position then rules out an RFC UUID and the value starts with a plausible time,
    it is read as a Timeflake (or ULID) in UUID form instead.
    """
    hex_id = str(node.value).lower()
    return bool(hex_re.fullmatch(hex_id)) and has_timeflake_layout(hex_id)


def add_parts(unfurl, node, hex_id):
    milliseconds = int(hex_id[:12], 16)
    unfurl.add_to_queue(
        data_type='epoch-milliseconds', key=None, value=milliseconds, label=f'Timestamp: {milliseconds}',
        hover='The first 48 bits are a Unix timestamp in milliseconds',
        parent_id=node.node_id, incoming_edge_config=timeflake_edge)

    random_hex = hex_id[12:]
    unfurl.add_to_queue(
        data_type='descriptor', key=None, value=random_hex, label=f'Random: {random_hex}',
        hover='The last 80 bits are random',
        parent_id=node.node_id, incoming_edge_config=timeflake_edge)


def run(unfurl, node):
    if node.data_type == 'timeflake':
        add_parts(unfurl, node, to_hex(node.value))
        return

    if node.data_type == 'uuid':
        if not claims_uuid(unfurl, node):
            return

        hex_id = str(node.value).lower()
        unfurl.add_to_queue(
            data_type='uuid-parsed', key=None, value=hex_id,
            label='Not a standard UUID; matches a Timeflake (or ULID) in UUID form',
            hover='The variant bits rule out a standard (RFC 9562) UUID, and the first 48 bits are a plausible '
                  'time. That matches a Timeflake, or a ULID converted to a UUID; both are a 48-bit Unix '
                  'timestamp in milliseconds followed by 80 random bits. '
                  '<a href="https://github.com/anthonynsimon/timeflake" target="_blank">[ref]</a>'
                  '<br><br>Neither format has marker bits, so an unrelated value can match by chance.',
            parent_id=node.node_id, incoming_edge_config=timeflake_edge)
        add_parts(unfurl, node, hex_id)
        return

    # A whole path or fragment that is only an ID also has a child (the path segment or fragment
    # anchor) with the same value; only the child is matched.
    if node.data_type in ('url.path', 'url.fragment') or node.data_type.startswith(('uuid', 'hash')):
        return

    if not isinstance(node.value, str):
        return

    hex_id = to_hex(node.value)
    if not hex_id or not has_timeflake_layout(hex_id):
        return

    # A UUID-shaped value with 1-8 in the version position gets a 'uuid' node from parse_uuid,
    # and is handled there (above) rather than added a second time here.
    if hex_id[12] in '12345678' and not base62_re.fullmatch(node.value):
        return

    hover = LAYOUT_HOVER
    if dashed_re.fullmatch(node.value):
        hover += ' A ULID converted to a UUID has the same layout.'
    elif hex_re.fullmatch(node.value):
        hover += ' A ULID written as hex has the same layout.'

    unfurl.add_to_queue(
        data_type='timeflake', key=None, value=node.value, label=f'Timeflake: {node.value}',
        hover=hover + CAVEAT_HOVER,
        parent_id=node.node_id, incoming_edge_config=timeflake_edge,
        extra_options={'widthConstraint': {'maximum': 300}})
