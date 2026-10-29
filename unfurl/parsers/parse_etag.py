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

import re

etag_edge = {
    'color': {
        'color': '#8B5A2B'
    },
    'title': 'ETag Parsing Functions',
    'label': 'ET'
}

# An ETag as it appears in an HTTP header: a quoted string, optionally marked weak with W/.
# Some sites mangle the weak marker into its own quoted string ("W/" "...") when copying it.
quoted_etag_re = re.compile(r'(?P<weak>W/|"W/" )?"(?P<tag>[^"]{1,200})"')

# Hex fields separated by hyphens, with an optional non-hex suffix that some servers
# append (Apache's mod_deflate adds "-gzip" to the ETag of a compressed response).
hex_fields_re = re.compile(r'(?P<fields>[0-9a-f]+(?:-[0-9a-f]+){1,2})(?:-(?P<suffix>[a-z]+))?')

# Express and other Node.js servers using the "etag" package tag a response body with
# hex(length)-base64(SHA-1), the hash truncated to 27 characters.
body_hash_re = re.compile(r'(?P<length>[0-9a-f]+)-(?P<hash>[A-Za-z0-9+/]{27})')

# Amazon S3 multipart uploads: the MD5 of the concatenated part MD5s, then the part count.
s3_multipart_re = re.compile(r'(?P<md5>[0-9a-f]{32})-(?P<parts>[1-9]\d{0,4})')

# File modification times are only decoded when they land in 2000 <= ts <= 2030.
MTIME_MIN = 946684800
MTIME_MAX = 1893456000

# How many hex digits an mtime has in each unit across that range, and the timestamp
# data_type that converts it. 12 and 14 digits fall outside the range in every unit.
MTIME_UNITS = {
    8: ('epoch-seconds', 1, 'seconds'),
    11: ('epoch-milliseconds', 1_000, 'milliseconds'),
    13: ('epoch-microseconds', 1_000_000, 'microseconds'),
}

ETAG_HOVER = ('An ETag is a validator a web server sends in a response header so a client can '
              'later ask whether its cached copy is still current. Many servers build it from '
              'the file\'s size and modification time. '
              '<a href="https://thelocalh0st.com/posts/etag-download-forensics/" target="_blank">[ref]</a>')

FORMAT_HINTS = {
    ('size', 'seconds'): '',
    ('size', 'milliseconds'): ' (typical of Node.js servers using the "etag" package)',
    ('size', 'microseconds'): ' (typical of Apache httpd)',
    ('inode', 'microseconds'): ' (Apache httpd with the INode FileETag component)',
    ('nginx', 'seconds'): ' (nginx)',
}


def mtime_unit(hex_value):
    """Return (data_type, unit name) if hex_value reads as a plausible mtime, else None."""
    unit = MTIME_UNITS.get(len(hex_value))
    if not unit:
        return None
    data_type, scale, name = unit
    if MTIME_MIN <= int(hex_value, 16) / scale <= MTIME_MAX:
        return data_type, name
    return None


def interpret_fields(fields):
    """Work out which hex field is which, returning None unless exactly one layout fits.

    Layouts, by producer:
      size-mtime          Apache httpd 2.4 (mtime in microseconds), Node.js etag (milliseconds), others
      mtime-size          nginx (mtime in seconds)
      inode-size-mtime    Apache httpd with FileETag INode (mtime in microseconds)
    """
    if len(fields) == 3:
        unit = mtime_unit(fields[2])
        if unit:
            return {'layout': 'inode', 'inode': fields[0], 'size': fields[1], 'mtime': fields[2], 'unit': unit}
        return None

    first, second = fields
    as_size_mtime = mtime_unit(second)
    as_nginx = mtime_unit(first) if len(first) == 8 else None

    # Both readings only fit when the size field is itself a plausible time (a file of
    # roughly 1 GB or more), so there is no telling them apart; leave it undecoded.
    if as_size_mtime and as_nginx:
        return None
    if as_size_mtime:
        return {'layout': 'size', 'size': first, 'mtime': second, 'unit': as_size_mtime}
    if as_nginx:
        return {'layout': 'nginx', 'size': second, 'mtime': first, 'unit': as_nginx}
    return None


def parse_file_etag(unfurl, node, tag):
    m = hex_fields_re.fullmatch(tag)
    if not m:
        return False

    layout = interpret_fields(m['fields'].split('-'))
    if not layout:
        return False

    unit_type, unit_name = layout['unit']
    if layout['layout'] == 'inode':
        description = 'hex(inode)-hex(size)-hex(mtime)'
    elif layout['layout'] == 'nginx':
        description = 'hex(mtime)-hex(size)'
    else:
        description = 'hex(size)-hex(mtime)'

    unfurl.add_to_queue(
        data_type='etag.format', key=None, value=description,
        label=f'ETag format: {description}, mtime in {unit_name}'
              f'{FORMAT_HINTS.get((layout["layout"], unit_name), "")}',
        hover=ETAG_HOVER, parent_id=node.node_id, incoming_edge_config=etag_edge)

    if layout['layout'] == 'inode':
        inode = int(layout['inode'], 16)
        unfurl.add_to_queue(
            data_type='etag.inode', key=None, value=inode, label=f'Inode: {inode}',
            hover='The file\'s inode number on the origin server',
            parent_id=node.node_id, incoming_edge_config=etag_edge)

    size = int(layout['size'], 16)
    unfurl.add_to_queue(
        data_type='etag.size', key=None, value=size, label=f'File size: {size:,} bytes',
        hover='The size of the file on the origin server when the ETag was generated',
        parent_id=node.node_id, incoming_edge_config=etag_edge)

    mtime = int(layout['mtime'], 16)
    unfurl.add_to_queue(
        data_type=unit_type, key=None, value=mtime, label=f'File last modified: {mtime}',
        hover='The modification time of the file on the origin server when the ETag was generated',
        parent_id=node.node_id, incoming_edge_config=etag_edge)

    if m['suffix']:
        hover = 'Text the server appended to the ETag'
        if m['suffix'] in ('gzip', 'br'):
            hover = (f'Apache httpd appends "-{m["suffix"]}" to the ETag when it compresses the '
                     f'response, so this file was served {m["suffix"]}-compressed')
        unfurl.add_to_queue(
            data_type='etag.suffix', key=None, value=m['suffix'], label=f'ETag suffix: {m["suffix"]}',
            hover=hover, parent_id=node.node_id, incoming_edge_config=etag_edge)

    return True


def parse_body_hash_etag(unfurl, node, tag):
    m = body_hash_re.fullmatch(tag)
    if not m:
        return False

    unfurl.add_to_queue(
        data_type='etag.format', key=None, value='hex(length)-base64(SHA-1)',
        label='ETag format: hex(length)-base64(SHA-1) (typical of Node.js servers using the "etag" package)',
        hover=ETAG_HOVER, parent_id=node.node_id, incoming_edge_config=etag_edge)

    length = int(m['length'], 16)
    unfurl.add_to_queue(
        data_type='etag.size', key=None, value=length, label=f'Response body size: {length:,} bytes',
        parent_id=node.node_id, incoming_edge_config=etag_edge)

    unfurl.add_to_queue(
        data_type='etag.hash', key=None, value=m['hash'], label=f'SHA-1 of body (base64, truncated): {m["hash"]}',
        hover='The first 27 characters of the base64-encoded SHA-1 hash of the response body',
        parent_id=node.node_id, incoming_edge_config=etag_edge)
    return True


def parse_s3_multipart_etag(unfurl, node, tag):
    m = s3_multipart_re.fullmatch(tag)
    if not m:
        return False

    unfurl.add_to_queue(
        data_type='etag.hash', key=None, value=m['md5'], label=f'MD5 of part MD5s: {m["md5"]}',
        hover='For a multipart upload, Amazon S3 sets the ETag to the MD5 of the concatenated '
              'binary MD5s of each part, so it is not the MD5 of the whole file',
        parent_id=node.node_id, incoming_edge_config=etag_edge)

    unfurl.add_to_queue(
        data_type='etag.parts', key=None, value=int(m['parts']), label=f'Multipart upload parts: {m["parts"]}',
        hover='The number of parts the object was uploaded in (typical of Amazon S3 and S3-compatible storage)',
        parent_id=node.node_id, incoming_edge_config=etag_edge)
    return True


def parse_etag(unfurl, node, tag, weak):
    """Decode an ETag's contents (quotes and W/ already removed). Returns True if decoded."""
    decoded = (parse_file_etag(unfurl, node, tag)
               or parse_body_hash_etag(unfurl, node, tag)
               or parse_s3_multipart_etag(unfurl, node, tag))

    if decoded and weak:
        unfurl.add_to_queue(
            data_type='etag.weak', key=None, value=True, label='Weak ETag (W/ prefix)',
            hover='A weak ETag says the content is equivalent, not necessarily byte-for-byte identical',
            parent_id=node.node_id, incoming_edge_config=etag_edge)
    return decoded


def run(unfurl, node):
    if not isinstance(node.value, str) or node.data_type.startswith('etag'):
        return

    # Some sites copy a file's ETag into a URL parameter as a cache buster, quotes and all.
    if node.data_type == 'url.query.pair' and str(node.key).lower() == 'etag':
        m = quoted_etag_re.fullmatch(node.value)
        tag, weak = (m['tag'], m['weak']) if m else (node.value, None)
        if parse_etag(unfurl, node, tag, weak):
            node.hover = ETAG_HOVER
        return

    # Elsewhere, only a value quoted the way it is in a header (as copied from a browser
    # cache or HTTP log) is treated as an ETag; a bare "hex-hex" is too common to guess from.
    m = quoted_etag_re.fullmatch(node.value)
    if m and parse_etag(unfurl, node, m['tag'], m['weak']):
        node.hover = ETAG_HOVER
