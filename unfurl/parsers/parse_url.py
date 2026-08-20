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

import pycountry
import re
import urllib.parse

from unfurl import utils
from unfurl.file_types import lookup_extension

urlparse_edge = {
    'color': {
        'color': '#4d4d4d'
    },
    'title': 'URL Parsing Functions',
    'label': 'u'
}


def parse_delimited_string(unfurl_instance, node, delimiter, pairs=False) -> None:
    split_values = node.value.split(delimiter)

    for split_value in split_values:
        if pairs:
            key, value = split_value.split('=')
            unfurl_instance.add_to_queue(
                data_type='url.query.pair', key=key, value=value,
                parent_id=node.node_id, incoming_edge_config=urlparse_edge)
        else:
            unfurl_instance.add_to_queue(
                data_type='string', key=None, value=split_value,
                parent_id=node.node_id, incoming_edge_config=urlparse_edge)


def try_url_unquote(unfurl_instance, node) -> bool:
    unquoted = urllib.parse.unquote_plus(node.value)
    # The regex is to avoid erroneously unquoting a timestamp string (ending with +00:00)
    if unquoted != node.value and not re.match(r'.*\+\d\d:\d\d$', node.value):
        unfurl_instance.add_to_queue(
            data_type='string', key=None, value=unquoted,
            hover='Unquoted URL (replaced %xx escapes with their single-character equivalent)',
            parent_id=node.node_id, incoming_edge_config=urlparse_edge)
        return True
    return False


def try_url_parse(unfurl_instance, node) -> bool:
    try:
        parsed_url = urllib.parse.urlparse(node.value)
        if (parsed_url.netloc and parsed_url.path) or (parsed_url.scheme and parsed_url.netloc):
            unfurl_instance.add_to_queue(
                data_type='url', key=None, value=node.value, parent_id=node.node_id,
                incoming_edge_config=urlparse_edge)
            return True
        return False
    except:
        return False


def run(unfurl, node):

    if not node.data_type.startswith('url'):
        try:
            # If a node isn't of type 'url' (but maybe 'string' or something) but we can recognize its
            # value as a URL, update the data_type so the rest of the parser can act on it.
            parsed_url = urllib.parse.urlparse(node.value)
            if (parsed_url.netloc and parsed_url.path) or (parsed_url.scheme and parsed_url.netloc):
                node.data_type = 'url'
        except:
            # Guess it wasn't a URL
            return

    if node.data_type == 'url':
        parsed_url = urllib.parse.urlparse(node.value)

        if parsed_url.netloc:
            if parsed_url.scheme:
                unfurl.add_to_queue(
                    data_type='url.scheme', key='Scheme', value=parsed_url.scheme,
                    hover='This is the URL <b>scheme</b>, per <a href="'
                          'https://tools.ietf.org/html/rfc3986" target="_blank">RFC3986</a>',
                    parent_id=node.node_id, incoming_edge_config=urlparse_edge)

            if parsed_url.netloc == parsed_url.hostname:
                unfurl.add_to_queue(
                    data_type='url.hostname', key=None, value=parsed_url.hostname,
                    hover='This is the <b>host</b> subcomponent of authority (also often called '
                          'netloc), per <a href="https://tools.ietf.org/html/rfc3986" target="_blank">RFC3986</a>',
                    parent_id=node.node_id, incoming_edge_config=urlparse_edge)
            else:
                unfurl.add_to_queue(
                    data_type='url.authority', key=None, value=parsed_url.netloc,
                    hover='This is the <b>authority</b> (also often called '
                          'netloc), per <a href="https://tools.ietf.org/html/rfc3986" target="_blank">RFC3986</a>',
                    parent_id=node.node_id, incoming_edge_config=urlparse_edge)

            if parsed_url.path and parsed_url.path != '/':
                unfurl.add_to_queue(
                    data_type='url.path', key=None, value=parsed_url.path,
                    hover='This is the URL <b>path</b>, per <a href="'
                          'https://tools.ietf.org/html/rfc3986" target="_blank">RFC3986</a>',
                    parent_id=node.node_id, incoming_edge_config=urlparse_edge)

            if parsed_url.params:
                unfurl.add_to_queue(
                    data_type='url.params', key=None, value=parsed_url.params,
                    hover='This is the URL path <b>parameters</b>, per <a href="'
                          'https://tools.ietf.org/html/rfc3986" target="_blank">RFC3986</a>',
                    parent_id=node.node_id, incoming_edge_config=urlparse_edge)

            if parsed_url.query:
                unfurl.add_to_queue(
                    data_type='url.query', key=None, value=parsed_url.query,
                    hover='This is the URL <b>query</b>, per <a href="'
                          'https://tools.ietf.org/html/rfc3986" target="_blank">RFC3986</a>',
                    parent_id=node.node_id, incoming_edge_config=urlparse_edge)

            if parsed_url.fragment:
                unfurl.add_to_queue(
                    data_type='url.fragment', key=None, value=parsed_url.fragment,
                    hover='This is the URL <b>fragment</b>, per <a href="'
                          'https://tools.ietf.org/html/rfc3986" target="_blank">RFC3986</a>',
                    parent_id=node.node_id, incoming_edge_config=urlparse_edge)

    elif node.data_type == 'url.path':
        # Adjacent slashes mean the path contains an empty segment. That is legal per
        # RFC 3986 (a path with an authority is *( "/" segment ), and a segment may be
        # empty), and standard normalization does not collapse them -- so "/a/b" and
        # "//a/b" are different, non-equivalent paths. Unfurl leaves empty segments out
        # of the numbering entirely, so parsers keying on segment position still match
        # either form.
        if '//' in node.value:
            unfurl.add_to_queue(
                data_type='descriptor', key=None, value='Path contains an empty segment ("//")',
                hover='This URL path contains <b>adjacent slashes</b>, meaning it has an '
                      '<b>empty path segment</b>. <br>This is legal, but servers disagree on how to '
                      'resolve it: some <br>collapse repeated slashes by default, while '
                      'browsers and many application <br>frameworks preserve them. <br><br>The path above is shown unmodified. The '
                      'empty segments are left out of the <br>numbered child segments, so a path with '
                      'them is numbered the same as one <br>without.',
                parent_id=node.node_id, incoming_edge_config=urlparse_edge)

        path_segments = [segment for segment in node.value.split('/') if segment != '']
        for segment_number, path_segment in enumerate(path_segments, start=1):
            unfurl.add_to_queue(
                data_type='url.path.segment', key=segment_number, value=path_segment,
                hover='This is a URL <b>path segment</b> (the URL path is split on "/"s). '
                      'Numbering starts at 1.', parent_id=node.node_id, incoming_edge_config=urlparse_edge)

    elif node.data_type == 'url.query' or node.data_type == 'url.fragment':
        fragment_value = node.value
        fragment_directive = None

        # Text Fragments (ref: https://wicg.github.io/scroll-to-text-fragment/) use :~: as a
        # fragment directive delimiter. The part before :~: is the traditional fragment; the part
        # after contains directives like text= that tell the browser to highlight/scroll to text.
        if node.data_type == 'url.fragment' and ':~:' in node.value:
            fragment_value, fragment_directive = node.value.split(':~:', 1)

        # Fragments can contain SPA-style routes with a '?' separating the path from query
        # params (e.g. "#/im?p=@user"). Split on '?' so parse_qs only sees the query part.
        fragment_path = None
        if fragment_value and node.data_type == 'url.fragment' and '?' in fragment_value:
            fragment_path, fragment_value = fragment_value.split('?', 1)

        # A fragment value without '=' is a plain anchor (e.g. "heading1"), not a query string.
        # Only parse through parse_qs if it contains key=value pairs.
        if fragment_value and node.data_type == 'url.fragment' and '=' not in fragment_value:
            fragment_path = fragment_value
            fragment_value = None

        if fragment_path:
            unfurl.add_to_queue(
                data_type='url.fragment.anchor', key='Fragment Anchor', value=fragment_path,
                label=f'Fragment Anchor: {fragment_path}',
                hover='This is the traditional URL <b>fragment</b> (anchor) that identifies '
                      'a specific section of the page.',
                parent_id=node.node_id, incoming_edge_config=urlparse_edge)

        if fragment_value:
            parsed_qs = urllib.parse.parse_qs(fragment_value, keep_blank_values=True)
            for key, value in parsed_qs.items():
                assert type(value) is list, 'parsed_qs should result in type list, but did not.'
                # In the majority of cases, query string keys are unique, but the spec is ambiguous. In the case of
                # duplicate keys, urllib.parse.parsed_qs adds them to a list. Unfurl will loop over and create a
                # node for each value in that list of values (this is typically only one value, but could be more).
                for v in value:
                    unfurl.add_to_queue(
                        data_type='url.query.pair', key=key, value=v, label=f'{key}: {v}',
                        parent_id=node.node_id, incoming_edge_config=urlparse_edge)

            # If the query string or fragment is actually another URL (as seen in some redirectors), we want to
            # continue doing subsequent parsing on it. For that, we need to recognize it and change the data_type to url.
            if not parsed_qs:
                parsed = try_url_parse(unfurl, node)
                if parsed:
                    return

        if fragment_directive:
            # Parse each directive (separated by &). Currently only text= is defined in the spec.
            directives = urllib.parse.parse_qs(fragment_directive, keep_blank_values=True)
            for directive_values in directives.get('text', []):
                decoded_text = urllib.parse.unquote_plus(directive_values)
                unfurl.add_to_queue(
                    data_type='url.fragment.text-fragment', key='Text Fragment', value=decoded_text,
                    label=f'Text Fragment: {decoded_text}',
                    hover='A <b>Text Fragment</b> tells the browser to scroll to and highlight '
                          'the specified text on the page. '
                          '<a href="https://wicg.github.io/scroll-to-text-fragment/" target="_blank">[spec]</a>',
                    parent_id=node.node_id, incoming_edge_config=urlparse_edge)

    elif node.data_type == 'url.params':
        split_params_re = re.compile(r'^(?P<key>[^=]+?)=(?P<value>[^=?]+)(?P<delim>[;,|])')
        split_params = split_params_re.match(node.value)
        if split_params:
            x = split_params.group('delim')
            parsed_params = node.value.split(x)
            for parsed_param in parsed_params:
                key, _, value = parsed_param.partition('=')
                unfurl.add_to_queue(
                    data_type='url.param.pair', key=key, value=value,
                    parent_id=node.node_id, incoming_edge_config=urlparse_edge)

    # This should only occur when a URL node was parsed previously and netloc != hostname, which means there are
    # additional subcomponents of the authority to parse: user, password, and/or port. Reparsing this way lets the
    # simple case of authority = hostname look uncluttered, but still support all the other subcomponents if given.
    elif node.data_type == 'url.authority':
        # We need to add in a fake scheme here, as we stripped in the previous run and urlparse needs one.
        parsed_authority = urllib.parse.urlparse(f'https://{node.value}')

        if parsed_authority.username:
            unfurl.add_to_queue(
                data_type='url.username', key='Username', value=parsed_authority.username,
                hover='This is the <b>username</b> subcomponent of authority, '
                      'per <a href="https://tools.ietf.org/html/rfc3986" target="_blank">RFC3986</a>',
                parent_id=node.node_id, incoming_edge_config=urlparse_edge)

        if parsed_authority.password:
            unfurl.add_to_queue(
                data_type='url.password', key='Password', value=parsed_authority.password,
                hover='This is the <b>password</b> subcomponent of authority, '
                      'per <a href="https://tools.ietf.org/html/rfc3986" '
                      'target="_blank">RFC3986</a>',
                parent_id=node.node_id, incoming_edge_config=urlparse_edge)

        unfurl.add_to_queue(
            data_type='url.hostname', key='Host', value=parsed_authority.hostname,
            hover='This is the <b>host</b> subcomponent of authority (also often called '
                  'netloc), per <a href="https://tools.ietf.org/html/rfc3986" target="_blank">RFC3986</a>',
            parent_id=node.node_id, incoming_edge_config=urlparse_edge)

        if parsed_authority.port:
            unfurl.add_to_queue(
                data_type='url.port', key='Port', value=parsed_authority.port,
                hover='This is the <b>port</b> subcomponent of authority, '
                      'per <a href="https://tools.ietf.org/html/rfc3986" target="_blank">RFC3986</a>',
                parent_id=node.node_id, incoming_edge_config=urlparse_edge)

    elif node.data_type == 'url.query.pair':
        if node.key in ['l', 'lang', 'language', 'set-lang']:
            language = None

            if len(node.value) == 2:
                language = pycountry.languages.get(alpha_2=node.value)
            elif len(node.value) == 3:
                language = pycountry.languages.get(alpha_3=node.value)

            if language:
                unfurl.add_to_queue(
                    data_type='descriptor', key='Language', value=language.name,
                    hover='This is a generic parser based on common query-string patterns across websites',
                    parent_id=node.node_id, incoming_edge_config=urlparse_edge)
                return

        elif node.key in ['c', 'cc', 'country', 'country_code']:
            country = None

            if len(node.value) == 2:
                country = pycountry.countries.get(alpha_2=node.value)
            elif len(node.value) == 3:
                country = pycountry.countries.get(alpha_3=node.value)

            if country:
                unfurl.add_to_queue(
                    data_type='descriptor', key='Country', value=country.name,
                    hover='This is a generic parser based on common query-string patterns across websites',
                    parent_id=node.node_id, incoming_edge_config=urlparse_edge)
                return

        # If the query pair value is itself a URL, parse it as one.
        if not try_url_parse(unfurl, node):
            try_url_unquote(unfurl, node)

    elif node.data_type == 'url.path.segment':
        match = lookup_extension(node.value)
        if match:
            extension, file_type = match

            hover = f'The data type typically associated with <b>{extension}</b> ' \
                    f'is <b>{file_type.media_type}</b>'
            if file_type.description:
                hover += f' ({file_type.description})'
            hover += '.'
            if file_type.note:
                # Wrap each paragraph before joining them. wrap_hover_text leaves any
                # text that already contains a <br> alone -- the author is assumed to
                # have chosen the breaks -- so adding the separator first would mean
                # the note never gets wrapped at all.
                hover = f'{utils.wrap_hover_text(hover)}<br><br>' \
                        f'{utils.wrap_hover_text(file_type.note)}'

            unfurl.add_to_queue(
                data_type='file.name', key='File Name',
                value=urllib.parse.unquote_plus(node.value[:-len(extension)]),
                parent_id=node.node_id, incoming_edge_config=urlparse_edge)
            unfurl.add_to_queue(
                data_type='file.ext', key='File Extension', value=extension,
                hover=hover,
                parent_id=node.node_id, incoming_edge_config=urlparse_edge)

    else:
        if not isinstance(node.value, str):
            return

        parsed = try_url_parse(unfurl, node)
        if parsed:
            return

        # If the value contains more pairs of the form "a=b|c=d|e=f"
        pipe_delimited_pairs_re = re.compile(
            r'((?P<key>[^/|=]+)=(?P<value>[^/|=]+)\|)+(?P<last_key>[^/|=]+)=(?P<last_value>[^/|=]+)')
        m = pipe_delimited_pairs_re.fullmatch(node.value)
        if m:
            parse_delimited_string(unfurl, node, delimiter='|', pairs=True)
            return

        # If the value contains more values in the form "a|b|c|d|e|f"
        pipe_delimited_values_re = re.compile(
            r'((?P<value>[^/|]+)\|)+(?P<last_value>[^/|]+)')
        m = pipe_delimited_values_re.fullmatch(node.value)
        if m:
            parse_delimited_string(unfurl, node, delimiter='|')
            return

        # If the value contains more pairs of the form "a=b&c=d&e=f"
        amp_delimited_pairs_re = re.compile(
            r'((?P<key>[^/&=]+)=(?P<value>[^/&=]*)&)+(?P<last_key>[^/&=]+)=(?P<last_value>[^/&=]*)')
        m = amp_delimited_pairs_re.fullmatch(node.value)
        if m:
            parse_delimited_string(unfurl, node, delimiter='&', pairs=True)
            return

        try_url_unquote(unfurl, node)
