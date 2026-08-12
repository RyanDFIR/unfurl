# Copyright 2021 Ryan Benson
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

brave_edge = {
    'color': {
        'color': '#fb542b'
    },
    'title': 'Brave Search-related Parsing Functions',
    'label': '🦁'
}


def run(unfurl, node):
    if unfurl.preceding_domain_matches(node, 'search.brave.com'):
        if node.data_type == 'url.query.pair':
            if node.key == 'tf':
                tf_mappings = {
                    'pd': 'Past Day',
                    'pw': 'Past Week',
                    'pm': 'Past Month',
                    'py': 'Past Year'
                }

                tf_friendly_value = tf_mappings.get(node.value)
                if not tf_friendly_value:
                    m = re.fullmatch(r'(?P<start_date>\d{4}-\d{2}-\d{2})to(?P<end_date>\d{4}-\d{2}-\d{2})', node.value)
                    if m:
                        tf_friendly_value = f'{m.group("start_date")} to {m.group("end_date")}'
                    else:
                        tf_friendly_value = 'Unknown'

                unfurl.add_to_queue(
                    data_type='descriptor', key='Time Filter', value=tf_friendly_value,
                    hover='Time Filter', parent_id=node.node_id, incoming_edge_config=brave_edge)

            elif node.key == 'q':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Search Query: {node.value}',
                    hover='Terms used in the Brave search', parent_id=node.node_id, incoming_edge_config=brave_edge)

            elif node.key == 'show_local':
                local_mapping = {'0': 'False', '1': 'True'}

                unfurl.add_to_queue(
                    data_type='descriptor', key='Localized Results',
                    value=f'{local_mapping.get(node.value, "Unknown")}',
                    hover='Location information is derived from user\'s IP address by default, but can be manually '
                          'changed. '
                          '<a href="https://search.brave.com/help/anonymous-local-results" target="_blank">[ref]</a>',
                    parent_id=node.node_id, incoming_edge_config=brave_edge)

            elif node.key == 'size':
                unfurl.add_to_queue(
                    data_type='descriptor', key='Image Size Filter', value=node.value,
                    parent_id=node.node_id, incoming_edge_config=brave_edge)

            elif node.key == '_type':
                unfurl.add_to_queue(
                    data_type='descriptor', key='Image Type Filter', value=node.value,
                    parent_id=node.node_id, incoming_edge_config=brave_edge)

            elif node.key == 'layout':
                unfurl.add_to_queue(
                    data_type='descriptor', key='Image Layout Filter', value=node.value,
                    parent_id=node.node_id, incoming_edge_config=brave_edge)

            elif node.key == 'color':
                unfurl.add_to_queue(
                    data_type='descriptor', key='Image Color Filter', value=node.value,
                    parent_id=node.node_id, incoming_edge_config=brave_edge)

            elif node.key == 'length':
                unfurl.add_to_queue(
                    data_type='descriptor', key='Video Length Filter', value=node.value,
                    parent_id=node.node_id, incoming_edge_config=brave_edge)

            elif node.key == 'resolution':
                unfurl.add_to_queue(
                    data_type='descriptor', key='Video Resolution Filter', value=node.value,
                    parent_id=node.node_id, incoming_edge_config=brave_edge)

        elif node.data_type == 'url.path.segment' and node.key == 1:
            search_type_mappings = {
                'images': 'Image Search',
                'news': 'News Search',
                'search': 'Web Search',
                'videos': 'Video Search',
            }
            search_type = search_type_mappings.get(node.value)
            if search_type:
                unfurl.add_to_queue(
                    data_type='descriptor', key='Search Type', value=search_type,
                    hover='Brave Search Type', parent_id=node.node_id, incoming_edge_config=brave_edge)
