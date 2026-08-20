# Copyright 2025 Ryan Benson
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
from typing import Literal, Union
import re
import requests

import unfurl
import logging
log = logging.getLogger(__name__)

bluesky_edge = {
    'color': {
        'color': '#1185fe'
    },
    'title': 'Bluesky TID',
    'label': '🦋'
}

atproto_edge = {
    'color': {
        'color': '#3b82f6'
    },
    'title': 'ATProtocol',
    'label': '@atproto'
}

tid_re = re.compile(r'[2-7a-z]{13}')

# Create a mapping from "base32-sortable" alphabet to standard base32 alphabet
BASE32_SORTABLE_ALPHABET = "234567abcdefghijklmnopqrstuvwxyz"
STANDARD_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
BASE32_SORTABLE_TRANS = str.maketrans(BASE32_SORTABLE_ALPHABET, STANDARD_ALPHABET)


def parse_bluesky_tid(unfurl: unfurl.core.Unfurl, node: unfurl.core.Unfurl.Node) -> None:
    # Ref: https://atproto.com/specs/record-key#record-key-type-tid
    assert tid_re.fullmatch(node.value), "Bluesky TID is not in the expected format (base32-sortable)"
    assert not ord(node.value[0]) & 0x40, "Bluesky TID high bit is set; it must be 0"

    # Translate the base32-sortable string to standard base32, then decode it to 8 raw bytes
    translated_str = node.value.translate(BASE32_SORTABLE_TRANS)
    decoded_bytes = base64.b32decode(translated_str+"===")

    # The first bit is 0, then the next 53 bits are the timestamp (microseconds since the UNIX epoch).
    # The last 10 are a random "clock identifier", so shift those out to get the timestamp.
    timestamp = int.from_bytes(decoded_bytes, byteorder="big") >> 9

    unfurl.add_to_queue(
        data_type='epoch-microseconds', key=None, value=timestamp, label=f'TID Timestamp: {timestamp}',
        hover='Bluesky uses <i>timestamp identifiers</i> ("TIDs") as a way to reference records, '
              'which contain an embedded timestamp.',
        parent_id=node.node_id, incoming_edge_config=bluesky_edge)


def resolve_bsky_handle_to_did(unfurl: unfurl.core.Unfurl, handle: str) -> str | None:
    if not unfurl.remote_lookups:
        return None
    r = requests.get(f'https://bsky.social/xrpc/com.atproto.identity.resolveHandle?handle={handle}', timeout=3)
    if r.status_code == 200 and r.content and r.json().get('did'):
        return r.json()['did']
    else:
        return None


def add_resolved_did_node(unfurl: unfurl.core.Unfurl, node: unfurl.core.Unfurl.Node, did: str) -> None:
    unfurl.add_to_queue(
        data_type='did.plc', key='did:plc', value=did.split(':', 2)[2],
        label=f'Bluesky handle resolves to {did}',
        # https://atproto.com/specs/did and https://github.com/did-method-plc/did-method-plc
        hover='Bluesky uses Decentralized identifiers ("DIDs") as persistent, long-term identifiers '
              'for every account.',
        parent_id=node.node_id, incoming_edge_config=bluesky_edge)


def get_did_plc_audit_log_values(
        unfurl: unfurl.core.Unfurl, did: str, record_index: int | None = None,
        field: str | None = None) -> Union[str, dict, Literal[False]]:
    if not unfurl.remote_lookups:
        return False
    r = requests.get(f'https://plc.directory/{did}/log/audit', timeout=3)
    if r.status_code == 200:
        if record_index is not None and field:
            return r.json()[record_index][field]
        else:
            return r.json()


def run(unfurl: unfurl.core.Unfurl, node: unfurl.core.Unfurl.Node) -> None:
    if not isinstance(node.value, str):
        return

    # We can use the plc.directory audit logs to find when a DID was created. We'll do this
    # on both nodes that were created by Unfurl from Bluesky handle lookups (which sets the
    # data_type to 'did.plc', or if we encounter a URL path segment or other node that looks
    # to be a did:plc string.
    if node.data_type == 'did.plc' or node.value.startswith('did:plc'):
        did_plc_value = node.value
        if node.data_type == 'did.plc':
            did_plc_value = f'did:plc:{node.value}'
        created = get_did_plc_audit_log_values(unfurl, did_plc_value, record_index=0, field='createdAt')
        if created and isinstance(created, str):
            unfurl.add_to_queue(
                data_type='timestamp.iso8601', key='createdAt', value=created, label=f'Created at {created}',
                hover='The audit log for DIDs on plc.directory contains "createdAt" timestamps.',
                parent_id=node.node_id, incoming_edge_config=bluesky_edge)

    # On bsky.app, handles have a predictable location in URLs. If a URL starts with https://bsky.app/profile,
    # the next URL path segment should be a Bluesky "handle" (or DID). We can resolve this handle to the backing
    # decentralized identifier (DID) using a Bluesky API. We can then do more lookups using that DID.
    if node.data_type == 'url.path.segment':
        preceding_domain = unfurl.find_preceding_domain(node)
        if preceding_domain in ['bsky.app']:
            if re.fullmatch(tid_re, node.value):
                parse_bluesky_tid(unfurl, node)
            elif node.key == 2 and unfurl.check_sibling_nodes(node, data_type='url.path.segment', key=1, value='profile'):
                did = resolve_bsky_handle_to_did(unfurl, node.value)
                if did and isinstance(did, str):
                    add_resolved_did_node(unfurl, node, did)

    # If it's the "root" node and in a format we recognize related to Bluesky, parse it.
    # This case covers someone parsing just an ID or handle, not a full URL.
    elif node.node_id == 1:
        if re.fullmatch(tid_re, node.value):
            parse_bluesky_tid(unfurl, node)
        elif node.value.endswith('.bsky.social'):
            did = resolve_bsky_handle_to_did(unfurl, node.value)
            if did and isinstance(did, str):
                add_resolved_did_node(unfurl, node, did)
