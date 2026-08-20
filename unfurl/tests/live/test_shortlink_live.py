"""Live contract tests for URL shorteners.

These make real network requests. They are not testing Unfurl -- `tests/unit/test_shortlink.py`
does that offline -- they are testing whether the third parties still behave the way
Unfurl assumes. A failure here means the outside world changed, which is useful to know
but is not a code regression, and should not turn a pull request red.

Run them on purpose:

    UNFURL_LIVE_TESTS=1 python -m unittest discover -s unfurl/tests/live -t .

They are skipped otherwise, including in CI, which runs the whole suite across nine
Python/OS combinations -- nine rounds of requests at LinkedIn and t.co per push, from
datacenter IPs that shorteners are prone to turning away.

The URLs below are long-lived public links, but they are still someone else's data: if
one is deleted the test fails through no fault of the code. Prefer adding assertions
about *shape* (a redirect was returned, an anchor was found) over assertions about
particular destinations.
"""

import os
import unittest

from unfurl.core import Unfurl
from unfurl.parsers.parse_shortlink import expand_url_via_redirect_header, parse_linkedin_slink_url


LIVE_TESTS_ENABLED = os.environ.get('UNFURL_LIVE_TESTS') == '1'

requires_network = unittest.skipUnless(
    LIVE_TESTS_ENABLED,
    'set UNFURL_LIVE_TESTS=1 to run tests that make real network requests')


def has_node(unfurl_instance, **criteria):
    for node in unfurl_instance.nodes.values():
        if all(getattr(node, attr, None) == val for attr, val in criteria.items()):
            return True
    return False


@requires_network
class TestShortlinkContracts(unittest.TestCase):

    def test_tco_still_answers_with_a_redirect(self):
        """t.co is expected to 3xx with a Location header."""

        expanded = expand_url_via_redirect_header('https://t.co/', 'g6VWYYwY12')

        self.assertTrue(expanded, 'expected a Location header from t.co')
        self.assertTrue(str(expanded).startswith('http'))

    def test_linkedin_interstitial_still_has_the_expected_anchor(self):
        """The selector "main a.artdeco-button" is the fragile part of this parser.

        It depends on LinkedIn's page markup, which we do not control and which carries
        no compatibility promise.
        """

        expanded = parse_linkedin_slink_url('fDJnJ64')

        self.assertTrue(expanded, 'no anchor matched "main a.artdeco-button"')
        self.assertTrue(str(expanded).startswith('http'))

    def test_twitter_shortlink_end_to_end(self):
        test = Unfurl(remote_lookups=True)
        test.add_to_queue(data_type='url', key=None, value='https://t.co/g6VWYYwY12')
        test.parse_queue()

        self.assertTrue(has_node(test, value='/g6VWYYwY12'))
        self.assertTrue(has_node(test, value='github.com'))

    def test_linkedin_shortlink_end_to_end(self):
        test = Unfurl(remote_lookups=True)
        test.add_to_queue(data_type='url', key=None, value='https://lnkd.in/fDJnJ64')
        test.parse_queue()

        self.assertTrue(has_node(test, value='/fDJnJ64'))
        self.assertTrue(has_node(test, value='thisweekin4n6.com'))


if __name__ == '__main__':
    unittest.main()
