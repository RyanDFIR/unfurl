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

# References:
#   Microsoft's Safe Links feature docs (describes behavior, not URL format):
#     https://learn.microsoft.com/en-us/defender-office-365/safe-links-about
#   forensicdave/unsafelink - community reverse-engineering of the `data` field;
#   source of the original position->label mapping (some labels later corrected
#   against a 20k-URL corpus audit, see docs/safelinks-format.md):
#     https://github.com/forensicdave/unsafelink
#   docs/safelinks-format.md - corpus-based audit (20,546 URLs) that
#   produced and corrected the position labels used here.

import urllib.parse

safelinks_edge = {
    'color': {
        'color': '#0078D4'
    },
    'title': 'Microsoft Defender Safe Links Parsing Functions',
    'label': '🛡️'
}

# Field positions inside the pipe-delimited `data` query parameter. Layout is
# reverse-engineered (not documented by Microsoft) and has shifted between
# versions.
DATA_FIELD_LABELS = {
    0: 'Version',
    1: 'Type',
    2: 'Recipient',
    3: 'Message GUID',
    4: 'Tenant GUID',
    7: 'Timestamp',
    8: 'Scan verdict',
    9: 'Scan payload',
    11: 'Scan context',
    12: 'Scan context',
    13: 'Scan context',
}

VERSION_DESCRIPTIONS = {
    '01': 'Safe Links data format v01 (6 fields). Earliest version observed in '
          'the audited corpus: type, recipient, per-message GUID, tenant GUID, '
          'and a single flag. No timestamp or verdict.',
    '02': 'Safe Links data format v02 (8 fields). Adds two zero flags and a '
          '.NET DateTime ticks timestamp. No scan verdict or scan payload.',
    '03': 'Safe Links data format v03 (10 fields). Adds scan verdict (observed: '
          '<code>Unknown</code>, <code>Bad</code>) and a base64 scan payload '
          'whose decoded prefix identifies the Defender component that processed '
          'the link (<code>Mailflow</code>, <code>ThreatIntel</code>, etc.).',
    '04': 'Safe Links data format v04 (11 fields). Adds a numeric code at '
          'position 10 (<code>0</code> / <code>1000</code> / <code>2000</code> / '
          '<code>3000</code> for mailflow scans; <code>1</code> for click-time '
          'scans inside Office/Teams).',
    '05': 'Safe Links data format v05 (14 fields). Same as v04 plus three '
          'trailing slots that carry suspected click-time scan context (Teams thread '
          'and message IDs, session/document GUIDs, etc.) when the scan came '
          'from Office desktop, Teams, or Office Web Apps; otherwise empty.',
}

DATA_FIELD_HOVER = {
    0: 'Format version of the Safe Links <code>data</code> field. Observed '
       'values: <code>01</code>-<code>05</code>. Each version has a fixed field '
       'count.',
    1: 'Observed values: <code>01</code> (dominant) and <code>02</code>. ',
    2: 'Observed as an email address in every populated record, but often empty.',
    3: 'Suspected unique per-message identifier.',
    4: 'Suspected tenant GUID.',
    7: 'Observed values decode to plausible scan or expiration timestamps for '
       'most records, but meaning is unknown.',
    8: "Microsoft Defender's verdict on the destination URL at scan time. "
       'Observed values: <code>Unknown</code> and <code>Bad</code>.',
    9: 'Base64-encoded scan payload. When valid, the decoded value has the '
       'form <code>Component|{json}</code>. Observed components values: '
       '<code>Mailflow</code>, <code>ThreatIntel</code>, '
       '<code>OfficeClient</code>, <code>Teams</code>, and <code>WAC</code>. '
       'The <code>{json}</code> portion carries component-specific metadata.'
}


def _maybe_decode_pipes(raw):
    """Some captured Safe Links arrive double-URL-encoded; the outer layer is
    stripped by ``urllib.parse.parse_qsl`` but the inner pipes survive as
    ``%7C``. If we see that shape, decode once so splitting on ``|`` works."""
    if '|' not in raw and '%7C' in raw.upper():
        return urllib.parse.unquote(raw)
    return raw


def run(unfurl, node):
    if node.data_type != 'url.query.pair':
        return

    if not unfurl.preceding_domain_matches(node, 'safelinks.protection.outlook.com'):
        return

    if node.key == 'url':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Wrapped destination URL (decoded by Safe Links)',
            hover='Microsoft Defender Safe Links wraps this destination URL and '
                  'routes clicks through <code>*.safelinks.protection.outlook.com</code> '
                  'so the destination can be scanned at click-time. The destination is '
                  'unfurled separately by the generic URL parser.',
            parent_id=node.node_id, incoming_edge_config=safelinks_edge)
        return

    if node.key == 'data':
        parts = _maybe_decode_pipes(node.value).split('|')
        for i, part in enumerate(parts):
            if not part:
                continue

            # Each branch handles one position. Positions appear in the same
            # order they appear in the data field. Branches that emit a
            # `string` or `datetime-ticks` node do so to let unfurl's
            # generic parsers (parse_uuid, parse_base64, parse_timestamp)
            # do further decoding downstream; branches that emit a
            # `descriptor` are pure annotation.
            if i in DATA_FIELD_LABELS:
                label_text = f'{DATA_FIELD_LABELS[i]} (Field {i}): {part}'
            else:
                label_text = f'Field {i}: {part}'
            hover = DATA_FIELD_HOVER.get(i, None)
            common = dict(key=None, label=label_text,
                          parent_id=node.node_id,
                          incoming_edge_config=safelinks_edge)

            if i == 0:
                # Version — annotation only, but hover swaps in a
                # version-specific description if we recognize the literal.
                unfurl.add_to_queue(
                    data_type='descriptor', value=label_text,
                    hover=VERSION_DESCRIPTIONS.get(part, hover), **common)

            elif i == 1:
                # Type — annotation only; meaning undocumented.
                unfurl.add_to_queue(
                    data_type='descriptor', value=label_text, hover=hover, **common)

            elif i == 2:
                # Recipient — email; emit raw so any future email parser
                # can pick it up.
                unfurl.add_to_queue(
                    data_type='string', value=part, hover=hover, **common)

            elif i == 3:
                # Per-message GUID — emit raw so parse_uuid recognizes it.
                unfurl.add_to_queue(
                    data_type='string', value=part, hover=hover, **common)

            elif i == 4:
                # Tenant GUID — emit raw so parse_uuid recognizes it.
                unfurl.add_to_queue(
                    data_type='string', value=part, hover=hover, **common)

            elif i == 7 and part.isdigit():
                # Timestamp — explicit datetime-ticks type triggers
                # parse_timestamp to emit a human-readable date child.
                unfurl.add_to_queue(
                    data_type='datetime-ticks', value=part, hover=hover, **common)

            elif i == 8:
                # Scan verdict — annotation only.
                unfurl.add_to_queue(
                    data_type='descriptor', value=label_text, hover=hover, **common)

            elif i == 9:
                # Scan payload — emit raw base64; parse_base64 decodes,
                # parse_url splits 'Component|{json}' on '|', parse_json
                # descends into the JSON.
                unfurl.add_to_queue(
                    data_type='string', value=part, hover=hover, **common)

            elif i in (11, 12, 13):
                # Scan-context slots — only populated for click-time scans.
                # Usually GUIDs (sometimes a base64 compound ID for Teams).
                # Emit raw so parse_uuid / parse_base64 fire.
                unfurl.add_to_queue(
                    data_type='string', value=part, hover=hover, **common)

            else:
                # Positions 5, 6, 10, or anything beyond the known layout:
                # bare flags / numeric codes / unknown — annotate only.
                unfurl.add_to_queue(
                    data_type='descriptor', value=label_text, hover=hover, **common)
        return

    if node.key == 'sdata':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Signature Data',
            hover='Always present in observed Safe Links URLs. The value is a '
                  'base64 blob whose role and algorithm are not publicly documented',
            parent_id=node.node_id, incoming_edge_config=safelinks_edge)
        return

    if node.key == 'reserved':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Reserved Safe Links parameter',
            hover='Reserved parameter set by Microsoft Defender Safe Links; '
                  'purpose is not publicly documented.',
            parent_id=node.node_id, incoming_edge_config=safelinks_edge)
        return
