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

import json

import logging
log = logging.getLogger(__name__)

json_edge = {
    'color': {
        'color': '#A7A7A7'
    },
    'title': 'JSON Parsing Functions',
    'label': 'JSON'
}

json_hover_text = ('This was parsed as JavaScript Object Notation (JSON), <br>'
                   'which uses human-readable text to store and transmit data objects')


def run(unfurl, node):

    if node.data_type in ('url.query.pair', 'string'):
        try:
            json_obj = json.loads(node.value)
            assert isinstance(json_obj, (dict, list)), 'Loaded object should be a dict or a list'

        except json.JSONDecodeError:
            return

        except AssertionError:
            # Likely a "valid" JSON of 23 or 1 or some single value; not what we want
            return

        try:
            if isinstance(json_obj, dict):
                for json_key, json_value in json_obj.items():
                    unfurl.add_to_queue(
                        data_type='json', key=json_key, value=json_value, label=f'{json_key}: {json_value}',
                        hover=json_hover_text, parent_id=node.node_id, incoming_edge_config=json_edge)
            elif isinstance(json_obj, list):
                for item in json_obj:
                    unfurl.add_to_queue(
                        data_type='json', key=None, value=item, label=f'[{len(item)} items]',
                        hover=json_hover_text, parent_id=node.node_id, incoming_edge_config=json_edge)

        except Exception as e:
            log.exception(f'Exception parsing JSON string: {e}')

    elif node.data_type == 'json':
        node_value = node.value
        if isinstance(node_value, str):
            try:
                node_value = json.loads(node_value)
            except json.JSONDecodeError:
                pass

        if isinstance(node_value, dict):
            try:
                for key, value in node_value.items():
                    if isinstance(value, dict):
                        unfurl.add_to_queue(
                            data_type='json', key=key, value=value, label=f'{key}: {{{len(value)} keys}}',
                            hover='This was parsed as JavaScript Object Notation (JSON), <br>'
                                  'which uses human-readable text to store and transmit data objects',
                            parent_id=node.node_id, incoming_edge_config=json_edge)
                    elif isinstance(value, list):
                        unfurl.add_to_queue(
                            data_type='json', key=key, value=value, label=f'{key}: [{len(value)} items]',
                            hover='This was parsed as JavaScript Object Notation (JSON), <br>'
                                  'which uses human-readable text to store and transmit data objects',
                            parent_id=node.node_id, incoming_edge_config=json_edge)
                    else:
                        unfurl.add_to_queue(
                            data_type='json', key=key, value=value, label=f'{key}: {value}',
                            hover='This was parsed as JavaScript Object Notation (JSON), <br>'
                                  'which uses human-readable text to store and transmit data objects',
                            parent_id=node.node_id, incoming_edge_config=json_edge)

            except Exception as e:
                log.exception(f'Exception parsing JSON: {e}')

        elif isinstance(node_value, list):
            try:
                for value in node_value:
                    unfurl.add_to_queue(
                        data_type='json', key=None, value=value, hover=json_hover_text,
                        parent_id=node.node_id, incoming_edge_config=json_edge)

            except Exception as e:
                log.exception(f'Exception parsing JSON: {e}')
