# Copyright 2022 Google LLC
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

linkedin_edge = {
    'color': {
        'color': '#2469bf'
    },
    'title': 'LinkedIn Parsing Functions',
    'label': '‍💼'
}


def parse_linkedin_profile_id(unfurl, node):
    linkedin_profile_with_base12_id_re = re.compile(r'[^/]+-([0-9ab]{3})([0-9ab]{3})([0-9ab]{3})$')
    if not isinstance(node.value, str):
        return
    m = re.match(linkedin_profile_with_base12_id_re, node.value)
    if m:
        numeric_id = (int(f'{m.group(3)}{m.group(2)}{m.group(1)}', 12))

        node.hover = 'By default, the last URL path segment in a LinkedIn Profile URLs has the form ' \
                     '<br>"|<b>first name</b>|-|<b>last name</b>|-|<b>encoded profile id</b>|". ' \
                     '<br><br>The profile ID can be decoded by splitting it into groups of three characters, ' \
                     '<br>reversing the groups, and interpreting the result as a base 12 number ' \
                     '<a href="https://twitter.com/jackcr/status/1575915823075495936" target="_blank">[ref]</a>.'

        unfurl.add_to_queue(
            data_type='description', key='LinkedIn Profile ID', value=numeric_id,
            hover='LinkedIn Profile IDs are generated sequentially, so smaller values correspond with older accounts.',
            parent_id=node.node_id, incoming_edge_config=linkedin_edge)


def parse_linkedin_id(unfurl, node, li_id):
    try:
        linkedin_id = int(li_id)
        # LinkedIn IDs are 63 bits long; the upper 41 bits are the timestamp.
        # Shift it 22 (63-22 = 41) bits right, leaving just the timestamp bits.
        # Reference: https://github.com/Ollie-Boyd/Linkedin-post-timestamp-extractor
        timestamp = (linkedin_id >> 22)

    except Exception as e:
        log.exception(f'Exception parsing LinkedIn ID: {e}')
        return

    unfurl.add_to_queue(
        data_type='epoch-milliseconds', key=None, value=timestamp, label=f'Timestamp: {timestamp}',
        hover='The leading 41 bits in a LinkedIn ID are a timestamp, '
              '<br>thought to represent when an item was posted or created.',
        parent_id=node.node_id, incoming_edge_config=linkedin_edge)


def parse_linkedin_message_id_v2(unfurl, node):
    if not isinstance(node.value, str):
        return

    # Example: https://www.linkedin.com/messaging/thread/2-ZTRkNzljZjgtOTRmNC00ZGJkLWJlYTktMDFjOWU4MTgxMjhjXzAxMA==/
    linkedin_message_id_v2_re = re.compile(r'2-([A-z0-9]{54}==)')
    m = re.fullmatch(linkedin_message_id_v2_re, node.value)
    if m:
        decoded_id = base64.b64decode(m.group(1))
        unfurl.add_to_queue(
            data_type='description', key='LinkedIn Message ID', value=decoded_id.decode('utf-8'),
            hover='When decoded, LinkedIn Message IDs (v2) appear to be UUIDs followed by three digits, separated by '
                  'an underscore. The UUID version seems to have changed from v5 to v4 around 2021-05-01.',
            parent_id=node.node_id, incoming_edge_config=linkedin_edge)


def run(unfurl, node):
    if unfurl.preceding_domain_matches(node, 'linkedin.com'):
        # Parsing LinkedIn Profile ID from the default Profile Page URL
        # Example: https://linkedin.com/in/charolette-pare-93b3a220a
        # h/t: Jack Crook (https://twitter.com/jackcr/status/1575915823075495936)
        if unfurl.check_sibling_nodes(node, data_type='url.path.segment', key=1, value='in'):
            if node.key == 2:
                parse_linkedin_profile_id(unfurl, node)

        # LinkedIn Message IDs come in two forms: "v1" and "v2" (my names).
        #  - v1 is just a LinkedIn ID.
        #      Ex: 6685980502161199104
        #  - v2 starts with "2-", followed by a base64-encoded ID.
        #      Ex: 2-ZTRkNzljZjgtOTRmNC00ZGJkLWJlYTktMDFjOWU4MTgxMjhjXzAxMA==
        elif unfurl.check_sibling_nodes(node, data_type='url.path.segment', key=1, value='messaging'):
            if node.key != 3:
                return
            elif len(node.value) == 19:
                parse_linkedin_id(unfurl, node, node.value)
            elif node.value.startswith('2-'):
                parse_linkedin_message_id_v2(unfurl, node)

        # LinkedIn IDs (19-digit numbers that contain an embedded timestamp) can appear in other places;
        # this is a more generic search for them. One common example is in the URLs of posts:
        # Ex: https://www.linkedin.com/posts/ryanabenson_more-search-url-parsing-misp-lists-more-activity-6904926959046938624-B2Ma  # noqa: E501
        elif node.data_type in ('url.path.segment', 'url.query.pair'):
            linkedin_post_id_re = re.compile(r'(\d{19})')
            m = re.search(linkedin_post_id_re, node.value)
            if m:
                # Check if the LinkedIn ID timestamp would be between 2016-11 and 2027-06
                if unfurl.check_if_int_between(int(m.group(1)), 6200000000000000000, 7600000000000000000):
                    parse_linkedin_id(unfurl, node, m.group(1))

    # If it's the "root" node and a plausible LinkedIn ID, parse it.
    # This case covers someone parsing just an ID, not a full URL.
    elif node.node_id == 1 and unfurl.check_if_int_between(node.value, 6200000000000000000, 7600000000000000000):
        parse_linkedin_id(unfurl, node, node.value)
