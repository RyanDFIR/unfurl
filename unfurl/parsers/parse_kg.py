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

import logging
import re

import requests

log = logging.getLogger(__name__)

# Knowledge Graph IDs are a short lowercase token after /m/ (Freebase MIDs, like /m/050zjwr)
# or /g/ (like /g/11c1xn_x4c). Matching only the prefix also sent whole URL paths to Google,
# such as ChatGPT's /g/g-p-{project}/c/{conversation}.
kg_id_re = re.compile(r'/[mg]/[0-9a-z_]{2,12}')

kg_edge = {
    'color': {
        'color': 'green'
    },
    'title': 'Google Knowledge Graph Lookup Functions',
    'label': '🧠'
}


def run(unfurl, node):
    if not unfurl.remote_lookups or not isinstance(node.value, str):
        return

    if node.data_type.startswith('url') or not kg_id_re.fullmatch(node.value):
        return

    api_key = unfurl.get_api_key('google_kg')
    if not api_key:
        log.warning('No API key for Google Knowledge Graph; skipping lookup.')
        return

    try:
        response = requests.get(
            'https://kgsearch.googleapis.com/v1/entities:search',
            params={'ids': node.value, 'limit': 10, 'key': api_key}, timeout=3)
        response.raise_for_status()
        response = response.json()
    # The exception text from requests includes the request URL, API key and all, so log
    # only the status code or the exception type.
    except requests.HTTPError as e:
        log.warning(f'Google Knowledge Graph lookup failed: HTTP {e.response.status_code}')
        return
    except Exception as e:
        log.warning(f'Google Knowledge Graph lookup failed: {type(e).__name__}')
        return

    for element in response.get('itemListElement', []):
        if element['result'].get('name'):
            value_text = element['result']['name']
            if element['result'].get('description'):
                value_text = f'{value_text}  ({element["result"]["description"]})'

            unfurl.add_to_queue(
                data_type='google.knowledge_graph', key='Name', value=value_text,
                hover='Value was retrieved from the Google Knowledge Graph', parent_id=node.node_id,
                incoming_edge_config=kg_edge)
