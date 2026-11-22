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
import json
import os
import re
import sys
from unfurl import core

JSON_TYPES = ('json', 'json-flat')


def configure_output_encoding():
    """Make the console streams able to carry unfurl's output.

    The text tree is drawn with box-drawing characters, edge labels can be
    emoji, and node values can hold anything that was in the input. Python
    encodes stdout using the locale's encoding, which on Windows is typically
    cp1252 and can represent none of those, so printing a tree raises
    UnicodeEncodeError and the whole run is lost.

    Switch the streams to UTF-8, unless the user set PYTHONIOENCODING, in which
    case they have already said what they want and we leave it alone.
    """
    if os.environ.get('PYTHONIOENCODING'):
        return

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8')
        except (AttributeError, OSError, ValueError):
            # Not a reconfigurable text stream (it may have been replaced with
            # something else entirely). Settle for not raising on characters it
            # cannot represent, if even that much is possible.
            try:
                stream.reconfigure(errors='replace')
            except (AttributeError, OSError, ValueError):
                pass


def json_default(value):
    """Encode a value json.dumps can't (bytes, for instance) as its str() form.

    One odd value shouldn't cost the whole record, and str() keeps it visible.
    """
    return str(value)


def json_record(unfurl_instance, item, output_type, output_filter=None):
    """One input's results as a single line of JSON."""
    record = {'input': item, 'unfurl_version': core.unfurl.__version__}
    if output_type == 'json-flat':
        record['nodes'] = unfurl_instance.generate_flat_json(output_filter=output_filter)
    else:
        record['tree'] = unfurl_instance.generate_tree_json(output_filter=output_filter)
    return json.dumps(record, ensure_ascii=False, default=json_default)


def command_line_interface():
    configure_output_encoding()

    parser = argparse.ArgumentParser(
        description='unfurl takes a URL and expands ("unfurls") it into a directed graph, extracting every '
                    'bit of information from the URL and exposing the obscured.')
    parser.add_argument(
        'what_to_unfurl',
        help='what to unfurl. typically this is a URL, but it also supports integers (timestamps), '
             'encoded protobufs, and more. if this is instead a file path, unfurl will open '
             'that file and process each line in it as a separate input.')
    parser.add_argument(
        '-d', '--detailed',
        help='show more detailed explanations (tree output; JSON output always includes them).',
        action='store_true')
    parser.add_argument(
        '-f', '--filter',
        help='only output lines that match this filter (a regex). for "json", matching nodes '
             'are kept along with their ancestors and marked "matched"; for "json-flat", only '
             'matching nodes are kept.')
    parser.add_argument(
        '-l', '--lookups', help='allow remote lookups to enhance results.',
        action='store_true', default=None)
    parser.add_argument(
        '-o', '--output',
        help='file to save output to (CSV for tree output, JSON Lines for JSON output). if '
             'omitted, output is sent to stdout (typically this means displayed in the console).')
    parser.add_argument(
        '-t', '--type', choices=['tree', *JSON_TYPES], default='tree',
        help='type of output to produce. "json" nests each node inside the node it came from; '
             '"json-flat" lists the nodes with a parent_id. JSON output is one object per input, '
             'one per line.')
    parser.add_argument(
        '-v', '-V', '--version', action='version', version=f'unfurl v{core.unfurl.__version__}')
    args = parser.parse_args()

    if args.filter:
        try:
            re.compile(args.filter)
        except re.error as e:
            parser.error(f'--filter is not a valid regular expression: {e}')

    items_to_unfurl = []

    if os.path.isfile(args.what_to_unfurl):
        with open(args.what_to_unfurl, errors='ignore') as f:
            for input_url in f:
                items_to_unfurl.append(input_url.rstrip())

    else:
        items_to_unfurl.append(args.what_to_unfurl)

    unfurl_instance = core.Unfurl(remote_lookups=args.lookups)

    def unfurl_items():
        """Unfurl each input in turn, yielding (input, instance) with its graph built."""
        for item in items_to_unfurl:
            unfurl_instance.add_to_queue(data_type='url', key=None, value=item)
            unfurl_instance.parse_queue()
            yield item, unfurl_instance
            unfurl_instance.reset_graph_state()

    if args.type in JSON_TYPES:
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as json_file:
                for item, instance in unfurl_items():
                    json_file.write(json_record(instance, item, args.type, args.filter) + '\n')
        else:
            for item, instance in unfurl_items():
                print(json_record(instance, item, args.type, args.filter))

    elif args.output:
        with open(args.output, 'w', newline='', encoding='utf-8') as csv_file:
            csv_writer = csv.writer(csv_file, quoting=csv.QUOTE_ALL)
            csv_writer.writerow(['url', 'unfurled'])
            for item, instance in unfurl_items():
                csv_writer.writerow(
                    [item, instance.generate_text_tree(
                        detailed=args.detailed, output_filter=args.filter)])

    else:
        for item, instance in unfurl_items():
            print(instance.generate_text_tree(
                detailed=args.detailed, output_filter=args.filter))
            print()


if __name__ == '__main__':
    command_line_interface()
