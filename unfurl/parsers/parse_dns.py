# Copyright 2023 Google LLC
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

from dnslib import DNSRecord
import re
from unfurl import utils

dns_edge = {
    'color': {
        'color': '#3b8bcc'
    },
    'title': 'DNS Parsing Functions',
    'label': 'dns'
}

DNS_MESSAGE_FIELDS = {
    'id': 'A 16 bit identifier assigned by the program that generates any kind of query. '
          'This identifier is copied the corresponding reply and can be used by the requester '
          'to match up replies to outstanding queries.',
    'type': 'A one bit field that specifies whether this message is a query (0), or a response (1).',
    'opcode': 'The kind of query in this message (QUERY, IQUERY, or STATUS). This value is set by the '
              'originator of a query and copied into the response.',
    'flags': 'Bits set to denote characteristics of the message. Flags are AA (Authoritative Answer), '
             'TC (TrunCation), RD (Recursion Desired), and RA (Recursion Available).',
    'rcode': 'Response code; options are: No error, Format error, Server failure, Name error, '
             'Not Implemented, or Refused.',
    'q': 'Count of entries in the "Question" section',
    'a': 'Count of entries in the "Answer" section',
    'ns': 'Count of entries in the "Authority" section',
    'ar': 'Count of entries in the "Additional Records" section',
    'qname': 'The domain name being queried',
    'qtype': 'The type of query (A, NS, CNAME, and so on)',
    'qclass': 'The class of the query (such as IN for Internet)'
}


def run(unfurl, node):
    if node.data_type == 'url.query.pair' and node.key == 'dns':
        decoded_query = utils.try_urlsafe_b64_decode(node.value)
        if decoded_query is None:
            return

        try:
            dns_record = DNSRecord.parse(decoded_query)

        # Might not have been encoded DNS after all
        except Exception:
            return

        parsed_dns = repr(dns_record)
        parsed_dns_lines = parsed_dns.split('\n')
        dns_line_re = re.compile(r'<(?P<section_type>DNS \w+): (?P<section_content>.*)>')

        for line in parsed_dns_lines:
            line_re = dns_line_re.fullmatch(line)
            if line_re:
                section_content_dict = {}
                content_pairs = line_re.group('section_content').split()

                if line_re.group('section_type') == 'DNS Question':
                    question = content_pairs.pop(0)
                    section_content_dict['qname'] = question

                for content_pair in content_pairs:
                    key, value = content_pair.split('=')
                    section_content_dict[key] = value

                unfurl.add_to_queue(
                    data_type='dns.section', key=line_re.group('section_type'), value=section_content_dict,
                    label=line_re.group('section_type'), hover='The section of the DNS Message', parent_id=node.node_id,
                    incoming_edge_config=dns_edge)

    elif node.data_type == 'dns.section':
        for key, value in node.value.items():
            unfurl.add_to_queue(
                data_type='dns.section.field', key=key, value=value, hover=DNS_MESSAGE_FIELDS.get(key),
                parent_id=node.node_id, incoming_edge_config=dns_edge)
