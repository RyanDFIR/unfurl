# Copyright 2019 Google LLC
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
import requests
import torf

magnet_edge = {
    'color': {
        'color': '#CF0024'
    },
    'title': 'Magnet-related Parsing Functions',
    'label': '🧲'
}

known_field_names = {
    'as_': {'name': 'Acceptable Source',
            'description': '<b>as_ (Acceptable Source)</b> is the web link to the file online'},
    'dn': {'name': 'Display Name',
           'description': '<b>dn (Display Name)</b> is the file name to display to the user, for convenience'},
    'kt': {'name': 'Keyword Topic',
           'description': '<b>kt (Keyword Topic)</b> is a more general search,'
                          ' specifying keywords, rather than a particular file'},
    'tr': {'name': 'Address Tracker',
           'description': '<b>tr (Address Tracker)</b> is the tracker URL for BitTorrent downloads'},
    'ws': {'name': 'Web Seed', 'description': '<b>ws (Web Seed)</b> is the payload data served over HTTP(S)'},
    'xl': {'name': 'Exact Length', 'description': '<b>xl (Exact Length)</b> is the size in bytes'},
    'xs': {'name': 'Exact Source',
           'description': '<b>xs (Exact Source)</b> is the P2P link identified by a content-hash'},
    'xt': {'name': 'Exact Topic', 'description': '<b>xt (Exact Topic)</b> is the URN containing file hash'}
}

# Based off https://en.wikipedia.org/wiki/Magnet_URI_scheme#BitTorrent_info_hash_(BTIH)
xt_hash_types = {
    'tree': '<b>Tiger Tree Hash (TTH)</B>. '
            '<br>These hashes are used on Direct Connect and G2 (Gnutella2), among others.',
    'sha1': '<b>Secure Hash Algorithm 1 (SHA-1)</b>. <br>These hash sums are used on gnutella and G2 (Gnutella2).',
    'bitprint': '<b>BitPrint</b>. <br>Such hash sums consist of an SHA-1 Hash, followed by a TTH Hash, '
                'delimited by a point; they are used on gnutella and G2 (Gnutella2).',
    'ed2k': '<b>ED2K (eDonkey2000) hash</b>. <br>These hash sums are used on eDonkey2000.',
    'aich': '<b>Advanced Intelligent Corruption Handler (AICH)</b>. <br>Not formal URNs for Magnet links, such hashes '
            'are used by eDonkey2000 to restore and control the integrity of downloading and already downloaded files.',
    'kzhash': '<b>Kazaa hash</b>. <br>Used on FastTrack, these hash sums are vulnerable to hash collision attacks.',
    'btih': '<b>BitTorrent info hash (BTIH)</b>. <br>These are hex-encoded SHA-1 hash sums of the "info" sections '
            '<br>of BitTorrent metafiles as used by BitTorrent to identify downloadable <br>files or sets of files. '
            'For backwards compatibility with existing <br>links, clients should also support the Base32 encoded '
            'version of the hash.',
    'md5': '<b>Message Digest 5 (MD5)</b>. '
           '<br>Supported by G2 (Gnutella2), such hashes are vulnerable to hash collision attacks.',
}


def check_tracker_statuses(magnet_url):
    try:
        r = requests.get('https://checker.openwebtorrent.com/check', params={'magnet': magnet_url},
                         allow_redirects=False, timeout=3)
    except requests.exceptions.RequestException:
        return {}

    if r.status_code == 200:
        statuses = {}
        content = r.content.decode('utf-8')
        content_json = json.loads(content)
        for tracker_status in content_json.get('extra'):
            if tracker_status.get('tracker'):
                statuses[tracker_status['tracker']] = tracker_status
                statuses[tracker_status['tracker']].pop('tracker')
        return statuses
    else:
        return {}


def run(unfurl, node):
    if node.data_type == 'magnet.tr.list':
        for node_item in node.value:
            unfurl.add_to_queue(
                data_type='magnet.tr.tracker', key=None, value=node_item,
                parent_id=node.node_id, incoming_edge_config=magnet_edge)

    elif node.data_type == 'magnet.tr.tracker':
        if unfurl.stash.get('tracker_statuses'):
            status = unfurl.stash['tracker_statuses'].get(node.value)
            if status:
                status_string = ''
                if status.get('error'):
                    status_string = f'\n⚠️ Error - {status["error"]}'
                if 'seeds' in status:
                    status_string += f'\n🔺Seeds: {status["seeds"]} '
                if 'peers' in status:
                    status_string += f'\n🔻Peers: {status["peers"]}'

                unfurl.add_to_queue(
                    data_type='descriptor', key='Tracker Status', value=status_string,
                    parent_id=node.node_id, incoming_edge_config=magnet_edge)

    elif node.data_type.startswith('magnet') and node.data_type.endswith('list'):
        for node_item in node.value:
            unfurl.add_to_queue(
                data_type='descriptor', key=None, value=node_item,
                parent_id=node.node_id, incoming_edge_config=magnet_edge)

    elif node.data_type == 'magnet.xt':
        urn, xt_type, xt_hash = node.value.split(':', 2)
        if xt_type in xt_hash_types.keys():
            unfurl.add_to_queue(
                data_type='descriptor', key='xt Hash Type', value=xt_type,
                hover=xt_hash_types[xt_type], parent_id=node.node_id,
                incoming_edge_config=magnet_edge)

        unfurl.add_to_queue(
            data_type='xt.hash', key='xt.hash', value=xt_hash,
            hover='This <b>xt hash</b> is used to find and verify the files specified in the Magnet link.',
            parent_id=node.node_id, incoming_edge_config=magnet_edge)

    elif isinstance(node.value, str):
        if node.value.startswith('magnet:?'):

            # TODO: torf won't parse xt.1, xt.2, etc fields, but those are allowed
            # ref: https://en.wikipedia.org/wiki/Magnet_URI_scheme#BitTorrent_info_hash_(BTIH)
            parsed_magnet = torf.Magnet.from_string(node.value)

            for known_field in known_field_names.keys():
                if getattr(parsed_magnet, known_field):
                    field_value = getattr(parsed_magnet, known_field)

                    if isinstance(field_value, torf._utils.MonitoredList):
                        if len(field_value) == 1:
                            unfurl.add_to_queue(
                                data_type=f'magnet.{known_field}', key=known_field_names[known_field]['name'],
                                value=field_value[0],
                                hover=known_field_names[known_field]['description'],
                                parent_id=node.node_id, incoming_edge_config=magnet_edge)
                        elif len(field_value) > 1:
                            unfurl.add_to_queue(
                                data_type=f'magnet.{known_field}.list', key=known_field_names[known_field]['name'],
                                value=list(field_value),
                                hover=known_field_names[known_field]['description'],
                                parent_id=node.node_id, incoming_edge_config=magnet_edge)

                    elif field_value:
                        unfurl.add_to_queue(
                            data_type=f'magnet.{known_field}', key=known_field_names[known_field]['name'],
                            value=field_value,
                            hover=known_field_names[known_field]['description'],
                            parent_id=node.node_id, incoming_edge_config=magnet_edge)

            # TODO: experimental x.* fields
            for field, value in parsed_magnet.__dict__.items():
                if field in [f'_{known}' for known in known_field_names.keys()]:
                    continue
                # 'infohash' is extracted from xt by torf and added as its own thing (for convenience); skip it
                elif field == '_infohash':
                    continue
                elif value:
                    unfurl.add_to_queue(
                        data_type='descriptor', key=field, value=value,
                        parent_id=node.node_id, incoming_edge_config=magnet_edge)

            if unfurl.remote_lookups:
                tracker_statuses = check_tracker_statuses(node.value)
                unfurl.add_to_stash('tracker_statuses', tracker_statuses)
