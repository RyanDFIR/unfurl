from unfurl.core import Unfurl
from unfurl.tests.http_mocks import FakeResponse, patch_requests_get, redirect
import unittest


def find_node(unfurl_instance, **criteria):
    """Find a node matching all given criteria (label, value, data_type, key)."""
    for node in unfurl_instance.nodes.values():
        if all(getattr(node, attr, None) == val for attr, val in criteria.items()):
            return node
    return None


def has_node(unfurl_instance, **criteria):
    """Check if a node matching all given criteria exists."""
    return find_node(unfurl_instance, **criteria) is not None


def expanded_nodes(unfurl_instance):
    return [node for node in unfurl_instance.nodes.values()
            if str(node.label).startswith('Expanded URL')]


# Captured from https://lnkd.in/fDJnJ64. Trimmed to the structure the parser depends on,
# with the wording and attributes left as LinkedIn sends them.
#
# The second artdeco-button is deliberate: LinkedIn puts a "learn more" link on the same
# page with the same class, outside <main>. It is what makes the "main " part of the
# selector load-bearing, so a fixture without it would let a broken selector pass.
LINKEDIN_INTERSTITIAL = """<!DOCTYPE html>
<html lang="en">
<body>
<main class="main">
<span class="sr-only">LinkedIn</span>
<h1 class="t-24 t-bold t-black mb2">This link will take you to a page that's not on LinkedIn</h1>
<h2 class="t-16 t-black mb3">Because this is an external link, we're unable to verify it for safety.</h2>
<a class="artdeco-button artdeco-button--tertiary"
   data-tracking-control-name="external_url_click" data-tracking-will-navigate
   href="https://thisweekin4n6.com/2020/04/19/week-16-2020/">Continue</a>
</main>
<footer>
<a class="t-14 artdeco-button artdeco-button--tertiary"
   data-tracking-control-name="learn_more_click" data-tracking-will-navigate
   href="https://www.linkedin.com/help/linkedin/answer/a1341680?trk=in_page_learn_more_click"
   target="_blank">Learn more</a>
</footer>
</body>
</html>
"""

# What LinkedIn serves when it does not want to answer -- no <main>, no anchor.
LINKEDIN_BLOCKED = '<!DOCTYPE html><html><body><h1>Sign in to continue</h1></body></html>'


class TestRedirectShortlinks(unittest.TestCase):
    """Shorteners that answer with a 3xx and a Location header."""

    def test_twitter_shortlink(self):
        routes = {'t.co/g6VWYYwY12':
                  redirect('https://github.com/obsidianforensics/unfurl#online-version')}

        with patch_requests_get(routes) as calls:
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(data_type='url', key=None, value='https://t.co/g6VWYYwY12')
            test.parse_queue()

        self.assertTrue(has_node(test, value='/g6VWYYwY12'))
        self.assertTrue(has_node(test, value='github.com'))
        self.assertTrue(has_node(test, data_type='url.path.segment', key=1,
                                 value='obsidianforensics'))
        self.assertTrue(test.queue.empty())

        self.assertEqual(1, len(calls), msg=f'expected one outbound request, got {calls}')

    def test_lowercase_location_header_is_handled(self):
        """Real shorteners send "location", not "Location".

        expand_url_via_redirect_header reads r.headers['Location'], which only works
        because requests uses a case-insensitive mapping. Pin that down.
        """

        routes = {'t.co/abc': FakeResponse(status_code=301,
                                           headers={'location': 'https://example.com/target'})}

        with patch_requests_get(routes):
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(data_type='url', key=None, value='https://t.co/abc')
            test.parse_queue()

        self.assertTrue(has_node(test, value='example.com'))

    def test_non_redirect_response_expands_nothing(self):
        """A 200 (or a 404) is not an expansion, and must not be reported as one."""

        for status_code in (200, 404, 410, 500):
            with self.subTest(status_code=status_code):
                routes = {'t.co/abc': FakeResponse(status_code=status_code)}

                with patch_requests_get(routes):
                    test = Unfurl(remote_lookups=True)
                    test.add_to_queue(data_type='url', key=None, value='https://t.co/abc')
                    test.parse_queue()

                self.assertEqual([], expanded_nodes(test))

    def test_all_redirect_status_codes_are_followed(self):
        for status_code in (301, 302, 303, 307, 308):
            with self.subTest(status_code=status_code):
                routes = {'t.co/abc': redirect('https://example.com/target',
                                               status_code=status_code)}

                with patch_requests_get(routes):
                    test = Unfurl(remote_lookups=True)
                    test.add_to_queue(data_type='url', key=None, value='https://t.co/abc')
                    test.parse_queue()

                self.assertTrue(has_node(test, value='example.com'))


class TestLinkedInShortlinks(unittest.TestCase):
    """LinkedIn serves an interstitial page instead of redirecting."""

    def test_linkedin_shortlink(self):
        routes = {'linkedin.com/slink': FakeResponse(content=LINKEDIN_INTERSTITIAL)}

        with patch_requests_get(routes):
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(data_type='url', key=None, value='https://lnkd.in/fDJnJ64')
            test.parse_queue()

        self.assertTrue(has_node(test, value='/fDJnJ64'))
        self.assertTrue(has_node(test, value='thisweekin4n6.com'))
        self.assertTrue(has_node(test, data_type='url.path.segment', key=4))
        self.assertTrue(test.queue.empty())

    def test_target_link_is_chosen_over_the_learn_more_link(self):
        """Both anchors carry the artdeco-button class; only one is the destination."""

        routes = {'linkedin.com/slink': FakeResponse(content=LINKEDIN_INTERSTITIAL)}

        with patch_requests_get(routes):
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(data_type='url', key=None, value='https://lnkd.in/fDJnJ64')
            test.parse_queue()

        self.assertTrue(has_node(test, value='thisweekin4n6.com'))
        self.assertFalse(has_node(test, value='www.linkedin.com'),
                         msg='expanded to the "learn more" link instead of the target')

    def test_blocked_interstitial_is_handled(self):
        """A page without the anchor must expand to nothing, not raise.

        Regression test: `soup.select_one(...)` returns None when LinkedIn serves a
        sign-in wall, changes its markup, or turns a datacenter IP away, and
        `link.get('href')` used to raise AttributeError on it. run_plugins swallowed the
        exception, so the symptom was a missing expansion plus a traceback in the log.
        """

        routes = {'linkedin.com/slink': FakeResponse(content=LINKEDIN_BLOCKED)}

        with self.assertLogs('unfurl.parsers.parse_shortlink', level='WARNING') as logged:
            with patch_requests_get(routes):
                test = Unfurl(remote_lookups=True)
                test.add_to_queue(data_type='url', key=None, value='https://lnkd.in/fDJnJ64')
                test.parse_queue()

        self.assertEqual([], expanded_nodes(test))
        self.assertIn('No destination link found', ''.join(logged.output))

    def test_non_200_interstitial_is_handled(self):
        """LinkedIn answers bots it declines to serve with HTTP 999."""

        for status_code in (999, 403, 404, 429):
            with self.subTest(status_code=status_code):
                routes = {'linkedin.com/slink': FakeResponse(status_code=status_code,
                                                             content=LINKEDIN_BLOCKED)}

                with self.assertLogs('unfurl.parsers.parse_shortlink',
                                     level='WARNING') as logged:
                    with patch_requests_get(routes):
                        test = Unfurl(remote_lookups=True)
                        test.add_to_queue(data_type='url', key=None,
                                          value='https://lnkd.in/fDJnJ64')
                        test.parse_queue()

                self.assertEqual([], expanded_nodes(test))
                self.assertIn(str(status_code), ''.join(logged.output))

    def test_anchor_without_href_is_handled(self):
        anchor_without_href = (
            '<html><body><main><a class="artdeco-button">Continue</a></main></body></html>')
        routes = {'linkedin.com/slink': FakeResponse(content=anchor_without_href)}

        with self.assertLogs('unfurl.parsers.parse_shortlink', level='WARNING'):
            with patch_requests_get(routes):
                test = Unfurl(remote_lookups=True)
                test.add_to_queue(data_type='url', key=None, value='https://lnkd.in/fDJnJ64')
                test.parse_queue()

        self.assertEqual([], expanded_nodes(test))

    def test_failure_does_not_raise_into_the_log(self):
        """The failure path must not produce a traceback.

        run_plugins logs any exception a parser raises, so "it still worked" hides a
        crash. Assert the parser handled it rather than threw.
        """

        routes = {'linkedin.com/slink': FakeResponse(content=LINKEDIN_BLOCKED)}

        with self.assertLogs('unfurl', level='WARNING') as logged:
            with patch_requests_get(routes):
                test = Unfurl(remote_lookups=True)
                test.add_to_queue(data_type='url', key=None, value='https://lnkd.in/fDJnJ64')
                test.parse_queue()

        self.assertFalse(any('AttributeError' in message for message in logged.output),
                         msg='a blocked page should be handled, not raise AttributeError')
        self.assertFalse(any('Traceback' in message for message in logged.output))


class TestShortlinkGuards(unittest.TestCase):
    """Cases that must not produce a request at all."""

    def test_shortlink_with_no_code(self):
        """A path of only slashes leaves no short code.

        Requesting the bare base URL would follow the shortener's own front-page
        redirect and report it as this link's expansion.
        """

        for url in ('https://t.co//', 'https://t.co///', 'https://bit.ly//'):
            with self.subTest(url=url):
                with patch_requests_get({}) as calls:
                    test = Unfurl(remote_lookups=True)
                    test.add_to_queue(data_type='url', key=None, value=url)
                    test.parse_queue()

                self.assertEqual([], expanded_nodes(test),
                                 msg=f'did not expect an expansion for {url}')
                self.assertEqual([], calls,
                                 msg=f'did not expect a network request for {url}')

    def test_no_lookups(self):
        """With remote lookups disabled, nothing is expanded and nothing is requested."""

        with patch_requests_get({}) as calls:
            test = Unfurl(remote_lookups=False)
            test.add_to_queue(data_type='url', key=None, value='https://t.co/g6VWYYwY12')
            test.parse_queue()

        self.assertTrue(has_node(test, value='/g6VWYYwY12'))
        self.assertFalse(has_node(test, value='github.com'))
        self.assertEqual([], calls)


if __name__ == '__main__':
    unittest.main()
