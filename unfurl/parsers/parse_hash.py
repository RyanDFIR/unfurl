# Copyright 2021 Google LLC
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

import requests
from unfurl import utils

log = logging.getLogger(__name__)

hash_edge = {
    'color': {
        'color': '#4A93AE'
    },
    'title': 'Hash Identification Functions',
    'label': '#'
}

hash_lookup_edge = {
    'color': {
        'color': '#4A93AE'
    },
    'title': 'Hash Lookup Functions',
    'label': '#'
}


def nitrxgen_md5_lookup(value):
    response = requests.get(f'https://www.nitrxgen.net/md5db/{value}', verify=False, timeout=3).text

    if response:
        return response
    else:
        return False


def virustotal_lookup(unfurl, hash_value):

    api_key = unfurl.get_api_key('virustotal')
    if not api_key:
        log.warning('No API key for VirusTotal; skipping lookup.')
        return

    response = requests.get(f'https://www.virustotal.com/api/v3/files/{hash_value}',
                            headers={'x-apikey': api_key}, timeout=3)

    if response.status_code == 200:
        try:
            result = response.json()
            return result['data']['attributes']
        except (ValueError, KeyError, TypeError):
            return False


def decode_cisco_type_7(encoded_text):
    cisco_constant = b"dsfd;kfoA,.iyewrkldJKDHSUBsgvca69834ncxv9873254k;fg87"
    try:
        salt = int(encoded_text[0:2])
    except ValueError:
        # Valid salts should be ints; if not, move on.
        return

    try:
        encoded = bytearray.fromhex(encoded_text[2:])
    except ValueError:
        # Not valid Type 7 encoded then; exit
        return

    plaintext = ''
    for i in range(0, len(encoded)):
        j = (i + salt) % 53
        p = encoded[i] ^ cisco_constant[j]
        plaintext += chr(p)

    # If the result isn't readable as ASCII, call it a false positive and move on without adding a node.
    try:
        _ = plaintext.encode('ascii', errors='strict')
    except UnicodeEncodeError:
        return

    return plaintext


def run(unfurl, node):

    if node.data_type.startswith('uuid'):
        return

    if node.data_type.startswith('hash'):
        if node.data_type == 'hash.md5' and unfurl.remote_lookups:
            hash_plaintext = nitrxgen_md5_lookup(node.value)

            if hash_plaintext:
                unfurl.add_to_queue(
                    data_type='text', key='Plaintext',
                    value=hash_plaintext,
                    hover='Queried Nitrxgen database of MD5 hashes and found a matching plaintext value',
                    parent_id=node.node_id, incoming_edge_config=hash_lookup_edge)

        if node.data_type in ('hash.md5', 'hash.sha-1', 'hash.sha-256') and unfurl.remote_lookups:
            vt_results = virustotal_lookup(unfurl, node.value)
            if vt_results:
                label_text = 'Hash found on VirusTotal'
                if vt_results.get("type_description"):
                    label_text += f'\nFile Type: {vt_results.get("type_description")};'

                if vt_results.get("meaningful_name"):
                    label_text += f'\nName: {vt_results.get("meaningful_name")};'

                if vt_results.get("reputation"):
                    label_text += f'\nReputation: {vt_results.get("reputation")};'

                unfurl.add_to_queue(
                    data_type='text', key='Hash found on VirusTotal',
                    value=None, label=label_text,
                    hover='Queried VirusTotal with the hash value and found a match.',
                    parent_id=node.node_id, incoming_edge_config=hash_lookup_edge)

    else:
        if not isinstance(node.value, str):
            return

        # Filter for values that are only hex chars (A-F,0-9) and contains both a letter and number.
        # This could conceivably filter out valid hashes, but will filter out many more invalid values.
        if not (utils.hex_re.fullmatch(node.value) and
                utils.digits_re.search(node.value) and utils.letters_re.search(node.value)):
            return

        # Cisco "Type 7" password encoding is very flexible, so detecting it is very false positive prone
        # as it isn't a fixed length. However, decoding it is easy, so Unfurl will only "detect" something as
        # using this encoding type if it can also decode it (as a method of verifying it).
        # Ref: https://passlib.readthedocs.io/en/stable/lib/passlib.hash.cisco_type7.html
        cisco_type_7_m = utils.cisco_7_re.fullmatch(node.value)
        if cisco_type_7_m:
            cisco_type_7_plaintext = decode_cisco_type_7(node.value)
            if cisco_type_7_plaintext:
                unfurl.add_to_queue(
                    data_type='text', key='Cisco "Type 7" encoding', value=cisco_type_7_plaintext,
                    label=f'Cisco "Type 7" encoding; plaintext is "{cisco_type_7_plaintext}"',
                    hover='Cisco "Type 7" password encoding is based<br> on XOR and is easily reversible '
                          '[<a hre="https://passlib.readthedocs.io/en/stable/lib/passlib.hash.cisco_type7.html">'
                          'ref</a>].', parent_id=node.node_id, incoming_edge_config=hash_edge)
            return

        if len(node.value) == 32 and node.value[12] == '4':
            # UUIDv4 is very common and it's the same length as an MD5 hash. This might filter out some legitimate
            # MD5 hashes, but it will filter out many more UUIDs. I think the tradeoff is worth it for Unfurl.
            return

        hash_name, hash_hover, new_node_value = None, None, None

        if len(node.value) == 32:
            hash_name = 'MD5'
            hash_hover = f'This is potentially a <b>{hash_name}</b> hash <br>(based on length and character set).'

        if len(node.value) == 40:
            hash_name = 'SHA-1'
            hash_hover = f'This is potentially a <b>{hash_name}</b> hash <br>(based on length and character set).'

        if len(node.value) == 64:
            hash_name = 'SHA-256'
            hash_hover = f'This is potentially a <b>{hash_name}</b> hash <br>(based on length and character set).'

        if len(node.value) == 128:
            hash_name = 'SHA-512'
            hash_hover = f'This is potentially a <b>{hash_name}</b> hash <br>(based on length and character set).'

        if hash_name in ('MD5', 'SHA-1', 'SHA-256'):
            # Pass through the values of three common file hashes for further analysis; don't send on the
            # other types to avoid duplicate processing.
            new_node_value = node.value

        if hash_name:
            unfurl.add_to_queue(
                data_type=f'hash.{hash_name.lower()}', key=f'{hash_name} Hash',
                value=new_node_value, label=f'Potential {hash_name} hash',
                hover=hash_hover, parent_id=node.node_id, incoming_edge_config=hash_edge)
