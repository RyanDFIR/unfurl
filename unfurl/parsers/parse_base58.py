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

b58_edge = {
    'color': {
        'color': '#2C63FF'
    },
    'title': 'Base58 Parsing Functions',
    'label': 'b58'
}

# Bitcoin/IPFS base58 alphabet (no 0 O I l, no padding).
_B58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
_B58_INDEX = {char: index for index, char in enumerate(_B58_ALPHABET)}


def _b58_decode(value):
    """Decode a base58 string to bytes, or None if it has a non-alphabet character.

    Base58 has no stdlib decoder; this is the equivalent of base64.b32decode. The
    decode is big-integer based, and each leading '1' is a leading zero byte.
    """
    if not all(char in _B58_INDEX for char in value):
        return None
    number = 0
    for char in value:
        number = number * 58 + _B58_INDEX[char]
    decoded = number.to_bytes((number.bit_length() + 7) // 8, 'big') if number else b''
    return b'\x00' * (len(value) - len(value.lstrip('1'))) + decoded


def run(unfurl, node):

    if not isinstance(node.value, str):
        return False

    # If a node is explicitly labeled as base58, decode it directly and skip the
    # auto-detection heuristics (all-letters filter, minimum length, printable gate).
    # Base58 is most often used for binary data (crypto addresses, IPFS CIDs), so a
    # non-printable decode is surfaced as bytes for a downstream parser to use.
    if node.data_type == 'base58':
        decoded = _b58_decode(node.value)
        if not decoded:
            return
        if utils.is_printable_ascii(decoded):
            unfurl.add_to_queue(data_type='string', key=None, value=decoded.decode('ascii'),
                                parent_id=node.node_id, incoming_edge_config=b58_edge)
        else:
            unfurl.add_to_queue(data_type='bytes', key=None, value=decoded,
                                parent_id=node.node_id, incoming_edge_config=b58_edge)
        return

    # Base58 is case-sensitive alphanumerics minus 0 O I l, with no padding.
    if not utils.base58_re.fullmatch(node.value):
        return

    # All-letter values are far more likely to be plain words than base58. It's
    # technically valid base58, but we filter to reduce noise.
    if utils.letters_re.fullmatch(node.value):
        return

    decoded = _b58_decode(node.value)

    # Require printable output. Base58's alphabet matches almost any alphanumeric
    # string, so this gate is the main defense against false positives. Binary
    # base58 (addresses, CIDs) is dropped here; the explicit path above keeps it.
    if not utils.is_printable_ascii(decoded):
        return

    unfurl.add_to_queue(data_type='string', key=None, value=decoded.decode('ascii'),
                        parent_id=node.node_id, incoming_edge_config=b58_edge)
