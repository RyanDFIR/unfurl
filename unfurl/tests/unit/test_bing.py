from unfurl.core import Unfurl
from unfurl.parsers.parse_bing import (
    explain_form_value, form_values, indexed_form_values, scrolled_suggestion_bar)
import re
import unittest


def strip_markup(text):
    """Text with markup removed and whitespace collapsed.

    Hover text is wrapped for display, which inserts <br> at positions that depend on the
    exact wording. Matching against the raw value makes an assertion pass or fail on where
    a line break happened to land, so match against what the reader actually sees. Some
    stored explanations are wrapped by hand and carry their own <br>, so expectations get
    stripped the same way the rendered hover does.
    """
    return ' '.join(re.sub(r'<[^>]+>', ' ', text or '').split())


def hover_text(node):
    """A node's hover as the reader sees it."""
    return strip_markup(node.hover)


def parse(url):
    # Remote lookups stay off: a Bing image URL carries a "mediaurl" pointing at whatever
    # site hosted the image, and the generic URL parser recurses into it.
    test = Unfurl(remote_lookups=False)
    test.add_to_queue(data_type='url', key=None, value=url)
    test.parse_queue()
    return test


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


def descriptors_starting_with(unfurl_instance, prefix):
    return [n for n in unfurl_instance.nodes.values()
            if n.data_type == 'descriptor' and str(n.value).startswith(prefix)]


def only_descriptor(test_case, unfurl_instance, prefix):
    """The single descriptor with this prefix, failing loudly if there isn't exactly one."""
    nodes = descriptors_starting_with(unfurl_instance, prefix)
    test_case.assertEqual(1, len(nodes), f'expected exactly one "{prefix}" node')
    return nodes[0]


class TestBing(unittest.TestCase):

    def test_bing(self):
        """ Test a typical and a unique Bing url """

        # test a Bing search url
        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.bing.com/search?q=digital+forensics&qs=n&form=QBLH&sp=-1'
                  '&pq=digital+forensic&sc=8-16&sk=&cvid=77BF13B59CF84B98B13C067AAA3DB701')
        test.parse_queue()

        # Test query parsing
        query_pairs = {n.key: n.value for n in get_nodes_by_type(test, 'url.query.pair')}
        self.assertEqual('digital forensics', query_pairs['q'])
        self.assertEqual('digital forensic', query_pairs['pq'])

        # is processing finished empty
        self.assertTrue(test.queue.empty())


class TestBingFormParameter(unittest.TestCase):
    """The "form" parameter records how a user navigated to a Bing results page.

    The codes and their meanings are documented in Spear, Hawbecker & McElyea, "Lantern to
    the Underworld" (HICSS 2021), which reverse-engineered them to timeline user actions
    from browser history. The forensic value is entirely in the explanation text, so these
    tests assert on the hover, not just that a node appeared.
    """

    def test_known_form_code_is_explained(self):
        """ A documented code carries its meaning in the hover """

        node = only_descriptor(
            self, parse('https://www.bing.com/images/search?q=kittens&FORM=IDMHDL'), 'Navigation Code: ')

        self.assertEqual('Navigation Code: IDMHDL', node.value)
        hover = hover_text(node)
        self.assertIn('records how the user navigated to this page', hover)
        self.assertIn('secondary search bar dropped down from the top of the page', hover)

    def test_unknown_form_code_still_parses_and_says_so(self):
        """ An unrecognized code is reported, not dropped, and is labelled as unknown.

        Bing's codes change over time, so an examiner will meet codes newer than Unfurl's
        list. Staying silent about the parameter would hide evidence that is present in
        the URL; claiming a meaning would invent one.
        """

        node = only_descriptor(
            self, parse('https://www.bing.com/images/search?q=kittens&FORM=ZZNOPE'), 'Navigation Code: ')

        self.assertEqual('Navigation Code: ZZNOPE', node.value)
        self.assertIn("not in Unfurl's list of known values", hover_text(node))

    def test_form_key_and_value_are_case_insensitive(self):
        """ Bing sends "FORM=", but history artifacts and manual notes vary in case """

        for url in ('https://www.bing.com/images/search?q=kittens&FORM=IDMHDL',
                    'https://www.bing.com/images/search?q=kittens&form=idmhdl',
                    'https://www.bing.com/images/search?q=kittens&Form=IdMhDl'):
            with self.subTest(url=url):
                hover = hover_text(only_descriptor(self, parse(url), 'Navigation Code: '))
                self.assertIn('secondary search bar dropped down from the top of the page', hover)

    def test_every_known_code_renders_its_explanation(self):
        """ Every entry in form_values reaches the hover, so no entry is unreachable """

        for code, explanation in form_values.items():
            with self.subTest(code=code):
                node = only_descriptor(
                    self, parse(f'https://www.bing.com/images/search?q=kittens&FORM={code}'),
                    'Navigation Code: ')

                self.assertEqual(f'Navigation Code: {code}', node.value)
                hover = hover_text(node)
                self.assertNotIn("not in Unfurl's list", hover)
                # The stored explanation has display whitespace and, where it was wrapped
                # by hand, markup of its own; compare the collapsed forms so neither a
                # trailing space in the table nor a hand-placed <br> fails the test.
                self.assertIn(strip_markup(explanation), hover)

    def test_form_is_only_parsed_for_bing(self):
        """ "form" is a generic parameter name; another site's must not get Bing meanings """

        other_site = parse('https://example.com/search?q=kittens&FORM=IDMHDL')
        self.assertEqual([], descriptors_starting_with(other_site, 'Navigation Code: '))


class TestBingIndexedFormParameter(unittest.TestCase):
    """Some "form" codes are a prefix plus the position of the item the user clicked.

    Horsman (2018) documents QSRE, where "QSRE3" means the third related-search suggestion.
    An exact-match-only table loses the number, which is the part identifying the choice.
    """

    def test_indexed_code_keeps_its_position(self):
        node = only_descriptor(
            self, parse('https://www.bing.com/search?q=kittens&FORM=QSRE3'), 'Navigation Code: ')

        self.assertEqual('Navigation Code: QSRE3', node.value)
        hover = hover_text(node)
        self.assertIn('related search suggestion number 3', hover)
        self.assertNotIn("not in Unfurl's list", hover)

    def test_each_indexed_prefix_resolves(self):
        """ Every indexed prefix resolves, and the position is read from the code """

        for prefix in indexed_form_values:
            for index in (1, 7, 12):
                with self.subTest(prefix=prefix, index=index):
                    hover = hover_text(only_descriptor(
                        self, parse(f'https://www.bing.com/search?q=kittens&FORM={prefix}{index}'),
                        'Navigation Code: '))
                    self.assertIn(f'number {index}', hover)

    def test_exact_codes_win_over_indexed_prefixes(self):
        """ "HDRSC1" has its own meaning and is not "HDRSC" suggestion #1 """

        hover = hover_text(only_descriptor(
            self, parse('https://www.bing.com/search?q=kittens&FORM=HDRSC1'), 'Navigation Code: '))

        self.assertIn(strip_markup(form_values['HDRSC1']), hover)
        self.assertNotIn('number 1', hover)

    def test_unknown_prefix_with_a_number_is_not_invented(self):
        """ A trailing digit alone must not manufacture a meaning """

        hover = hover_text(only_descriptor(
            self, parse('https://www.bing.com/search?q=kittens&FORM=ZZNOPE9'), 'Navigation Code: '))

        self.assertIn("not in Unfurl's list of known values", hover)


class TestBingImageDetailParameters(unittest.TestCase):
    """Parameters that appear when a user opens a full-size image from the results grid.

    The Lantern paper's timeline reads "IRPRST" together with "thid" and "mediaurl" as a
    single user action: a thumbnail was clicked to view the full-size image.
    """

    def test_thumbnail_and_full_size_image(self):
        test = parse('https://www.bing.com/images/search?q=kittens&FORM=IRPRST'
                     '&thid=OIP.abc123&mediaurl=https%3A%2F%2Fexample.com%2Ffull.jpg')

        self.assertEqual('Thumbnail ID: OIP.abc123',
                         only_descriptor(self, test, 'Thumbnail ID: ').value)

        media_node = only_descriptor(self, test, 'Full-size Image URL')
        self.assertIn('the image the user actually opened', hover_text(media_node))

        # The embedded address is unquoted and parsed as a URL in its own right, so the
        # host serving the image is visible as a node rather than buried in an escape.
        embedded = [n.value for n in get_nodes_by_type(test, 'url')]
        self.assertIn('https://example.com/full.jpg', embedded)

    def test_reverse_image_search_by_upload(self):
        """ A reverse image search carries the name of the file the user uploaded """

        test = parse('https://www.bing.com/images/search?view=detailv2'
                     '&iss=sbiupload&sbifnm=PA.33894042.jpg')

        self.assertEqual('Uploaded Image Filename: PA.33894042.jpg',
                         only_descriptor(self, test, 'Uploaded Image Filename: ').value)
        self.assertEqual('View: detailv2', only_descriptor(self, test, 'View: ').value)

        iss_node = only_descriptor(self, test, 'Image Search Source: ')
        self.assertIn('the user uploaded an image file to search with', hover_text(iss_node))

    def test_unknown_iss_value_is_not_given_a_meaning(self):
        iss_node = only_descriptor(
            self, parse('https://www.bing.com/images/search?iss=somethingelse'),
            'Image Search Source: ')

        self.assertEqual('Image Search Source: somethingelse', iss_node.value)
        self.assertIn("not in Unfurl's list of known values", hover_text(iss_node))

    def test_background_json_request_is_distinguished_from_a_navigation(self):
        """ "format=snrjson" marks a request the page made, not one the user made.

        The Lantern paper's IRIBEP example is one of these. It matters when attributing a
        URL in history to a deliberate user action.
        """

        test = parse('https://www.bing.com/images/search?q=kittens&FORM=IRIBEP'
                     '&sid=3AB&format=snrjson&jsoncbid=2')

        json_node = only_descriptor(self, test, 'Response Format: JSON')
        self.assertIn('fetched in the background by the page itself', hover_text(json_node))
        self.assertEqual('JSON Callback ID: 2',
                         only_descriptor(self, test, 'JSON Callback ID: ').value)

    def test_html_format_is_not_reported_as_json(self):
        """ Only "snrjson" means a background fetch; other "format" values are left alone """

        test = parse('https://www.bing.com/images/search?q=kittens&format=rss')
        self.assertEqual([], descriptors_starting_with(test, 'Response Format'))


class TestBingUnverifiedParameters(unittest.TestCase):
    """Parameters Unfurl names but cannot decode should not overstate what they prove."""

    def test_qt_does_not_claim_a_verified_timestamp(self):
        """ "qt" is labelled a timestamp but is never decoded.

        Horsman (2018) searched for embedded time and date data in Bing search URLs and
        reported finding none, unlike Google's "ei" or Yahoo's "ylc". The hover has to
        carry that caveat so an examiner does not read the raw value as a time.
        """

        hover = hover_text(only_descriptor(
            self, parse('https://www.bing.com/search?q=kittens&qt=7'), 'Timestamp: '))

        self.assertIn('not decoded here', hover)
        self.assertIn('should not be relied on as a verified timestamp', hover)

    def test_first_does_not_assert_a_page_size(self):
        """ Results per page varies by vertical and era, so no page number is derived """

        hover = hover_text(only_descriptor(
            self, parse('https://www.bing.com/search?q=kittens&first=11'), 'Starting Result: '))

        self.assertIn('index of the first result', hover)
        self.assertNotIn('8 results per page', hover)


class TestBingUpstreamParameterTable(unittest.TestCase):
    """Coverage of the reference table the Lantern project publishes.

    https://github.com/lanterntool/lantern/blob/main/parameters.md is the maintained list
    behind the HICSS paper, verified upstream between 2021-05-21 and 2021-06-08. Bing's
    codes drift, so this guards against losing coverage we already have rather than
    asserting the table is still current.
    """

    UPSTREAM_CODES = (
        'AWIR', 'HDRSC1', 'HDRSC2', 'HDRSC3', 'IDINTS', 'IGRE', 'ILPTRD', 'ILPVIS',
        'INLIRS', 'IQFRBA', 'IQFRML', 'IRBPRS', 'IRIBEP', 'IRIBIP', 'IRMHEP', 'IRMHIP',
        'IRMHRE', 'IRMHRS', 'IRMHTS', 'IRPRST', 'IRTRRL', 'ISTRTH', 'QBILPG', 'QBIR',
        'QBIRMH', 'RCIR', 'RESTAB', 'Z9LH',
    )

    def test_every_upstream_code_is_explained(self):
        unexplained = [code for code in self.UPSTREAM_CODES if explain_form_value(code) is None]
        self.assertEqual([], unexplained, 'codes in upstream parameters.md with no explanation')

    def test_scrolled_suggestion_codes_share_one_meaning(self):
        """Five codes differ only by how far the user had scrolled.

        Upstream documents these together: "ID will change depending on how far down the
        user scrolled, indicated by one of the five form IDs listed here." Identical text
        across them is deliberate, so assert the grouping rather than treating it as
        duplication to be cleaned up.
        """

        family = ('IRMHRS', 'IRMHTS', 'IRMHIP', 'IRMHEP', 'IRMHRE')

        for code in family:
            with self.subTest(code=code):
                self.assertEqual(scrolled_suggestion_bar, explain_form_value(code))

        self.assertIn('how far down the user had scrolled', scrolled_suggestion_bar)

    def test_thumbnail_id_distinguishes_freshly_indexed_images(self):
        """The "thid" prefix says whether Bing had the image already or indexed it recently.

        Upstream splits IRPRST into thid=OIP and thid=OIF for exactly this reason, and the
        OIF case tells an examiner the image was new to Bing's index at the time.
        """

        already_indexed = hover_text(only_descriptor(
            self, parse('https://www.bing.com/images/search?q=k&FORM=IRPRST&thid=OIP.abc123'),
            'Thumbnail ID: '))
        self.assertIn('an image Bing had already indexed', already_indexed)

        recently_indexed = hover_text(only_descriptor(
            self, parse('https://www.bing.com/images/search?q=k&FORM=IRPRST&thid=OIF.xyz789'),
            'Thumbnail ID: '))
        self.assertIn('posted and indexed by Bing recently', recently_indexed)

    def test_long_form_explanation_reaches_the_reader_wrapped(self):
        """The longest explanation is wrapped for display, with hyphenated words intact.

        IRPRST is the entry that exposed two wrapping problems at once: the "form" hover
        puts a hard break before the explanation, and the explanation contains
        "full-size". wrap_hover_text() wraps between hard breaks rather than giving up on
        seeing one, and does not break on hyphens, so neither shows up here.
        """

        node = only_descriptor(
            self, parse('https://www.bing.com/images/search?q=k&FORM=IRPRST'), 'Navigation Code: ')

        lines = [line for line in node.hover.split('<br>') if line.strip()]
        self.assertGreater(len(lines), 1, 'IRPRST hover rendered as a single long line')
        self.assertLessEqual(max(len(line) for line in lines), 70)
        self.assertNotIn('full-<br>size', node.hover)
        self.assertIn('full-size', node.hover)

    def test_unknown_thumbnail_prefix_is_not_given_a_meaning(self):
        hover = hover_text(only_descriptor(
            self, parse('https://www.bing.com/images/search?q=k&thid=ZZZ.q'), 'Thumbnail ID: '))

        self.assertIn('Identifies the specific thumbnail image', hover)
        self.assertNotIn('already indexed', hover)
        self.assertNotIn('recently', hover)


if __name__ == '__main__':
    unittest.main()
