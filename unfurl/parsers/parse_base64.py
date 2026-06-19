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

b64_edge = {
    'color': {
        'color': '#2C63FF'
    },
    'title': 'Base64 Parsing Functions',
    'label': 'b64'
}


def run(unfurl, node):

    if not isinstance(node.value, str):
        return False

    # If a node is explicitly labeled as base64, decode it directly and skip the
    # auto-detection heuristics (length/regex filters and the printable-only gate).
    if node.data_type == 'base64':
        stripped = node.value.rstrip('=')
        if len(stripped) % 4 == 1:
            return
        padded = stripped + ('=' * (-len(stripped) % 4))
        try:
            if '-' in node.value or '_' in node.value:
                decoded = base64.urlsafe_b64decode(padded)
            else:
                decoded = base64.b64decode(padded, validate=True)
        except (binascii.Error, ValueError):
            return
        if utils.is_printable_ascii(decoded):
            unfurl.add_to_queue(data_type='string', key=None, value=decoded.decode('ascii'),
                                parent_id=node.node_id, incoming_edge_config=b64_edge)
        elif decoded:
            unfurl.add_to_queue(data_type='bytes', key=None, value=decoded,
                                parent_id=node.node_id, incoming_edge_config=b64_edge)
        return

    if len(node.value) % 4 == 1:
        # A valid b64 string will not be this length
        return False

    if node.data_type == 'url.query.pair' and node.key == 'dns':
        return False

    urlsafe_b64_m = utils.urlsafe_b64_re.fullmatch(node.value)
    standard_b64_m = utils.standard_b64_re.fullmatch(node.value)
    long_int_m = utils.long_int_re.fullmatch(node.value)
    all_letters_m = utils.letters_re.fullmatch(node.value)

    # Long integers and normal words pass the b64 regex, but we don't want those here.
    # It's technically valid base64, but to reduce false positives, we're filtering them out.
    if long_int_m or all_letters_m:
        return

    decoded = None
    padded_value = unfurl.add_b64_padding(node.value)
    if not padded_value:
        return

    if urlsafe_b64_m:
        decoded = base64.urlsafe_b64decode(padded_value)
    elif standard_b64_m:
        decoded = base64.b64decode(padded_value)

    # Require printable output. This limits the plugin to ASCII strings that were
    # base64-encoded; a wrong guess almost always decodes to control-character
    # bytes (which a plain ASCII decode would still accept). It also keeps base64
    # from claiming base32 values that decode to garbage. Other things can be
    # base64-encoded (gzip, protobufs), but those are handled by their own parsers.
    if not utils.is_printable_ascii(decoded):
        return

    unfurl.add_to_queue(data_type='string', key=None, value=decoded.decode('ascii'),
                        parent_id=node.node_id, incoming_edge_config=b64_edge)
