#!/usr/bin/env python3

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

import configparser
import logging
import importlib
import networkx
import os
import queue
import re
import unfurl.parsers

from pymispwarninglists import WarningLists
from unfurl import utils

log = logging.getLogger(__name__)


def config_paths():
    """Ordered list of config files to read; earlier files are overridden by later ones.

    "unfurl.ini" is tracked in git and ships with empty API keys, so it works as a
    template for anyone cloning the repo. "unfurl.local.ini" is gitignored and holds
    real keys and machine-specific settings. Each is looked for both alongside the
    installed/cloned package and in the current working directory, so Unfurl finds its
    config when run from somewhere other than the repo root.

    All templates are listed before all local files so that a local value always wins,
    even over a template in a more specific directory — a template's empty API keys
    must never clobber real ones.
    """
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    search_dirs = [package_root, os.getcwd()]
    return ([os.path.join(d, 'unfurl.ini') for d in search_dirs]
            + [os.path.join(d, 'unfurl.local.ini') for d in search_dirs])


def load_config():
    """Read Unfurl's layered config. configparser silently skips files that don't exist."""
    config = configparser.ConfigParser()
    config.read(config_paths())
    return config


# The MISP warninglists are immutable reference data bundled with the package, and
# parsing them costs about half a second. Loaded once per process; see
# Unfurl.build_known_domain_lists().
_known_domain_lists = None

# Union of the top-sites lists, derived from the above and therefore just as immutable.
# Also process-wide: rebuilding it per instance cost ~1.3 ms of pure waste on every
# request the web app served. See Unfurl.domain_in_top_sites_list().
_top_sites_domains = None

REMOTE_LOOKUPS_ENV_VAR = 'UNFURL_REMOTE_LOOKUPS'

# Enabling remote lookups from the environment is worth announcing, but the web app
# builds an Unfurl per request, so say it once per process rather than every time.
_warned_about_env_remote_lookups = False


def remote_lookups_from_env():
    """Whether UNFURL_REMOTE_LOOKUPS enables lookups, or None if it isn't set.

    Accepts the same values the config file does ("true"/"yes"/"on"/"1" and their
    negatives). An unset or empty variable means "not configured" and defers to the
    config files; a value that can't be interpreted fails safe to disabled instead,
    since ignoring it would quietly hand the decision to a config file that may enable
    lookups.
    """
    global _warned_about_env_remote_lookups

    raw = os.environ.get(REMOTE_LOOKUPS_ENV_VAR)
    if not raw:
        return None

    enabled = configparser.ConfigParser.BOOLEAN_STATES.get(raw.strip().lower())
    if enabled is None:
        log.warning(
            f'Could not interpret {REMOTE_LOOKUPS_ENV_VAR}="{raw}" as true/false; '
            f'leaving remote lookups disabled.')
        return False

    if enabled and not _warned_about_env_remote_lookups:
        log.warning(
            f'Remote lookups enabled via {REMOTE_LOOKUPS_ENV_VAR}; data from the input '
            f'will be sent to third-party APIs.')
        _warned_about_env_remote_lookups = True

    return enabled


def resolve_remote_lookups(explicit=None, config=None):
    """Decide whether remote lookups are allowed, disabled unless something enables them.

    Precedence: an explicit True *or False* from the caller, then UNFURL_REMOTE_LOOKUPS,
    then the config files. The environment beats the config file so that a container can
    enable lookups without editing the mounted unfurl.ini.

    `explicit=None` means "not specified" and defers to the environment and config, which
    matches remote_lookups_from_env(). This used to test `if explicit:`, so False was
    indistinguishable from unspecified and `Unfurl(remote_lookups=False)` could not turn
    lookups off -- on a machine with them enabled in unfurl.ini it silently made real
    requests. Callers that want to defer must pass None, not False.
    """
    if explicit is not None:
        return bool(explicit)

    from_env = remote_lookups_from_env()
    if from_env is not None:
        return from_env

    if config is None:
        config = load_config()

    if config.has_section('UNFURL_APP'):
        try:
            return bool(config['UNFURL_APP'].getboolean('remote_lookups', False))
        # If we can't interpret it as a boolean, fail "safe" to not allowing lookups
        except ValueError:
            return False

    return False


def preload_reference_data():
    """Parse and cache the bundled reference data before serving any traffic.

    Building the warninglists takes roughly 0.4s, and the top-sites union another few
    milliseconds. Both are process-wide caches, so the cost is paid once -- but by
    default it is paid by whichever request happens to construct the first Unfurl.

    On a scale-to-zero host such as Cloud Run that request is a real person waiting
    through a cold start. Calling this during startup moves the work to where the
    platform expects it, and where Cloud Run's startup CPU boost applies.

    Safe to call more than once; subsequent calls are no-ops.
    """

    Unfurl(remote_lookups=False).domain_in_top_sites_list('example.com')


class Unfurl:
    def __init__(self, remote_lookups=None):
        self.graph = networkx.DiGraph()
        self.nodes = {}
        self.edges = []
        self.total_nodes = 0
        self.next_id = 1
        self.queue = queue.Queue()
        self.api_keys = {}
        self.known_domain_lists = None
        self.node_limit = 500
        # How many times one (data_type, value) may appear along a single line of
        # ancestry before Unfurl stops expanding it. See find_repeated_ancestor().
        self.max_repeated_ancestors = 2
        self.stash = {}

        config = load_config()
        if config.has_section('API_KEYS'):
            self.api_keys = config['API_KEYS']

        self.remote_lookups = resolve_remote_lookups(explicit=remote_lookups, config=config)

        if not self.known_domain_lists:
            self.build_known_domain_lists()

    @staticmethod
    def api_key_env_var(name):
        """The environment variable holding the API key for config key `name`.

        Namespaced and uppercased by convention: "virustotal" -> UNFURL_VIRUSTOTAL_API_KEY.
        Env var names are case-sensitive everywhere except Windows, so a bare lowercase
        name works on one platform and silently fails on another.
        """
        return f'UNFURL_{name.upper()}_API_KEY'

    def get_api_key(self, name):
        """Return the configured API key called `name`, or None if there isn't one.

        Resolution order: the config files, then the namespaced environment variable,
        then the bare lowercase environment variable older versions used.

        An empty value counts as "not set" at every level. That matters because the
        tracked unfurl.ini template lists every key with an empty value, so treating one
        as a real key would stop the environment from ever being consulted.
        """
        configured = self.api_keys.get(name)
        if configured:
            return configured

        namespaced = os.environ.get(self.api_key_env_var(name))
        if namespaced:
            return namespaced

        # Deprecated, but still honored: pip installs ship no unfurl.ini, so for those
        # users a bare lowercase env var was the only way to supply a key that worked.
        legacy = os.environ.get(name)
        if legacy:
            log.warning(
                f'Using deprecated environment variable "{name}"; rename it to '
                f'"{self.api_key_env_var(name)}".')
            return legacy

        return None

    class Node:
        def __init__(self, node_id, data_type, key, value, label=None, hover=None,
                     parent_id=None, incoming_edge_config=None, extra_options=None):
            self.node_id = node_id
            self.data_type = data_type
            self.key = key
            self.value = value
            self.label = label
            self.hover = hover
            self.parent_id = parent_id
            self.incoming_edge_config = incoming_edge_config
            self.extra_options = extra_options

            if self.label is None:
                if self.key and self.value:
                    self.label = f'{self.key}: {self.value}'
                elif self.value:
                    self.label = self.value
                elif self.key:
                    self.label = f'{self.key}:'

        def __repr__(self):
            return str(self.__dict__)

        def to_dict(self):
            return self.__dict__

    def add_to_stash(self, key: str, value: dict) -> None:
        if not self.stash.get(key):
            self.stash[key] = value
        else:
            self.stash[key] = self.stash[key] | value

    def build_known_domain_lists(self):
        """Load the MISP warninglists, reusing the result across instances.

        WarningLists() parses ~90 bundled JSON files, some with a million entries, and
        takes about half a second -- effectively all of the cost of constructing an
        Unfurl. It was previously rebuilt for every instance, which is invisible for a
        single CLI run but dominates anything that makes many: the test suite spends
        minutes on it, and the web app pays it on every request.

        The lists are immutable reference data shipped with the package, so one copy is
        shared. Instances only read from it.
        """

        global _known_domain_lists

        if _known_domain_lists is None:
            warning_lists_dict = WarningLists().warninglists

            # This list has some values I think may confuse users (t.co, drive.google.com, etc), as most things on
            # those domains are not security blog-related, so I'm removing it.
            warning_lists_dict.pop('List of known security providers/vendors blog domain', 1)
            warning_lists_dict.pop('OSINT.DigitalSide.IT Warning List', 1)

            # And the capitalization was bothering me, so fixing it here.
            warning_lists_dict['List of known google domains'].name = 'List of known Google domains'
            warning_lists_dict['List of known microsoft domains'].name = 'List of known Microsoft domains'

            _known_domain_lists = warning_lists_dict

        self.known_domain_lists = _known_domain_lists

    # Popularity lists tight enough to mean "this is a destination people visit".
    # Deliberately excludes the 1M-entry lists: at that depth the list contains most of
    # the web, including plenty of link shorteners, so membership stops being a signal.
    TOP_SITES_LIST_PREFIXES = ('Top 1000', 'Top 500 ', 'Top 10 000', 'Top 10K')

    def domain_in_top_sites_list(self, domain):
        """Whether `domain` is in one of the tighter popularity lists.

        Used to tell a well-known site apart from an unknown link shortener. The union is
        built once per process and shared: the alternative is scanning every warninglist
        for every domain, and some of those lists have a million entries.
        """

        global _top_sites_domains

        if _top_sites_domains is None:
            combined = set()
            for known_list in self.known_domain_lists.values():
                if str(known_list.name).startswith(self.TOP_SITES_LIST_PREFIXES):
                    combined.update(known_list.list)
            _top_sites_domains = combined

        return domain in _top_sites_domains

    def search_known_domain_lists(self, domain):
        lists_found_in = []
        for known_list in self.known_domain_lists.values():
            if domain in known_list.list:
                lists_found_in.append({'name': known_list.name, 'description': known_list.description})

        return_list = []
        for found in lists_found_in:
            if not found['name'].startswith(('Top', 'google-chrome-crux-1million')):
                return_list.append(found)

        top_found = [x['name'] for x in lists_found_in if str(x['name']).startswith('Top')]
        top_1k = [x for x in top_found if x.startswith(('Top 1000', 'Top 500 '))]
        top_10k = [x for x in top_found if x.startswith(('Top 10 000', 'Top 10K'))]
        top_1m = [x for x in top_found if x.startswith(('Top 1,000,000', 'Top 20 000', 'google-chrome-crux-1million'))]

        if top_1k:
            return_list.append({'name': 'Domain is extremely popular (found in "Top 1000" lists)',
                                'description': f'Domain is found in {len(top_1k)} lists: {", ".join(top_1k)}'})

        elif top_10k:
            return_list.append({'name': 'Domain is very popular (found in "Top 10K" lists)',
                                'description': f'Domain is found in {len(top_10k)} lists: {", ".join(top_10k)}'})

        elif top_1m:
            return_list.append({'name': 'Domain is popular (found in "Top 1M" lists)',
                                'description': f'Domain is found in {len(top_1m)} lists: {", ".join(top_1m)}'})

        return return_list

    def get_predecessor_node(self, node):
        if not node.parent_id:
            return False
        predecessor = list(self.graph.predecessors(node))
        return predecessor

    def get_predecessor_chain(self, node, chain: list = None) -> list:
        if not chain:
            chain = []

        predecessor = Unfurl.get_predecessor_node(self, node)
        if predecessor:
            chain.append(predecessor[0])
            Unfurl.get_predecessor_chain(self, predecessor[0], chain)

        return chain

    def find_repeated_ancestor(self, data_type, value, parent_id):
        """Return the ancestor that pushes this value over the repeat limit, or None.

        Unfurl's parsers can feed each other in a loop. A 1drv.ms link expands to an
        onedrive.live.com redirect whose "redeem" parameter is base64 of the *original*
        1drv.ms URL, so decoding it hands the shortlink parser the same link again.
        Nothing in the queue noticed, so a single input filled the graph with identical
        branches until it hit node_limit -- and every lap fired another HTTP request at
        the shortener.

        Two choices here are deliberate:

        Compared against ancestors, not against every node. The same value legitimately
        appears in sibling branches -- a path with two "file" segments, a parameter
        repeated across two URLs -- and those are separate, real observations. Only a
        value repeating along one line of ancestry means the parsers are going in
        circles.

        Allows a repeat before stopping (max_repeated_ancestors). Stopping at the very
        first repeat would misfire on genuine redirect chains that keep a path while
        changing the query, e.g. /x?a=1 -> /x?a=2 -> /x?a=3, where url.path repeats but
        each hop is real evidence. Requiring the value to come around twice keeps those
        intact while still bounding a true loop to a couple of laps.
        """

        if parent_id is None:
            return None

        # A node can be attached to more than one parent; any of their lines counts.
        parent_ids = parent_id if isinstance(parent_id, list) else [parent_id]

        seen = 0
        for single_parent_id in parent_ids:
            parent = self.nodes.get(single_parent_id)
            if not parent:
                continue

            for ancestor in [parent] + self.get_predecessor_chain(parent):
                if ancestor.data_type == data_type and ancestor.value == value:
                    seen += 1
                    if seen >= self.max_repeated_ancestors:
                        return ancestor

        return None

    @staticmethod
    def check_if_in_node_chain(chain: list, key, value, chain_index: int) -> bool:
        if chain_index >= len(chain):
            return False

        # If a multiple values are passed into value, return True if any of them are
        # found (effectively an OR; allows for searching for multiple terms at once)
        if isinstance(value, (list, tuple)):
            if getattr(chain[chain_index], key) in value:
                return True
            else:
                return False

        if getattr(chain[chain_index], key) == value:
            return True
        return False

    def get_successor_nodes(self, node):
        successors = list(self.graph.successors(node))
        return successors

    def check_sibling_nodes(self, node, data_type=None, key=None, value=None, return_node=False):
        parent_nodes = self.get_predecessor_node(node)

        if not parent_nodes:
            return False

        sibling_nodes = []

        for parent_node in parent_nodes:
            sibling_nodes.extend(self.get_successor_nodes(parent_node))

        for sibling_node in sibling_nodes:

            # Skip the "sibling" if it's actually the source node
            if node.node_id == sibling_node.node_id:
                continue

            # For each attribute, check if it is set. If it is, and it
            # doesn't match, stop checking this node and go to the next
            if data_type:
                if data_type != sibling_node.data_type:
                    continue
            if key:
                if key != sibling_node.key:
                    continue
            if value:
                if value != sibling_node.value:
                    continue

            # This node matched all the given criteria;
            if return_node:
                return sibling_node
            return True

        # If we got here, no nodes matched all criteria.
        return False

    def find_preceding_domain(self, node):
        parent_nodes = self.get_predecessor_node(node)

        preceding_domain = ''

        if not parent_nodes:
            return preceding_domain

        assert isinstance(parent_nodes, list)

        for parent_node in parent_nodes:
            if parent_node.data_type == 'url.hostname':
                assert isinstance(parent_node.value, str)
                preceding_domain = parent_node.value
                break
            elif parent_node.data_type == 'url':
                for child_node in self.get_successor_nodes(parent_node):
                    if child_node.data_type == 'url.hostname':
                        assert isinstance(child_node.value, str)
                        preceding_domain = child_node.value
                        break
                    elif child_node.data_type == 'url.authority':
                        for subcomponent in self.get_successor_nodes(child_node):
                            if subcomponent.data_type == 'url.hostname':
                                assert isinstance(subcomponent.value, str)
                                preceding_domain = subcomponent.value
                                break
            else:
                preceding_domain = self.find_preceding_domain(parent_node)

        return preceding_domain

    def preceding_domain_matches(self, node, domain):
        """Check if the preceding domain matches the given domain exactly.
        Handles subdomains: preceding_domain_matches(node, 'yahoo.com')
        matches 'yahoo.com' and 'www.yahoo.com' but not 'notyahoo.com'."""
        preceding = self.find_preceding_domain(node)
        return preceding == domain or preceding.endswith(f'.{domain}')

    def preceding_domain_contains(self, node, label):
        """Check if the preceding domain contains the given label as a domain segment.
        preceding_domain_contains(node, 'google') matches 'google.com',
        'www.google.co.uk', but not 'notgoogle.com'."""
        preceding = self.find_preceding_domain(node)
        labels = preceding.split('.')
        return label in labels

    def find_preceding_path(self, node):
        """Find the URL path associated with a node by traversing up to the URL
        ancestor and looking for a url.path sibling."""
        parent_nodes = self.get_predecessor_node(node)

        if not parent_nodes:
            return ''

        for parent_node in parent_nodes:
            if parent_node.data_type == 'url':
                for child_node in self.get_successor_nodes(parent_node):
                    if child_node.data_type == 'url.path':
                        return child_node.value
                return ''
            else:
                result = self.find_preceding_path(parent_node)
                if result:
                    return result

        return ''

    def find_preceding_url(self, node):
        """Return the value of the nearest 'url' ancestor, or '' if there isn't one.

        Most parsers work from the pieces Unfurl has already split out -- the domain, a
        path segment, a query pair. A few need the URL as it was actually written,
        because the thing they care about spans those pieces: a redirector whose token
        sits in the query string and whose host is a subdomain cannot be rebuilt from a
        registered domain and a path.
        """

        parent_nodes = self.get_predecessor_node(node)

        if not parent_nodes:
            return ''

        for parent_node in parent_nodes:
            if parent_node.data_type == 'url':
                return parent_node.value

            result = self.find_preceding_url(parent_node)
            if result:
                return result

        return ''

    def get_id(self):
        new_id = self.next_id
        self.next_id += 1
        return new_id

    def create_node(
            self, data_type, key, value, label, hover, parent_id=None,
            incoming_edge_config=None, extra_options=None):
        new_node = self.Node(
            self.get_id(), data_type=data_type, key=key, value=value,
            label=label, hover=hover, parent_id=parent_id,
            incoming_edge_config=incoming_edge_config,
            extra_options=extra_options)
        assert new_node.node_id not in self.nodes.keys()
        self.nodes[new_node.node_id] = new_node
        self.graph.add_node(new_node)
        self.total_nodes += 1

        if parent_id:
            if isinstance(parent_id, list):
                for parent in parent_id:
                    self.graph.add_edge(self.nodes[parent], new_node)
            else:
                self.graph.add_edge(self.nodes[parent_id], new_node)

        return new_node.node_id

    @staticmethod
    def check_if_int_between(value, low, high):
        try:
            value = int(value)
        except Exception:
            return False

        if low < value < high:
            return True
        else:
            return False

    def add_to_queue(
            self, data_type, key, value, label=None, hover=None,
            parent_id=None, incoming_edge_config=None, extra_options=None):
        new_item = {
            'data_type': data_type,
            'key': key,
            'value': value,
            'label': label,
            'hover': hover,
            'incoming_edge_config': incoming_edge_config,
            'extra_options': extra_options
        }

        if parent_id:
            new_item['parent_id'] = parent_id

        if not extra_options:
            max_row_length = len(str(value)) * 2.2
            new_item['extra_options'] = \
                {'widthConstraint': {'maximum': max(max_row_length, 200)}}

        log.info(f'Added to queue: {new_item}')
        self.queue.put(new_item)

    def run_plugins(self, node):

        for unfurl_parser in unfurl.parsers.__all__:
            try:
                parser = importlib.import_module(f'unfurl.parsers.{unfurl_parser}')
            except ImportError as e:
                log.exception(f'Failed to import {unfurl_parser}: {e}')
                continue

            try:
                parser.run(self, node)
            except Exception as e:
                log.exception(f'Exception in {unfurl_parser}: {e}')

    def parse(self, queued_item):
        item = queued_item

        repeated_ancestor = self.find_repeated_ancestor(
            item['data_type'], item['value'], item.get('parent_id'))

        hover = utils.wrap_hover_text(item['hover'])
        if repeated_ancestor:
            # The node is still created. It is a real observation -- the value genuinely
            # came around again -- and silently dropping it would hide the loop instead
            # of showing it. What stops is the parsing below, and the hover says so, so
            # the missing children read as Unfurl's decision rather than as the data
            # simply ending here.
            cycle_hover = utils.wrap_hover_text(
                f'Unfurl stopped expanding here. This same value already appears '
                f'{self.max_repeated_ancestors} times above this node in the graph '
                f'(most recently at node {repeated_ancestor.node_id}), which means the '
                f'parsers are looping. The node is kept, but it was not parsed further.')
            hover = f'{hover}<br><br>{cycle_hover}' if hover else cycle_hover

        node_id = self.create_node(
            data_type=item['data_type'], key=item['key'], value=item['value'],
            label=item['label'], hover=hover,
            parent_id=item.get('parent_id', None),
            incoming_edge_config=item.get('incoming_edge_config', None),
            extra_options=item.get('extra_options', None))

        if repeated_ancestor:
            log.info(
                f'Not parsing node {node_id}; its value repeats ancestor '
                f'{repeated_ancestor.node_id} ({item["data_type"]})')
            return

        self.run_plugins(self.nodes[node_id])

    def parse_queue(self):
        while not self.queue.empty() and self.total_nodes < self.node_limit:
            self.parse(self.queue.get())

    def reset_graph_state(self):
        self.graph = networkx.DiGraph()
        self.nodes = {}
        self.edges = []
        self.total_nodes = 0
        self.next_id = 1

    @staticmethod
    def transform_node(node):
        transformed = {
            'id': int(node.node_id),
            'label': f'{node.label}'
        }
        if node.hover:
            transformed['title'] = node.hover
        if node.extra_options:
            transformed.update(node.extra_options)
        return transformed

    @staticmethod
    def transform_edge(edge):
        transformed = {
            'from': int(edge[0].node_id),
            'to': int(edge[1].node_id)
        }

        if edge[1].incoming_edge_config:
            transformed.update(edge[1].incoming_edge_config)
        return transformed

    def generate_json(self):
        data_json = {'nodes': [], 'edges': []}
        for orig_node in self.graph.nodes():
            data_json['nodes'].append(self.transform_node(orig_node))
        for orig_edge in self.graph.edges():
            data_json['edges'].append(self.transform_edge(orig_edge))

        edge_summary = {}
        for edge in data_json.get('edges'):
            edge_summary.setdefault(edge.get('title'), 0)
            edge_summary[edge.get('title')] += 1

        data_json['summary'] = edge_summary

        return data_json

    def generate_full_json(self):
        data_json = {'nodes': [], 'edges': []}
        for orig_node in self.graph.nodes():
            data_json['nodes'].append(orig_node.to_dict())
        for orig_edge in self.graph.edges():
            data_json['edges'].append(orig_edge)

        return data_json

    @staticmethod
    def transform_3d_node(node):
        def val_func(node_id):
            if node_id == 1:
                return 15
            elif node_id < 10:
                return 10
            else:
                return 5

        def shorten_name(node_string):
            node_string = str(node_string)
            if len(node_string) > 60:
                return f'{node_string[:25]}...{node_string[-25:]}'
            else:
                return node_string

        node_color = '#aabfad'
        if node.incoming_edge_config:
            if node.incoming_edge_config['color']:
                node_color = node.incoming_edge_config['color']['color']

        transformed = {
            'id': str(node.node_id),
            'name': shorten_name(node.label),
            'fullName': f'{node.label}',
            'dataType': f'{node.data_type}',
            'val': val_func(node.node_id),
            'color': node_color
        }

        if node.hover:
            transformed['description'] = re.sub(r'<.*?>|\[.*?\]', '', node.hover)

        return transformed

    @staticmethod
    def transform_3d_edge(edge):
        transformed = {
            'source': str(edge[0].node_id),
            'target': str(edge[1].node_id)
        }

        if edge[1].incoming_edge_config:
            transformed.update(edge[1].incoming_edge_config)

        if transformed.get('color', {}).get('color'):
            transformed['color'] = transformed['color']['color']
        return transformed

    def generate_3d_json(self):
        data_json = {'nodes': [], 'links': []}
        for orig_node in self.graph.nodes():
            data_json['nodes'].append(self.transform_3d_node(orig_node))
        for orig_edge in self.graph.edges():
            data_json['links'].append(self.transform_3d_edge(orig_edge))
        return data_json

    def generate_text_tree(self, detailed=False, output_filter=None):
        tree_root = None
        for node_contents in self.graph.nodes(data=True):
            # Get the root node; id is 1. Needed for networkx tree_data().
            if node_contents[0].__dict__.get('node_id') == 1:
                tree_root = node_contents[0]
                break

        tree_data = networkx.readwrite.json_graph.tree_data(
            self.graph, root=tree_root)
        output_tree = Unfurl.text_tree(tree_data, detailed=detailed)

        if output_filter:
            filtered_tree = ''
            for line in output_tree.splitlines():
                if re.search(output_filter, line):
                    filtered_tree += f'\n{line}'
            output_tree = filtered_tree

        return output_tree

    @staticmethod
    def text_tree(tree_data, indent='', last_child=False, text_output='', detailed=False):

        node = tree_data['id']
        label = re.sub(r'\n', ' ', str(node.label))

        if node.node_id == 1:
            # This is the root node; don't indent to save space
            text_output += f'[{node.node_id}] {label}'
            if detailed:
                text_output += f' (type: {node.data_type})'
                if node.hover:
                    hover = re.sub(r'<.*?>|\[.*?\]', '', node.hover)
                    text_output += f' -- {hover}'

            indent += ' '

        elif not last_child:
            text_output += f'\n{indent}├─({node.incoming_edge_config["label"]})─[{node.node_id}] {label}'
            if detailed:
                text_output += f' (type: {node.data_type})'
                if node.hover:
                    hover = re.sub(r'<.*?>|\[.*?\]', '', node.hover)
                    text_output += f' -- {hover}'

            indent += '|  '
        else:
            text_output += f'\n{indent}└─({node.incoming_edge_config["label"]})─[{node.node_id}] {label}'
            if detailed:
                text_output += f' (type: {node.data_type})'
                if node.hover:
                    hover = re.sub(r'<.*?>|\[.*?\]', '', node.hover)
                    text_output += f' -- {hover}'

            indent += '   '

        if tree_data.get('children'):
            children_text_output = ''
            for number, child in enumerate(tree_data['children']):
                last_child = \
                    True if (number + 1) == len(tree_data['children']) else False
                children_text_output += \
                    Unfurl.text_tree(
                        child, indent=indent, last_child=last_child, detailed=detailed)
            text_output += children_text_output

        return text_output


def run(url, data_type='url', return_type='json', remote_lookups=None, extra_options=None):
    u = Unfurl(remote_lookups=remote_lookups)
    u.add_to_queue(
        data_type=data_type,
        key=None,
        value=url,
        extra_options=extra_options
    )
    u.parse_queue()

    if return_type == 'text':
        return_object = u.generate_text_tree()
    elif return_type == 'full_json':
        return_object = u.generate_full_json()
    else:
        return_object = u.generate_json()

    u.reset_graph_state()
    return return_object
