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

import re

from unfurl import utils

urlparse_edge = {
    'color': {
        'color': '#6734eb'
    },
    'title': 'URL Parsing Functions',
    'label': 'IP'
}


def run(unfurl, node):

    if node.data_type == 'url.hostname':
        parsed_ip = utils.parse_ip_address(node.value)

        if parsed_ip and re.fullmatch(utils.digits_re, node.value):
            hover = 'Converted to IP address from an integer representation'
        elif parsed_ip and re.fullmatch(r'0x[A-F0-9]{8}', node.value, flags=re.IGNORECASE):
            hover = 'Converted to IP address from a hex representation'
        elif parsed_ip and re.fullmatch(utils.octal_ip_re, node.value):
            hover = 'Converted to IP address from an octal representation'
        else:
            return

        unfurl.add_to_queue(
            data_type='ip', key=None, value=str(parsed_ip),
            hover=hover,
            parent_id=node.node_id, incoming_edge_config=urlparse_edge)
