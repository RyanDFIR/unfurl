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

import fnmatch
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None
    log.warning('PyYAML not installed; YAML site definitions will not be loaded.')

# Cache loaded definitions so we only read from disk once.
_site_defs = None


def _load_site_defs():
    """Load all YAML site definitions from the site_defs/ directory."""
    global _site_defs
    if _site_defs is not None:
        return _site_defs

    _site_defs = []
    if yaml is None:
        return _site_defs

    defs_dir = Path(__file__).parent / 'site_defs'
    if not defs_dir.is_dir():
        return _site_defs

    for yaml_file in sorted(defs_dir.glob('*.yaml')):
        try:
            with open(yaml_file, encoding='utf-8') as f:
                site_def = yaml.safe_load(f)
            if site_def:
                # Pre-build the edge config from the definition
                edge_raw = site_def.get('edge', {})
                site_def['_edge_config'] = {
                    'color': {'color': edge_raw.get('color', '#888888')},
                    'title': edge_raw.get('title', site_def.get('name', '')),
                    'label': edge_raw.get('label', ''),
                }
                # Pre-compile fragment patterns
                for rule in site_def.get('fragment_rules', []):
                    if 'pattern' in rule:
                        rule['_compiled'] = re.compile(rule['pattern'])
                _site_defs.append(site_def)
                log.info(f'Loaded site definition: {site_def.get("name")} from {yaml_file.name}')
        except Exception as e:
            log.warning(f'Failed to load site definition {yaml_file}: {e}')

    return _site_defs


def _format_label(template, value, groups=None):
    """Format a label template with {value} and optional regex group placeholders."""
    result = template.replace('{value}', str(value) if value else '')
    if groups:
        for key, val in groups.items():
            result = result.replace('{' + key + '}', str(val) if val else '')
    return result


def _apply_path_rule(unfurl, node, rule, site_def):
    """Apply a path_rule to a node, adding child nodes as specified."""
    apply = rule['apply']
    edge_config = site_def['_edge_config']

    label = _format_label(apply.get('label', '{value}'), node.value)

    unfurl.add_to_queue(
        data_type=apply.get('data_type', 'descriptor'),
        key=None,
        value=node.value if apply.get('data_type', 'descriptor') != 'descriptor' else None,
        label=label,
        hover=apply.get('hover', ''),
        parent_id=node.node_id,
        incoming_edge_config=edge_config,
    )


def _check_path_rule(unfurl, node, rule, site_def):
    """Check if a path_rule matches the current node.

    Returns True if the rule matched and was applied.
    """
    match = rule.get('match', {})

    # "on_value" rules: fire on any segment whose value matches
    if 'on_value' in rule:
        if node.value != rule['on_value']:
            return False
        # Still need to check match constraints (sibling segments)
        for seg_key, seg_value in match.items():
            if not unfurl.check_sibling_nodes(
                    node, data_type='url.path.segment',
                    key=int(seg_key), value=str(seg_value)):
                return False
        _apply_path_rule(unfurl, node, rule, site_def)
        return True

    # "position" rules: fire only when the node's key (segment position) matches
    if 'position' in rule:
        if node.key != rule['position']:
            return False

        # Check exclude_values: skip if this node's value matches the exclusion list.
        # Supports wildcards (e.g., '*.php') via fnmatch.
        for pattern in rule.get('exclude_values', []):
            if fnmatch.fnmatch(node.value, pattern):
                return False

        # Check exclude_sibling: skip if a sibling segment matches any excluded value.
        # Supports wildcards (e.g., '*.php') via fnmatch.
        exclude_sib = rule.get('exclude_sibling')
        if exclude_sib:
            sibling = unfurl.check_sibling_nodes(
                node, data_type='url.path.segment',
                key=int(exclude_sib['key']), return_node=True)
            if sibling:
                for pattern in exclude_sib.get('values', []):
                    if fnmatch.fnmatch(str(sibling.value), pattern):
                        return False

        # Check match constraints
        for seg_key, seg_value in match.items():
            if not unfurl.check_sibling_nodes(
                    node, data_type='url.path.segment',
                    key=int(seg_key), value=str(seg_value)):
                return False
        _apply_path_rule(unfurl, node, rule, site_def)
        return True

    return False


def _check_query_rule(unfurl, node, rule, site_def):
    """Check if a query_rule matches the current node."""
    if node.key != rule.get('key'):
        return False

    # Optional path scoping: only apply this rule when the URL path matches.
    if 'path' in rule:
        preceding_path = unfurl.find_preceding_path(node)
        if preceding_path != rule['path']:
            return False

    apply = rule['apply']

    # hover_only: just set hover text on the existing node, don't create a child
    if apply.get('hover_only'):
        node.hover = apply.get('hover', '')
        return True

    edge_config = site_def['_edge_config']
    label = _format_label(apply.get('label', '{value}'), node.value)

    data_type = apply.get('data_type', 'descriptor')

    unfurl.add_to_queue(
        data_type=data_type,
        key=None,
        value=node.value if data_type != 'descriptor' else None,
        label=label,
        hover=apply.get('hover', ''),
        parent_id=node.node_id,
        incoming_edge_config=edge_config,
    )
    return True


def _check_fragment_rule(unfurl, node, rule, site_def):
    """Check if a fragment_rule matches the current node."""
    compiled = rule.get('_compiled')
    if not compiled:
        return False

    m = compiled.search(str(node.value))
    if not m:
        return False

    apply = rule['apply']
    edge_config = site_def['_edge_config']
    groups = m.groupdict()

    # Choose label template based on groups present
    if 'end' in groups and groups['end'] is None and 'label_single' in apply:
        template = apply['label_single']
    else:
        template = apply.get('label', '{value}')

    label = _format_label(template, node.value, groups)

    unfurl.add_to_queue(
        data_type=apply.get('data_type', 'descriptor'),
        key=None,
        value=node.value,
        label=label,
        hover=apply.get('hover', ''),
        parent_id=node.node_id,
        incoming_edge_config=edge_config,
    )
    return True


def run(unfurl, node):
    site_defs = _load_site_defs()

    for site_def in site_defs:
        domains = site_def.get('domains', [])

        # Check if this node belongs to one of the site's domains
        if not any(unfurl.preceding_domain_matches(node, d) for d in domains):
            continue

        # Path segment rules
        if node.data_type == 'url.path.segment':
            for rule in site_def.get('path_rules', []):
                if _check_path_rule(unfurl, node, rule, site_def):
                    break  # First matching rule wins for this node

        # Query parameter rules
        elif node.data_type == 'url.query.pair':
            for rule in site_def.get('query_rules', []):
                if _check_query_rule(unfurl, node, rule, site_def):
                    break

        # Fragment rules
        elif node.data_type == 'url.fragment':
            for rule in site_def.get('fragment_rules', []):
                if _check_fragment_rule(unfurl, node, rule, site_def):
                    break