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

from unfurl import utils

import logging
log = logging.getLogger(__name__)

twitter_snowflake_edge = {
    'color': {
        'color': '#1da1f2'
    },
    'title': 'Twitter Snowflake',
    'label': '❄'
}

twitter_edge = {
    'color': {
        'color': '#1da1f2'
    },
    'title': 'Twitter Parsing Functions',
    'label': '@'
}


def parse_twitter_snowflake(unfurl, node, encoding_type='integer', on_twitter=True):
    # Ref: https://blog.twitter.com/engineering/en_us/a/2010/announcing-snowflake.html
    #      https://ws-dl.blogspot.com/2019/08/2019-08-03-tweetedat-finding-tweet.html
    if encoding_type == 'integer':
        try:
            snowflake = int(node.value)
            timestamp = (snowflake >> 22) + 1288834974657
            machine_id = (snowflake & 0x3FF000) >> 12
            sequence = snowflake & 0xFFF
            assert 0 <= sequence <= 4096, \
                f'Sequence number should be between 0 and 4096; got {sequence}'

        except Exception as e:
            log.exception(f'Exception parsing snowflake: {e}')
            return

    # Ref: https://www.hackerfactor.com/blog/index.php?/archives/634-Name-Dropping.html
    # So far, I've only observed this in file attachments (images) to tweets. This format
    # also has three extra bytes at the "end" (LSBs); I don't know their function.
    elif encoding_type == 'base64':
        snowflake_bytes = utils.try_urlsafe_b64_decode(node.value, min_length=8)
        if snowflake_bytes is None:
            return

        try:
            snowflake_int = int.from_bytes(snowflake_bytes, 'big')
            timestamp = (snowflake_int >> 46) + 1288834974657
            machine_id = (snowflake_int & 0x3FF000000000) >> 36
            sequence = (snowflake_int & 0xFFF000000) >> 24
            assert 0 <= sequence <= 4096, \
                f'Sequence number should be between 0 and 4096; got {sequence}'

            # Since we are trying to parse things that might not be valid, make sure the decoded
            # timestamp is "reasonable" (between 2010-11 (the Snowflake epoch) and 2030-01
            if not 1288834974657 < timestamp < 1893456000000:
                return

        except Exception as e:
            log.warning(f'Exception parsing snowflake: {e}')
            return
    else:
        return

    if on_twitter:
        node.hover = 'Twitter Snowflakes are time-based IDs. ' \
                     '<a href="https://blog.twitter.com/engineering/en_us/a/2010/announcing-snowflake.html" ' \
                     'target="_blank">[ref]</a>'

    else:
        unfurl.add_to_queue(
            data_type='descriptor', key=None, value='File may originally be from Twitter (based on file name)',
            hover='File name is consistent with Twitter\'s naming scheme for image attachments. The name also contains '
                  'an embedded timestamp.', parent_id=node.node_id, incoming_edge_config=twitter_snowflake_edge)

    unfurl.add_to_queue(
        data_type='epoch-milliseconds', key=None, value=timestamp, label=f'Timestamp: {timestamp}',
        hover='The first value in a Twitter Snowflake is a timestamp',
        parent_id=node.node_id, incoming_edge_config=twitter_snowflake_edge)

    unfurl.add_to_queue(
        data_type='integer', key=None, value=machine_id, label=f'Machine ID: {machine_id}',
        hover='The second value in a Twitter Snowflake is the machine ID. A machine ID can be further divided '
              'into a datacenter ID (first 5 bits) and worker ID (last 5 bits)',
        parent_id=node.node_id, incoming_edge_config=twitter_snowflake_edge)

    unfurl.add_to_queue(
        data_type='integer', key=None, value=sequence, label=f'Sequence: {sequence}',
        hover='For every ID that is generated, this number is incremented and rolls over every 4096',
        parent_id=node.node_id, incoming_edge_config=twitter_snowflake_edge)

def create_twitter_id(timestamp=None, days_ahead=None, sequence=1, machine_id=1):
    id_timestamp = utils.create_epoch_seconds_timestamp(iso_timestamp=timestamp, days_ahead=days_ahead, offset=1288834974.657)

    # Multiply the timestamp by 1000, as Twitter used a millisecond timestamp
    timestamp_bits = utils.set_bits(id_timestamp*1000, 22)
    machine_id_bits = utils.set_bits(machine_id, 12)
    sequence_bits = utils.set_bits(sequence, 0)

    return int(timestamp_bits + machine_id_bits + sequence_bits)

def run(unfurl, node):
    preceding_domain = unfurl.find_preceding_domain(node)
    if preceding_domain in ['twitter.com', 'mobile.twitter.com', 'x.com', 'mobile.x.com']:
        # Make sure potential snowflake is reasonable: between 2015-02-01 & a year from now
        min_reasonable_id = create_twitter_id('2015-02-01T00:00:00')
        max_reasonable_id = create_twitter_id(days_ahead=365)
        if node.data_type == 'url.path.segment' and \
                unfurl.check_if_int_between(node.value, min_reasonable_id, max_reasonable_id):
            parse_twitter_snowflake(unfurl, node)

        # Based on information found in a Javascript file on Twitter's website. Thanks 2*yo (https://github.com/2xyo)!
        # ref:
        #   https://web.archive.org/web/20220924170519/https://abs.twimg.com/responsive-web/client-web/main.ea5f3cf9.js
        elif node.data_type == 'url.query.pair' and node.key == 's':
            sharing_codes = {
                '01': ' from an Android using SMS',
                '02': ' from an Android using Email',
                '03': ' from an Android using Gmail',
                '04': ' from an Android using Facebook',
                '05': ' from an Android using WeChat',
                '06': ' from an Android using Line',
                '07': ' from an Android using FBMessenger',
                '08': ' from an Android using WhatsApp',
                '09': ' from an Android using Other',
                '10': ' from iOS using Messages or SMS',
                '11': ' from iOS using Email',
                '12': ' from iOS using Other',
                '13': ' from an Android using Download',
                '14': ' from iOS using Download',
                '15': ' from an Android using Hangouts',
                '16': ' from an Android using Twitter DM',
                '17': ' from Twitter Web using Email',
                '18': ' from Twitter Web using Download',
                '19': ' from an Android using Copy',
                '20': ' from Twitter Web using Copy',
                '21': ' from iOS using Copy',
                '22': ' from iOS using Snapchat',
                '23': ' from an Android using Snapchat',
                '24': ' from iOS using WhatsApp',
                '25': ' from iOS using FBMessenger',
                '26': ' from iOS using Facebook',
                '27': ' from iOS using Gmail',
                '28': ' from iOS using Telegram',
                '29': ' from iOS using Line',
                '30': ' from iOS using Viber',
                '31': ' from an Android using Slack',
                '32': ' from an Android using Kakao',
                '33': ' from an Android using Discord',
                '34': ' from an Android using Reddit',
                '35': ' from an Android using Telegram',
                '36': ' from an Android using Instagram',
                '37': ' from an Android using Daum',
                '38': ' from iOS using Instagram',
                '39': ' from iOS using LinkedIn',
                '40': ' from an Android using LinkedIn',
                '41': ' from Gryphon using Copy',
                '42': ' from an iPhone using SMS',
                '43': ' from an iPhone using Email',
                '44': ' from an iPhone using Other',
                '45': ' from an iPhone using Download',
                '46': ' from an iPhone using Copy',
                '47': ' from an iPhone using Snapchat',
                '48': ' from an iPhone using WhatsApp',
                '49': ' from an iPhone using FBMessenger',
                '50': ' from an iPhone using Facebook',
                '51': ' from an iPhone using Gmail',
                '52': ' from an iPhone using Telegram',
                '53': ' from an iPhone using Line',
                '54': ' from an iPhone using Viber',
                '55': ' from an iPhone using Instagram',
                '56': ' from an iPhone using LinkedIn',
                '57': ' from an iPad using SMS',
                '58': ' from an iPad using Email',
                '59': ' from an iPad using Other',
                '60': ' from an iPad using Download',
                '61': ' from an iPad using Copy',
                '62': ' from an iPad using Snapchat',
                '63': ' from an iPad using WhatsApp',
                '64': ' from an iPad using FBMessenger',
                '65': ' from an iPad using Facebook',
                '66': ' from an iPad using Gmail',
                '67': ' from an iPad using Telegram',
                '68': ' from an iPad using Line',
                '69': ' from an iPad using Viber',
                '70': ' from an iPad using Instagram',
                '71': ' from an iPad using LinkedIn'
            }

            unfurl.add_to_queue(
                data_type='descriptor', key=None, value=f'Tweet was shared{sharing_codes.get(node.value, "")}',
                hover='The sharing codes are based on a JS file from Twitter\'s website '
                      '<a href="https://github.com/obsidianforensics/unfurl/issues/162" target="_blank">[ref]</a>',
                parent_id=node.node_id, incoming_edge_config=twitter_edge)

    # I've only seen `pbs.twimg.com`, but there could be other subdomains used for image attachments to tweets
    elif preceding_domain == 'twimg.com' or preceding_domain.endswith('.twimg.com'):
        if node.data_type == 'url.path.segment':
            # Viewing an image attached to a tweet
            # Ex: https://pbs.twimg.com/media/ErD8xv0VkAIBJe7?format=jpg&name=medium
            if unfurl.check_sibling_nodes(node, data_type='url.path.segment', key=1, value='media'):
                if node.key == 2:
                    parse_twitter_snowflake(unfurl, node, encoding_type='base64')

    # Images from Twitter can be viewed in other ways than the above (including being saved/downloaded and then
    # uploaded somewhere else). The file name pattern appears fairly unique, so if we see a file name that matches it
    # and decodes to a "reasonable" timestamp, show it in the graph.
    if node.data_type == 'file.name' and len(node.value) == 15:
        on_twitter = preceding_domain == 'twimg.com' or preceding_domain.endswith('.twimg.com')
        parse_twitter_snowflake(unfurl, node, encoding_type='base64', on_twitter=on_twitter)
