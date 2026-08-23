from unfurl.core import Unfurl
from unfurl.parsers import parse_url
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


class TestUrlUnquoting(unittest.TestCase):
    """"+" means a space in a query string and a literal plus everywhere else.

    parse_url's final branch is a catch-all that runs on any node holding a string,
    including data types other parsers invent, so decoding "+" as a space there
    corrupted values it had no business touching.
    """

    class FakeNode:
        node_id = 1

        def __init__(self, value):
            self.value = value

    def unquote(self, value, plus_is_space=False):
        """Return the values try_url_unquote would emit for `value`."""
        test = Unfurl()
        changed = parse_url.try_url_unquote(
            test, self.FakeNode(value), plus_is_space=plus_is_space)
        emitted = [item['value'] for item in list(test.queue.queue)]
        return changed, emitted

    def test_literal_plus_is_left_alone(self):
        """A Gmail compose payload separates its IDs with "+"; they are not spaces."""
        changed, emitted = self.unquote('a:r-21+msg-a:r-45')
        self.assertFalse(changed)
        self.assertEqual(emitted, [])

    def test_plus_becomes_a_space_when_asked(self):
        changed, emitted = self.unquote('dfir+data', plus_is_space=True)
        self.assertTrue(changed)
        self.assertEqual(emitted, ['dfir data'])

    def test_percent_escapes_still_decode(self):
        """Turning off the "+" behaviour must not stop ordinary unquoting."""
        changed, emitted = self.unquote('a%20b')
        self.assertTrue(changed)
        self.assertEqual(emitted, ['a b'])

    def test_utc_offset_is_not_unquoted(self):
        changed, emitted = self.unquote('2020-06-25 21:54:34.675+00:00')
        self.assertFalse(changed)
        self.assertEqual(emitted, [])

    def test_gmail_payload_survives_a_full_parse(self):
        """End to end: the decoded payload node keeps its "+" separators."""
        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://mail.google.com/mail/u/0/#inbox?compose='
                  'GTvVlcSKjDPsKDHWvqZCTKmmgKbhqgbxKlfhjNjPKtqMrDXmxjvJDlprDkjgXFpGnCmFpRcRHHcQf')
        test.parse_queue()

        payloads = [n.value for n in test.nodes.values()
                    if n.data_type == 'gmail.token.payload']
        self.assertEqual(payloads, ['a:r-7217035772637032756+msg-a:r-8051540162134737577'])

        # Corruption would look like both IDs in one node joined by a space instead of
        # a "+". The individual gmail.id nodes legitimately contain neither.
        corrupted = [n.value for n in test.nodes.values()
                     if isinstance(n.value, str)
                     and 'r-7217035772637032756' in n.value
                     and 'r-8051540162134737577' in n.value
                     and '+' not in n.value]
        self.assertEqual(corrupted, [])


class TestSemicolonDelimitedPairs(unittest.TestCase):
    """A run of ";"-delimited "key=value" pairs is decomposed into a node per pair.

    Ad servers put these inside a path segment, where urlparse leaves them joined:
    it splits path parameters off the *last* segment only, and the last segment of a
    click tracker is rarely the one carrying them.
    """

    class FakeNode:
        node_id = 1

        def __init__(self, value):
            self.value = value

    def split(self, value):
        """Return whether `value` was split, and the pairs it was split into."""
        test = Unfurl()
        matched = parse_url.try_semicolon_delimited_pairs(test, self.FakeNode(value))
        emitted = [(item['key'], item['value']) for item in list(test.queue.queue)]
        return matched, emitted

    def test_pairs_are_split(self):
        matched, emitted = self.split('a=1;b=2;c=3')
        self.assertTrue(matched)
        self.assertEqual([('a', '1'), ('b', '2'), ('c', '3')], emitted)

    def test_empty_values_are_kept(self):
        """"idfa=" is a parameter the tracker sent empty, not one it left out."""
        matched, emitted = self.split('idfa=;cid=;p=1')
        self.assertTrue(matched)
        self.assertEqual([('idfa', ''), ('cid', ''), ('p', '1')], emitted)

    def test_trailing_semicolon_is_a_terminator(self):
        """Ad tags often end with ";"; it does not introduce an empty pair."""
        matched, emitted = self.split('a=1;b=2;')
        self.assertTrue(matched)
        self.assertEqual([('a', '1'), ('b', '2')], emitted)

    def test_value_may_contain_its_own_equals(self):
        """The key is everything up to the first "="; the rest of the chunk is the value."""
        matched, emitted = self.split('ord=@CACHEBUSTER@redirect=https:;n=1')
        self.assertTrue(matched)
        self.assertEqual([('ord', '@CACHEBUSTER@redirect=https:'), ('n', '1')], emitted)

    def test_values_that_are_not_a_pair_run_are_left_alone(self):
        """Every chunk has to be a pair, so a value is split entirely or not at all.

        A partial match would mean guessing which semicolons are separators, and the
        guess would be presented with the same authority as a real decoding.
        """
        for value in ('a=1',                          # one pair has nothing to split
                      'foo; bar; baz',                # prose
                      'key=value; another thing',     # only the first chunk is a pair
                      'cats;lang=en',                 # only the last chunk is a pair
                      'https://a.com;https://b.com',  # URLs, not pairs
                      'text/html;charset=utf-8',      # a media type
                      'YWJj==;ZGVm==',                # "="-padded base64
                      'a=1;;b=2',                     # an empty chunk mid-run
                      'path/to/x=1;y=2',              # a path, not a pair run
                      ''):
            matched, emitted = self.split(value)
            self.assertFalse(matched, msg=f'did not expect {value!r} to be split')
            self.assertEqual([], emitted)

    def test_ad_tag_in_a_path_segment(self):
        """End to end: the click tracker this was built for.

        The destination URL is unencoded, so RFC 3986 scatters it across several
        segments; that is a separate problem. What matters here is that the tracker's
        own parameters come apart.
        """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://trkn.us/click/process/partner=1086;c=11270;p=23056986;idfa=;'
                  'cid=;ord=@CACHEBUSTER@redirect=https://curiositystream.com'
                  '?utm_source=Audacy')
        test.parse_queue()

        pairs = {node.key: node.value for node in test.nodes.values()
                 if node.data_type == 'url.query.pair'}
        self.assertEqual('1086', pairs['partner'])
        self.assertEqual('11270', pairs['c'])
        self.assertEqual('23056986', pairs['p'])
        self.assertEqual('', pairs['idfa'])
        self.assertEqual('', pairs['cid'])
        self.assertEqual('@CACHEBUSTER@redirect=https:', pairs['ord'])

        # The segment the pairs came from is still shown unaltered.
        segments = [node.value for node in test.nodes.values()
                    if node.data_type == 'url.path.segment']
        self.assertIn(
            'partner=1086;c=11270;p=23056986;idfa=;cid=;ord=@CACHEBUSTER@redirect=https:',
            segments)

    def test_pair_run_inside_a_query_parameter(self):
        """A query parameter whose value is itself a run of pairs."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://example.com/page?data=a%3D1%3Bb%3D2%3Bc%3D3')
        test.parse_queue()

        pairs = {node.key: node.value for node in test.nodes.values()
                 if node.data_type == 'url.query.pair'}
        self.assertEqual('a=1;b=2;c=3', pairs['data'])
        self.assertEqual('1', pairs['a'])
        self.assertEqual('2', pairs['b'])
        self.assertEqual('3', pairs['c'])

    def test_semicolon_in_a_query_value_is_not_split(self):
        """"?q=cats;lang=en" is one parameter whose value contains a semicolon.

        Semicolon was once an accepted query separator, so this could be read as two
        parameters -- but nothing in the URL says which reading is right, and "cats"
        is not a pair, so the value is left as the server would have received it.
        """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None, value='https://example.com/search?q=cats;lang=en')
        test.parse_queue()

        pairs = {node.key: node.value for node in test.nodes.values()
                 if node.data_type == 'url.query.pair'}
        self.assertEqual({'q': 'cats;lang=en'}, pairs)


class TestPathParameters(unittest.TestCase):
    """RFC 3986 path parameters -- the ";" run urlparse splits off the last path segment.

    They are emitted as query pairs so the parsers keyed on query pairs see them too; a
    "utm_source" is the same thing wherever in the URL it was carried. What does differ
    is "+", which is a space in a query string and a literal plus in a path.
    """

    @staticmethod
    def pairs_for(url):
        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value=url)
        test.parse_queue()
        return test, {node.key: node.value for node in test.nodes.values()
                      if node.data_type == 'url.query.pair'}

    def test_empty_value_does_not_drop_the_run(self):
        """"idfa=" is a parameter sent blank, not a parameter left out.

        The detection regex used to require a character of value before the delimiter,
        so a run containing an empty one matched nothing and every pair in it was lost,
        including the well-formed ones.
        """
        _, pairs = self.pairs_for('https://example.com/a/x;partner=1086;idfa=;c=1')
        self.assertEqual('1086', pairs['partner'])
        self.assertEqual('', pairs['idfa'])
        self.assertEqual('1', pairs['c'])

    def test_run_without_an_empty_value_still_works(self):
        _, pairs = self.pairs_for('https://example.com/a/x;c=11270;p=23056986')
        self.assertEqual('11270', pairs['c'])
        self.assertEqual('23056986', pairs['p'])

    def test_trailing_delimiter_is_a_terminator(self):
        test, pairs = self.pairs_for('https://example.com/a/x;a=1;b=2;')
        self.assertEqual({'a': '1', 'b': '2'}, pairs)
        self.assertNotIn('', [node.key for node in test.nodes.values()])

    def test_chunk_without_an_equals_is_not_shown_as_a_pair(self):
        """"garbage" and "garbage=" are different inputs and must not render alike.

        Splitting a chunk that has no "=" into a key with an empty value would assert a
        separator the URL never contained, so it is kept whole instead.
        """
        test, pairs = self.pairs_for('https://example.com/a/x;a=1;garbage;b=2')
        self.assertEqual({'a': '1', 'b': '2'}, pairs)
        self.assertIn('garbage', [node.value for node in test.nodes.values()
                                  if node.data_type == 'string'])

    def test_plus_in_a_path_parameter_stays_literal(self):
        """A path parameter is not a query string, so "+" is a plus and not a space."""
        test, pairs = self.pairs_for('https://example.com/a/x;name=a+b;c=1')
        self.assertEqual('a+b', pairs['name'])
        self.assertNotIn('a b', [node.value for node in test.nodes.values()
                                 if isinstance(node.value, str)])

    def test_plus_in_a_semicolon_run_in_an_earlier_segment_stays_literal(self):
        """The same holds for a run urlparse leaves inside a path segment."""
        test, pairs = self.pairs_for('https://example.com/click/p=a+b;c=1/end')
        self.assertEqual('a+b', pairs['p'])
        self.assertNotIn('a b', [node.value for node in test.nodes.values()
                                 if isinstance(node.value, str)])

    def test_plus_in_a_real_query_parameter_is_still_a_space(self):
        """The provenance check must not switch off "+" decoding where it belongs."""
        _, pairs = self.pairs_for('https://example.com/a/b?name=a+b')
        self.assertEqual('a b', pairs['name'])

    def test_percent_escapes_in_a_path_parameter_still_decode(self):
        """Keeping "+" literal must not stop ordinary unquoting."""
        test, _ = self.pairs_for('https://example.com/a/x;name=a%20b;c=1')
        self.assertIn('a b', [node.value for node in test.nodes.values()
                              if isinstance(node.value, str)])


if __name__ == '__main__':
    unittest.main()
