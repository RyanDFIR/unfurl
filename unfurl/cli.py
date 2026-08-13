#!/usr/bin/env python3

# Copyright 2024 Ryan Benson
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

import argparse
import csv
import os
from unfurl import core


def command_line_interface():
    parser = argparse.ArgumentParser(
        description='unfurl takes a URL and expands ("unfurls") it into a directed graph, extracting every '
                    'bit of information from the URL and exposing the obscured.')
    parser.add_argument(
        'what_to_unfurl',
        help='what to unfurl. typically this is a URL, but it also supports integers (timestamps), '
             'encoded protobufs, and more. if this is instead a file path, unfurl will open '
             'that file and process each line in it as a separate input.')
    parser.add_argument(
        '-d', '--detailed', help='show more detailed explanations.', action='store_true')
    parser.add_argument(
        '-f', '--filter', help='only output lines that match this filter.')
    parser.add_argument(
        '-l', '--lookups', help='allow remote lookups to enhance results.', action='store_true')
    parser.add_argument(
        '-o', '--output',
        help='file to save output (as CSV) to. if omitted, output is sent to '
             'stdout (typically this means displayed in the console).')
    parser.add_argument(
        '-t', '--type', help='Type of output to produce', choices=['tree', 'json'], default='tree'
    )
    parser.add_argument(
        '-v', '-V', '--version', action='version', version=f'unfurl v{core.unfurl.__version__}')
    args = parser.parse_args()

    items_to_unfurl = []

    if os.path.isfile(args.what_to_unfurl):
        with open(args.what_to_unfurl, errors='ignore') as f:
            for input_url in f:
                items_to_unfurl.append(input_url.rstrip())

    else:
        items_to_unfurl.append(args.what_to_unfurl)

    if args.output:
        with open(args.output, 'w', newline='', encoding='utf-8') as csv_file:
            csv_writer = csv.writer(csv_file, quoting=csv.QUOTE_ALL)
            csv_writer.writerow(['url', 'unfurled'])

            unfurl_instance = core.Unfurl(remote_lookups=args.lookups)
            for item in items_to_unfurl:
                unfurl_instance.add_to_queue(
                    data_type='url', key=None,
                    value=item)
                unfurl_instance.parse_queue()
                if args.type == 'json':
                    csv_writer.writerow(
                        [item, unfurl_instance.generate_full_json()])
                else:
                    csv_writer.writerow(
                        [item, unfurl_instance.generate_text_tree(
                            detailed=args.detailed,
                            output_filter=args.filter)])
                unfurl_instance.reset_graph_state()

    else:
        unfurl_instance = core.Unfurl(remote_lookups=args.lookups)
        for item in items_to_unfurl:
            unfurl_instance.add_to_queue(
                data_type='url', key=None,
                value=item)
            unfurl_instance.parse_queue()

            if args.type == 'json':
                print(unfurl_instance.generate_full_json())
            else:
                print(unfurl_instance.generate_text_tree(
                    detailed=args.detailed, output_filter=args.filter))
            print()
            unfurl_instance.reset_graph_state()


if __name__ == '__main__':
    command_line_interface()
