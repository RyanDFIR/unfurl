from unfurl.core import Unfurl
from unfurl.parsers import parse_shortlink
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


class TestShortenerDetection(unittest.TestCase):
    """Which domains Unfurl is willing to guess are link shorteners.

    The guess used to be "any domain under eight characters", which fired at x.com,
    box.com, cnn.com, npr.org, ibm.com, ups.com, vk.com, qq.com, ok.ru, ya.ru, t.me and
    wa.me. For a forensics tool that is worse than a wasted round trip: fetching a URL
    tells that site someone is looking at it.
    """

    # Short domains that are destinations, not shorteners.
    REAL_SITES = ['x.com', 'box.com', 'cnn.com', 'npr.org', 'ibm.com', 'ups.com',
                  'vk.com', 'qq.com', 'ok.ru', 'ya.ru', 't.me', 'wa.me']

    # Shorteners that must still be expanded, via the redirect-header path.
    SHORTENERS = ['t.co', 'goo.gl', 'is.gd', 'a.co', 'g.co', 'git.io', 'trib.al',
                  'tinyurl.com', 'buff.ly']

    def requested_domains(self, domain):
        """Parse https://{domain}/abc123 and report the URLs actually requested."""

        with patch_requests_get({}) as calls:
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(data_type='url', key=None, value=f'https://{domain}/abc123')
            test.parse_queue()
        return calls

    def test_real_sites_are_not_treated_as_shorteners(self):
        for domain in self.REAL_SITES:
            with self.subTest(domain=domain):
                self.assertEqual(
                    [], self.requested_domains(domain),
                    msg=f'{domain} is a destination, not a shortener; Unfurl must not '
                        f'fetch it just because the domain is short')

    def test_known_shorteners_are_still_expanded(self):
        for domain in self.SHORTENERS:
            with self.subTest(domain=domain):
                self.assertTrue(
                    self.requested_domains(domain),
                    msg=f'{domain} is a link shortener and should still be expanded')

    def test_misp_list_is_reachable_for_short_domains(self):
        """Regression: the length heuristic used to return unconditionally.

        That made the MISP known-shortener list -- the authoritative one -- dead code for
        every domain under eight characters, which is most shorteners.
        """

        test = Unfurl(remote_lookups=False)
        misp = test.known_domain_lists['List of known URL Shorteners domains'].list

        short_and_known = [d for d in misp if len(d) < 8]
        self.assertTrue(short_and_known, 'expected the MISP list to contain short domains')

        # Pick one that is not in the hard-coded redirect_expands table, so the only way
        # it can be expanded is through the MISP lookup.
        self.assertTrue(self.requested_domains('is.gd'))

    def test_popularity_gate_uses_only_the_tighter_lists(self):
        """The 1M-entry lists contain most of the web, shorteners included."""

        test = Unfurl(remote_lookups=False)
        self.assertTrue(test.domain_in_top_sites_list('x.com'))
        self.assertFalse(test.domain_in_top_sites_list('git.io'))

    def test_top_sites_lookup_is_cached_across_instances(self):
        """The union is immutable reference data, so it is built once per process.

        Rebuilding it per instance cost ~1.3 ms on every request the web app served.
        """

        from unfurl import core

        core._top_sites_domains = None
        first_instance = Unfurl(remote_lookups=False)
        first_instance.domain_in_top_sites_list('x.com')
        built = core._top_sites_domains
        self.assertIsNotNone(built)

        # A separate instance reuses it rather than rebuilding.
        Unfurl(remote_lookups=False).domain_in_top_sites_list('example.com')
        self.assertIs(built, core._top_sites_domains)

    def test_named_shorteners_are_expanded(self):
        """Every domain in additional_shortener_domains must actually be expanded.

        These are popular enough to sit in top-sites lists, so the length guess skips
        them deliberately -- naming them is the only thing keeping them working.
        """

        for domain in sorted(parse_shortlink.additional_shortener_domains):
            with self.subTest(domain=domain):
                self.assertTrue(
                    self.requested_domains(domain),
                    msg=f'{domain} is a named shortener but was not expanded')

    def test_named_shorteners_are_still_needed(self):
        """The audit invariant: each named domain is popular and absent from MISP.

        If MISP picks one up, the entry here is redundant and should be deleted rather
        than left to drift. If one drops out of the top-sites lists, the length guess
        covers it again. Either way this test says so instead of the list quietly rotting.
        """

        test = Unfurl(remote_lookups=False)
        misp = set(test.known_domain_lists['List of known URL Shorteners domains'].list)

        for domain in sorted(parse_shortlink.additional_shortener_domains):
            with self.subTest(domain=domain):
                self.assertNotIn(
                    domain, misp,
                    msg=f'{domain} is now in the MISP list; drop it from '
                        f'additional_shortener_domains')
                self.assertTrue(
                    test.domain_in_top_sites_list(domain),
                    msg=f'{domain} is no longer in a top-sites list, so the length guess '
                        f'would cover it; the explicit entry may be unnecessary')


class TestQueryTokenRedirectors(unittest.TestCase):
    """Redirectors whose token is in the query string, e.g. Constant Contact.

    These need the original URL passed through untouched. The generic expander rebuilds
    a URL from the registered domain and path, which drops the token; a tokenless
    r20.rs6.net/tn.jsp answers 200, so it expands to nothing.
    """

    TRACKER_URL = 'https://r20.rs6.net/tn.jsp?f=001abcTOKEN&c=xyz&ch=abc'
    DESTINATION = 'https://files.constantcontact.com/2efaa8b7001/a5bddf98.pdf'

    def parse_tracker(self, url=None):
        """Parse a tracker URL, returning (unfurl, urls_requested)."""

        routes = {'r20.rs6.net': redirect(self.DESTINATION, status_code=302)}
        with patch_requests_get(routes) as calls:
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(data_type='url', key=None, value=url or self.TRACKER_URL)
            test.parse_queue()
        return test, calls

    def test_full_url_is_passed_through_untouched(self):
        """Host, path and query all matter, so none of them may be rebuilt."""

        _, calls = self.parse_tracker()

        self.assertEqual([self.TRACKER_URL], calls)

    def test_destination_is_reported(self):
        test, _ = self.parse_tracker()

        self.assertTrue(has_node(test, data_type='url', value=self.DESTINATION))
        self.assertTrue(has_node(test, value='files.constantcontact.com'))

    def test_subdomain_is_matched_against_the_registered_domain(self):
        """find_preceding_domain returns "r20.rs6.net", the table is keyed "rs6.net"."""

        test = Unfurl(remote_lookups=False)
        test.add_to_queue(data_type='url', key=None, value=self.TRACKER_URL)
        test.parse_queue()

        path_node = next(n for n in test.nodes.values() if n.data_type == 'url.path')
        self.assertEqual('r20.rs6.net', test.find_preceding_domain(path_node))
        self.assertTrue(test.preceding_domain_matches(path_node, 'rs6.net'))

    def test_hover_warns_that_the_click_may_be_registered(self):
        """The token is per-recipient; fetching it can tell the sender they engaged."""

        test, _ = self.parse_tracker()

        expanded = next(n for n in test.nodes.values()
                        if str(n.label).startswith('Expanded URL'))
        self.assertIn('click tracker', expanded.hover)
        self.assertIn('Constant Contact', expanded.hover)

    def test_nothing_is_requested_without_remote_lookups(self):
        with patch_requests_get({}) as calls:
            test = Unfurl(remote_lookups=False)
            test.add_to_queue(data_type='url', key=None, value=self.TRACKER_URL)
            test.parse_queue()

        self.assertEqual([], calls)
        self.assertEqual([], expanded_nodes(test))


class TestFindPrecedingUrl(unittest.TestCase):
    """The helper that hands a parser the URL as it was actually written."""

    def test_returns_the_full_url_from_a_path_node(self):
        url = 'https://r20.rs6.net/tn.jsp?f=001abc&c=xyz'
        test = Unfurl(remote_lookups=False)
        test.add_to_queue(data_type='url', key=None, value=url)
        test.parse_queue()

        path_node = next(n for n in test.nodes.values() if n.data_type == 'url.path')
        self.assertEqual(url, test.find_preceding_url(path_node))

    def test_reaches_past_intermediate_nodes(self):
        url = 'https://example.com/a/b?x=1'
        test = Unfurl(remote_lookups=False)
        test.add_to_queue(data_type='url', key=None, value=url)
        test.parse_queue()

        segment = next(n for n in test.nodes.values()
                       if n.data_type == 'url.path.segment' and n.value == 'b')
        self.assertEqual(url, test.find_preceding_url(segment))

    def test_returns_empty_when_there_is_no_url_ancestor(self):
        test = Unfurl(remote_lookups=False)
        test.add_to_queue(data_type='string', key=None, value='not-a-url')
        test.parse_queue()

        root = test.nodes[1]
        self.assertEqual('', test.find_preceding_url(root))


if __name__ == '__main__':
    unittest.main()
