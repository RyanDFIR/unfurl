# Copyright 2025 Ryan Benson LLC
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

import re
from collections import Counter

cleaning_edge = {
    'color': {
        'color': '#2C63FF'
    },
    'title': 'Initial Cleaning Functions',
    'label': '🧹'
}

# "Defanging" rewrites an indicator so it can't be clicked or auto-linked by accident,
# which is how URLs, domains, IPs, and email addresses are usually shared in threat
# intel: "hxxps://evil[.]com". Each pattern here undoes one common convention.
#
# Some other conventions are deliberately left out. "{.}" shows up far more often as a
# template placeholder left in a URL ("{{.}}") than as defanging, and "\." as a Windows
# path ("..\..\") or regex, and both appear in hosts that were never defanged.
defang_markers = (
    (re.compile(r'\[://\]'), '://'),
    (re.compile(r'\[:\]'), ':'),
    (re.compile(r'\[/\]'), '/'),
    (re.compile(r'\[\.\]|\(\.\)|\[dot\]|\(dot\)', re.IGNORECASE), '.'),
    (re.compile(r'\[@\]|\[at\]|\(at\)', re.IGNORECASE), '@'),
)

# "hxxp" only counts as a masked scheme when a scheme separator (possibly defanged
# itself) follows it, so it isn't found inside a hostname like "shxxpt.com".
defanged_scheme_re = re.compile(r'\bhxxp(?=s?(?::|\[:\]|\[://\]))', re.IGNORECASE)

scheme_prefix_re = re.compile(r'[a-z][a-z0-9+.\-]*(?:://|\[://\]|\[:\]//)', re.IGNORECASE)

# A "/" ends the authority unless it is a defanged one, "[/]".
authority_end_re = re.compile(r'[?#]|(?<!\[)/|/(?!\])')


def scheme_and_authority(value):
    """The part of a possibly-defanged URL up to the end of its host (and port).

    With no scheme this is everything before the first "/" (other than a defanged "[/]"),
    "?" or "#", which covers a bare domain, IP, or email address as well as a scheme-less
    URL.
    """
    scheme_prefix = scheme_prefix_re.match(value)
    authority_start = scheme_prefix.end() if scheme_prefix else 0
    authority_end = authority_end_re.search(value, authority_start)
    return value[:authority_end.start()] if authority_end else value


def remove_whitespace(value):
    if ' ' not in value:
        return None
    return value.replace(' ', ''), 'Removed whitespace from input value'


def remove_outer_quotes(value):
    quoted_re = re.fullmatch(r'["\'](.*)["\']', value)
    if not quoted_re:
        return None
    return quoted_re.group(1), 'Removed outer quotes (" or \') from input value'


def refang(value):
    """Reverse common defanging conventions, if the value's scheme or host is defanged.

    Markers are only looked for in the scheme and host. A real URL can't have brackets
    there (an IPv6 literal aside, and no marker is a valid one), but it can have them in
    its path or query, so finding one there says nothing about whether the URL was
    defanged. Once the scheme or host shows it was, markers are reversed throughout the
    value, since defanging tools commonly bracket the dots in the path too.
    """
    head = scheme_and_authority(value)
    if not (defanged_scheme_re.search(head) or any(p.search(head) for p, _ in defang_markers)):
        return None

    replaced = Counter()

    def unmask_scheme(match):
        # Keep the case of each masked letter: "hXXp" becomes "hTTp", not "http".
        unmasked = ''.join({'x': 't', 'X': 'T'}.get(c, c) for c in match.group(0))
        replaced[(match.group(0), unmasked)] += 1
        return unmasked

    def replace_with(replacement):
        def substitute(match):
            replaced[(match.group(0), replacement)] += 1
            return replacement
        return substitute

    refanged = defanged_scheme_re.sub(unmask_scheme, value)
    for pattern, replacement in defang_markers:
        refanged = pattern.sub(replace_with(replacement), refanged)

    replacements = [
        f'"<b>{original}</b>" with "<b>{new}</b>"' + (f' ({count} times)' if count > 1 else '')
        for (original, new), count in replaced.items()]

    hover = ('Refanged the input value. "Defanging" rewrites a URL, domain, or IP so it '
             'can\'t be clicked or auto-linked by accident. <br><br>'
             f'Replaced {", ".join(replacements)}.')
    return refanged, hover


# Applied in this order. See run().
cleaning_steps = (remove_whitespace, remove_outer_quotes, refang)


def run(unfurl, node):

    if not isinstance(node.value, str):
        return

    # Cleaning applies to the input and to each cleaned version of it, so the steps can
    # build on each other: a quoted, defanged URL needs two.
    if node.node_id != 1 and node.incoming_edge_config is not cleaning_edge:
        return

    # Only the first step that changes the value runs here. Its result comes back through
    # this parser, where the next step gets its turn. That makes the cleaning one chain
    # from the input to the fully cleaned value, rather than a sibling per step that each
    # fixes one thing (and a duplicate branch for every order they could be applied in).
    for step in cleaning_steps:
        cleaned = step(node.value)
        if cleaned:
            cleaned_value, hover = cleaned
            unfurl.add_to_queue(data_type=node.data_type, key=node.key, value=cleaned_value,
                                hover=hover, parent_id=node.node_id,
                                incoming_edge_config=cleaning_edge)
            return
