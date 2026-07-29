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
        if '-' in node.value or '_' in node.value:
            decoded = utils.try_urlsafe_b64_decode(node.value)
        else:
            decoded = utils.try_standard_b64_decode(node.value)
        if decoded is None:
            return
        if utils.is_printable_ascii(decoded):
            unfurl.add_to_queue(data_type='string', key=None, value=decoded.decode('ascii'),
                                parent_id=node.node_id, incoming_edge_config=b64_edge)
        elif decoded:
            unfurl.add_to_queue(data_type='bytes', key=None, value=decoded,
                                parent_id=node.node_id, incoming_edge_config=b64_edge)
        return

    if node.data_type == 'url.query.pair' and node.key == 'dns':
        return False

    # Long integers and normal words pass the b64 regex, but we don't want those here.
    # It's technically valid base64, but to reduce false positives, we're filtering them out.
    if utils.long_int_re.fullmatch(node.value) or utils.letters_re.fullmatch(node.value):
        return

    # Require a minimum encoded length of 8 as another false-positive gate; short
    # values are too likely to be something else that happens to decode.
    decoded = utils.try_urlsafe_b64_decode(node.value, min_length=8)
    if decoded is None:
        decoded = utils.try_standard_b64_decode(node.value, min_length=8)

    # Require printable output. This limits the plugin to ASCII strings that were
    # base64-encoded; a wrong guess almost always decodes to control-character
    # bytes (which a plain ASCII decode would still accept). It also keeps base64
    # from claiming base32 values that decode to garbage. Other things can be
    # base64-encoded (gzip, protobufs), but those are handled by their own parsers.
    if not utils.is_printable_ascii(decoded):
        return

    unfurl.add_to_queue(data_type='string', key=None, value=decoded.decode('ascii'),
                        parent_id=node.node_id, incoming_edge_config=b64_edge)
