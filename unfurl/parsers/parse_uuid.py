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
import uuid

uuid_edge = {
    'color': {
        'color': 'orange'
    },
    'title': 'UUID Parsing Functions',
    'label': 'UU'
}


def run(unfurl, node):
    if not node.data_type.startswith(('uuid', 'hash')):
        # Leading '/' optional, 8-4-4-4-12 hex digits with '-' optional, 13th char limited to [1-6]
        m = re.fullmatch(r'/?([0-9A-F]{8}-?[0-9A-F]{4}-?[1-8][0-9A-F]{3}-?[0-9A-F]{4}-?[0-9A-F]{12})',
                         str(node.value), re.IGNORECASE)
        if m:
            u = m.group(1)
            u = u.replace('-', '')
            unfurl.add_to_queue(
                data_type='uuid', key=None, value=u, label=f'UUID: {u[:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:]}',
                parent_id=node.node_id, incoming_edge_config=uuid_edge,
                hover='This is potentially a UUID, based on length',
                extra_options={'widthConstraint': {'maximum': 500}})

    elif node.data_type == 'uuid':
        u = uuid.UUID(node.value)
        # TODO: reference: http://www.mahonri.info/cgi/uuid.cgi
        if u.version == 1:
            unfurl.add_to_queue(
                data_type='uuid-parsed', key=None, value=node.value,
                label='Version 1 UUID is based on time and MAC address',
                parent_id=node.node_id, incoming_edge_config=uuid_edge)

            # Timestamp is 60-bits, the number of 100-nanosecond intervals since midnight 15 October 1582 Coordinated
            # Universal Time (UTC). The offset to the Unix epoch is 12219292800000 milliseconds. Divide ts by 10000
            # to go from 100-ns intervals to milliseconds.x
            timestamp = u.time/10000 - 12219292800000
            unfurl.add_to_queue(
                data_type='epoch-milliseconds', key=None, value=timestamp, label=f'Time generated: {timestamp}',
                parent_id=node.node_id, incoming_edge_config=uuid_edge)

            # Detection for randomly generated MACs (random 48-bit number with its eighth bit set to 1 as
            #  recommended in RFC 4122)
            if (u.node >> 40) & 0x01 == 1:
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value='The Node ID in this UUID is random',
                    hover='The Node ID in this UUID is set to a random number, <br>rather than an actual MAC address. '
                          '<a href="https://tools.ietf.org/html/rfc4122#section-4.5">[ref]</a>',
                    parent_id=node.node_id, incoming_edge_config=uuid_edge)

            else:
                pretty_mac = f'{u.node:0{12}X}'
                pretty_mac = ':'.join([pretty_mac[i]+pretty_mac[i+1] for i in range(0, 12, 2)])

                unfurl.add_to_queue(
                    data_type='mac-address', key=None, value=pretty_mac, label=f'MAC address: {pretty_mac}',
                    parent_id=node.node_id, incoming_edge_config=uuid_edge)

        elif u.version == 3:
            unfurl.add_to_queue(
                data_type='uuid-parsed', key=None, value=node.value,
                label='Version 3 UUID is generated based on a namespace and a name, which are '
                      'combined and hashed using MD5', parent_id=node.node_id, incoming_edge_config=uuid_edge)

        elif u.version == 4:
            # Limits to timestamp values between 2018-01 and 2025-05
            if 0x8A <= int(node.value[:2], 16) <= 0x9F:
                # Ref: https://itnext.io/laravel-the-mysterious-ordered-uuid-29e7500b4f8
                unfurl.add_to_queue(
                    data_type='descriptor', key=None,
                    value='This UUID matches the structure of both UUIDv4 (random) '
                          '& Laravel "Ordered UUIDs".',
                    hover='Laravel Ordered UUIDs appear similar to UUIDv4s, but they are outside RFC 4122 '
                          '<a href="https://itnext.io/laravel-the-mysterious-ordered-uuid-29e7500b4f8">[ref]</a>.'
                          '<br>The "Ordered UUID" is composed of a timestamp and random bits, while UUIDv4 is '
                          '<br>random and does not contain a timestamp.'
                          '<br><br>Unfurl differentiates between them based on potential timestamp values. There is '
                          '<br>a chance of misidentifying them, as they use the same structure. UUIDv4 is more common, '
                          '<br>but Unfurl is parsing this as an "Ordered UUID" to show the potential timestamp.',
                    extra_options={'widthConstraint': {'maximum': 250}},
                    parent_id=node.node_id, incoming_edge_config=uuid_edge)

                unfurl.add_to_queue(
                    data_type='epoch-ten-microseconds', key='Timestamp', value=int(node.value[:12], 16),
                    hover='The first 48 bits of an Ordered UUID are a timestamp',
                    parent_id=node.node_id, incoming_edge_config=uuid_edge)

            else:
                unfurl.add_to_queue(
                    data_type='uuid-parsed', key=None, value=node.value, label='Version 4 UUID is randomly generated',
                    parent_id=node.node_id, incoming_edge_config=uuid_edge)

        elif u.hex[12] == '5':
            unfurl.add_to_queue(
                data_type='uuid-parsed', key=None, value=node.value,
                label='Version 5 UUID is generated based on a namespace and a name, which are '
                      'combined and hashed using SHA-1', parent_id=node.node_id, incoming_edge_config=uuid_edge)

        elif u.version == 6:
            # Verified by: version nibble (hex[12] = 0x6), RFC 4122 variant bits (hex[16] ∈ {8,9,A,B}),
            # decodable 60-bit Gregorian timestamp, and node field parsed as MAC or random flag.
            #
            # UUIDv6 reorders the 60-bit v1 timestamp (100ns intervals since Oct 15 1582) to make
            # the UUID lexicographically sortable. The timestamp is stored MSB-first across three fields:
            #
            #   hex[0:8]   time_high: most significant 32 bits of the 60-bit timestamp
            #   hex[8:12]  time_mid:  next 16 bits
            #   hex[12]    ver:       '6'
            #   hex[13:16] time_low:  least significant 12 bits
            #
            # Concatenating all three fields yields the full 60-bit timestamp integer,
            # identical in value to a v1 UUID timestamp for the same moment.
            unfurl.add_to_queue(
                data_type='uuid-parsed', key=None, value=node.value,
                label='Version 6 UUID is a time-ordered UUID based on time and MAC address',
                hover='UUIDv6: time-ordered variant of v1. Timestamp (60-bit Gregorian) and node (MAC or random) '
                      'are verified. <a href="https://www.rfc-editor.org/rfc/rfc9562#name-uuid-version-6">[ref]</a>',
                parent_id=node.node_id, incoming_edge_config=uuid_edge)

            v6_hex = u.hex
            ts_hex = v6_hex[0:8] + v6_hex[8:12] + v6_hex[13:16]
            v1_timestamp = int(ts_hex, 16)
            timestamp = v1_timestamp / 10000 - 12219292800000
            unfurl.add_to_queue(
                data_type='epoch-milliseconds', key=None, value=timestamp, label=f'Time generated: {timestamp}',
                parent_id=node.node_id, incoming_edge_config=uuid_edge)

            if (u.node >> 40) & 0x01 == 1:
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value='The Node ID in this UUID is random',
                    hover='The Node ID in this UUID is set to a random number, <br>rather than an actual MAC address. '
                          '<a href="https://tools.ietf.org/html/rfc4122#section-4.5">[ref]</a>',
                    parent_id=node.node_id, incoming_edge_config=uuid_edge)
            else:
                pretty_mac = f'{u.node:0{12}X}'
                pretty_mac = ':'.join([pretty_mac[i]+pretty_mac[i+1] for i in range(0, 12, 2)])
                unfurl.add_to_queue(
                    data_type='mac-address', key=None, value=pretty_mac, label=f'MAC address: {pretty_mac}',
                    parent_id=node.node_id, incoming_edge_config=uuid_edge)

        elif u.version == 7:
            # Verified by: version nibble (hex[12] = 0x7), RFC 4122 variant bits (hex[16] ∈ {8,9,A,B}),
            # and a decodable 48-bit Unix millisecond timestamp (hex[0:12]).
            # rand_a (hex[13:16]) and rand_b (hex[17:32]) are pseudo-random or sub-millisecond
            # precision data; content is implementation-defined and not parsed.
            unfurl.add_to_queue(
                data_type='uuid-parsed', key=None, value=node.value,
                label='Version 7 UUID is a time-ordered UUID based on Unix time',
                hover='UUIDv7: Unix millisecond timestamp (hex[0:12]) verified. Remaining bits are random '
                      'or implementation-defined sub-ms data. '
                      '<a href="https://www.rfc-editor.org/rfc/rfc9562#name-uuid-version-7">[ref]</a>',
                parent_id=node.node_id, incoming_edge_config=uuid_edge)

            # The first 48 bits (hex[0:12]) are the Unix timestamp in milliseconds.
            timestamp = int(u.hex[:12], 16)
            unfurl.add_to_queue(
                data_type='epoch-milliseconds', key=None, value=timestamp, label=f'Time generated: {timestamp}',
                parent_id=node.node_id, incoming_edge_config=uuid_edge)

        elif u.version == 8:
            # Verified by: version nibble (hex[12] = 0x8) and RFC 4122 variant bits (hex[16] ∈ {8,9,A,B}).
            # All other bits are vendor-defined; no further parsing is possible without knowing the implementation.
            unfurl.add_to_queue(
                data_type='uuid-parsed', key=None, value=node.value,
                label='Version 8 UUID is vendor-specific; the structure is implementation-defined',
                hover='UUIDv8: only version nibble and variant bits are standard. All other bits are vendor-defined. '
                      '<a href="https://www.rfc-editor.org/rfc/rfc9562#name-uuid-version-8">[ref]</a>',
                parent_id=node.node_id, incoming_edge_config=uuid_edge)

    # TODO: Add lookup of well-known GUIDs?
    # https://github.com/EricZimmerman/GuidMapping/blob/master/Resources/GuidToName.txt
