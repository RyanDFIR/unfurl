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

import logging
log = logging.getLogger(__name__)

gmail_edge = {
    'color': {
        'color': '#ea4335'
    },
    'title': 'Gmail ID Parsing Functions',
    'label': '✉'
}

# Legacy Gmail message/thread IDs are 15-16 hex digits (16 digits starting Nov 2004).
legacy_id_re = re.compile(r'^[0-9a-fA-F]{15,16}$')

# New-style Gmail web tokens (2018+ interface) use a 40-character alphabet of
# upper- and lowercase consonants only. Observed tokens are 32 characters; the bound is a
# floor rather than an exact length in case shorter ones exist, but anything shorter than
# 32 is currently ignored.
new_token_re = re.compile(r'^[b-df-hj-np-tv-zB-DF-HJ-NP-TV-Z]{32,}$')

# Decoded form of a Gmail ID: thread or message, server-assigned (f) or client-assigned
# (a), followed by the decimal ID. Client-assigned IDs have an "r" prefix and are signed,
# so they can be negative (they are random 64-bit values, not timestamps).
gmail_id_re = re.compile(r'(?P<kind>thread|msg)-(?P<style>[af]):(?P<digits>r?-?\d{1,20})')

# One reference inside a decoded new-style token payload. Unlike the canonical form above,
# the payload names only the style and ID for a thread ("f:1834...") and adds a "msg-"
# keyword for a message ("msg-a:r-805..."); there is no "thread" keyword in the data.
token_ref_re = re.compile(r'(?:(?P<kind>msg)-)?(?P<style>[af]):(?P<digits>r?-?\d{1,20})')

base64_alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
reduced_alphabet = 'BCDFGHJKLMNPQRSTVWXZbcdfghjklmnpqrstvwxz'

# Gmail launched on 2004-04-01; treat embedded timestamps outside 2004-2035 as
# not plausible to keep false positives down.
min_reasonable_ms = 1080777600000  # 2004-04-01
max_reasonable_ms = 2051222400000  # 2035-01-01

metaspike_ref = (
    '<a href="https://www.metaspike.com/dates-gmail-message-id-thread-id-timestamps/" '
    'target="_blank">[ref: Metaspike]</a>')
arsenal_ref = (
    '<a href="https://github.com/ArsenalRecon/GmailURLDecoder" '
    'target="_blank">[ref: Arsenal Recon]</a>')


def decode_new_style_token(token):
    """Decode a new-style Gmail web token into its raw payload string.

    The token is a big integer written in a 40-character alphabet (consonants only);
    converting it to the standard base64 alphabet and base64-decoding the result yields
    the payload, e.g. "f:1834473457053461654". Based on research and implementation by
    Arsenal Recon (https://github.com/ArsenalRecon/GmailURLDecoder).

    The payload is returned exactly as decoded. Arsenal Recon's implementation prepends
    "thread-" when the decoded string lacks it, so the result reads like a Gmail API ID,
    but no observed token contains that keyword -- 17 view tokens decoded to "f:<id>" and
    2 compose tokens to "a:<id>+msg-a:<id>" forms. Adding it here would misreport what the
    URL actually held, and it also hid every reference after the first in a multi-draft
    compose token, since only the first got a keyword the ID regex could match.

    Returns None for anything that doesn't decode, including tokens containing
    characters outside the alphabet.
    """
    value = 0
    for char in token:
        position = reduced_alphabet.find(char)
        if position == -1:
            return None
        value = value * 40 + position

    b64_digits = []
    while value:
        b64_digits.append(base64_alphabet[value % 64])
        value //= 64
    b64_string = ''.join(reversed(b64_digits))

    try:
        padding = '=' * (-len(b64_string) % 4)
        decoded = base64.b64decode(b64_string + padding).decode('utf-8')
    except (ValueError, UnicodeDecodeError):
        return None

    return decoded


def parse_decoded_payload(decoded):
    """Split a decoded new-style token payload into canonical Gmail IDs.

    Observed payload shapes:
        f:1834473457053461654                            a thread (viewing a message)
        a:r-72...+msg-a:r-80...                          one draft: its thread and message
        a:r-21...+msg-a:r-45...,a:r-31...+msg-a:r-38...  two drafts, comma-separated

    A reference carrying no "msg-" keyword is the thread. The IDs returned use the
    canonical "thread-f:"/"msg-a:" notation that Gmail itself uses in print-view URLs and
    the API, rather than the compact form the token carries; callers surface the raw
    payload alongside so the transformation stays visible.

    Returns [] unless every reference parses. A payload that is only half understood means
    the format model is wrong, and quietly emitting the recognized half is exactly how a
    multi-draft compose token used to lose an ID.
    """
    gmail_ids = []
    for draft in decoded.split(','):
        for reference in draft.split('+'):
            reference_match = token_ref_re.fullmatch(reference)
            if not reference_match:
                return []
            kind = reference_match.group('kind') or 'thread'
            gmail_ids.append(
                f'{kind}-{reference_match.group("style")}:{reference_match.group("digits")}')
    return gmail_ids


def parse_gmail_token(unfurl, node, token, kind):
    """Recognize a Gmail URL token and start the chain that decodes it.

    Each conversion gets its own node rather than jumping from the URL straight to a
    timestamp, so that an examiner can see the hex value that was recognized, the decimal
    notation it converts to, and which bits of it the timestamp came from.
    """
    if legacy_id_re.fullmatch(token):
        # Only treat it as a Gmail ID if the embedded timestamp is plausible
        if not min_reasonable_ms <= (int(token, 16) >> 20) <= max_reasonable_ms:
            return
        unfurl.add_to_queue(
            data_type='gmail.id.hex', key=kind, value=token,
            label=f'Gmail {kind.capitalize()} ID (hex): {token}',
            hover=f'Gmail message and thread IDs are 64-bit values, written as {len(token)} hex '
                  f'digits in legacy-interface URLs and message headers. {metaspike_ref}',
            parent_id=node.node_id, incoming_edge_config=gmail_edge)

    elif new_token_re.fullmatch(token):
        decoded = decode_new_style_token(token)
        if not decoded:
            return
        if not parse_decoded_payload(decoded):
            log.debug(f'Gmail token "{token}" decoded to an unrecognized payload: "{decoded}"')
            return
        unfurl.add_to_queue(
            data_type='gmail.token.payload', key=None, value=decoded,
            label=f'Decoded token: {decoded}',
            hover=f'New-style Gmail URL tokens are an obfuscated (base conversion + base64) form '
                  f'of Gmail\'s internal IDs. This is the payload the token decodes to, shown '
                  f'exactly as decoded. {arsenal_ref}',
            parent_id=node.node_id, incoming_edge_config=gmail_edge)


def parse_hex_id(unfurl, node):
    """Split a legacy hex Gmail ID and convert it to the notation Gmail uses elsewhere.

    In hex the split needs no arithmetic: the last 5 digits are the low 20 bits, and
    everything before them is the arrival time in epoch milliseconds. The timestamp half is
    handed to parse_timestamp as "epoch-hex-milliseconds" rather than converted here.
    """
    hex_id = str(node.value)
    kind = str(node.key or 'thread')
    timestamp_hex, low_bits_hex = hex_id[:-5], hex_id[-5:]

    value = f'{kind}-f:{int(hex_id, 16)}'
    unfurl.add_to_queue(
        data_type='gmail.id', key=None, value=value, label=f'Gmail ID: {value}',
        hover=f'The same 64-bit value in decimal, which Gmail uses internally, in '
              f'print-view URLs, and in its API. {metaspike_ref}',
        parent_id=node.node_id, incoming_edge_config=gmail_edge)

    unfurl.add_to_queue(
        data_type='epoch-hex-milliseconds', key=None, value=timestamp_hex,
        label=f'{kind.capitalize()} Timestamp (hex, upper 44 bits): {timestamp_hex}',
        hover=f'Dropping the last 5 hex digits of a Gmail ID leaves the {kind}\'s creation '
              f'time as epoch milliseconds, still in hex. A thread\'s timestamp is that of '
              f'its first message. {metaspike_ref}',
        parent_id=node.node_id, incoming_edge_config=gmail_edge)

    unfurl.add_to_queue(
        data_type='descriptor', key=None, value=None,
        label=f'Low 20 bits: {low_bits_hex}',
        hover=f'The last 5 hex digits, which are not part of the timestamp. Their meaning is '
              f'not publicly documented. {metaspike_ref}',
        parent_id=node.node_id, incoming_edge_config=gmail_edge)


def parse_token_payload(unfurl, node):
    """Split a decoded token payload into the Gmail IDs it names.

    A compose token carries one thread and one message per open draft, so a single token
    can yield four or more IDs.
    """
    for value in parse_decoded_payload(str(node.value)):
        unfurl.add_to_queue(
            data_type='gmail.id', key=None, value=value, label=f'Gmail ID: {value}',
            hover=f'The payload names a thread by its style letter alone and prefixes a message '
                  f'with "msg-"; this is the same reference in the canonical notation Gmail uses '
                  f'in print-view URLs and its API. {arsenal_ref}',
            parent_id=node.node_id, incoming_edge_config=gmail_edge)


def parse_gmail_id(unfurl, node):
    """Parse a decoded Gmail ID ("thread-f:...", "msg-f:...", etc.) and add child nodes."""
    id_match = gmail_id_re.fullmatch(str(node.value))
    if not id_match:
        return

    kind = 'Thread' if id_match.group('kind') == 'thread' else 'Message'
    digits = id_match.group('digits')

    # The style letter, not the "r" prefix, is what says who assigned the ID.
    if id_match.group('style') == 'a':
        unfurl.add_to_queue(
            data_type='description', key=None, value=None,
            label=f'Client-assigned {kind} ID',
            hover=f'Gmail IDs with an "-a:" style are assigned by the client (e.g. drafts and '
                  f'sent messages) and do not embed a timestamp. {arsenal_ref}',
            parent_id=node.node_id, incoming_edge_config=gmail_edge)
        return

    # Server-assigned ("-f:") IDs carry a timestamp, but only the plain unsigned decimal form
    # can be read as one. An "r"-prefixed or negative "-f:" ID isn't a shape Gmail is known to
    # produce; the ID node still stands on its own, so just don't claim a timestamp for it.
    if not digits.isdigit():
        return

    # A hex ID was already split on its own node, where the split is just "drop the last 5
    # digits"; repeating it here in decimal would show the same timestamp twice.
    parent = unfurl.nodes.get(getattr(node, 'parent_id', None))
    if parent is not None and parent.data_type == 'gmail.id.hex':
        return

    # The 64-bit value splits in two: the upper 44 bits are the timestamp, the low 20 are not.
    # Both halves get a node, so the split is visible rather than implied by a bare result.
    gmail_id = int(digits)
    timestamp_ms = gmail_id >> 20
    low_bits = gmail_id & 0xFFFFF
    if not min_reasonable_ms <= timestamp_ms <= max_reasonable_ms:
        return

    unfurl.add_to_queue(
        data_type='epoch-milliseconds', key=None, value=timestamp_ms,
        label=f'{kind} Timestamp (upper 44 bits):\n{timestamp_ms}',
        hover=f'Dropping the low 20 bits of a server-assigned ("-f:") Gmail ID leaves the '
              f'{kind.lower()}\'s creation time as an epoch milliseconds timestamp (in hex). '
              f'A thread\'s timestamp is that of its first message. {metaspike_ref}',
        parent_id=node.node_id, incoming_edge_config=gmail_edge)

    unfurl.add_to_queue(
        data_type='descriptor', key=None, value=None,
        label=f'Low 20 bits: 0x{low_bits:05x}',
        hover=f'What remains of the 64-bit ID after the 44 timestamp bits. This part is not '
              f'time-based and its meaning is not publicly documented. {metaspike_ref}',
        parent_id=node.node_id, incoming_edge_config=gmail_edge)


def run(unfurl, node):
    # Each step of the decoding is its own node type, re-entering here as it is created.
    if node.data_type == 'gmail.id.hex':
        parse_hex_id(unfurl, node)
        return

    if node.data_type == 'gmail.token.payload':
        parse_token_payload(unfurl, node)
        return

    if node.data_type == 'gmail.id':
        parse_gmail_id(unfurl, node)
        return

    if not unfurl.preceding_domain_matches(node, 'mail.google.com'):
        return

    # Ex: https://mail.google.com/mail/u/0/#inbox/172ed79b0337c14f (legacy interface)
    # Ex: https://mail.google.com/mail/u/0/#inbox/FMfcgzQbffcMwhxlgVgQNtfsQngqqzMQ
    # Ex: https://mail.google.com/mail/u/0/#search/some+terms/172ed79b0337c14f
    if node.data_type == 'url.fragment.anchor':
        for segment in str(node.value).split('/'):
            # The token when viewing a message identifies the conversation thread
            parse_gmail_token(unfurl, node, segment, kind='thread')

    elif node.data_type == 'url.query.pair':
        # Ex: https://mail.google.com/mail/u/0/?ui=2&view=btop&th=172ed79b0337c14f
        if node.key == 'th':
            parse_gmail_token(unfurl, node, str(node.value), kind='thread')

        # Ex: #inbox?compose=DmwnWrRttPGlHpKcnZZbTLNKvhcrbHCwqSlPTGxRbGKmxxLtHfwWkVjkTRHTkfHbTFkQvvVwHKKFtHZQ
        # Legacy compose tokens can be a comma-separated list (multiple drafts open at once)
        elif node.key == 'compose':
            for token in str(node.value).split(','):
                if token != 'new':
                    parse_gmail_token(unfurl, node, token, kind='msg')

        # Ex: #inbox/<token>?projector=1 (attachment opened in the preview overlay)
        elif node.key == 'projector':
            unfurl.add_to_queue(
                data_type='descriptor', key=None, value=None,
                label='Attachment preview was open',
                hover='Gmail adds "projector=1" when an attachment is opened in the in-browser '
                      'preview overlay, so the URL records that an attachment on this message '
                      'was viewed.',
                parent_id=node.node_id, incoming_edge_config=gmail_edge)

        # Ex: ?view=pt&search=all&permmsgid=msg-f:1670936980932986545 (print view)
        elif node.key in ('permmsgid', 'permthid'):
            id_match = gmail_id_re.fullmatch(str(node.value))
            if id_match:
                unfurl.add_to_queue(
                    data_type='gmail.id', key=None, value=id_match.group(0),
                    label=f'Gmail ID: {id_match.group(0)}',
                    hover=f'Permanent Gmail message/thread IDs, as seen in print view URLs '
                          f'and the Gmail API. {metaspike_ref}',
                    parent_id=node.node_id, incoming_edge_config=gmail_edge)
