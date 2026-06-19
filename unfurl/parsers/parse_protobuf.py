# Copyright 2020 Google LLC
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

import base64
import json
import logging
import os

import blackboxprotobuf
from google.protobuf import json_format
from unfurl import utils
from unfurl.parsers.proto import proto_registry, enum_registry

log = logging.getLogger(__name__)

# Load proto field name mappings from the JSON config file.
# This allows labeling proto fields with friendly names (e.g., field "2" -> "Subject")
# without writing a dedicated parser for each proto structure.
_field_names_path = os.path.join(os.path.dirname(__file__), 'proto', 'field_names.json')
with open(_field_names_path, 'r') as f:
    proto_field_names = json.load(f)

proto_edge = {
    'color': {
        'color': '#2D9A58'
    },
    'title': 'Protobuf Parsing Functions',
    'label': 'proto'
}

hex_proto_edge = {
    'color': {
        'color': '#2D9A58'
    },
    'title': 'Parsed from hex bytes, then as a protobuf',
    'label': 'hex+proto'
}

b64_proto_edge = {
    'color': {
        'color': '#2D9A58'
    },
    'title': 'Parsed from base64, then as a protobuf',
    'label': 'b64+proto'
}

b32_proto_edge = {
    'color': {
        'color': '#2D9A58'
    },
    'title': 'Parsed from base32, then as a protobuf',
    'label': 'b32+proto'
}

wire_types = {
    'int': '<b>varint (0)</b>. <br><br>It is displayed here as an int, but it could orginially have '
           'been <br>a int32, int64, uint32, uint64, sint32, sint64, bool, or enum.',
    'fixed64': '<b>64-bit (1)</b>. <br><br>It is displayed here as a fixed64, but it could originally '
               'have been <br>a fixed64, sfixed64, or double.',
    'bytes': '<b>length-delimited (2)</b>. <br><br>It is displayed here as bytes, but it could originally '
             'have been <br>a string, bytes, embedded messages, or packed repeated fields.',
    'string': '<b>length-delimited (2)</b>. <br><br>It is displayed here as a string, but it could originally '
             'have been <br>a string, bytes, embedded messages, or packed repeated fields.',
    'fixed32': '<b>32-bit (5)</b>. <br><br>It is displayed here as an int, but it could originally '
               'have been <br>a fixed32, sfixed32, or float.'
}


def find_proto_context(unfurl, node):
    """Walk up the parent chain to find a proto_context tag in the stash.
    Returns (context_string, should_skip) tuple.
    Stash entries are dicts with 'context' (required) and 'skip' (optional)."""
    proto_contexts = unfurl.stash.get('proto_context', {})
    current = node
    while current:
        if current.node_id in proto_contexts:
            entry = proto_contexts[current.node_id]
            if isinstance(entry, dict):
                return entry.get('context'), entry.get('skip', False) and current.node_id == node.node_id
            # Backwards compat: plain string
            return entry, False
        if current.parent_id:
            current = unfurl.nodes.get(current.parent_id)
        else:
            break
    return None, False


def decode_with_compiled_proto(unfurl, node, raw_bytes, context, edge_type):
    """Decode proto bytes using a compiled proto class from the registry.
    Returns True if a compiled proto was found and used, False otherwise."""
    proto_class = proto_registry.get(context)
    if not proto_class:
        return False

    try:
        message = proto_class.FromString(raw_bytes)
        message_dict = json_format.MessageToDict(message)
    except Exception as e:
        log.debug(f'Failed to decode {context} with compiled proto: {e}')
        return False

    for key, value in message_dict.items():
        if isinstance(value, dict):
            unfurl.add_to_queue(
                data_type=context, key=key, value=value, label=f'{key}: {{{len(value)} keys}}',
                parent_id=node.node_id, incoming_edge_config=edge_type)
        elif isinstance(value, list):
            unfurl.add_to_queue(
                data_type=context, key=key, value=value, label=f'{key}: [{len(value)} items]',
                parent_id=node.node_id, incoming_edge_config=edge_type)
        else:
            unfurl.add_to_queue(
                data_type=context, key=key, value=value, label=f'{key}: {value}',
                parent_id=node.node_id, incoming_edge_config=edge_type)

    return True


def resolve_enum_value(enum_class, value):
    """Convert a protobuf enum int to a human-friendly name.
    E.g., SuggestType(69) -> 'Native Chrome'."""
    try:
        name = enum_class.Name(int(value))
        # Strip common prefixes (TYPE_, SUBTYPE_, etc.)
        for prefix in ('TYPE_', 'SUBTYPE_'):
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        return name.replace('_', ' ').title()
    except (ValueError, TypeError):
        return f'Unknown ({value})'


def run(unfurl, node):

    # Resolve enum-typed nodes. Any node whose data_type is in the enum_registry
    # gets a friendly label from the proto enum definition.
    if node.data_type in enum_registry:
        enum_class = enum_registry[node.data_type]
        friendly = resolve_enum_value(enum_class, node.value)
        node.label = f'{node.key}: {friendly}' if node.key else friendly
        return

    def get_field_meta(path, field_map):
        """Look up field metadata using a dotted path (e.g., '13.1.1') in a flat field map.
        Entry can be a string (just the name) or a dict with 'name' and/or 'hover'.
        Returns (name, hover) tuple."""
        if not field_map:
            return None, None
        entry = field_map.get(path)
        if entry is None:
            return None, None
        if isinstance(entry, str):
            return entry, None
        return entry.get('name'), entry.get('hover')

    def parse_protobuf_into_nodes(pb_value_dict, pb_types, edge_type=None,
                                  context=None, path_prefix=''):
        assert isinstance(pb_value_dict, dict), \
            f'"parse_protobuf_into_nodes" expects a dict, but got {type(pb_value_dict)} as input'

        # When context is a string, use it as the data_type so downstream parsers
        # (e.g., parse_google) can interpret the fields semantically.
        context_str = context if isinstance(context, str) else None
        dt_leaf = context_str or 'proto'
        dt_dict = context_str or 'proto.dict'
        dt_list = context_str or 'proto.list'

        field_map = proto_field_names.get(context, {}) if isinstance(context, str) else {}

        if len(pb_value_dict) > 0:
            for field_number, field_value in pb_value_dict.items():
                field_path = f'{path_prefix}{field_number}'
                name, hover = get_field_meta(field_path, field_map)
                label = f'{name} ({field_number}): {field_value}' if name else None
                wire_type = wire_types.get(pb_types[field_number]["type"])
                field_hover = hover or (f'Field number <b>{field_number}</b> has a wire '
                                        f'type of {wire_type}' if wire_type else
                                        f'Field number <b>{field_number}</b>')
                if isinstance(field_value, (str, int, float, bytes, bytearray)):
                    unfurl.add_to_queue(
                        data_type=dt_leaf, key=field_number, value=str(field_value),
                        label=label,
                        hover=field_hover,
                        parent_id=node.node_id, incoming_edge_config=edge_type)
                elif isinstance(field_value, dict):
                    unfurl.add_to_queue(
                        data_type=dt_dict, key=field_number,
                        value={'field_values': field_value,
                               'field_types': pb_types[field_number]["message_typedef"],
                               'field_path': f'{field_path}.'},
                        label=label or f'{field_number}: {field_value}',
                        hover=field_hover,
                        parent_id=node.node_id, incoming_edge_config=edge_type)
                elif isinstance(field_value, list):
                    nested_types = pb_types[field_number]
                    if pb_types[field_number].get("message_typedef"):
                        nested_types = pb_types[field_number]["message_typedef"]

                    unfurl.add_to_queue(
                        data_type=dt_list, key=field_number,
                        value={'field_values': field_value, 'field_types': nested_types,
                               'field_path': f'{field_path}.'},
                        label=label or f'{field_number}: {field_value}',
                        hover=field_hover,
                        parent_id=node.node_id, incoming_edge_config=edge_type)

    context, skip = find_proto_context(unfurl, node)

    # Handle nested proto messages. These may have data_type='proto.dict'/'proto.list'
    # (no context) or a context-specific type like 'google.ved' (with context).
    # In both cases, the value is a dict with 'field_values' and 'field_types'.
    # Pass along field_path (dotted prefix for field_names.json lookups)
    # so nested fields can get labels too.
    if isinstance(node.value, dict) and 'field_values' in node.value:
        field_values = node.value.get('field_values')
        field_types = node.value.get('field_types')
        path_prefix = node.value.get('field_path', '')
        if isinstance(field_values, dict):
            parse_protobuf_into_nodes(field_values, field_types, proto_edge, context,
                                      path_prefix)
            return
        elif isinstance(field_values, list):
            for fv in field_values:
                ft = field_types
                if not isinstance(fv, dict):
                    fv = {node.key: fv}
                    ft = {node.key: ft}
                parse_protobuf_into_nodes(fv, ft, proto_edge, context, path_prefix)
            return

    if node.data_type == 'bytes':
        # If a compiled proto is registered for this context, use it for precise named fields.
        if context and decode_with_compiled_proto(unfurl, node, node.value, context, proto_edge):
            return

        try:
            protobuf_values, protobuf_values_types = blackboxprotobuf.decode_message(node.value)
            parse_protobuf_into_nodes(protobuf_values, protobuf_values_types, proto_edge, context)
            return

        # This will often fail for a wide array of reasons when it tries to parse a non-pb as a pb
        except Exception:
            pass

    if not isinstance(node.value, str):
        return False

    # Skip b64 decoding if this node is explicitly marked (e.g., ved has a version
    # byte prefix that would produce garbage proto fields; a child node has the
    # cleaned value instead).
    if skip:
        return

    if node.data_type.startswith(('uuid', 'hash')):
        return False

    urlsafe_b64_m = utils.urlsafe_b64_re.fullmatch(node.value)
    standard_b64_m = utils.standard_b64_re.fullmatch(node.value)
    hex_m = utils.hex_re.fullmatch(node.value)
    # Updating to all letters/digits and forward slashes, to catch URL paths that may,
    # by some chance, validly decode as protobuf, but really aren't.
    all_digits_m = utils.digits_and_slash_re.fullmatch(node.value)
    all_letters_m = utils.letters_and_slash_re.fullmatch(node.value)

    # Build the ordered list of (decoded_bytes, edge) candidates to try as a
    # protobuf. Exactly one of hex/base64 is selected as the primary (same
    # precedence as before); base32 is appended as a fallback so base32-encoded
    # protobufs decode too. Base32's alphabet is a subset of base64's, so a
    # base32 value also matches the b64 regex -- without this fallback it would
    # be claimed (and fail) as base64. We try each candidate in order and emit on
    # the first that decodes, so a failed primary no longer ends the parser.
    attempts = []

    if not (all_digits_m or all_letters_m):
        # A valid b64 string is never length % 4 == 1 (hex is always even-length,
        # so this guard only affects the base64 candidates).
        b64_ok = len(node.value) % 4 != 1
        if hex_m:
            try:
                attempts.append((bytes.fromhex(node.value), hex_proto_edge))
            except ValueError:
                pass
        elif urlsafe_b64_m and b64_ok:
            try:
                attempts.append(
                    (base64.urlsafe_b64decode(unfurl.add_b64_padding(node.value)), b64_proto_edge))
            except Exception:
                pass
        elif standard_b64_m and b64_ok:
            try:
                attempts.append(
                    (base64.b64decode(unfurl.add_b64_padding(node.value)), b64_proto_edge))
            except Exception:
                pass

        b32_decoded = utils.try_base32_decode(node.value)
        if b32_decoded is not None:
            attempts.append((b32_decoded, b32_proto_edge))

    for decoded, edge in attempts:
        if context and decode_with_compiled_proto(unfurl, node, decoded, context, edge):
            return
        try:
            protobuf_values, protobuf_values_types = blackboxprotobuf.decode_message(decoded)
        # This will often fail for a wide array of reasons when it tries to parse
        # a non-pb as a pb; try the next candidate instead of giving up.
        except Exception:
            continue
        parse_protobuf_into_nodes(protobuf_values, protobuf_values_types, edge, context)
        return
