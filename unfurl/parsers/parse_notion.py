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

import datetime
import json
import os
import re

from unfurl import utils
from unfurl.parsers.parse_chatgpt import path_segment_before

notion_edge = {
    'color': {
        'color': '#787774'
    },
    'title': 'Notion Parsing Functions',
    'label': 'N'
}

NOTION_DOMAINS = ('notion.so', 'notion.com', 'notion.site')

# Notion's IDs (since about 2024-09-13) are UUIDv8s built by its web client from 16 random
# bytes with fields written over them. Read from the client's ID generator on 2026-11-03 and
# checked against ~9,000 archived IDs (none had a day later than its first capture):
#
#   hex[0:3]    12-bit day: days since 2024-01-01 UTC (random for workspace IDs; 'fff' for
#               "testing" IDs)
#   hex[3:12]   36-bit workspace "short ID" (the space's short_id field)
#   hex[12]     '8' (UUIDv8 version nibble)
#   hex[13]     '0' minted by the client, '1' minted by Notion's server, '2'/'3' deterministic
#   hex[16]     variant ('8'-'b')
#   hex[20:24]  record type: blocks set the top two bits ('c'-'f', rest random); other
#               tables write a 15-bit table code ('000c' view, '000b' data source, ...)
#
# Deterministic IDs ('2'/'3' at hex[13]) are an md5 of a seed with the short ID and a 7-bit
# type code (low bits of hex[20:22]) written in. They carry no date; Notion uses them for
# copies (duplicates, template installs) and some records it creates at signup.

EPOCH = datetime.date(2024, 1, 1)
# Earliest day seen on a non-workspace Notion ID (Wayback, Common Crawl and urlscan.io)
EARLIEST_SEEN = datetime.date(2024, 9, 13)
TESTING_PREFIX = 'fff'
# Records outside any workspace (users) carry the production "main" short ID
MAIN_SHORT_ID = 'd872b594c'
SPACE_TABLE_CODE = 3

with open(os.path.join(os.path.dirname(__file__), 'notion_table_codes.json'), encoding='utf-8') as _f:
    _codes = json.load(_f)
TABLE_CODES = {code: name for name, code in _codes['v1_table_codes'].items()}
DETERMINISTIC_CODES = {code: name for name, code in _codes['deterministic_type_codes'].items()}

TABLE_NAMES = {
    'block': 'Block (a page, text, image, file, database row, ...)',
    'collection': 'Data source (database)',
    'collection_view': 'Database view',
    'space': 'Workspace',
    'space_view': 'Workspace view (a user\'s settings for a workspace)',
    'space_user': 'Workspace member',
    'notion_user': 'User',
    'team': 'Teamspace',
    'discussion': 'Discussion (comment thread)',
    'comment': 'Comment',
    'thread': 'Thread (such as a Notion AI chat)',
    'notification': 'Notification',
    'invite': 'Invite',
    'automation': 'Automation',
    'sidebar_section': 'Sidebar section',
    'site': 'Published site',
    'custom_emoji': 'Custom emoji',
}

QUERY_DESCRIPTIONS = {
    'v': ('Database view ID', 'Which view of the database the link opens.'),
    'p': ('Page opened in peek', 'A page opened as a side or center peek over the main page (pm=s or pm=c).'),
    'd': ('Discussion ID', 'Opens a discussion (comment thread) on the page.'),
    't': ('Thread ID', 'Opens a thread record, such as a Notion AI chat.'),
    'n': ('Notification ID', 'The notification this link was opened from.'),
    'invite': ('Invite ID', 'A workspace or page invite. The state parameter that goes with it is base64 JSON '
                            'holding the invitee\'s email address.'),
    'db': ('Database block ID', 'The database block that this data source belongs to.'),
    'spaceId': ('Workspace ID', 'The workspace that holds the file.'),
    'userId': ('Viewer\'s user ID', 'The signed-in user who loaded this image in the Notion app. On a public '
                                    'notion.site page it is empty.'),
    'expirationTimestamp': ('Signed link expiry',
                            'When this signed file link stops working (Unix ms). In one test it was the next '
                            'midnight UTC after the link was issued, which roughly brackets when the link was '
                            'handed out.'),
}

QUERY_VALUE_DESCRIPTIONS = {
    ('pm', 's'): ('Peek mode: side peek', 'The ?p= page opens in a panel at the side.'),
    ('pm', 'c'): ('Peek mode: center peek', 'The ?p= page opens in a pop-up in the center.'),
}

slug_id_re = re.compile(r'(.+)-([0-9a-fA-F]{32})')
candidate_re = re.compile(
    r'(?<![0-9a-fA-F])([0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?8[0-3][0-9a-fA-F]{2}-?[89abAB][0-9a-fA-F]{3}-?'
    r'[0-9a-fA-F]{12})(?![0-9a-fA-F])')
s3_host_re = re.compile(r'(?:([a-z0-9.-]+)\.)?s3[.-](?:[a-z0-9-]+\.)?amazonaws\.com')

# Off Notion's own hosts, IDs are decoded only where there's evidence they are Notion's. A
# scan of a large corpus of real URLs found that a lone Notion-shaped value on an unknown
# host is often something else (image hashes, session IDs, other vendors' UUIDs): 855 of
# 1,006 such dated values were dated after the URL was first captured, which a real ID
# can't be. Two kinds of evidence held up with no such impossible dates:
#
# 1. Notion site builders that pass Notion's IDs through, in the one spot they do it.
# 2. Two or more different IDs in the input sharing a workspace short ID (36 bits; two
#    unrelated random values match about 1 time in 69 billion).
BUILDER_NAMES = {
    'oopy': 'Oopy (a Notion site builder)',
    'usenotioncms': 'NotionCMS (serves Notion content to other sites)',
    'wraptas': 'Wraptas (a Notion site builder; its image store keeps the Notion block ID)',
}


def under_notion_domain(unfurl, node):
    return any(unfurl.preceding_domain_matches(node, d) for d in NOTION_DOMAINS)


def is_notion_v8(hex_id):
    """The fixed parts of the layout: version 8, RFC variant, and a known kind of record."""
    if len(hex_id) != 32 or hex_id[12] != '8' or hex_id[16] not in '89ab':
        return False
    if hex_id[13] in '01':
        if int(hex_id[20], 16) >= 0xc:
            return True
        return int(hex_id[20:24], 16) in TABLE_CODES
    if hex_id[13] in '23':
        return int(hex_id[20:22], 16) & 0x7f in DETERMINISTIC_CODES
    return False


def is_space_id(hex_id):
    return int(hex_id[20], 16) < 0xc and int(hex_id[20:24], 16) == SPACE_TABLE_CODE


def builder_for(unfurl, parent):
    """Name of the Notion site builder if `parent` (the node an ID came from) is where it puts Notion IDs."""
    host = unfurl.find_preceding_domain(parent)
    if parent.data_type == 'url.query.pair':
        if parent.key == 'blockId' and host == 'oopy.lazyrockets.com':
            return 'oopy'
        return None
    if parent.data_type != 'url.path.segment':
        return None
    if host == 'api-prod.usenotioncms.com' and path_segment_before(unfurl, parent) == 'block':
        return 'usenotioncms'
    m = s3_host_re.fullmatch(host)
    if m:
        # Path-style (s3.../wraptas-prod/{site}/{id}/) or virtual-hosted (wraptas-prod.s3.../{site}/{id}/)
        if m.group(1) == 'wraptas-prod' and parent.key == 2:
            return 'wraptas'
        if not m.group(1) and parent.key == 3 and path_segment_before(unfurl, parent, 2) == 'wraptas-prod':
            return 'wraptas'
    return None


def qualifies(hex_id):
    """Passes every check Unfurl can make without knowing the host: the layout, plus a plausible day."""
    if not is_notion_v8(hex_id):
        return False
    if hex_id[13] in '23':
        return True
    if hex_id.startswith(TESTING_PREFIX) or is_space_id(hex_id):
        return False
    day = EPOCH + datetime.timedelta(days=int(hex_id[:3], 16))
    return EARLIEST_SEEN <= day <= datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=1)


def shared_workspace_ids(unfurl, node, hex_id):
    """Distinct Notion-qualifying IDs in the whole input that share hex_id's workspace short ID.

    Returns the list only if there are at least two and at least one is a dated (random)
    ID; the deterministic check alone is too weak to count as evidence.
    """
    if not qualifies(hex_id):
        return []
    chain = unfurl.get_predecessor_chain(node)
    root = chain[-1] if chain else node
    found = set()
    for m in candidate_re.finditer(str(root.value)):
        other = m.group(1).replace('-', '').lower()
        if len(other) == 32 and other[3:12] == hex_id[3:12] and qualifies(other):
            found.add(other)
    found.add(hex_id)
    if len(found) < 2 or not any(h[13] in '01' for h in found):
        return []
    return sorted(found)


def attribution(unfurl, parent, hex_id):
    """Why an ID that came from `parent` is treated as Notion's: 'notion', a builder name, 'shared', or None."""
    if under_notion_domain(unfurl, parent):
        return 'notion'
    if not is_notion_v8(hex_id):
        return None
    builder = builder_for(unfurl, parent)
    if builder:
        return builder
    if shared_workspace_ids(unfurl, parent, hex_id):
        return 'shared'
    return None


def is_old_record_id(unfurl, node, hex_id, reason):
    """A UUIDv4 record ID on Notion's own hosts. Uploaded files (file./img.) keep v4 IDs, so they're excluded."""
    return (reason == 'notion' and len(hex_id) == 32 and hex_id[12] == '4'
            and not unfurl.find_preceding_domain(node).startswith(('file.', 'img.')))


def claims_uuid(unfurl, node):
    """True if this parser decodes the given 'uuid' node (so parse_uuid can skip its generic notes).

    That covers Notion v8 IDs, and v4 record IDs on Notion's hosts: those are Notion's older
    random IDs, so parse_uuid's guess that a v4 might be a Laravel "Ordered UUID" (with a
    timestamp) doesn't apply.
    """
    hex_id = str(node.value).lower()
    parents = unfurl.get_predecessor_node(node)
    if not parents:
        return False
    if is_notion_v8(hex_id):
        return attribution(unfurl, parents[0], hex_id) is not None
    return is_old_record_id(unfurl, node, hex_id, 'notion' if under_notion_domain(unfurl, parents[0]) else None)


def claims_hex_value(unfurl, node):
    """True if a bare 32-hex value is a Notion v8 ID, so parse_hash shouldn't call it a potential MD5.

    `node` is where the value sits (a path segment or query pair), so the same attribution
    rules apply as for the 'uuid' node parse_uuid makes from it.
    """
    value = node.value
    if not isinstance(value, str) or len(value) != 32 or not utils.hex_re.fullmatch(value):
        return False
    hex_id = value.lower()
    return is_notion_v8(hex_id) and attribution(unfurl, node, hex_id) is not None


def add_descriptor(unfurl, node, label, hover, value=None, data_type='descriptor'):
    unfurl.add_to_queue(
        data_type=data_type, key=None, value=label if value is None else value, label=label, hover=hover,
        parent_id=node.node_id, incoming_edge_config=notion_edge)


def table_label(name):
    return TABLE_NAMES.get(name, name)


def add_workspace(unfurl, node, hex_id, deterministic=False):
    short_id = hex_id[3:12]
    if short_id == MAIN_SHORT_ID:
        add_descriptor(
            unfurl, node, 'Workspace: none (Notion "main" value)',
            'Records that belong to no workspace, such as user accounts, carry this fixed value '
            f'({MAIN_SHORT_ID}) where other IDs have a workspace short ID.', value=short_id,
            data_type='notion.short-id')
        return
    hover = ('The workspace\'s "short ID" (its short_id field, in hex). Every ID minted in a workspace carries '
             'the same value, so it ties together pages, published sites, custom domains and image URLs from one '
             'workspace.')
    if deterministic:
        hover += ' Deterministic IDs carry it too (it matched the other IDs in the same URL in 28 of 28 cases).'
    # Typed so parse_timestamp doesn't read an all-digit short ID (724669122) as a timestamp
    add_descriptor(unfurl, node, f'Workspace short ID: {short_id}', hover, value=short_id,
                   data_type='notion.short-id')


def decode_random_id(unfurl, node, hex_id):
    type_code = int(hex_id[20:24], 16)
    is_block = int(hex_id[20], 16) >= 0xc
    table = 'block' if is_block else TABLE_CODES[type_code]
    testing = hex_id.startswith(TESTING_PREFIX)

    if table == 'space':
        label = 'Notion workspace ID (no date)'
        hover = ('Notion workspace IDs use the same layout as its other IDs, except that the first 12 bits are '
                 'random rather than a day, so they carry no date.')
    elif testing:
        label = 'Notion "testing" ID (no date)'
        hover = ('Notion\'s ID generator writes fff in the first 12 bits when asked for a "testing" ID, so these '
                 'carry no date. The few seen in URLs were all database views minted by Notion\'s server; why '
                 'is unknown.')
    else:
        label = 'Notion ID: UUIDv8 with an embedded creation date'
        hover = ('Notion IDs created since about 2024-09-13 are UUIDv8s holding the UTC day the record was '
                 'created, the workspace\'s short ID, whether the client or Notion\'s server minted it, and '
                 'the record type.')
    unfurl.add_to_queue(
        data_type='uuid-parsed', key=None, value=hex_id, label=label, hover=hover,
        parent_id=node.node_id, incoming_edge_config=notion_edge)

    if table != 'space' and not testing:
        add_day(unfurl, node, hex_id)

    add_workspace(unfurl, node, hex_id)

    if hex_id[13] == '0':
        add_descriptor(unfurl, node, 'Minted by: client (browser or app)',
                       'The character after the version 8 is 0 when the ID was made by Notion\'s client (the '
                       'web app or desktop/mobile app), as for pages and blocks made in the editor.')
    else:
        add_descriptor(unfurl, node, 'Minted by: Notion server',
                       'The character after the version 8 is 1 when Notion\'s server made the ID (about 12-16% of '
                       'IDs seen in URLs). Workspaces and users created at signup are server-minted; which other '
                       'server paths (API, imports, integrations, AI) mint IDs is not known.')

    if is_block:
        type_hover = ('Block IDs have the top two bits of the first 4 characters of the last group set, so that '
                      'character is c, d, e or f; the rest is random. Pages, text, images, files and database '
                      'rows are all blocks.')
    else:
        type_hover = (f'The first 4 characters of the last group ({hex_id[20:24]}) are Notion\'s code for the '
                      f'"{table}" table.')
    add_descriptor(unfurl, node, f'Record type: {table_label(table)}', type_hover, value=table)


def add_day(unfurl, node, hex_id):
    days = int(hex_id[:3], 16)
    unfurl.add_to_queue(
        data_type='notion-days', key=None, value=days, label=f'Day created: {days} days after 2024-01-01',
        hover='The first 12 bits are the number of days since 2024-01-01, UTC: the day the record was created '
              '(or copied). There is no time of day. Verified against the API\'s created_time for 156 of 156 '
              'public blocks, and none of ~8,900 archived IDs had a day later than its first capture. For '
              'database views the API\'s created_time can be months later than this day; the ID is the more '
              'reliable of the two.',
        parent_id=node.node_id, incoming_edge_config=notion_edge)

    day = EPOCH + datetime.timedelta(days=days)
    today = datetime.datetime.now(datetime.UTC).date()
    if day > today + datetime.timedelta(days=1):
        add_descriptor(unfurl, node, 'Day is in the future',
                       'This day is later than today, so it cannot be when the ID was created. The ID may be '
                       'edited, fabricated, or not a Notion ID at all.')
    elif day < EARLIEST_SEEN:
        add_descriptor(unfurl, node, 'Day is earlier than any Notion ID seen',
                       f'Dated Notion IDs first appear around {EARLIEST_SEEN}. This ID decodes to {day}, so treat '
                       f'the date with caution.')


def decode_deterministic_id(unfurl, node, hex_id):
    table = DETERMINISTIC_CODES[int(hex_id[20:22], 16) & 0x7f]
    unfurl.add_to_queue(
        data_type='uuid-parsed', key=None, value=hex_id, label='Notion deterministic ID (no date)',
        hover='When the character after the version 8 is 2 or 3, Notion built the ID from an md5 hash of a seed '
              'rather than random bytes, so it carries no date. Notion uses these for copies (duplicating a page, '
              'installing a template) and some records made at signup. All 45 archived examples that could be '
              'looked up were copies.',
        parent_id=node.node_id, incoming_edge_config=notion_edge)
    add_workspace(unfurl, node, hex_id, deterministic=True)
    add_descriptor(unfurl, node, 'Most likely a copy (duplicate or template)',
                   'Deterministic IDs showed up for pages duplicated from the page menu, for every record of an '
                   'installed template, and for some records Notion makes at signup. Copies can also get normal, '
                   'dated IDs.')
    add_descriptor(unfurl, node, f'Record type: {table_label(table)}',
                   f'Deterministic IDs hold a 7-bit type code in the first 2 characters of the last group; '
                   f'{int(hex_id[20:22], 16) & 0x7f} is Notion\'s code for "{table}".', value=table)


def add_attribution(unfurl, node, hex_id, reason):
    """Explain why an ID off Notion's own hosts is being decoded as Notion's."""
    if reason in BUILDER_NAMES:
        add_descriptor(unfurl, node, f'Notion ID passed through by {BUILDER_NAMES[reason]}',
                       'This site serves Notion content, and this is the spot in its URLs where it carries the '
                       'Notion ID, so the ID is decoded as Notion\'s.', value=reason)
    else:
        shared = shared_workspace_ids(unfurl, node, hex_id)
        add_descriptor(unfurl, node, f'Matches Notion\'s ID layout; {len(shared)} IDs here share a workspace',
                       f'This is not a Notion URL, but {len(shared)} different IDs in it match Notion\'s layout and '
                       f'carry the same 36-bit workspace short ID ({hex_id[3:12]}). Unrelated random values would '
                       f'almost never share it, so these are most likely Notion IDs, for example on a custom domain '
                       f'or a site built from Notion. A single ID like this is not decoded on other sites, because '
                       f'many unrelated values happen to fit the layout.', value='shared workspace')


def decode_uuid(unfurl, node):
    hex_id = str(node.value).lower()
    if len(hex_id) != 32:
        return
    parents = unfurl.get_predecessor_node(node)
    if not parents:
        return
    reason = attribution(unfurl, parents[0], hex_id)
    if not reason:
        return

    if is_notion_v8(hex_id):
        if reason != 'notion':
            add_attribution(unfurl, node, hex_id, reason)
        if hex_id[13] in '01':
            decode_random_id(unfurl, node, hex_id)
        else:
            decode_deterministic_id(unfurl, node, hex_id)
        return

    if is_old_record_id(unfurl, node, hex_id, reason):
        add_descriptor(unfurl, node, 'Older Notion ID format (random UUIDv4)',
                       'Notion switched to dated UUIDv8 IDs around 2024-09-13, so a UUIDv4 suggests the record is '
                       'older than that. It does not prove it: Notion can still fall back to UUIDv4 (a personal '
                       'home page made in 2026 had one).')


def add_uuid(unfurl, node, hex_id, hover):
    unfurl.add_to_queue(
        data_type='uuid', key=None, value=hex_id,
        label=f'UUID: {hex_id[:8]}-{hex_id[8:12]}-{hex_id[12:16]}-{hex_id[16:20]}-{hex_id[20:]}',
        hover=hover, parent_id=node.node_id, incoming_edge_config=notion_edge,
        extra_options={'widthConstraint': {'maximum': 500}})


def parse_path_segment(unfurl, node):
    # NotionCMS's proxy-2 form encodes the slashes: /block/{block id}%2F{file id}%2F{name}
    m = re.match(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})%2F', str(node.value))
    if m and builder_for(unfurl, node) == 'usenotioncms':
        add_uuid(unfurl, node, m.group(1).replace('-', '').lower(), 'The Notion block ID at the start of this segment.')
        return

    m = slug_id_re.fullmatch(str(node.value))
    if not m:
        return
    hex_id = m.group(2).lower()
    if not under_notion_domain(unfurl, node) and attribution(unfurl, node, hex_id) is None:
        return
    add_descriptor(unfurl, node, f'Page title (from the URL): {m.group(1)}',
                   'Notion puts a slug of the page title before the page ID. Notion ignores it when opening the '
                   'link, so it reflects the title when the link was made.', value=m.group(1))
    add_uuid(unfurl, node, hex_id, 'The page ID at the end of a Notion page URL.')


def parse_query_pair(unfurl, node):
    described = QUERY_VALUE_DESCRIPTIONS.get((node.key, str(node.value))) or QUERY_DESCRIPTIONS.get(node.key)
    if described and node.value:
        label, hover = described
        add_descriptor(unfurl, node, label, hover)


def run(unfurl, node):
    if node.data_type == 'uuid':
        decode_uuid(unfurl, node)
        return

    if node.data_type == 'url.path.segment':
        parse_path_segment(unfurl, node)
        return

    if node.data_type == 'url.query.pair' and node.key == 'blockId' and builder_for(unfurl, node) == 'oopy':
        add_descriptor(unfurl, node, 'Notion block ID',
                       'Oopy\'s image proxy names the Notion image block it is serving.')
        return

    if node.data_type == 'url.query.pair' and under_notion_domain(unfurl, node):
        parse_query_pair(unfurl, node)
