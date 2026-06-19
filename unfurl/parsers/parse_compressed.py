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
import re
import zlib
from unfurl import utils

zip_edge = {
    'color': {
        'color': '#2C63FF'
    },
    'title': 'Compression-related Parsing Functions',
    'label': 'zip'
}

b64_zip_edge = {
    'color': {
        'color': '#2C63FF'
    },
    'title': 'Compression-related Parsing Functions',
    'label': 'b64+zip'
}

b32_zip_edge = {
    'color': {
        'color': '#2C63FF'
    },
    'title': 'Compression-related Parsing Functions',
    'label': 'b32+zip'
}


def _queue_inflated(unfurl, node, inflated_bytes, edge, hover):
    """Add a node for decompressed bytes: a string if it's printable ASCII that
    looks like URL-ish data, otherwise the raw bytes for a downstream parser."""
    try:
        inflated_str = inflated_bytes.decode('ascii', errors='strict')
        if re.fullmatch(r'[\w=&%\.-]+', inflated_str):
            unfurl.add_to_queue(
                data_type='string', key=None, value=inflated_str,
                parent_id=node.node_id, hover=hover, incoming_edge_config=edge)
            return
    except UnicodeDecodeError:
        # If we couldn't decode the inflated bytes as ASCII, that's ok; we'll
        # just show the raw inflated bytes below.
        pass

    unfurl.add_to_queue(
        data_type='bytes', key=None, value=inflated_bytes, parent_id=node.node_id,
        hover=hover, incoming_edge_config=edge)


def run(unfurl, node):

    if not isinstance(node.value, str):
        return False

    if node.data_type == 'zlib':
        try:
            inflated_str = utils.safe_decompress(node.value)
        except (zlib.error, ValueError):
            return
        unfurl.add_to_queue(
            data_type='zlib-inflate', key=None, value=inflated_str,
            hover='This data was inflated using zlib',
            parent_id=node.node_id, incoming_edge_config=zip_edge)
        return

    if node.data_type in ('url.scheme', 'url.host', 'url.domain', 'url.tld'):
        return

    # Collect candidate decodings to try inflating. base64 is the long-standing
    # case (often used before compression); base32 is also tried so base32-encoded
    # compressed payloads inflate too. Initially the base64 decoding was in
    # parse_base64.py, but the intermediary (decoded-but-still-compressed) node was
    # not useful clutter, so the decode happens here and we only emit on success.
    attempts = []

    # base64 candidate. A valid b64 string is never length % 4 == 1, and long
    # integers pass the b64 regex but aren't what we want here.
    if len(node.value) % 4 != 1 and not utils.long_int_re.fullmatch(node.value):
        padded_value = unfurl.add_b64_padding(node.value)
        if padded_value:
            decoded = None
            if utils.urlsafe_b64_re.fullmatch(node.value):
                decoded = base64.urlsafe_b64decode(padded_value)
            elif utils.standard_b64_re.fullmatch(node.value):
                decoded = base64.b64decode(padded_value)
            if decoded:
                attempts.append((decoded, b64_zip_edge,
                                 'This data was base64-decoded, then zlib inflated'))

    # base32 candidate.
    b32_decoded = utils.try_base32_decode(node.value)
    if b32_decoded:
        attempts.append((b32_decoded, b32_zip_edge,
                         'This data was base32-decoded, then zlib inflated'))

    for decoded, edge, hover in attempts:
        try:
            inflated_bytes = utils.safe_decompress(decoded)
        except (zlib.error, ValueError):
            # Can't inflate it (or it exceeds the size limit); try the next candidate.
            continue
        _queue_inflated(unfurl, node, inflated_bytes, edge, hover)
        return
