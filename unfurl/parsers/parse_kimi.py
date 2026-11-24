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

from unfurl import utils
from unfurl.parsers.parse_chatgpt import path_segment_before

kimi_edge = {
    'color': {
        'color': '#1783ff'
    },
    'title': 'Kimi Parsing Functions',
    'label': 'K'
}

KIMI_DOMAINS = ('kimi.com', 'kimi.moonshot.cn')

# Kimi (Moonshot AI) share links, /share/{id} (also /share/en/{id} and /share/zh/{id}), use
# two ID formats, worked out from every share URL in the Wayback Machine (2026-11-02):
#
# UUIDv8 (from 2025-09-25), e.g. 19a6cdb5-fe52-83ce-8000-00009fe6eafd:
#   hex[0:11]   44-bit Unix time, milliseconds (1,044 of 1,044 before first capture)
#   hex[11]     always '2'
#   hex[12]     '8' (version)
#   hex[13:16]  12 bits, unknown (random or a sequence within the millisecond)
#   hex[16:24]  always '80000000' (RFC variant, then zeros)
#   hex[24:32]  32 random bits
#
# xid (2024-03 to 2025-12), 20 lowercase base32hex chars (github.com/rs/xid): 4 bytes of Unix
# seconds, 3 of machine ID, 2 of process ID, 3 of counter, then 4 zero padding bits
# (346 of 346 before first capture).

UUID_FLOOR_MS = utils.create_epoch_seconds_timestamp('2025-09-01T00:00:00') * 1000
XID_FLOOR = utils.create_epoch_seconds_timestamp('2023-10-01T00:00:00')  # Kimi launched in October 2023
BASE32HEX = '0123456789abcdefghijklmnopqrstuv'

xid_re = re.compile(r'[0-9a-v]{20}')


def under_kimi_domain(unfurl, node):
    return any(unfurl.preceding_domain_matches(node, d) for d in KIMI_DOMAINS)


def is_share_segment(unfurl, segment_node):
    """True if this url.path.segment is the ID in /share/{id}, /share/en/{id} or /share/zh/{id}."""
    before = path_segment_before(unfurl, segment_node)
    if before == 'share':
        return True
    return before in ('en', 'zh') and path_segment_before(unfurl, segment_node, 2) == 'share'


def has_kimi_layout(hex_id):
    return (len(hex_id) == 32 and hex_id[11] == '2' and hex_id[12] == '8'
            and hex_id[16:24] == '80000000')


def in_share_path(unfurl, node):
    """True if a 'uuid' node came from the ID segment of a Kimi share URL."""
    if not under_kimi_domain(unfurl, node):
        return False
    parents = unfurl.get_predecessor_node(node)
    return bool(parents) and parents[0].data_type == 'url.path.segment' and is_share_segment(unfurl, parents[0])


def claims_uuid(unfurl, node):
    """True if this parser decodes the given 'uuid' node (so parse_uuid can skip its generic notes)."""
    return has_kimi_layout(str(node.value).lower()) and in_share_path(unfurl, node)


def add_descriptor(unfurl, node, label, hover, value=None):
    unfurl.add_to_queue(
        data_type='descriptor', key=None, value=label if value is None else value, label=label, hover=hover,
        parent_id=node.node_id, incoming_edge_config=kimi_edge)


def add_field(unfurl, node, label, hover, value):
    # Typed so other parsers (hash, protobuf, timestamp) don't re-decode an ID's raw pieces,
    # such as reading the random tail 6205d501 as a hex timestamp
    unfurl.add_to_queue(
        data_type='kimi.field', key=None, value=value, label=label, hover=hover,
        parent_id=node.node_id, incoming_edge_config=kimi_edge)


def decode_uuid(unfurl, node, hex_id):
    milliseconds = int(hex_id[:11], 16)
    unfurl.add_to_queue(
        data_type='uuid-parsed', key=None, value=hex_id, label='Kimi share ID: UUIDv8 with an embedded timestamp',
        hover='Kimi share links since September 2025 use UUIDv8s that start with a Unix time in milliseconds. '
              'The time is most likely when the share link was created, which can be later than the conversation.',
        parent_id=node.node_id, incoming_edge_config=kimi_edge)
    unfurl.add_to_queue(
        data_type='epoch-milliseconds', key=None, value=milliseconds, label=f'Time generated: {milliseconds}',
        hover='The first 44 bits (11 hex characters) are a Unix time in milliseconds. None of 1,044 archived '
              'share IDs had a time later than its first capture (the closest was 13.5 seconds before).',
        parent_id=node.node_id, incoming_edge_config=kimi_edge)

    if milliseconds < UUID_FLOOR_MS:
        add_descriptor(unfurl, node, 'Timestamp predates this ID format',
                       'Kimi share IDs in this format first appear on 2025-09-25, so this time is not plausible. '
                       'Treat it with caution.')
    elif milliseconds > utils.create_epoch_seconds_timestamp(days_ahead=1) * 1000:
        add_descriptor(unfurl, node, 'Timestamp is in the future',
                       'This time is later than now, so it cannot be when the ID was created. The ID may be edited '
                       'or fabricated.')

    add_field(unfurl, node, f'Unknown: {hex_id[13:16]}',
              'The 12 bits after the version 8 take many different values (933 in 1,044 IDs). They may be '
              'random or a sequence number within the millisecond. The character before the version is '
              'always 2, and the next 8 characters are always 80000000.', hex_id[13:16])
    add_field(unfurl, node, f'Random: {hex_id[24:]}', 'The last 32 bits are random.', hex_id[24:])


def decode_xid(value):
    """Return (seconds, machine, process, counter) for a valid xid, or None."""
    number = 0
    for char in value:
        number = number * 32 + BASE32HEX.index(char)
    if number & 0xf:
        return None  # xid's 4 padding bits are always zero
    raw = (number >> 4).to_bytes(12, 'big')
    seconds = int.from_bytes(raw[0:4], 'big')
    if not XID_FLOOR <= seconds <= utils.create_epoch_seconds_timestamp(days_ahead=1):
        return None
    return seconds, raw[4:7].hex(), int.from_bytes(raw[7:9], 'big'), int.from_bytes(raw[9:12], 'big')


def parse_share_segment(unfurl, node):
    value = str(node.value)
    if xid_re.fullmatch(value):
        decoded = decode_xid(value)
        if not decoded:
            return
        seconds, machine, process, counter = decoded
        add_descriptor(unfurl, node, 'Kimi share ID (xid)',
                       'Kimi share links from 2024 to late 2025 use xid IDs: 20 base32hex characters holding a Unix '
                       'time in seconds, a machine ID, a process ID and a counter. The time is most likely when '
                       'the share link was created. None of 346 archived share IDs had a time later than its first '
                       'capture.')
        unfurl.add_to_queue(
            data_type='epoch-seconds', key=None, value=seconds, label=f'Time generated: {seconds}',
            hover='The first 4 bytes of an xid are a Unix time in seconds.',
            parent_id=node.node_id, incoming_edge_config=kimi_edge)
        add_field(unfurl, node, f'Machine ID: {machine}',
                  'Bytes 5-7 of an xid identify the server that made it.', machine)
        add_field(unfurl, node, f'Process ID: {process}',
                  'Bytes 8-9 of an xid are the ID of the process that made it.', process)
        add_field(unfurl, node, f'Counter: {counter}',
                  'The last 3 bytes of an xid are a per-process counter.', counter)
        return

    if re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', value, re.IGNORECASE):
        add_descriptor(unfurl, node, 'Kimi share ID',
                       'Identifies a shared Kimi (Moonshot AI) conversation link.')


def run(unfurl, node):
    if node.data_type == 'uuid':
        hex_id = str(node.value).lower()
        if has_kimi_layout(hex_id) and in_share_path(unfurl, node):
            decode_uuid(unfurl, node, hex_id)
        return

    if node.data_type == 'url.path.segment' and under_kimi_domain(unfurl, node) and is_share_segment(unfurl, node):
        parse_share_segment(unfurl, node)
