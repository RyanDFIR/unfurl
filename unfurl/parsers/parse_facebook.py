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
import html
import json
import logging
import re
import urllib.request

log = logging.getLogger(__name__)

# Modern Facebook Click IDs (fbclid) use a binary serialization format:
#   [2-char header][base64url-encoded payload][optional _aem_ suffix]
#
# Headers are two literal characters, not part of the base64. They match the
# app_id inside: Facebook app IDs (Comet web, Android, iPhone, Lite, Messenger)
# appear only under 'Iw', and Instagram app IDs only under 'PA'. The one
# exception is the old "WWW" app ID, which shows up under both.
#   'Iw' = clicked on Facebook
#   'PA' = clicked on Instagram
#
# The payload is a sequence of fields, each a 4-character ASCII name followed
# by a value whose type depends on the name (there is no length byte for the
# fixed-size types):
#   u32 timestamp  clck, tdcp, tdex, ... (seconds since FBCLID_EPOCH)
#   u64            adid (decimal; ad-related, but not the advertiser's ad ID)
#   u8             pdof
#   string         brid, afdk, fdid ([length byte][bytes])
#   map            extn, srtc ([len][key][len][value]... ended by 0x00)
# The fields end at a 0x01 byte, which starts a trailer of 44 or 46 bytes
# (0x01, then 0x1d/0x1e for 'Iw' or 0xa6/0xa7 for 'PA'; the second byte looks
# like a per-platform version, +1 when the trailer grew). The remaining bytes
# are uninterpreted. It has the same shape as a whole legacy fbclid, which
# decodes to 0x01 0x1d plus 42 uninterpreted bytes.
#
# Field names are reverse-engineered and not documented by Meta. Timestamp
# fields were identified by comparing values against urlscan.io, Wayback
# Machine, and Common Crawl capture times.
#
# Optional '_aem_' suffix: usually a 16-byte hash for Aggregated Event Measurement

# 2024-01-01 20:29:36 UTC. First estimated as the smallest (capture time - field
# value) across thousands of captured URLs, which gave 20:29:41; that's only an
# upper bound. Two timed clicks on facebook.com (click logged in the browser,
# clock checked against time.is) both decoded 4.75 s after the click with that
# value, so it was moved 5 s earlier to make clck match the click second.
# The click adds clck to the link's existing fbclid; nothing else changes.
FBCLID_EPOCH = 1704140976

# A whole input that looks like an fbclid on its own: a case-sensitive header,
# then base64url (the _aem_ suffix uses the same characters). Real ones are
# 60+ characters; the length floor keeps short words like "PAris" out.
BARE_FBCLID_RE = re.compile(r'(?:Iw|PA)[A-Za-z0-9_-]{40,}')

facebook_edge = {
    'color': {
        'color': '#1877F2'
    },
    'title': 'Facebook Click ID',
    'label': 'f'
}

# 4-byte big-endian timestamps, in seconds since FBCLID_EPOCH. Names also
# appear in uppercase (TDCP, OMEX, ...). When an fbclid has two, clck is
# usually 3 to 15 seconds earlier than the other.
TIMESTAMP_FIELDS = {
    'clck', 'tdcp', 'tdex', 'tdsv', 'tdsh', 'omcp', 'omex', 'ftsh', 'igrd',
    'aoex', 'aosb', 'sscp', 'bocl', 'igdl', 'ioex',
}
U32_FIELDS = {'tsaf'}
U64_FIELDS = {'adid', 'usrm'}
U8_FIELDS = {'pdof'}
STRING_FIELDS = {'brid', 'afdk', 'fdid'}
MAP_FIELDS = {'extn', 'srtc'}

MAP_HOVERS = {
    'extn': 'A map field: length-prefixed key/value strings, ended by a 0x00 byte. '
            'Usually holds a single <b>aem</b> entry.',
    'srtc': 'A map field: length-prefixed key/value strings, ended by a 0x00 byte. '
            'Usually holds the <b>app_id</b>, and occasionally <b>callsite</b>.',
}

KNOWN_FIELDS = {
    'brid': ('Browser ID', 'Probably a browser identifier (17 characters). The '
             'same <b>brid</b> shows up in fbclids clicked days or months apart, '
             'on unrelated sites, and from different parts of the Facebook '
             'website (it only appears with web App IDs, never the mobile apps). '
             'Two URLs sharing one were likely clicked in the same web browser, '
             'but its exact scope (browser profile, cookie, or account) is '
             'unknown. (Reverse-engineered, not documented by Meta.)'),
    'app_id': ('App ID', 'The Facebook App ID of the app the link was clicked '
               'in (inside the <b>srtc</b> field). Resolvable with the Graph API.'),
    'adid': ('Ad-related ID', 'An 8-byte number, present when the click came from an ad. '
             'It looks like a Facebook object ID (usually 18 digits starting with 120), but '
             'it does not match the ad ID advertisers put in their own URL parameters (like '
             'ad_id or utm_content), so it identifies something else; exactly what is '
             'unknown. (Reverse-engineered, not documented by Meta.)'),
    'aem': ('AEM Flags', 'A bitmask inside the <b>extn</b> field, written out in binary '
            '(0, 1, 10, 11, and 100 seen so far; no digit other than 0 or 1 has appeared). '
            'Nearly every fbclid with an <b>adid</b> has 0. What each bit means is unknown; '
            'possibly related to Aggregated Event Measurement.'),
    'pdof': ('pdof', 'A 1-byte value (1 to 5 seen so far). Meaning unknown.'),
    'afdk': ('afdk', 'A short string value. Meaning unknown.'),
    'fdid': ('fdid', 'A binary value (usually 22 bytes). Meaning unknown.'),
    'tsaf': ('tsaf', 'A 4-byte number with small values; not a timestamp. '
             'Meaning unknown.'),
    'usrm': ('usrm', 'An 8-byte number with small values. Meaning unknown.'),
}

# The two-character header names the Meta app the fbclid was generated in
PLATFORMS = {'iw': 'Facebook', 'pa': 'Instagram'}

# Known Facebook App IDs, resolved via the Graph API (April 2026).
# These are Meta's own internal app identifiers and are stable.
KNOWN_APP_IDS = {
    '2220391788200892': 'WWW (Comet)',
    '256281040558': 'WWW',
    '350685531728': 'Facebook for Android',
    '6628568379': 'Facebook for iPhone',
    '124024574287414': 'Instagram',
    '567067343352427': 'Instagram for Android (Analytics Only)',
    '905593853150754': 'Instagram Carbon',
    '936619743392459': 'Instagram Web',
    '275254692598279': 'Facebook Lite',
    '409962623085609': 'Facebook Lite for Web (WebLite)',
    '173847642670370': 'Facebook for iPad',
    '437626316973788': 'Messenger for iOS',
    '514771569228061': 'BizWeb',
    '119211728144504': 'Power editor',
    '412378670482': 'Msite',
    '436761779744620': 'Business Manager',
    '2094176354154603': 'Ads Events Manager',
}


def lookup_app_id(app_id, remote=False):
    """Resolve a Facebook App ID to its name.

    Uses a built-in table of known IDs first, then falls back to
    the Graph API for unknown IDs (only if remote=True).
    """
    # Check offline table first
    if app_id in KNOWN_APP_IDS:
        return KNOWN_APP_IDS[app_id]

    if not remote:
        return None

    # Fall back to Graph API
    try:
        url = f'https://graph.facebook.com/{app_id}'
        req = urllib.request.Request(url, headers={'User-Agent': 'unfurl/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get('name')
    except Exception as e:
        log.debug(f'Failed to resolve Facebook App ID {app_id}: {e}')
        return None


def _decode_string(value_bytes):
    """Return printable ASCII as text and anything else as 0x-prefixed hex."""
    if all(0x20 <= b < 0x7f for b in value_bytes):
        return value_bytes.decode('ascii')
    return f'0x{value_bytes.hex()}'


def _parse_map(data, i=0):
    """Read map entries ([len][key][len][value]..., ended by 0x00) starting at i.

    Returns (entries, end), where end is the index just past the 0x00, or
    (entries, None) if the data ran out before the map was complete.
    """
    entries = []
    while i < len(data) and data[i] != 0x00:
        key_len = data[i]
        map_key = data[i + 1:i + 1 + key_len]
        i += 1 + key_len
        if i >= len(data) or i + 1 + data[i] > len(data):
            return entries, None
        map_value = data[i + 1:i + 1 + data[i]]
        i += 1 + data[i]
        entries.append((_decode_string(map_key), _decode_string(map_value)))
    if i >= len(data):
        return entries, None
    return entries, i + 1


def parse_fbclid_payload(data):
    """Walk a decoded fbclid payload.

    Returns (fields, unknown_field, trailer). fields is a list of
    (name, value) pairs in payload order; for a map field (extn, srtc) the
    value is the raw map bytes, which _parse_map turns into entries. Parsing
    stops at the 0x01 that starts the opaque trailer (returned as trailer), at
    an unknown field name (whose value size can't be known; returned as
    unknown_field), or at truncated data. Whatever was read before the stop
    is returned.
    """
    fields = []
    i = 0
    while i + 4 <= len(data) and data[i] != 0x01:
        key_bytes = data[i:i + 4]
        if not all(0x20 <= b < 0x7f for b in key_bytes):
            break
        key = key_bytes.decode('ascii')
        name = key.lower()
        i += 4

        if name in TIMESTAMP_FIELDS or name in U32_FIELDS:
            if i + 4 > len(data):
                break
            fields.append((key, int.from_bytes(data[i:i + 4], 'big')))
            i += 4

        elif name in U64_FIELDS:
            if i + 8 > len(data):
                break
            fields.append((key, str(int.from_bytes(data[i:i + 8], 'big'))))
            i += 8

        elif name in U8_FIELDS:
            if i + 1 > len(data):
                break
            fields.append((key, str(data[i])))
            i += 1

        elif name in STRING_FIELDS:
            if i >= len(data) or i + 1 + data[i] > len(data):
                break
            fields.append((key, _decode_string(data[i + 1:i + 1 + data[i]])))
            i += 1 + data[i]

        elif name in MAP_FIELDS:
            entries, end = _parse_map(data, i)
            if end is None:
                # Truncated mid-map; keep the raw bytes so the entries read so
                # far still show
                if entries:
                    fields.append((key, data[i:]))
                return fields, None, None
            fields.append((key, data[i:end]))
            i = end

        else:
            # Only report it if the field list so far is real; random bytes
            # that happen to be printable at offset 0 aren't a "new field"
            return fields, key if fields else None, None

    trailer = data[i:] if i < len(data) and data[i] == 0x01 else None
    return fields, None, trailer


def _b64decode(value):
    return base64.urlsafe_b64decode(value + '=' * ((4 - len(value) % 4) % 4))


def _add_child(unfurl, node, data_type, value, label, hover):
    unfurl.add_to_queue(
        data_type=data_type, key=None, value=value, label=label, hover=hover,
        parent_id=node.node_id, incoming_edge_config=facebook_edge)


def parse_fbclid(unfurl, node):
    """Split a Facebook Click ID into its parts: header, payload, and AEM suffix.

    Each part is its own node, and is expanded by run() when it comes off the
    queue: the header into the platform, the payload into its fields, and the
    suffix into the decoded AEM value. Showing the parts makes it visible which
    characters of the fbclid each decoded value came from.
    """
    fbclid = str(node.value)

    header = fbclid[:2]
    platform = PLATFORMS.get(header.lower())
    payload = fbclid[2:]
    aem_suffix = None
    if '_aem_' in payload:
        payload, aem_suffix = payload.split('_aem_', 1)

    try:
        data = _b64decode(payload)
    except Exception:
        data = b''

    fields, _, _ = parse_fbclid_payload(data)

    # Legacy fbclids (IwAR..., PAAa...) are the header plus an opaque blob
    # starting 0x01, with no fields before it.
    legacy = bool(platform) and data[:1] == b'\x01'

    if not fields and not legacy:
        # Base64 is case-sensitive, so a lowercased fbclid can't be decoded.
        # Real values always have uppercase characters, so an all-lowercase
        # one was almost certainly lowercased somewhere along the way.
        if platform and len(fbclid) > 20 and fbclid == fbclid.lower():
            _add_child(
                unfurl, node, 'descriptor', 'Lowercased fbclid',
                'Lowercased fbclid (can\'t be decoded)',
                'This fbclid is all lowercase. Real ones are case-sensitive base64 with '
                'mixed case, so something likely lowercased the URL, which destroys the '
                'encoded data.')
        # Other values that don't start with a field name (an opaque variant of
        # 44 or 56 random-looking bytes, or junk) aren't decoded.
        return

    if legacy:
        node.hover = f'Facebook Click ID (fbclid) in the legacy format, from {platform}.'
    else:
        node.hover = (
            f'Facebook Click ID (fbclid) from {platform or "an unknown platform"}, '
            'containing tracking fields.')

    _add_child(
        unfurl, node, 'facebook.fbclid.header', header, f'Header: {header}',
        'The first two characters of the fbclid. They are a plain tag, not part of the '
        'base64 that follows, and identify the Meta app the fbclid was generated in.')

    _add_child(
        unfurl, node, 'facebook.fbclid.payload', payload, f'Payload: {payload}',
        f'Everything between the header and <b>_aem_</b>, base64url-encoded. It decodes '
        f'to {len(data)} bytes: a list of named fields, then a trailer.<br><br>'
        f'0x{data.hex()}')

    if aem_suffix is not None:
        _add_child(
            unfurl, node, 'facebook.fbclid.aem_suffix', aem_suffix, f'AEM Suffix: {aem_suffix}',
            'The part after <b>_aem_</b>, base64url-encoded separately from the payload.')

    if legacy:
        _add_child(
            unfurl, node, 'descriptor', 'Legacy fbclid format', 'Legacy format (no named fields)',
            'Older fbclid format: the header followed only by the trailer (a marker byte, a '
            'version byte, and bytes whose meaning is unknown), with no named fields. Modern '
            'fbclids keep this trailer at the end, after their named fields.')


def parse_header(unfurl, node):
    platform = PLATFORMS.get(str(node.value).lower())
    if not platform:
        return
    _add_child(
        unfurl, node, 'facebook.fbclid.platform', platform, f'Platform: {platform}',
        f'<b>Iw</b> fbclids come from Facebook App IDs (web, Android, iPhone, Lite, '
        'Messenger) and <b>PA</b> from Instagram ones. (Reverse-engineered, not '
        'documented by Meta.)')


def parse_payload(unfurl, node):
    try:
        data = _b64decode(str(node.value))
    except Exception:
        return

    fields, unknown_field, trailer = parse_fbclid_payload(data)

    for field_key, value in fields:
        if field_key.lower() in MAP_FIELDS:
            # The value stays raw hex (parse_map re-reads it); the label shows
            # the entries readably and the hover keeps the bytes
            entries, _ = _parse_map(value)
            readable = ', '.join(f'{map_key}: {map_value}' for map_key, map_value in entries)
            _add_child(
                unfurl, node, 'facebook.fbclid.map', f'0x{value.hex()}',
                f'{field_key}: {{{readable}}}',
                f'{MAP_HOVERS[field_key.lower()]} Raw bytes: 0x{value.hex()}')
        else:
            _add_field(unfurl, node, field_key, value)

    if unknown_field:
        _add_child(
            unfurl, node, 'facebook.fbclid.unknown_field', unknown_field,
            f'Unknown field: {unknown_field} (parsing stopped)',
            f'<b>{html.escape(unknown_field)}</b> isn\'t a known fbclid field, so the size '
            'of its value is unknown and the rest of the fbclid can\'t be parsed. It may be '
            'a new field, or the fbclid may be truncated or corrupted.')

    if trailer:
        version = f' Its second byte (0x{trailer[1]:02x}) looks like a version number: ' \
            'Facebook fbclids use 0x1d or 0x1e and Instagram ones 0xa6 or 0xa7, each +1 ' \
            'when the trailer grew from 44 to 46 bytes.' if len(trailer) > 1 else ''
        _add_child(
            unfurl, node, 'facebook.fbclid.trailer', f'0x{trailer.hex()}',
            f'Trailer: 0x{trailer.hex()}',
            f'{len(trailer)} bytes at the end of the payload, starting with 0x01.{version} '
            'What the rest means is unknown; it may be a signature or an ID Facebook checks on its side. '
            'A legacy fbclid is just this trailer, with no fields in front of it.')


def parse_map(unfurl, node):
    try:
        raw = bytes.fromhex(str(node.value)[2:])
    except ValueError:
        return
    entries, _ = _parse_map(raw)
    for map_key, map_value in entries:
        _add_field(unfurl, node, map_key, map_value)


def parse_aem_suffix(unfurl, node):
    try:
        # 0x prefix marks it as raw bytes, so a 32-character hex string isn't
        # re-parsed as an MD5 hash or UUID
        aem_value = f'0x{_b64decode(str(node.value)).hex()}'
    except Exception:
        return
    _add_child(
        unfurl, node, 'facebook.fbclid.aem_value', aem_value, f'AEM Value: {aem_value}',
        'The decoded AEM suffix, usually 16 bytes. AEM likely stands for Aggregated Event '
        'Measurement, Facebook\'s privacy-preserving ad attribution system. The value is '
        'opaque; it may be a hash, a token, or something else.')


def _add_field(unfurl, node, field_key, value):
    """Queue one decoded field (or map entry) as a child of node."""
    name = field_key.lower()

    if name in TIMESTAMP_FIELDS:
        # Keep the raw value; the timestamp parser adds FBCLID_EPOCH and shows the math
        meaning = ('It is the time the link was clicked: test clicks on facebook.com decoded '
                   'to the click second.') if name == 'clck' else (
                   'Probably the time the link was clicked; only <b>clck</b> has been tested '
                   'against known click times.')
        unfurl.add_to_queue(
            data_type='fbclid-seconds', key=field_key, value=value,
            label=f'{field_key}: {value}',
            hover=f'<b>{field_key}</b> is a 4-byte timestamp ({value:,}). It counts seconds '
                  f'from 2024-01-01 20:29:36 UTC, not from 1970, so add {FBCLID_EPOCH:,} to '
                  'get Unix time. That epoch was estimated from when URLs containing fbclids '
                  f'were captured, then calibrated with timed test clicks. {meaning} '
                  '(Reverse-engineered, not documented by Meta.)',
            parent_id=node.node_id,
            incoming_edge_config=facebook_edge)
        return

    if name not in KNOWN_FIELDS:
        # Only map keys get here (an unknown top-level field stops the walk),
        # such as "callsite", which sometimes appears beside app_id in srtc
        _add_child(
            unfurl, node, 'facebook.fbclid.map_entry', value, f'{field_key}: {value}',
            f'A key/value pair inside one of the fbclid\'s map fields. The meaning of '
            f'<b>{html.escape(field_key)}</b> is unknown.')
        return
    label_name, hover_text = KNOWN_FIELDS[name]

    # For app_id, resolve to a human-readable name
    if name == 'app_id':
        app_name = lookup_app_id(value, remote=unfurl.remote_lookups)
        if app_name:
            label_name = 'App'
            value = f'{app_name} ({value})'

    label = f'{label_name}: {value}'

    # The aem value is a bitmask in binary; list the set bits, keeping the raw value
    if name == 'aem' and value and set(value) <= {'0', '1'}:
        set_bits = [str(bit) for bit, digit in enumerate(reversed(value)) if digit == '1']
        if not set_bits:
            label += ' (no bits set)'
        elif len(set_bits) == 1:
            label += f' (bit {set_bits[0]} set)'
        else:
            label += f' (bits {" and ".join(set_bits)} set)'

    unfurl.add_to_queue(
        data_type=f'facebook.fbclid.{name}',
        key=None, value=value,
        label=label,
        hover=hover_text,
        parent_id=node.node_id,
        incoming_edge_config=facebook_edge)


def run(unfurl, node):
    if node.data_type == 'url.query.pair' and node.key == 'fbclid':
        parse_fbclid(unfurl, node)
    elif node.parent_id is None and BARE_FBCLID_RE.fullmatch(str(node.value)):
        # A bare fbclid pasted on its own, without the URL around it.
        # parse_fbclid still only expands it if the payload decodes.
        parse_fbclid(unfurl, node)
    elif node.data_type == 'facebook.fbclid.header':
        parse_header(unfurl, node)
    elif node.data_type == 'facebook.fbclid.payload':
        parse_payload(unfurl, node)
    elif node.data_type == 'facebook.fbclid.map':
        parse_map(unfurl, node)
    elif node.data_type == 'facebook.fbclid.aem_suffix':
        parse_aem_suffix(unfurl, node)
