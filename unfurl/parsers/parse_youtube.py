# Copyright 2020 Google LLC
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


import time


youtube_edge = {
    'color': {
        'color': '#ff0000'
    },
    'title': 'Youtube Parsing Functions',
    'label': 'YT'
}


def format_seconds(seconds):
    if seconds.endswith('s'):
        seconds = seconds[:-1]
    try:
        seconds = int(seconds)
    except ValueError:
        return None

    if seconds < 60:
        return f'{seconds} seconds'
    elif seconds < 3600:
        return time.strftime('%M:%S', time.gmtime(seconds)) + ' (mm:ss)'
    else:
        return time.strftime('%H:%M:%S', time.gmtime(seconds)) + ' (hh:mm:ss)'


def run(unfurl, node):
    youtube_domains = ['youtube.com', 'youtu.be']
    if any(unfurl.preceding_domain_matches(node, d) for d in youtube_domains):
        if node.key == 't' or node.key == 'time_continue' or node.key == 'start':
            time_formatted = format_seconds(node.value)

            if time_formatted:
                param_text = f'Video will start playing at {time_formatted}'
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=node.value, label=param_text,
                    parent_id=node.node_id, incoming_edge_config=youtube_edge)

        if node.key == 'v' or (node.data_type == 'url.path.segment' and len(node.value) == 11):
            param_text = f'Video ID: {node.value}'
            unfurl.add_to_queue(
                data_type='descriptor', key=None, value=node.value, label=param_text,
                parent_id=node.node_id, incoming_edge_config=youtube_edge)
