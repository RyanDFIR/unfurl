# Copyright 2020 Moshe Kaplan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License athttps://channel9.msdn.com/Shows/Going+Deep?page=20
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

yahoo = {
    'color': {
        'color': '#6001d2'
    },
    'title': 'Yahoo Search-related Parsing Functions',
    'label': 'Y!'
}


def run(unfurl, node):
    if node.data_type == 'url.query.pair':
        if unfurl.preceding_domain_matches(node, 'yahoo.com'):

            if node.key == 'durs':
                durs_mappings = {
                    'short': 'Short (less than 5 minutes)',
                    'medium': 'Medium (5-20 minutes)',
                    'long': 'Long (more than 20 minutes)',
                }
                value = durs_mappings.get(node.value, 'Unknown')
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Video Duration: {value}',
                    hover='Yahoo Video Search Duration', parent_id=node.node_id, incoming_edge_config=yahoo)

            elif node.key == 'imgc':
                imgc_mappings = {
                    'black': 'Black',
                    'blue': 'Blue',
                    'brown': 'Brown',
                    'bw': 'Black & White',
                    'gray': 'Gray',
                    'green': 'Green',
                    'orange': 'Orange',
                    'pink': 'Pink',
                    'purple': 'Purple',
                    'red': 'Red',
                    'teal': 'Teal',
                    'white': 'White',
                    'yellow': 'Yellow',

                }
                value = imgc_mappings.get(node.value, 'Unknown')
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Image Size: {value}',
                    hover='Yahoo Image Search Size', parent_id=node.node_id, incoming_edge_config=yahoo)

            elif node.key == 'imgsz':
                imgsz_mappings = {
                    'small': 'Small',
                    'medium': 'Medium',
                    'large': 'Large',
                }
                value = imgsz_mappings.get(node.value, 'Unknown')
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Image Size: {value}',
                    hover='Yahoo Image Search Size', parent_id=node.node_id, incoming_edge_config=yahoo)

            elif node.key == 'imgty':
                imgty_mappings = {
                    'clipart': 'Clipart',
                    'face': 'Face',
                    'gif': 'GIF',
                    'graphics': 'Graphics',
                    'linedrawing': 'Line Drawing',
                    'nonportrait': 'Non Portrait',
                    'photo': 'Photo',
                    'portrait': 'Portrait',
                }
                value = imgty_mappings.get(node.value, 'Unknown')
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Image Type: {value}',
                    hover='Yahoo Image Search Type', parent_id=node.node_id, incoming_edge_config=yahoo)

            elif node.key == 'p':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Search Query: {node.value}',
                    hover='Terms used in the Yahoo search', parent_id=node.node_id, incoming_edge_config=yahoo)

            elif node.key == 'vage':
                vage_mappings = {
                    'day': 'Past 24 hours',
                    'month': 'Past month',
                    'year': 'Past year',
                }
                value = vage_mappings.get(node.value, 'Unknown')
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Video Duration: {value}',
                    hover='Yahoo Video Search Duration', parent_id=node.node_id, incoming_edge_config=yahoo)
