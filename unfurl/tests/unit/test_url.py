from unfurl.core import Unfurl
import unittest


class TestUrl(unittest.TestCase):

    def test_url(self):
        """ Test a generic URL with a query string"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.test-example.com/testing/1?2=3&4=5')
        test.parse_queue()

        # confirm the scheme is parsed
        self.assertIn('https', test.nodes[2].label)

        # confirm the scheme is parsed
        self.assertEqual('/testing/1', test.nodes[4].label)

        # confirm the query string params parse
        self.assertEqual('4: 5', test.nodes[12].label)

    def test_lang_param(self):
        """ Test a URL with a language query string param"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.test-example.com/testing/1?2=3&4=5&lang=en')
        test.parse_queue()

        # confirm the scheme is parsed
        self.assertIn('English', test.nodes[14].label)

    def test_file_path_url(self):
        """ Test a URL that ends with a file path"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://dfir.blog/content/images/2019/01/logo.png')
        test.parse_queue()

        # confirm the scheme is parsed
        self.assertIn('File Extension: .png', test.nodes[13].label)


    def test_single_path_segment(self):
        """Test that a path with only one segment is still split into a segment node.

        Regression test for https://github.com/RyanDFIR/unfurl/issues/220
        """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None, value='https://example.com/@RyanDFIR')
        test.parse_queue()

        segments = {node.key: node.value for node in test.nodes.values()
                    if node.data_type == 'url.path.segment'}
        self.assertEqual({1: '@RyanDFIR'}, segments)

    def test_path_segment_numbering(self):
        """Test that path segments are numbered from 1, ignoring empty segments.

        Empty segments (from adjacent slashes) are left out of the numbering, so a
        path containing them is numbered the same as the equivalent path without.
        Parsers key on segment position, so this keeps them matching either way; the
        empty segment itself is reported separately as a descriptor.
        """

        def segments_for(url):
            test = Unfurl()
            test.add_to_queue(data_type='url', key=None, value=url)
            test.parse_queue()
            return {node.key: node.value for node in test.nodes.values()
                    if node.data_type == 'url.path.segment'}

        self.assertEqual({1: 'a', 2: 'b', 3: 'c'}, segments_for('https://example.com/a/b/c'))

        # A trailing slash does not add an empty segment
        self.assertEqual({1: 'a', 2: 'b', 3: 'c'}, segments_for('https://example.com/a/b/c/'))

        # Empty segments are skipped wherever they appear: leading, middle, trailing
        self.assertEqual({1: 'a', 2: 'b'}, segments_for('https://example.com//a/b'))
        self.assertEqual({1: 'a', 2: 'b'}, segments_for('https://example.com/a//b'))
        self.assertEqual({1: 'a', 2: 'b'}, segments_for('https://example.com/a/b//'))
        self.assertEqual({1: 'a', 2: 'b'}, segments_for('https://example.com///a///b///'))

        # A path with no segments at all yields none
        self.assertEqual({}, segments_for('https://example.com//'))

        # The raw path is preserved verbatim, even though segments are normalized
        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value='https://example.com//a//b')
        test.parse_queue()
        paths = [node.value for node in test.nodes.values() if node.data_type == 'url.path']
        self.assertEqual(['//a//b'], paths)

    def test_empty_path_segment_descriptor(self):
        """Test that an empty path segment ("//") is called out to the user.

        Segment numbering normalizes away leading empty segments so that parsers
        keying on segment 1 still match; this descriptor keeps that visible.
        """

        def empty_segment_descriptors(unfurl_instance):
            return [node.value for node in unfurl_instance.nodes.values()
                    if node.data_type == 'descriptor'
                    and str(node.value).startswith('Path contains an empty segment')]

        # A doubled slash anywhere in the path is flagged
        for url in ('https://example.com//a/b',
                    'https://example.com/a//b',
                    'https://example.com/a/b//',
                    'https://example.com///a'):
            test = Unfurl()
            test.add_to_queue(data_type='url', key=None, value=url)
            test.parse_queue()
            self.assertEqual(
                ['Path contains an empty segment ("//")'], empty_segment_descriptors(test),
                msg=f'expected an empty-segment descriptor for {url}')

        # Ordinary paths, including a normal trailing slash, are not flagged
        for url in ('https://example.com/a/b',
                    'https://example.com/a/b/',
                    'https://example.com/a',
                    'https://example.com/'):
            test = Unfurl()
            test.add_to_queue(data_type='url', key=None, value=url)
            test.parse_queue()
            self.assertEqual(
                [], empty_segment_descriptors(test),
                msg=f'did not expect an empty-segment descriptor for {url}')

    def test_text_fragment(self):
        """Test that Text Fragments (#:~:text=...) are parsed.

        Regression test for https://github.com/RyanDFIR/unfurl/issues/140
        """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://blog.chromium.org/2019/12/chrome-80-content-indexing-es-modules.html'
                  '#:~:text=ECMAScript%20Modules%20in%20Web%20Workers')
        test.parse_queue()

        # confirm the text fragment is parsed out with the decoded text
        text_fragments = [node for node in test.nodes.values()
                          if node.data_type == 'url.fragment.text-fragment']
        self.assertEqual(1, len(text_fragments))
        self.assertEqual('ECMAScript Modules in Web Workers', text_fragments[0].value)

    def test_text_fragment_multiple(self):
        """Test that multiple Text Fragments are each parsed as separate nodes."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://example.com/page#:~:text=first%20match&text=second%20match')
        test.parse_queue()

        text_fragments = [node for node in test.nodes.values()
                          if node.data_type == 'url.fragment.text-fragment']
        self.assertEqual(2, len(text_fragments))
        self.assertEqual('first match', text_fragments[0].value)
        self.assertEqual('second match', text_fragments[1].value)

    def test_text_fragment_with_anchor(self):
        """Test a fragment that has both a traditional anchor and a text fragment."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://example.com/page#heading1:~:text=highlighted%20text')
        test.parse_queue()

        text_fragments = [node for node in test.nodes.values()
                          if node.data_type == 'url.fragment.text-fragment']
        self.assertEqual(1, len(text_fragments))
        self.assertEqual('highlighted text', text_fragments[0].value)

    def test_query_param_no_value(self):
        """Test that query parameters with no value are preserved."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.facebook.com/photo.php?type=3&theater')
        test.parse_queue()

        # confirm that both query params are present, including the valueless "theater"
        query_pairs = {node.key: node.value for node in test.nodes.values()
                       if node.data_type == 'url.query.pair'}
        self.assertIn('type', query_pairs)
        self.assertIn('theater', query_pairs)
        self.assertEqual('3', query_pairs['type'])
        self.assertEqual('', query_pairs['theater'])


if __name__ == '__main__':
    unittest.main()
