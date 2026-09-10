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

from unfurl import utils

import logging
log = logging.getLogger(__name__)

fernet_edge = {
    'color': {
        'color': '#0F9B8E'
    },
    'title': 'Fernet Token',
    'label': '🔐'
}

# A Fernet token is base64url of:
#
#     0x80 | 8-byte big-endian Unix seconds | 16-byte IV | ciphertext | 32-byte HMAC
#
# The timestamp sits outside the ciphertext so a recipient can enforce a TTL
# before spending time decrypting. It is covered by the HMAC, so it cannot be
# altered undetected, but it was never hidden: any Fernet token in a URL
# records when it was minted, readable without the key.
# ref: https://github.com/fernet/spec/blob/master/Spec.md
FERNET_VERSION = 0x80

# Version byte + timestamp + IV + HMAC. Everything but the ciphertext.
FERNET_OVERHEAD = 57

# The ciphertext is AES-128-CBC with PKCS7 padding, so it is always a whole
# number of blocks, and there is always at least one.
FERNET_BLOCK_SIZE = 16

# The Fernet spec was published in 2013; a token cannot predate it.
# (2013-01-01T00:00:00Z)
FERNET_EPOCH_START = 1356998400

# Bytes 0-8 are 0x80 followed by a timestamp whose top four bytes are zero for
# any date between 1970 and 2106, so the payload always starts
# 80 00 00 00 00 ..., which base64url always renders as this prefix.
FERNET_PREFIX = 'gAAAAA'

FERNET_SPEC_REF = '<a href="https://github.com/fernet/spec/blob/master/Spec.md" ' \
                  'target="_blank">[ref]</a>'


def _byte_length(hex_value):
    """Length in bytes of a '0x'-prefixed hex value emitted by this parser."""
    return (len(hex_value) - 2) // 2


def describe_iv(value):
    return (f'Initialization vector ({_byte_length(value)} bytes) for the '
            f'AES-128-CBC encryption'), None


def describe_ciphertext(value):
    length = _byte_length(value)
    return (f'Encrypted contents: {length} bytes, '
            f'{length // FERNET_BLOCK_SIZE} AES blocks'), \
        'Reading this requires the key held by whoever issued the token. The size is ' \
        'still informative, as it bounds how much data the token can carry'


def describe_signature(value):
    return f'HMAC-SHA256 ({_byte_length(value)} bytes) over every preceding byte', \
        'The issuer verifies this with a secret key to detect tampering. It covers the ' \
        'version, timestamp, IV and ciphertext, so none of them can be altered without ' \
        'invalidating the token'


# Each part this parser splits out gets its meaning added underneath it on a
# later pass, once the node exists, rather than folded into its label. That
# keeps the node itself showing the bytes it actually holds.
fernet_parts = {
    'fernet.iv': describe_iv,
    'fernet.ciphertext': describe_ciphertext,
    'fernet.signature': describe_signature,
}


def decode_fernet_token(value, earliest, latest):
    """Try to read value as a Fernet token.

    Returns (payload, rewrite) where payload is the decoded bytes and rewrite
    describes any change that had to be made to the input to decode it (None
    if it decoded as-is). The caller splits that rewrite out as its own node so
    the change stays visible rather than being applied silently.
    """
    readings = [(value, None)]

    # OpenAI's ChatGPT Ads click IDs (oppref and olref) carry a trailing 'w'
    # where a canonical Fernet token has its '=' padding, and one 'w' stands in
    # for however many '=' there were. Only try that reading if the value does
    # not already decode cleanly, since a token whose length needs no padding
    # can legitimately end in 'w'.
    if value.endswith('w'):
        readings.append((value[:-1], "trailing 'w' read as '=' padding"))

    for candidate, rewrite in readings:
        payload = utils.try_urlsafe_b64_decode(candidate)
        if not payload or len(payload) <= FERNET_OVERHEAD:
            continue

        if payload[0] != FERNET_VERSION:
            continue

        ciphertext_length = len(payload) - FERNET_OVERHEAD
        if ciphertext_length % FERNET_BLOCK_SIZE:
            continue

        # The timestamp is the strongest false-positive gate. Other formats do
        # begin with these bytes; what they do not do is carry a plausible
        # date in them.
        if not earliest <= int.from_bytes(payload[1:9], 'big') < latest:
            continue

        return payload, rewrite

    return None, None


def split_token(unfurl, node, payload):
    """Split a decoded Fernet payload into its parts, beneath node."""

    unfurl.add_to_queue(
        data_type='fernet.version', key='Version', value=f'0x{payload[0]:02x}',
        hover='Byte 0 of the token, identifying its version. <b>0x80</b> is Fernet '
              f'version 1, the only version ever defined. {FERNET_SPEC_REF}',
        parent_id=node.node_id, incoming_edge_config=fernet_edge)

    # Queued as epoch-seconds so the timestamp parser converts it to a date,
    # the same way the JWT parser hands off its "iat" claim.
    unfurl.add_to_queue(
        data_type='epoch-seconds', key='Timestamp', value=int.from_bytes(payload[1:9], 'big'),
        hover='Bytes 1-8, a big-endian integer, holding the time the token was created. It '
              'sits <b>outside</b> the encrypted section so a recipient can reject an '
              'expired token without decrypting it, which is why it can be read without the '
              'key. The signature covers it, so it cannot be altered undetected',
        parent_id=node.node_id, incoming_edge_config=fernet_edge)

    # The remaining three are opaque bytes, rendered as 0x-prefixed hex both to
    # mark them as raw and to keep other parsers from misreading them: 64 bare
    # hex characters look like a SHA-256 hash, and 32 with a plausible version
    # nibble look like a UUID, which a random IV or signature sometimes is by
    # chance.
    unfurl.add_to_queue(
        data_type='fernet.iv', key='IV', value=f'0x{payload[9:25].hex()}',
        hover='Bytes 9-24 of the token',
        parent_id=node.node_id, incoming_edge_config=fernet_edge)

    unfurl.add_to_queue(
        data_type='fernet.ciphertext', key='Ciphertext', value=f'0x{payload[25:-32].hex()}',
        hover='Everything between the IV and the trailing signature',
        parent_id=node.node_id, incoming_edge_config=fernet_edge)

    unfurl.add_to_queue(
        data_type='fernet.signature', key='Signature', value=f'0x{payload[-32:].hex()}',
        hover='The last 32 bytes of the token',
        parent_id=node.node_id, incoming_edge_config=fernet_edge)


def run(unfurl, node):

    if not isinstance(node.value, str):
        return

    # A token that had to be re-padded before it would decode. Everything the
    # parser goes on to show was read out of this value rather than out of the
    # value as found, so the parts are split beneath it, and nothing else in
    # this parser needs to run on this pass.
    if node.data_type == 'fernet.normalized':
        payload, _ = decode_fernet_token(
            node.value, FERNET_EPOCH_START,
            utils.create_epoch_seconds_timestamp(days_ahead=365))
        if payload:
            split_token(unfurl, node, payload)
        return

    # A part split out of a token earlier, so say what it means. Doing it here
    # rather than at creation keeps the part's own node showing its raw value.
    if node.data_type in fernet_parts:
        description, hover = fernet_parts[node.data_type](node.value)
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value=description, hover=hover,
            parent_id=node.node_id, incoming_edge_config=fernet_edge)
        return

    # Don't re-run on anything else this parser produced.
    if node.data_type.startswith('fernet'):
        return

    # Cheap gate that keeps this parser off nearly every node it sees. Measured
    # against a large corpus of real-world URLs, only 70 values started with
    # this prefix, and 55 of those were Fernet tokens.
    if not node.value.startswith(FERNET_PREFIX):
        return

    payload, rewrite = decode_fernet_token(
        node.value, FERNET_EPOCH_START,
        utils.create_epoch_seconds_timestamp(days_ahead=365))
    if not payload:
        return

    node.hover = ('This looks like a <b>Fernet</b> token, a symmetric encrypt-then-MAC '
                  'container widely used by Python web applications. Its contents are '
                  'encrypted, but the time it was created is not, and can be read '
                  f'without the key. {FERNET_SPEC_REF}')

    if rewrite:
        # Hand off to the branch above: the parts belong under the re-padded
        # value they are actually read from, not under the value as found.
        unfurl.add_to_queue(
            data_type='fernet.normalized', key='Normalized Token', value=node.value[:-1] + '=',
            hover='The value as found does not decode. Its trailing "w" stands in for the '
                  '"=" padding, and with that restored it is a well-formed Fernet token. '
                  "OpenAI's <b>oppref</b> and <b>olref</b> ChatGPT ad click IDs are written "
                  'this way, with a single "w" for however many "=" characters the padding '
                  'needed. The token itself is unaltered; only the padding notation differs '
                  'from what the Fernet libraries emit',
            parent_id=node.node_id, incoming_edge_config=fernet_edge)
        return

    split_token(unfurl, node, payload)
