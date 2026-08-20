from unfurl.core import Unfurl
from unfurl.file_types import EXCLUDED_EXTENSIONS, lookup_extension
import unittest


def file_nodes(unfurl_instance):
    """Return {data_type: value} for the file.name / file.ext nodes in a graph."""

    return {node.data_type: node.value for node in unfurl_instance.nodes.values()
            if node.data_type in ('file.name', 'file.ext')}


def hover_for(unfurl_instance, data_type):
    for node in unfurl_instance.nodes.values():
        if node.data_type == data_type:
            return node.hover
    return None


def unfurl_url(value):
    test = Unfurl()
    test.add_to_queue(data_type='url', key=None, value=value)
    test.parse_queue()
    return test


class TestLookupExtension(unittest.TestCase):
    """Unit tests for the extension table itself."""

    def test_office_open_xml_extensions(self):
        """Office documents are the most common cloud-storage filenames and are
        absent from Python's mimetypes."""

        for filename, expected in (('Budget FY26.xlsx', '.xlsx'),
                                   ('Report.docx', '.docx'),
                                   ('Deck.pptx', '.pptx')):
            with self.subTest(filename=filename):
                match = lookup_extension(filename)
                self.assertIsNotNone(match)
                self.assertEqual(expected, match[0])

    def test_archive_extensions(self):
        for filename, expected in (('hanyu.rar', '.rar'),
                                   ('payload.7z', '.7z'),
                                   ('disk.iso', '.iso'),
                                   ('setup.msi', '.msi')):
            with self.subTest(filename=filename):
                match = lookup_extension(filename)
                self.assertIsNotNone(match)
                self.assertEqual(expected, match[0])

    def test_longest_extension_wins(self):
        """'.tar.gz' must beat '.gz', otherwise the name keeps a stray '.tar'."""

        match = lookup_extension('backup.tar.gz')
        self.assertIsNotNone(match)
        self.assertEqual('.tar.gz', match[0])

        match = lookup_extension('backup.tar.bz2')
        self.assertIsNotNone(match)
        self.assertEqual('.tar.bz2', match[0])

    def test_matching_is_case_insensitive_but_preserves_casing(self):
        """Real URLs carry '.JPG'; the node should still say '.JPG'."""

        match = lookup_extension('林暮色16部A.JPG')
        self.assertIsNotNone(match)
        self.assertEqual('.JPG', match[0])
        self.assertEqual('image/jpeg', match[1].media_type)

    def test_mimetypes_entries_still_resolve(self):
        """The Unfurl table supplements mimetypes rather than replacing it."""

        match = lookup_extension('logo.png')
        self.assertIsNotNone(match)
        self.assertEqual('.png', match[0])
        self.assertEqual('image/png', match[1].media_type)

    def test_excluded_extensions_do_not_match(self):
        """'.com' and '.url' collide with ordinary path segments, so a segment
        holding a bare hostname must not be reported as an executable."""

        self.assertIn('.com', EXCLUDED_EXTENSIONS)
        self.assertIsNone(lookup_extension('example.com'))
        self.assertIsNone(lookup_extension('route.url'))

    def test_single_character_extensions_do_not_match(self):
        """mimetypes ships .a/.c/.h/.o/.t; case-insensitive matching turns them
        into noise on cache-busting tokens and truncated hostnames."""

        self.assertIsNone(lookup_extension('k=xjs.s.ja.NOfIU4zhi6w.O'))
        self.assertIsNone(lookup_extension('news.bbc.c'))

    def test_segment_that_is_only_an_extension_does_not_match(self):
        """A dotfile or bare extension has no name part to report."""

        self.assertIsNone(lookup_extension('.pdf'))
        self.assertIsNone(lookup_extension('.gitignore'))

    def test_non_filenames_do_not_match(self):
        for value in ('v1.2', 'index.php', 'noext', '', 'segment'):
            with self.subTest(value=value):
                self.assertIsNone(lookup_extension(value))

    def test_forensic_note_present_on_notable_types(self):
        match = lookup_extension('invoice.pdf.lnk')
        self.assertIsNotNone(match)
        self.assertEqual('.lnk', match[0])
        self.assertIsNotNone(match[1].note)


class TestFileTypesInUrls(unittest.TestCase):
    """End-to-end: the extensions show up as nodes when parsing a real URL."""

    def test_sharepoint_office_document(self):
        """Regression: '.xlsx' produced no file nodes at all before the
        Unfurl-owned extension table existed."""

        test = unfurl_url(
            'https://contoso-my.sharepoint.com/:w:/r/personal/john_contoso_com'
            '/Documents/Budget%20FY26.xlsx?csf=1&web=1')

        nodes = file_nodes(test)
        self.assertEqual('Budget FY26', nodes.get('file.name'))
        self.assertEqual('.xlsx', nodes.get('file.ext'))

    def test_mediafire_archive(self):
        test = unfurl_url(
            'https://www.mediafire.com/file/0000nmedi480w2n/hanyu.rar')

        nodes = file_nodes(test)
        self.assertEqual('hanyu', nodes.get('file.name'))
        self.assertEqual('.rar', nodes.get('file.ext'))

    def test_backblaze_uppercase_extension(self):
        """Percent-encoded non-ASCII name with an uppercase extension, taken
        from a real Wayback corpus URL."""

        test = unfurl_url(
            'https://f000.backblazeb2.com/file/2023-2/'
            '%E6%9E%97%E6%9A%AE%E8%89%B216%E9%83%A8A.JPG')

        nodes = file_nodes(test)
        self.assertEqual('林暮色16部A', nodes.get('file.name'))
        self.assertEqual('.JPG', nodes.get('file.ext'))

    def test_compound_extension_in_url(self):
        test = unfurl_url('https://example.com/dist/release-2.1.tar.gz')

        nodes = file_nodes(test)
        self.assertEqual('release-2.1', nodes.get('file.name'))
        self.assertEqual('.tar.gz', nodes.get('file.ext'))

    def test_hostname_in_path_is_not_treated_as_a_file(self):
        """A path segment holding a bare hostname must not yield file nodes."""

        test = unfurl_url('https://example.com/redirect/example.com/next')
        self.assertEqual({}, file_nodes(test))

    def test_hover_includes_description_and_note(self):
        test = unfurl_url('https://example.com/downloads/invoice.pdf.lnk')

        nodes = file_nodes(test)
        self.assertEqual('invoice.pdf', nodes.get('file.name'))
        self.assertEqual('.lnk', nodes.get('file.ext'))

        hover = hover_for(test, 'file.ext')
        self.assertIn('application/x-ms-shortcut', hover)
        self.assertIn('Windows shortcut', hover)


if __name__ == '__main__':
    unittest.main()
