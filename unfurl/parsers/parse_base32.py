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

import base64
import binascii
from unfurl import utils

b32_edge = {
    'color': {
        'color': '#2C63FF'
    },
    'title': 'Base32 Parsing Functions',
    'label': 'b32'
}


def run(unfurl, node):

    if not isinstance(node.value, str):
        return False

    # If a node is explicitly labeled as base32, decode it directly and skip the
    # auto-detection heuristics (all-letters filter, minimum length, printable gate).
    if node.data_type == 'base32':
        stripped = node.value.rstrip('=')
        try:
            decoded = base64.b32decode(stripped + ('=' * (-len(stripped) % 8)))
        except (binascii.Error, ValueError):
            return
        if utils.is_printable_ascii(decoded):
            unfurl.add_to_queue(data_type='string', key=None, value=decoded.decode('ascii'),
                                parent_id=node.node_id, incoming_edge_config=b32_edge)
        elif decoded:
            unfurl.add_to_queue(data_type='bytes', key=None, value=decoded,
                                parent_id=node.node_id, incoming_edge_config=b32_edge)
        return

    # Base32 uses the uppercase alphabet A-Z and digits 2-7, optionally
    # padded with '='. fullmatch ensures the whole value is base32.
    if not utils.base32_re.fullmatch(node.value):
        return

    # All-letter values are far more likely to be plain words/acronyms than
    # base32. It's technically valid base32, but we filter to reduce noise.
    if utils.letters_re.fullmatch(node.value.rstrip('=')):
        return

    decoded = utils.try_base32_decode(node.value)

    # Require printable output. A wrong guess almost always decodes to
    # control-character bytes, which a strict ASCII decode would still accept.
    # (is_printable_ascii also returns False for None/empty, covering a failed
    # decode.) Base32 (like base64) intentionally doesn't emit non-printable bytes
    # here; binary chains (e.g. base32+zlib, base32+protobuf) are handled by the
    # downstream parsers, which re-decode from the source string.
    if not utils.is_printable_ascii(decoded):
        return

    unfurl.add_to_queue(data_type='string', key=None, value=decoded.decode('ascii'),
                        parent_id=node.node_id, incoming_edge_config=b32_edge)
