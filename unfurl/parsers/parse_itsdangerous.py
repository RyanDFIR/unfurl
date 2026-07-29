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
import zlib
from unfurl import utils

import logging
log = logging.getLogger(__name__)

itsdangerous_edge = {
    'color': {
        'color': '#CC3333'
    },
    'title': 'itsdangerous Signed Token',
    'label': '🔏'
}

# itsdangerous versions before 2.0 stored timestamps as seconds since
# 2011-01-01 (the library's release year) rather than the Unix epoch.
ITSDANGEROUS_LEGACY_EPOCH = 1293840000

# Tokens from itsdangerous's URLSafeTimedSerializer (used by Flask and many
# other Python web apps for email verification links, password resets,
# session cookies, etc.) look similar to JWTs but have a different structure:
#   base64(payload) . base64(big-endian timestamp) . base64(HMAC signature)
# If the payload was zlib-compressed, the whole token gets a leading '.'.
# The timestamp segment is a minimal big-endian integer (4 bytes / 6 base64
# characters for current dates), which is what distinguishes these from JWTs
# (whose middle segment is a JSON payload, far longer than 8 characters).
itsdangerous_token_re = re.compile(
    r'(?P<compressed>\.)?'
    r'(?P<payload>[A-Za-z0-9_\-]{4,}={0,2})\.'
    r'(?P<timestamp>[A-Za-z0-9_\-]{4,8})\.'
    r'(?P<signature>[A-Za-z0-9_\-]{27,86}={0,2})')


def run(unfurl, node):

    if not isinstance(node.value, str):
        return

    # Don't re-run on the component nodes this parser creates.
    if node.data_type.startswith('itsdangerous'):
        return

    m = itsdangerous_token_re.fullmatch(node.value)
    if not m:
        return

    timestamp_bytes = utils.try_urlsafe_b64_decode(m['timestamp'])
    signature_bytes = utils.try_urlsafe_b64_decode(m['signature'])
    payload_bytes = utils.try_urlsafe_b64_decode(m['payload'])
    if not (timestamp_bytes and signature_bytes and payload_bytes):
        return

    # HMAC digests run from 16 bytes (MD5) to 64 (SHA-512); itsdangerous
    # defaults to SHA-1 (20 bytes), and SHA-256 (32) is also common.
    if not 16 <= len(signature_bytes) <= 64:
        return

    # The timestamp is the strongest false-positive gate: the decoded bytes,
    # read as a big-endian integer, must be a plausible signing time. Values
    # that don't fit either the modern (Unix epoch) or legacy (2011 epoch)
    # interpretation mean this isn't an itsdangerous token; bail out.
    timestamp_int = int.from_bytes(timestamp_bytes, 'big')
    plausible_range_start = ITSDANGEROUS_LEGACY_EPOCH
    plausible_range_end = utils.create_epoch_seconds_timestamp(days_ahead=365)
    legacy = False
    if plausible_range_start <= timestamp_int < plausible_range_end:
        epoch_seconds = timestamp_int
    elif plausible_range_start <= timestamp_int + ITSDANGEROUS_LEGACY_EPOCH < plausible_range_end:
        epoch_seconds = timestamp_int + ITSDANGEROUS_LEGACY_EPOCH
        legacy = True
    else:
        return

    if m['compressed']:
        try:
            payload_bytes = utils.safe_decompress(payload_bytes)
        except (zlib.error, ValueError):
            return

    node.hover = 'This looks like a signed token from the Python <b>itsdangerous</b> library ' \
                 '(used by Flask and other web frameworks for verification links, password ' \
                 'resets, and session cookies). ' \
                 '<a href="https://itsdangerous.palletsprojects.com/" target="_blank">[ref]</a>'

    payload_hover = 'itsdangerous tokens have three parts: the payload, a timestamp, and a ' \
                    'signature. The <b>payload</b> is the base64-encoded data that was signed'
    if m['compressed']:
        payload_hover += ', which was also zlib-compressed (indicated by the token\'s leading ".")'
        if utils.is_printable_ascii(payload_bytes):
            unfurl.add_to_queue(
                data_type='string', key='Payload', value=payload_bytes.decode('ascii'),
                hover=payload_hover, parent_id=node.node_id, incoming_edge_config=itsdangerous_edge)
        else:
            unfurl.add_to_queue(
                data_type='bytes', key='Payload', value=payload_bytes,
                hover=payload_hover, parent_id=node.node_id, incoming_edge_config=itsdangerous_edge)
    else:
        # Queue the still-encoded payload as an explicit base64 node; the base64
        # parser will decode it (bypassing its auto-detection heuristics) and
        # downstream parsers (JSON, etc.) can continue from there.
        unfurl.add_to_queue(
            data_type='base64', key='Payload', value=m['payload'],
            hover=payload_hover, parent_id=node.node_id, incoming_edge_config=itsdangerous_edge)

    timestamp_hover = 'itsdangerous tokens have three parts: the payload, a timestamp, and a ' \
                      'signature. The <b>timestamp</b> is when the token was signed, encoded ' \
                      'as a base64 big-endian integer'
    if legacy:
        timestamp_hover += '. This token stores it as seconds since 2011-01-01 ' \
                           '(itsdangerous versions before 2.0)'
    unfurl.add_to_queue(
        data_type='epoch-seconds', key='Timestamp', value=epoch_seconds,
        label=f'Signing Timestamp: {epoch_seconds}',
        hover=timestamp_hover, parent_id=node.node_id, incoming_edge_config=itsdangerous_edge)

    unfurl.add_to_queue(
        data_type='itsdangerous.signature', key='Signature', value=m['signature'],
        label=f'HMAC Signature ({len(signature_bytes)} bytes)',
        hover='itsdangerous tokens have three parts: the payload, a timestamp, and a '
              'signature. The <b>signature</b> is an HMAC of the payload and timestamp; '
              'the server verifies it with a secret key to detect tampering',
        parent_id=node.node_id, incoming_edge_config=itsdangerous_edge)
