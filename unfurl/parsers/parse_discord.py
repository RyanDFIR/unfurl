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

from unfurl import utils

import logging
log = logging.getLogger(__name__)

discord_edge = {
    'color': {
        'color': '#7289da'
    },
    'title': 'Discord Snowflake',
    'label': '❄'
}


def create_discord_id(timestamp=None, days_ahead=None, worker_id=0, process_id=0, increment=0):
    id_timestamp = utils.create_epoch_seconds_timestamp(
        iso_timestamp=timestamp, days_ahead=days_ahead, offset=1420070400)

    # Multiply the timestamp by 1000, as Discord uses a millisecond timestamp
    timestamp_bits = utils.set_bits(id_timestamp * 1000, 22)
    worker_id_bits = utils.set_bits(worker_id, 17)
    process_id_bits = utils.set_bits(process_id, 12)
    increment_bits = utils.set_bits(increment, 0)

    return int(timestamp_bits + worker_id_bits + process_id_bits + increment_bits)


def parse_discord_snowflake(unfurl, node):
    try:
        snowflake = int(node.value)
    # Some non-integer values can appear here (like @me) instead; abandon parsing
    except ValueError:
        return

    try:
        # Ref: https://discordapp.com/developers/docs/reference#snowflakes
        timestamp = (snowflake >> 22) + 1420070400000
        worker_id = (snowflake & 0x3E0000) >> 17
        internal_process_id = (snowflake & 0x1F000) >> 12
        increment = snowflake & 0xFFF

    except Exception as e:
        log.exception(f'Exception parsing Discord snowflake: {e}')
        return

    node.hover = 'Discord Snowflakes are unique, time-based IDs. ' \
                 '<a href="https://discordapp.com/developers/docs/reference#snowflakes" target="_blank">[ref]</a>'

    unfurl.add_to_queue(
        data_type='epoch-milliseconds', key=None, value=timestamp, label=f'Timestamp:\n{timestamp}',
        hover='The first value in a Discord Snowflake is a timestamp associated with object creation',
        parent_id=node.node_id, incoming_edge_config=discord_edge)

    unfurl.add_to_queue(
        data_type='integer', key=None, value=worker_id, label=f'Worker ID: {worker_id}',
        hover='The second value in a Discord Snowflake is the internal worker ID',
        parent_id=node.node_id, incoming_edge_config=discord_edge)

    unfurl.add_to_queue(
        data_type='integer', key=None, value=internal_process_id, label=f'Process ID: {internal_process_id}',
        hover='The third value in a Discord Snowflake is the internal process ID',
        parent_id=node.node_id, incoming_edge_config=discord_edge)

    unfurl.add_to_queue(
        data_type='integer', key=None, value=increment, label=f'Increment: {increment}',
        hover='For every ID that is generated on that process, this number is incremented',
        parent_id=node.node_id, incoming_edge_config=discord_edge)


def run(unfurl, node):

    # Known patterns from main Discord site
    discord_domains = ['discordapp.com', 'discordapp.net', 'discord.com']
    if any(unfurl.preceding_domain_matches(node, d) for d in discord_domains):
        # Make sure a potential Snowflake is reasonable: between 2015-02-01
        # (shortly before Discord launched) & a year from now
        min_reasonable_id = create_discord_id('2015-02-01T00:00:00')
        max_reasonable_id = create_discord_id(days_ahead=365)

        if node.data_type == 'url.path.segment':
            # Viewing a channel on a server
            # Ex: https://discordapp.com/channels/427876741990711298/551531058039095296
            if unfurl.check_sibling_nodes(node, data_type='url.path.segment', key=1, value='channels'):
                if node.key == 2:
                    unfurl.add_to_queue(
                        data_type='description', key=None, value=None, label='Server ID',
                        hover='The timestamp in the associated Discord Snowflake is the time of Server creation',
                        parent_id=node.node_id, incoming_edge_config=discord_edge)
                    parse_discord_snowflake(unfurl, node)

                elif node.key == 3:
                    unfurl.add_to_queue(
                        data_type='description', key=None, value=None, label='Channel ID',
                        hover='The timestamp in the associated Discord Snowflake is the time of Channel creation '
                              'on the given Server',
                        parent_id=node.node_id, incoming_edge_config=discord_edge)
                    parse_discord_snowflake(unfurl, node)

                # Linking to a specific message
                # Ex: https://discordapp.com/channels/427876741990711298/537760691302563843/643183730227281931
                elif node.key == 4:
                    unfurl.add_to_queue(
                        data_type='description', key=None, value=None, label='Message ID',
                        hover='The timestamp in the associated Discord Snowflake is the time the Message was sent',
                        parent_id=node.node_id, incoming_edge_config=discord_edge)
                    parse_discord_snowflake(unfurl, node)

            # File Attachment URLs
            # Ex: https://cdn.discordapp.com/attachments/622136585277931532/626893414490832918/asdf.png
            elif unfurl.check_sibling_nodes(node, data_type='url.path.segment', key=1, value='attachments'):
                if node.key == 2:
                    unfurl.add_to_queue(
                        data_type='description', key=None, value=None, label='Channel ID',
                        hover='The timestamp in the associated Discord Snowflake is the time of channel creation',
                        parent_id=node.node_id, incoming_edge_config=discord_edge)
                    parse_discord_snowflake(unfurl, node)

                elif node.key == 3:
                    unfurl.add_to_queue(
                        data_type='description', key=None, value=None, label='File ID',
                        hover='The timestamp in the associated Discord Snowflake is the time the attachment '
                              'was uploaded.',
                        parent_id=node.node_id, incoming_edge_config=discord_edge)
                    parse_discord_snowflake(unfurl, node)

                elif node.key == 4:
                    unfurl.add_to_queue(
                        data_type='description', key=None, value=None, label='Attachment File Name',
                        parent_id=node.node_id, incoming_edge_config=discord_edge)

            # Check if the node's value would correspond to a Snowflake with a plausible timestamp
            elif unfurl.check_if_int_between(node.value, min_reasonable_id, max_reasonable_id):
                parse_discord_snowflake(unfurl, node)

        # Snowflakes also show up outside URL paths (query values, JSON payloads in
        # tokens, etc.); decode anything under a Discord domain that looks like one.
        elif unfurl.check_if_int_between(node.value, min_reasonable_id, max_reasonable_id):
            parse_discord_snowflake(unfurl, node)
