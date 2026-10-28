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

import re

from unfurl import utils

chatgpt_edge = {
    'color': {
        'color': '#10a37f'
    },
    'title': 'ChatGPT / OpenAI Parsing Functions',
    'label': 'GPT'
}

CHATGPT_DOMAINS = ('chatgpt.com', 'chat.openai.com')
SORA_DOMAINS = ('sora.chatgpt.com', 'sora.com')
OAI_CONTENT_DOMAIN = 'oaiusercontent.com'

# Most of OpenAI's newer IDs share one 128-bit layout (worked out from ~440k archived IDs):
#
#   hex[0:8]    32-bit Unix timestamp, seconds
#   hex[8:12]   14-bit sub-second value, shifted left 2 (the low 2 bits are always 0)
#   hex[12]     '8' (UUIDv8 version nibble)
#   hex[13:16]  12-bit node; deliberate decimal ranges (0-19, 400-440, 800-819, 900-939, 1000+, 2000+)
#   hex[16:32]  2 variant bits ('10') + 62 random bits
#
# Conversation and share IDs are written as dashed UUIDs. GPT, project, /s/ share, Sora post,
# Codex, Operator, notification and many API IDs use the same layout as 32 bare hex chars,
# usually behind a prefix. ChatGPT image file IDs use it with the timestamp zeroed.

# Timestamped IDs first appeared on 2024-08-30 (canary on node 6; all nodes by 09-04)
FORMAT_START = utils.create_epoch_seconds_timestamp('2024-08-30T00:00:00')

# Until about 2024-10-28 the sub-second value was nanoseconds >> 16, so it never went
# above 15258. Afterwards it uses the full 14-bit range (probably a binary fraction).
NANOSECOND_ERA_END = utils.create_epoch_seconds_timestamp('2024-11-04T00:00:00')
NANOSECOND_ERA_MAX = 999_999_999 >> 16

# Node ranges observed in conversation and share IDs. Used only to recognize IDs that
# arrive without a ChatGPT URL around them; under a ChatGPT domain any node is decoded.
KNOWN_NODE_RANGES = ((0, 31), (800, 1023))
# Nodes seen in GPT, project and snippet IDs (401 in nearly all; 400, 420 and 440 rarely)
OBJECT_NODE_RANGE = (400, 447)

object_id_re = re.compile(r'(g-p-|g-|t_)([0-9a-f]{32})(?:-(.+))?')
share_id_re = re.compile(r'([a-z]{1,3}_)?([0-9a-f]{32})')
legacy_gpt_id_re = re.compile(r'g-([0-9A-Za-z]{9})(?:-(.+))?')
codex_task_re = re.compile(r'(task_[a-z]_)([0-9a-f]{32})')
sora_post_re = re.compile(r'(s_)([0-9a-f]{32})')
sora_ulid_re = re.compile(r'(gen_|task_)([0-9a-hjkmnp-tv-z]{26})')
api_id_re = re.compile(r'(resp|msg|fc|rs|cntr|vs|batch|eval|cfile)_([0-9a-f]{32}|[0-9a-f]{48}|[0-9a-f]{50})')
completion_id_re = re.compile(r'(chatcmpl-|cmpl-)([0-9A-Za-z]{29})')
image_file_re = re.compile(r'file_(00000000[0-9a-f]{24})(?![0-9a-f])')
b58_file_re = re.compile(r'file-([1-9A-HJ-NP-Za-km-z]{22})')
dashed_uuid_re = re.compile(r'/?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)
sdmntpr_host_re = re.compile(r'sdmntpr([a-z0-9]+)\.oaiusercontent\.com')

OBJECT_ID_TYPES = {
    'g-': 'GPT ID',
    'g-p-': 'Project ID',
    't_': 'Shared Snippet ID',
}

SHARE_TYPES = {
    None: ('Share Link ID', 'A /s/ share link with no type prefix.'),
    't_': ('Shared Snippet ID', 'A shared text snippet (a selection from a conversation).'),
    'm_': ('Share Link ID (m_)', 'The most common /s/ share type. The prefix probably stands for "message" '
                                 '(not confirmed).'),
    'dr_': ('Share Link ID (dr_)', 'Probably a shared deep research report (inferred from the prefix only).'),
    'cd_': ('Share Link ID (cd_)', 'Probably a shared canvas document (inferred from the prefix only).'),
    'cx_': ('Share Link ID (cx_)', 'First seen in August 2026; probably a Codex share (inferred from the prefix '
                                   'only).'),
}

API_ID_TYPES = {
    'resp': 'Responses API response ID',
    'msg': 'Responses API message ID',
    'fc': 'Responses API function call ID',
    'rs': 'Responses API reasoning item ID',
    'cntr': 'OpenAI API container ID',
    'vs': 'OpenAI API vector store ID',
    'batch': 'OpenAI API batch ID',
    'eval': 'OpenAI API eval ID',
    'cfile': 'OpenAI API container file ID',
}

# ChatGPT image file IDs have a zeroed timestamp, but each version nibble first appeared
# in a known month (Wayback first captures; version 5 matches the 2025-03-25 launch of
# GPT-4o image generation).
IMAGE_FILE_ERAS = {'5': '2025-03', '6': '2025-04', '7': '2025-11', '8': '2026-07'}

# chatcmpl- and legacy cmpl- IDs: base62 of the first 5 chars + this = Unix seconds
COMPLETION_EPOCH = 1_576_800_000  # 2019-12-20 00:00:00 UTC
COMPLETION_FLOORS = {
    'chatcmpl-': utils.create_epoch_seconds_timestamp('2023-03-01T00:00:00'),
    'cmpl-': utils.create_epoch_seconds_timestamp('2020-06-01T00:00:00'),
}
BASE62 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
BASE58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
CROCKFORD = '0123456789abcdefghjkmnpqrstvwxyz'
SORA_FLOOR_MS = utils.create_epoch_seconds_timestamp('2024-01-01T00:00:00') * 1000

# Node types whose whole value might be a bare OpenAI ID
BARE_VALUE_TYPES = ('url', 'url.path.segment', 'url.query.pair', 'file.name', 'string')

QUERY_DESCRIPTIONS = {
    'historySearchQuery': (
        'Text typed into ChatGPT history search',
        'The conversation was opened from the sidebar\'s history search, and this is the text the user '
        'searched for. Treat it as user-entered content.'),
    'model': (
        'Model selected when the link was made',
        'ChatGPT opens the conversation with this model chosen (for example gpt-4o, or gpt-4o-canmore for '
        'canvas).'),
    'messageId': (
        'Link to a specific message in the conversation',
        'A deep link that scrolls to one message.'),
    'notification_channel_id': (
        'Channel of the notification that opened this link',
        'Seen values: jawbone (an internal name, meaning unknown) and image_gen (an image finished '
        'generating).'),
    'open-connector': (
        'Connector being linked',
        'Set while linking a connector (for example gdrive, o365_personal or github_connector).'),
}

QUERY_VALUE_DESCRIPTIONS = {
    ('src', 'history_search'): (
        'Opened from ChatGPT history search',
        'The conversation was opened from a result in the sidebar\'s history search. A historySearchQuery '
        'parameter, if present, holds the search text.'),
    ('temporary-chat', 'true'): (
        'Temporary chat (not saved to history)',
        'Opens a temporary chat, which ChatGPT does not save to the user\'s history.'),
    ('hints', 'search'): (
        'Web search enabled for the prompt',
        'Opens ChatGPT with web search turned on for the prefilled prompt.'),
    ('_tm', 'oauth_success'): (
        'Returned from a successful connector sign-in',
        'ChatGPT adds this after a connector\'s OAuth sign-in completes, so a connector was just linked.'),
}


def under_chatgpt_domain(unfurl, node):
    return any(unfurl.preceding_domain_matches(node, d) for d in CHATGPT_DOMAINS)


def has_chatgpt_layout(hex_id, node_check):
    """Check the fixed parts of the layout: version 8, RFC variant, zero low sub-second bits."""
    if len(hex_id) != 32 or hex_id[12] != '8' or hex_id[16] not in '89ab':
        return False
    if int(hex_id[8:12], 16) & 0b11:
        return False
    return node_check(int(hex_id[13:16], 16))


def plausible_time(seconds, floor=FORMAT_START):
    return floor <= seconds <= utils.create_epoch_seconds_timestamp(days_ahead=1)


def looks_like_chatgpt_uuid(hex_id):
    """Strict check for a bare UUID with no ChatGPT URL around it.

    Requires the fixed layout bits, a timestamp between the format's launch and
    tomorrow, and a node in a range ChatGPT has actually used. A random UUIDv8 passes
    all of that well under 0.1% of the time.
    """
    def known_node(n):
        return any(low <= n <= high for low, high in KNOWN_NODE_RANGES)

    if not has_chatgpt_layout(hex_id, known_node):
        return False
    return plausible_time(int(hex_id[:8], 16))


def written_dashed(unfurl, node):
    """True if the value a 'uuid' node came from was written with dashes.

    ChatGPT conversation and share IDs are always written dashed. Undashed 32-hex values
    are mostly hashes, and some of those pass every other check (Gravatar MD5s, for
    example), so a bare match needs the dashes.
    """
    parents = unfurl.get_predecessor_node(node)
    return bool(parents) and bool(dashed_uuid_re.fullmatch(str(parents[0].value)))


def is_image_file_id(hex_id):
    """A ChatGPT image file ID: the object layout with the timestamp zeroed and version 5-8."""
    return (len(hex_id) == 32 and hex_id[:8] == '00000000' and hex_id[12] in IMAGE_FILE_ERAS
            and hex_id[16] in '89ab' and not int(hex_id[8:12], 16) & 0b11)


def claims_uuid(unfurl, node):
    """True if this parser decodes the given 'uuid' node (so parse_uuid can skip its generic notes)."""
    hex_id = str(node.value).lower()
    if len(hex_id) != 32:
        return False
    if is_image_file_id(hex_id) and unfurl.preceding_domain_matches(node, OAI_CONTENT_DOMAIN):
        return True
    if under_chatgpt_domain(unfurl, node):
        return has_chatgpt_layout(hex_id, lambda n: True)
    return written_dashed(unfurl, node) and looks_like_chatgpt_uuid(hex_id)


def claims_hex_value(unfurl, node):
    """True if a bare 32-hex value is a ChatGPT ID, so parse_hash shouldn't call it a potential MD5.

    Covers undashed object IDs under a ChatGPT URL: notification_id values and path
    segments such as /s/{hex}, Operator /c/ and /v/, and Codex environments.
    """
    value = node.value
    if not isinstance(value, str) or len(value) != 32 or not utils.hex_re.fullmatch(value):
        return False
    return has_chatgpt_layout(value.lower(), lambda n: True) and under_chatgpt_domain(unfurl, node)


def describe_node_id(node_id):
    if 0 <= node_id <= 19:
        return 'Nodes 0-19 issued conversation IDs from 2024-08-30 until about 2025-08-05 (some share IDs later).'
    if OBJECT_NODE_RANGE[0] <= node_id <= OBJECT_NODE_RANGE[1]:
        return ('Nodes 400-440 issue object IDs: GPTs, projects, /s/ shares, Sora posts, Operator, notifications '
                'and API objects. Node 401 (0x191) is by far the most common. GPT IDs used node 400 from '
                '2024-11-10 to 2024-11-15, then 401.')
    if 800 <= node_id <= 839:
        return ('Nodes 800-819 issued Codex cloud task IDs from 2025-06-01 and conversation IDs from late July '
                '2025 (replacing 0-19), and tapered off by mid-2026. A few IDs use values just above 819.')
    if 900 <= node_id <= 949:
        return 'Nodes 900-939 first appeared on 2026-01-21 and were mostly retired by mid-2026.'
    if 1000 <= node_id <= 1023:
        return 'Nodes 1000-1006 were added one at a time from 2026-02-11 and issued most IDs from mid-2026.'
    if node_id == 25:
        return 'Node 25 issued a small number of conversation IDs from 2025-06-18 to 2025-07-11 (probably a test).'
    if 2000 <= node_id <= 2009:
        return 'Nodes 2000-2002 issue Responses API item IDs (seen in 2026).'
    return 'This node value has not been seen in sampled ChatGPT IDs.'


def add_time(unfurl, node, timestamp, hover):
    unfurl.add_to_queue(
        data_type='epoch-seconds', key=None, value=timestamp, label=f'Time generated: {timestamp}',
        hover=hover, parent_id=node.node_id, incoming_edge_config=chatgpt_edge)


def decode_chatgpt_id(unfurl, node, hex_id):
    timestamp = int(hex_id[:8], 16)
    sub_second = int(hex_id[8:12], 16) >> 2
    node_id = int(hex_id[13:16], 16)

    add_time(unfurl, node, timestamp,
             'The first 32 bits of ChatGPT IDs are a Unix timestamp (seconds) of when the ID was created. '
             'Verified against archived captures of ~180,000 conversation IDs (none had an embedded time '
             'later than when the archive first saw it) and ~95,000 other OpenAI IDs.')

    if timestamp < FORMAT_START:
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value='Timestamp predates this ID format',
            label='Timestamp predates this ID format',
            hover='Timestamped ChatGPT IDs first appeared on 2024-08-30, so this embedded time is not plausible. '
                  'A small number of real-looking IDs (about 1 in 20,000) carry dates like this. A bad client '
                  'clock or a hand-edited ID could explain it. Treat this timestamp with caution.',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
    elif not plausible_time(timestamp):
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value='Timestamp is in the future',
            label='Timestamp is in the future',
            hover='This embedded time is later than now, so it cannot be when the ID was created. The ID may be '
                  'edited, fabricated, or not a ChatGPT ID at all.',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)

    if timestamp < NANOSECOND_ERA_END and sub_second <= NANOSECOND_ERA_MAX:
        microseconds = sub_second * 65536 // 1000
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value=sub_second,
            label=f'Sub-second: 0.{microseconds:06d}',
            hover='The next 14 bits are a sub-second value. In IDs created before November 2024 it was '
                  'nanoseconds >> 16 (units of 65.536 µs); the maximum value of 15258 seen in that period '
                  'confirms the encoding.',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
    else:
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value=sub_second,
            label=f'Sub-second: {sub_second / 16384:.4f} (probable)',
            hover='The next 14 bits are a sub-second value. Since November 2024 it spans the full 14-bit range, '
                  'most likely a binary fraction of a second (value / 16384, ~61 µs resolution). The earlier '
                  'nanosecond encoding is confirmed; this one is inferred.',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)

    add_node_and_random(unfurl, node, hex_id)


def add_node_and_random(unfurl, node, hex_id, node_note=None):
    node_id = int(hex_id[13:16], 16)
    unfurl.add_to_queue(
        data_type='descriptor', key=None, value=node_id, label=f'Node: {node_id}',
        hover=f'The 12 bits after the version nibble identify the generator node (or shard) that '
              f'issued the ID. {node_note or describe_node_id(node_id)}',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge)

    unfurl.add_to_queue(
        data_type='descriptor', key=None, value=hex_id[16:], label=f'Random: {hex_id[16:]}',
        hover='The last 64 bits are 2 variant bits (binary 10) followed by 62 random bits.',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge)


def path_segment_before(unfurl, node, offset=1):
    """Value of the url.path.segment `offset` positions before this one, or None."""
    if not isinstance(node.key, int) or node.key - offset < 1:
        return None
    sibling = unfurl.check_sibling_nodes(
        node, data_type='url.path.segment', key=node.key - offset, return_node=True)
    return sibling.value if sibling else None


def uuid_context(unfurl, node):
    """For a 'uuid' node under a ChatGPT URL, name the kind of ID from where it sits.

    Returns 'conversation', 'share', 'notification', or 'object' (an undashed object ID in a
    path), or None.
    """
    parents = unfurl.get_predecessor_node(node)
    if not parents:
        return None
    parent = parents[0]
    if parent.data_type == 'url.query.pair':
        return 'notification' if parent.key == 'notification_id' else None
    if parent.data_type != 'url.path.segment':
        return None
    before = path_segment_before(unfurl, parent)
    if unfurl.find_preceding_domain(node) != 'operator.chatgpt.com':
        if before == 'c':
            return 'conversation'
        if before == 'share' or (before == 'e' and path_segment_before(unfurl, parent, 2) == 'share'):
            return 'share'
    if not dashed_uuid_re.fullmatch(str(parent.value)):
        return 'object'
    return None


def parent_is_whole_path(unfurl, node):
    """True if a 'uuid' node came from the url.path node rather than a path segment.

    parse_uuid accepts a leading '/', so a one-segment path like /{uuid} yields a 'uuid'
    node from both the path and the segment. Only the segment's copy is decoded.
    """
    parents = unfurl.get_predecessor_node(node)
    return bool(parents) and parents[0].data_type == 'url.path'


def add_description(unfurl, node, label, hover):
    unfurl.add_to_queue(
        data_type='description', key=None, value=None, label=label, hover=hover,
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge)


def uuid_hex(value):
    """The 32 lowercase hex of a dashed or undashed UUID-format value, or None."""
    if dashed_uuid_re.fullmatch(value) or re.fullmatch(r'[0-9a-fA-F]{32}', value):
        return value.replace('-', '').lstrip('/').lower()
    return None


def has_layout(hex_id):
    return bool(hex_id) and has_chatgpt_layout(hex_id, lambda n: True)


def parse_path_segment(unfurl, node):
    value = str(node.value)
    before = path_segment_before(unfurl, node)
    host = unfurl.find_preceding_domain(node)
    hex_id = uuid_hex(value)

    if host == 'operator.chatgpt.com' and before in ('c', 'v') and has_layout(hex_id):
        if before == 'c':
            add_description(unfurl, node, 'Operator Conversation ID',
                            'Identifies a shared Operator conversation. The ID uses the same layout as other '
                            'ChatGPT object IDs, so it embeds the time it was created.')
        else:
            add_description(unfurl, node, 'Operator Shared Video ID',
                            'Identifies a shared recording of an Operator session. The ID embeds the time it '
                            'was created.')
        return

    # Conversation and share paths only on chatgpt.com / chat.openai.com, and only for UUID-format values
    on_chat_host = host not in SORA_DOMAINS and host != 'operator.chatgpt.com'

    if before == 'c' and on_chat_host and hex_id:
        add_description(unfurl, node, 'Conversation ID',
                        'Identifies a ChatGPT conversation. Since 2024-08-30, the ID embeds the time the '
                        'conversation was created.')
        return

    if before == 'share' and on_chat_host and hex_id:
        add_description(unfurl, node, 'Shared Conversation ID',
                        'Identifies a shared ChatGPT conversation link. The ID is probably minted when the link is '
                        'shared, separately from the conversation ID (not yet confirmed).')
        return

    if before == 'e' and path_segment_before(unfurl, node, 2) == 'share' and on_chat_host and hex_id:
        add_description(unfurl, node, 'Shared Conversation ID (workspace)',
                        'Identifies a shared ChatGPT conversation link. The /share/e/ form is likely a share '
                        'restricted to a Team or Enterprise workspace.')
        return

    if before == 's':
        m = share_id_re.fullmatch(value)
        if m and m.group(1) in SHARE_TYPES and has_layout(m.group(2)):
            label, hover = SHARE_TYPES[m.group(1)]
            if m.group(1):
                add_object_id(unfurl, node, m.group(1), m.group(2), label=label, hover=hover)
            else:
                # Bare hex: parse_uuid turns it into a 'uuid' node, which run() decodes
                add_description(unfurl, node, label, f'{hover} The ID embeds the time the link was created.')
        return

    if before == 'tasks' and 'codex' in unfurl.find_preceding_path(node).split('/'):
        m = codex_task_re.fullmatch(value)
        if m and has_layout(m.group(2)):
            add_object_id(
                unfurl, node, m.group(1), m.group(2), label=f'Codex Task ID ({m.group(1)})',
                hover='A Codex cloud task. What the letter after task_ means (e, b or i) is unknown. Task IDs '
                      'take node values from the 800-819 pool that conversations moved to later.')
        return

    if (before in ('environment', 'environments') and re.fullmatch(r'[0-9a-f]{32}', value)
            and has_layout(value)):
        add_description(unfurl, node, 'Codex Environment ID',
                        'A Codex cloud environment. The ID embeds the time the environment was created.')
        return

    if host in SORA_DOMAINS:
        m = sora_post_re.fullmatch(value)
        if m and before == 'p' and has_layout(m.group(2)):
            add_object_id(unfurl, node, m.group(1), m.group(2), label='Sora Post ID',
                          hover='A Sora 2 post. The ID embeds the time the post was created.')
            return
        m = sora_ulid_re.fullmatch(value)
        if m:
            add_sora_ulid(unfurl, node, m.group(1), m.group(2))
        return

    m = object_id_re.fullmatch(value)
    if m and m.group(1) in ('g-', 'g-p-'):
        add_object_id(unfurl, node, m.group(1), m.group(2), slug=m.group(3))
        return

    m = legacy_gpt_id_re.fullmatch(value)
    if m and before == 'g':
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value=m.group(1), label=f'GPT ID: {m.group(1)}',
            hover='Custom GPTs created before about November 2024 use a 9-character base62 ID, which does not '
                  'contain a timestamp. Newer GPT IDs are 32 hex characters with an embedded creation time.',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
        if m.group(2):
            add_slug(unfurl, node, m.group(2))


def add_slug(unfurl, node, slug):
    unfurl.add_to_queue(
        data_type='descriptor', key=None, value=slug, label=f'Name: {slug}',
        hover='A readable slug of the GPT or project name. ChatGPT ignores it when resolving the link, so it '
              'reflects the name at the time the link was copied.',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge)


def add_object_id(unfurl, node, prefix, hex_id, slug=None, label=None, hover=None):
    id_type = label or OBJECT_ID_TYPES.get(prefix, f'ChatGPT Object ID ({prefix})')
    layout_note = (f'{id_type}s use the same 128-bit layout as ChatGPT conversation IDs (timestamp, '
                   f'sub-second, node, random), written as 32 hex characters.')
    # The value keeps its prefix so the generic UUID and hash parsers don't re-claim the bare hex
    unfurl.add_to_queue(
        data_type='chatgpt.object-id', key=prefix, value=f'{prefix}{hex_id}', label=f'{id_type}: {hex_id}',
        hover=f'{hover} {layout_note}' if hover else layout_note,
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge,
        extra_options={'widthConstraint': {'maximum': 500}})
    if slug:
        add_slug(unfurl, node, slug)


def decode_crockford(value):
    number = 0
    for char in value.lower():
        number = number * 32 + CROCKFORD.index(char)
    return number


def add_sora_ulid(unfurl, node, prefix, body):
    milliseconds = decode_crockford(body[:10])
    if not SORA_FLOOR_MS <= milliseconds <= utils.create_epoch_seconds_timestamp(days_ahead=1) * 1000:
        return
    kind = 'Generation' if prefix == 'gen_' else 'Task'
    unfurl.add_to_queue(
        data_type='chatgpt.sora-id', key=prefix, value=f'{prefix}{body}', label=f'Sora {kind} ID: {body}',
        hover='Sora generation and task IDs are ULIDs: the first 10 characters (Crockford base32) are a Unix '
              'time in milliseconds, and the other 16 are random. None of ~2,350 archived IDs had a time later '
              'than its first capture.',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge,
        extra_options={'widthConstraint': {'maximum': 500}})


def decode_sora_ulid(unfurl, node):
    body = str(node.value)[len(node.key):]
    milliseconds = decode_crockford(body[:10])
    unfurl.add_to_queue(
        data_type='epoch-milliseconds', key=None, value=milliseconds, label=f'Time generated: {milliseconds}',
        hover='The first 48 bits of a ULID are the Unix time in milliseconds when the ID was created.',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
    unfurl.add_to_queue(
        data_type='descriptor', key=None, value=body[10:], label=f'Random: {body[10:]}',
        hover='The last 80 bits of a ULID are random.',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge)


def api_object_part(body):
    """Return (offset, object_hex) of the timestamped object ID inside an API ID body, or None.

    32 hex: the object ID itself. 48 hex (2025 container and response IDs): the object ID
    followed by 16 more hex. 50 hex (Responses API items from late 2025): 16 hex, a 00 or
    01 byte, then the object ID.
    """
    if len(body) == 50:
        if body[16:18] not in ('00', '01'):
            return None
        offset = 18
    else:
        offset = 0
    hex_id = body[offset:offset + 32]
    if not has_chatgpt_layout(hex_id, lambda n: True) or not plausible_time(int(hex_id[:8], 16)):
        return None
    return offset, hex_id


def decode_api_id(unfurl, node):
    prefix = node.key
    body = str(node.value)[len(prefix) + 1:]
    offset, hex_id = api_object_part(body)
    decode_chatgpt_id(unfurl, node, hex_id)
    if len(body) == 50:
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value=f'Unknown: {body[:16]} {body[16:18]}',
            label=f'Unknown: {body[:16]} {body[16:18]}',
            hover='Responses API item IDs since late 2025 are 50 hex characters: 16 hex of unknown meaning, a '
                  '00 or 01 byte, then a 32-hex object ID with an embedded time. The time matched the API\'s '
                  'created_at in 13 of 13 public examples.',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
    elif len(body) == 48:
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value=f'Unknown: {body[32:]}', label=f'Unknown: {body[32:]}',
            hover='This form of ID is a 32-hex object ID with an embedded time, followed by 16 more hex '
                  'characters of unknown meaning.',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)


def add_api_id(unfurl, node, prefix, body):
    if not api_object_part(body):
        return
    id_type = API_ID_TYPES[prefix]
    unfurl.add_to_queue(
        data_type='openai.api-id', key=prefix, value=f'{prefix}_{body}', label=f'{id_type}: {prefix}_{body}',
        hover=f'{id_type}s contain an object ID in the same 128-bit layout as ChatGPT conversation IDs, so they '
              f'embed the time the object was created. Checked against the API\'s own created_at values.',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge,
        extra_options={'widthConstraint': {'maximum': 500}})


def decode_base62(value):
    number = 0
    for char in value:
        number = number * 62 + BASE62.index(char)
    return number


def add_completion_id(unfurl, node, prefix, body):
    timestamp = decode_base62(body[:5]) + COMPLETION_EPOCH
    if not plausible_time(timestamp, COMPLETION_FLOORS[prefix]):
        return
    kind = 'Chat Completions' if prefix == 'chatcmpl-' else 'Completions'
    unfurl.add_to_queue(
        data_type='descriptor', key=None, value=f'{prefix}{body}', label=f'OpenAI {kind} ID',
        hover='OpenAI\'s 29-character completion IDs start with a timestamp: the first 5 characters, read as '
              'base62 (0-9, A-Z, a-z), are seconds since 2019-12-20 00:00:00 UTC. This matched the response\'s '
              '"created" time to within a second in 150 of 152 public chatcmpl- examples and 18 of 19 legacy '
              'cmpl- examples. IDs of other lengths '
              '(from other servers and proxies) carry no time.',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
    unfurl.add_to_queue(
        data_type='epoch-seconds', key=None, value=timestamp, label=f'Time created: {timestamp}',
        hover='When OpenAI\'s API created the response. Decoded from the first 5 base62 characters plus '
              '1,576,800,000 (2019-12-20 00:00:00 UTC).',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge)


def add_image_file_id(unfurl, node, hex_id):
    # The value keeps the file_ prefix so the generic UUID and hash parsers don't re-claim the bare hex
    unfurl.add_to_queue(
        data_type='chatgpt.image-file-id', key=None, value=f'file_{hex_id}',
        label=f'ChatGPT image file ID: {hex_id[:8]}-{hex_id[8:12]}-{hex_id[12:16]}-{hex_id[16:20]}-{hex_id[20:]}',
        hover='Images made in ChatGPT get file IDs in the same layout as other ChatGPT IDs, but with the 32-bit '
              'timestamp set to zero. The version character still dates the file to an era.',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge,
        extra_options={'widthConstraint': {'maximum': 500}})


def decode_image_file_id(unfurl, node, hex_id):
    version = hex_id[12]
    unfurl.add_to_queue(
        data_type='descriptor', key=None, value='Timestamp field is zeroed', label='Timestamp field is zeroed',
        hover='The first 32 bits, which hold the creation time in other ChatGPT IDs, are always zero in image '
              'file IDs. The file\'s creation time is not recoverable from the ID.',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
    unfurl.add_to_queue(
        data_type='descriptor', key=None, value=version,
        label=f'Version {version}: probably created no earlier than {IMAGE_FILE_ERAS[version]}',
        hover='The version character of ChatGPT image file IDs moved from 5 to 8 over time, going by when each '
              'was first archived: 5 from 2025-03 (when GPT-4o image generation launched), 6 from 2025-04, 7 from '
              '2025-11, and 8 from 2026-07. Old files keep being seen after a new version starts, so this is a '
              'lower bound, not a window. It is inferred from archive dates, not documented.',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
    add_node_and_random(unfurl, node, hex_id,
                        node_note='Image file IDs use nodes in their own ranges (500-509, 518-529, 559-560, 579, '
                                  '582).')


def add_b58_file_id(unfurl, node, body):
    number = 0
    for char in body:
        number = number * 58 + BASE58.index(char)
    if number >= 2 ** 128:
        return
    hex_id = f'{number:032x}'
    if not has_chatgpt_layout(hex_id, lambda n: 0xff0 <= n <= 0xfff):
        return
    # The value is the label rather than the bare hex, so the UUID and hash parsers leave it alone
    unfurl.add_to_queue(
        data_type='descriptor', key=None, value=f'Decoded file ID: {hex_id}',
        label=f'OpenAI file ID (base58): {hex_id}',
        hover='Newer OpenAI file IDs are 22 base58 characters. Decoded, they have the same 128-bit layout as '
              'ChatGPT IDs (version 8, zero low sub-second bits, a node of 4080-4095; 4087-4089 and 4095 have been '
              'seen), but the first 32 bits '
              'are not a timestamp: they decode to dates in the 1970s and 1980s and do not match known upload '
              'times. That part looks scrambled, so no time is shown.',
        parent_id=node.node_id, incoming_edge_config=chatgpt_edge,
        extra_options={'widthConstraint': {'maximum': 500}})


def parse_bare_value(unfurl, node, skip_object_ids=False):
    """Recognize OpenAI IDs that make up a whole value: a bare input, path segment, query value or file name.

    Every pattern here has a literal prefix and a fixed length, and is only claimed if the
    decoded layout and time check out. GPT, project and snippet IDs in a ChatGPT path are
    left to parse_path_segment (skip_object_ids).
    """
    value = node.value.strip()

    m = object_id_re.fullmatch(value)
    if m:
        if skip_object_ids:
            return
        # Bare GPT, project or snippet IDs (outside a ChatGPT URL) are only claimed when they
        # carry the exact layout, a known object node and a plausible time.
        hex_id = m.group(2)
        if (has_chatgpt_layout(hex_id, lambda n: OBJECT_NODE_RANGE[0] <= n <= OBJECT_NODE_RANGE[1])
                and plausible_time(int(hex_id[:8], 16))):
            add_object_id(unfurl, node, m.group(1), hex_id, slug=m.group(3))
        return

    m = api_id_re.fullmatch(value)
    if m:
        add_api_id(unfurl, node, m.group(1), m.group(2))
        return

    m = completion_id_re.fullmatch(value)
    if m:
        add_completion_id(unfurl, node, m.group(1), m.group(2))
        return

    # A path segment with an extension also becomes a file.name node; match only that one
    m = image_file_re.match(value)
    if m and is_image_file_id(m.group(1)) and not (node.data_type == 'url.path.segment' and '.' in value):
        add_image_file_id(unfurl, node, m.group(1))
        return

    m = b58_file_re.fullmatch(value)
    if m:
        add_b58_file_id(unfurl, node, m.group(1))


def parse_query_pair(unfurl, node):
    value = str(node.value)
    if node.key == 'utm_source' and value == 'chatgpt.com':
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value='Visit came from a link in ChatGPT',
            label='Visit came from a link in ChatGPT',
            hover='ChatGPT adds utm_source=chatgpt.com to links it shows in answers (search results and '
                  'citations), so this URL was most likely opened from a ChatGPT response.',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
        return

    if not under_chatgpt_domain(unfurl, node):
        return

    described = QUERY_VALUE_DESCRIPTIONS.get((node.key, value)) or QUERY_DESCRIPTIONS.get(node.key)
    if described:
        label, hover = described
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value=label, label=label, hover=hover,
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
    elif node.key in ('q', 'prompt') and value:
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value='Prefilled prompt', label='Prefilled prompt',
            hover='Opens ChatGPT with this text already in the message box. The text came from whoever made the '
                  'link, not necessarily the user. Many of these links are "Summarize with AI" buttons on other '
                  'sites, and some prompts ask ChatGPT to remember the site as a trusted source (an attempt to '
                  'influence future answers).',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)


def parse_sas_param(unfurl, node):
    """Explain the Azure SAS times on oaiusercontent.com file links."""
    host = unfurl.find_preceding_domain(node)
    value = str(node.value)
    if node.key == 'se' and re.match(r'2[1-9]\d\d-', value):
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value='Expiry is about 100 years out',
            label='Expiry is about 100 years out',
            hover='Some files.oaiusercontent.com links (GPT avatars, 2023-2024) expire 100 years after they '
                  'were issued. If that holds, the expiry minus 100 years is when this link was made '
                  '(a hypothesis, not confirmed).',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
    elif node.key == 'se' and sdmntpr_host_re.fullmatch(host):
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value='Link expiry (made about an hour earlier)',
            label='Link expiry (made about an hour earlier)',
            hover='ChatGPT image links expire about an hour after they are generated: across 3,236 archived '
                  'links, the archive captured 99% of them within an hour before this time. So the link was '
                  'most likely generated in the hour before.',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
    elif node.key in ('skt', 'ske') and sdmntpr_host_re.fullmatch(host):
        which = 'start' if node.key == 'skt' else 'end'
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value=f'Signing key validity {which}',
            label=f'Signing key validity {which}',
            hover='The Azure signing key behind this link is valid for 24 or 48 hours and is shared by many links, '
                  'so this is the key\'s time, not the file\'s.',
            parent_id=node.node_id, incoming_edge_config=chatgpt_edge)


def run(unfurl, node):
    if node.data_type == 'chatgpt.object-id':
        hex_id = str(node.value)[len(node.key):]
        if has_chatgpt_layout(hex_id, lambda n: True):
            decode_chatgpt_id(unfurl, node, hex_id)
        return

    if node.data_type == 'openai.api-id':
        decode_api_id(unfurl, node)
        return

    if node.data_type == 'chatgpt.sora-id':
        decode_sora_ulid(unfurl, node)
        return

    if node.data_type == 'chatgpt.image-file-id':
        decode_image_file_id(unfurl, node, str(node.value)[len('file_'):])
        return

    if node.data_type == 'uuid':
        hex_id = str(node.value).lower()
        if len(hex_id) != 32 or parent_is_whole_path(unfurl, node):
            return

        if is_image_file_id(hex_id) and unfurl.preceding_domain_matches(node, OAI_CONTENT_DOMAIN):
            decode_image_file_id(unfurl, node, hex_id)
            return

        if under_chatgpt_domain(unfurl, node):
            context = uuid_context(unfurl, node)
            if has_chatgpt_layout(hex_id, lambda n: True):
                if context == 'notification':
                    label = 'ChatGPT notification ID with an embedded timestamp'
                    hover = ('Links opened from a ChatGPT notification carry its ID. The ID uses the ChatGPT '
                             'object layout, so it embeds the time the notification was created. In 9 of 9 archived '
                             'examples that time was after the conversation was created and before the link was '
                             'captured.')
                elif context == 'object':
                    label = 'ChatGPT object ID with an embedded timestamp'
                    hover = ('Written as 32 hex characters without dashes, in the same layout as ChatGPT\'s UUIDv8 '
                             'IDs: a Unix timestamp, a sub-second value, a generator node, and 62 random bits.')
                else:
                    label = 'ChatGPT ID: UUIDv8 with an embedded timestamp'
                    hover = ('ChatGPT IDs created since 2024-08-30 are UUIDv8s: a Unix timestamp, a sub-second '
                             'value, a generator node, and 62 random bits.')
                unfurl.add_to_queue(
                    data_type='uuid-parsed', key=None, value=hex_id, label=label, hover=hover,
                    parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
                decode_chatgpt_id(unfurl, node, hex_id)

            elif hex_id[12] == '4' and context in ('conversation', 'share'):
                cutover = '2024-08-30' if context == 'conversation' else 'on or before 2024-11-06'
                share_note = ' (the earliest timestamped share ID seen is from that date)' if context == 'share' else ''
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value='Older ChatGPT ID format (random UUIDv4)',
                    label='Older ChatGPT ID format (random UUIDv4)',
                    hover=f'ChatGPT {context} IDs switched from random UUIDv4 to timestamped UUIDv8 {cutover}'
                          f'{share_note}. A UUIDv4 here suggests the {context} was created before then.',
                    parent_id=node.node_id, incoming_edge_config=chatgpt_edge)

        elif written_dashed(unfurl, node) and looks_like_chatgpt_uuid(hex_id):
            unfurl.add_to_queue(
                data_type='uuid-parsed', key=None, value=hex_id,
                label='UUIDv8 matching the structure of ChatGPT IDs',
                hover='This UUIDv8 matches every fixed part of the layout ChatGPT uses for conversation and share '
                      'IDs (plausible timestamp, zero low sub-second bits, a known node value). It is decoded on '
                      'that basis, but without a ChatGPT URL around it the attribution is not certain.',
                parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
            decode_chatgpt_id(unfurl, node, hex_id)
        return

    if node.data_type == 'url.hostname':
        m = sdmntpr_host_re.fullmatch(str(node.value))
        if m:
            unfurl.add_to_queue(
                data_type='descriptor', key=None, value=m.group(1), label=f'Azure storage region: {m.group(1)}',
                hover='ChatGPT stores generated images in Azure Blob Storage, and the sdmntpr subdomain names the '
                      'region holding this file. Why a file lands in a given region (user location, data '
                      'residency or load balancing) is not known.',
                parent_id=node.node_id, incoming_edge_config=chatgpt_edge)
        return

    in_chatgpt_path = False
    if node.data_type == 'url.path.segment':
        if under_chatgpt_domain(unfurl, node) or any(unfurl.preceding_domain_matches(node, d) for d in SORA_DOMAINS):
            in_chatgpt_path = True
            parse_path_segment(unfurl, node)

    if node.data_type == 'url.query.pair':
        parse_query_pair(unfurl, node)
        if unfurl.preceding_domain_matches(node, OAI_CONTENT_DOMAIN):
            parse_sas_param(unfurl, node)

    if isinstance(node.value, str) and node.data_type in BARE_VALUE_TYPES:
        parse_bare_value(unfurl, node, skip_object_ids=in_chatgpt_path)
