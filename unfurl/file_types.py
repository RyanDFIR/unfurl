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

"""File extension knowledge used when a URL path segment looks like a filename.

Python's ``mimetypes.types_map`` is the obvious source for this, but it is built
for serving web content, not for examining evidence. It carries ~154 entries and
omits nearly everything an analyst actually finds in a cloud-storage or download
URL: no ``.docx``/``.xlsx``/``.pptx``, no ``.rar``/``.7z``/``.iso``, and none of
the Windows script and installer formats used to deliver malware.

This module keeps an Unfurl-owned table of those extensions and merges it over
``mimetypes``. Owning the table also buys a place to record *why* an extension
matters, which a media type alone cannot express -- an analyst is better served
by "Windows shortcut; frequently abused to launch commands" than by
``application/x-ms-shortcut``.

The table is deliberately additive. Extensions that collide with common non-file
path segments are left out on purpose; see ``EXCLUDED_EXTENSIONS``.
"""

import mimetypes
from typing import NamedTuple, Optional, Tuple


class FileType(NamedTuple):
    """What Unfurl knows about one file extension."""

    media_type: str
    description: Optional[str] = None
    # Why an analyst should care. Shown in hover text when present.
    note: Optional[str] = None


# Extensions Unfurl deliberately refuses to recognize, because the false
# positives cost more than the hits are worth:
#
#   .com  - a TLD before it is an MS-DOS executable. Any path segment holding a
#           bare hostname ("example.com", common in redirect paths) would be
#           mislabeled as an executable, which is a scary and wrong finding.
#   .url  - a real Windows shortcut format, but "*.url" also matches ordinary
#           words and route names in paths.
#
# The single-character extensions mimetypes ships (.a .c .h .o .t) are compiler
# and archive artifacts that essentially never appear as a shared file in a URL,
# while matching any path segment whose last dot-group is one character. Measured
# against 23,186 path segments from general web traffic, ".o" alone accounted for
# every remaining false positive -- cache-busting tokens like
# "k=xjs.s.ja.NOfIU4zhi6w.O". Case-insensitive matching makes them worse, so they
# are excluded rather than special-cased.
EXCLUDED_EXTENSIONS = frozenset({'.com', '.url', '.a', '.c', '.h', '.o', '.t'})


# Extensions Unfurl knows about beyond what mimetypes provides. Where an
# extension has no registered IANA media type, the de-facto type in common use
# is recorded instead; genuinely ambiguous containers get
# application/octet-stream rather than an invented type.
UNFURL_FILE_TYPES = {
    # -- Microsoft Office, OOXML --------------------------------------------
    '.docx': FileType(
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'Microsoft Word document'),
    '.xlsx': FileType(
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'Microsoft Excel workbook'),
    '.pptx': FileType(
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'Microsoft PowerPoint presentation'),
    '.docm': FileType(
        'application/vnd.ms-word.document.macroEnabled.12',
        'Microsoft Word document, macro-enabled',
        'Macro-enabled Office formats can carry VBA code and are a long-standing '
        'malware delivery vector.'),
    '.xlsm': FileType(
        'application/vnd.ms-excel.sheet.macroEnabled.12',
        'Microsoft Excel workbook, macro-enabled',
        'Macro-enabled Office formats can carry VBA code and are a long-standing '
        'malware delivery vector.'),
    '.pptm': FileType(
        'application/vnd.ms-powerpoint.presentation.macroEnabled.12',
        'Microsoft PowerPoint presentation, macro-enabled',
        'Macro-enabled Office formats can carry VBA code and are a long-standing '
        'malware delivery vector.'),
    '.one': FileType('application/onenote', 'Microsoft OneNote section'),
    '.msg': FileType('application/vnd.ms-outlook', 'Microsoft Outlook message'),
    '.pst': FileType(
        'application/vnd.ms-outlook-pst', 'Microsoft Outlook personal folders',
        'A full offline mailbox. Rarely shared innocently -- a common bulk email '
        'exfiltration artifact.'),
    '.ost': FileType(
        'application/vnd.ms-outlook-ost', 'Microsoft Outlook offline folders',
        'A full offline mailbox. Rarely shared innocently -- a common bulk email '
        'exfiltration artifact.'),

    # -- OpenDocument -------------------------------------------------------
    '.odt': FileType('application/vnd.oasis.opendocument.text', 'OpenDocument text'),
    '.ods': FileType('application/vnd.oasis.opendocument.spreadsheet', 'OpenDocument spreadsheet'),
    '.odp': FileType('application/vnd.oasis.opendocument.presentation', 'OpenDocument presentation'),

    # -- Archives and disk images -------------------------------------------
    '.rar': FileType('application/vnd.rar', 'RAR archive'),
    '.7z': FileType('application/x-7z-compressed', '7-Zip archive'),
    '.gz': FileType('application/gzip', 'gzip-compressed data'),
    '.tar.gz': FileType('application/gzip', 'gzip-compressed tar archive'),
    '.tgz': FileType('application/gzip', 'gzip-compressed tar archive'),
    '.tar.bz2': FileType('application/x-bzip2', 'bzip2-compressed tar archive'),
    '.bz2': FileType('application/x-bzip2', 'bzip2-compressed data'),
    '.tar.xz': FileType('application/x-xz', 'xz-compressed tar archive'),
    '.xz': FileType('application/x-xz', 'xz-compressed data'),
    '.zst': FileType('application/zstd', 'Zstandard-compressed data'),
    '.cab': FileType('application/vnd.ms-cab-compressed', 'Microsoft cabinet archive'),
    '.wim': FileType('application/x-ms-wim', 'Windows Imaging Format archive'),
    '.iso': FileType(
        'application/x-iso9660-image', 'ISO 9660 disc image',
        'Disc images mount without applying the Mark-of-the-Web to their contents, '
        'which is why they became a favored malware container.'),
    '.img': FileType(
        'application/octet-stream', 'Raw disk image',
        'Disc images mount without applying the Mark-of-the-Web to their contents, '
        'which is why they became a favored malware container.'),
    '.vhd': FileType('application/x-vhd', 'Virtual hard disk'),
    '.vhdx': FileType('application/x-vhdx', 'Virtual hard disk (VHDX)'),
    '.vmdk': FileType('application/x-vmdk', 'VMware virtual disk'),
    '.ova': FileType('application/x-virtualbox-ova', 'Open Virtualization Appliance'),

    # -- Windows executables, installers, and scripts -----------------------
    '.msi': FileType(
        'application/x-msi', 'Windows Installer package',
        'Executes with installer privileges; a common malware delivery format.'),
    '.msix': FileType('application/msix', 'Windows MSIX application package'),
    '.appx': FileType('application/vnd.ms-appx', 'Windows APPX application package'),
    '.lnk': FileType(
        'application/x-ms-shortcut', 'Windows shortcut',
        'A shortcut stores an arbitrary command line, so a .lnk can launch anything. '
        'Heavily abused in phishing since macros were restricted by default.'),
    '.scr': FileType(
        'application/x-msdownload', 'Windows screensaver (a PE executable)',
        'A .scr is an ordinary Windows executable with a different extension -- a '
        'classic disguise.'),
    '.pif': FileType(
        'application/x-msdownload', 'Program Information File',
        'Legacy MS-DOS shortcut format that Windows will execute as a program.'),
    '.cpl': FileType(
        'application/x-msdownload', 'Windows Control Panel item (a DLL)',
        'A .cpl is a DLL that Windows will load and run.'),
    '.hta': FileType(
        'application/hta', 'HTML Application',
        'Runs script outside the browser sandbox with full user privileges.'),
    '.vbs': FileType(
        'text/vbscript', 'VBScript script',
        'Executed by Windows Script Host with the invoking user\'s privileges.'),
    '.vbe': FileType(
        'text/vbscript', 'Encoded VBScript script',
        'Executed by Windows Script Host with the invoking user\'s privileges.'),
    '.jse': FileType(
        'text/javascript', 'Encoded JScript script',
        'Executed by Windows Script Host with the invoking user\'s privileges.'),
    '.wsf': FileType(
        'application/x-ms-wsf', 'Windows Script File',
        'Executed by Windows Script Host with the invoking user\'s privileges.'),
    '.wsh': FileType('application/x-ms-wsh', 'Windows Script Host settings file'),
    '.ps1': FileType('application/x-powershell', 'PowerShell script'),
    '.psm1': FileType('application/x-powershell', 'PowerShell module'),
    '.cmd': FileType('application/x-bat', 'Windows command script'),
    '.chm': FileType(
        'application/vnd.ms-htmlhelp', 'Compiled HTML Help',
        'Can embed and execute script; used to deliver malware.'),
    '.reg': FileType(
        'text/plain', 'Windows registry export',
        'Double-clicking imports the contents into the registry.'),
    '.inf': FileType('text/plain', 'Windows setup information file'),
    '.sys': FileType('application/octet-stream', 'Windows system/driver file'),
    '.settingcontent-ms': FileType(
        'application/xml', 'Windows settings shortcut',
        'An XML format that can specify an arbitrary command to execute.'),
    '.diagcab': FileType(
        'application/vnd.ms-cab-compressed', 'Windows troubleshooting package',
        'A signed cabinet that can run script through the diagnostics platform.'),

    # -- Other platforms ----------------------------------------------------
    '.apk': FileType('application/vnd.android.package-archive', 'Android application package'),
    '.aab': FileType('application/octet-stream', 'Android App Bundle'),
    '.ipa': FileType('application/octet-stream', 'iOS application archive'),
    '.dmg': FileType('application/x-apple-diskimage', 'Apple disk image'),
    '.pkg': FileType('application/octet-stream', 'macOS installer package'),
    '.deb': FileType('application/vnd.debian.binary-package', 'Debian package'),
    '.rpm': FileType('application/x-rpm', 'RPM package'),
    '.jar': FileType('application/java-archive', 'Java archive'),
    '.crx': FileType('application/x-chrome-extension', 'Chrome extension package'),
    '.xpi': FileType('application/x-xpinstall', 'Firefox extension package'),

    # -- Data, databases, and forensic artifacts ----------------------------
    '.sqlite': FileType('application/vnd.sqlite3', 'SQLite database'),
    '.sqlite3': FileType('application/vnd.sqlite3', 'SQLite database'),
    '.db': FileType('application/octet-stream', 'Database file (format varies)'),
    '.evtx': FileType('application/octet-stream', 'Windows event log'),
    '.pcap': FileType('application/vnd.tcpdump.pcap', 'Packet capture'),
    '.pcapng': FileType('application/x-pcapng', 'Packet capture (pcapng)'),
    '.log': FileType('text/plain', 'Log file'),
    '.ini': FileType('text/plain', 'Configuration file'),
    '.torrent': FileType('application/x-bittorrent', 'BitTorrent metainfo file'),
    '.epub': FileType('application/epub+zip', 'EPUB publication'),

    # -- Media not covered by mimetypes -------------------------------------
    '.mkv': FileType('video/x-matroska', 'Matroska video'),
    '.heif': FileType('image/heif', 'HEIF image'),
    '.avif': FileType('image/avif', 'AVIF image'),
    '.opus': FileType('audio/opus', 'Opus audio'),
    '.flac': FileType('audio/flac', 'FLAC audio'),
}


def _build_extension_map() -> dict:
    """Merge the Unfurl table over mimetypes, honoring EXCLUDED_EXTENSIONS."""

    combined = {}
    for extension, media_type in mimetypes.types_map.items():
        if extension in EXCLUDED_EXTENSIONS:
            continue
        combined[extension.lower()] = FileType(media_type)

    for extension, file_type in UNFURL_FILE_TYPES.items():
        if extension in EXCLUDED_EXTENSIONS:
            continue
        combined[extension.lower()] = file_type

    return combined


# Extension -> FileType. Keys are lowercase; look up with a lowercased value.
EXTENSION_MAP = _build_extension_map()

# The most dots any known extension contains (".tar.gz" -> 2). Bounds how far
# back a candidate search has to look.
_MAX_EXTENSION_PARTS = max(extension.count('.') for extension in EXTENSION_MAP)


def lookup_extension(segment: str) -> Optional[Tuple[str, FileType]]:
    """Find the longest known extension that ``segment`` ends with.

    Returns ``(extension_as_written, FileType)``, or None when the segment does
    not end in a recognized extension or has no filename before it.

    Matching is case-insensitive -- real URLs carry ``.JPG`` as readily as
    ``.jpg`` -- but the returned extension preserves the original casing so the
    node shows what the URL actually said.

    Longest match wins, so ``backup.tar.gz`` reports ``.tar.gz`` rather than
    ``.gz``.
    """

    if not segment or '.' not in segment:
        return None

    parts = segment.split('.')

    # Try the most dot-separated candidate first (".tar.gz" before ".gz") so the
    # longest known extension wins.
    for part_count in range(min(_MAX_EXTENSION_PARTS, len(parts) - 1), 0, -1):
        candidate = '.' + '.'.join(parts[-part_count:])
        file_type = EXTENSION_MAP.get(candidate.lower())
        if file_type is None:
            continue

        # Require something before the extension; a segment that is *only* an
        # extension (".pdf", or a dotfile like ".gitignore") is not a filename
        # with a meaningful name part.
        if len(segment) == len(candidate):
            return None

        return candidate, file_type

    return None
