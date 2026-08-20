from unfurl.core import Unfurl
from urllib.parse import urlparse
import re
import unittest


def hover_text(node):
    """A node's hover with markup removed and whitespace collapsed.

    Hover text is wrapped for display, which inserts <br> at positions that depend on the
    exact wording. Matching against the raw value makes an assertion pass or fail on where
    a line break happened to land, so match against what the reader actually sees.
    """
    return ' '.join(re.sub(r'<[^>]+>', ' ', node.hover or '').split())


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestGoogle(unittest.TestCase):

    def test_google_search_with_rlz(self):
        """ Test a Google search URL with a RLZ param """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.google.com/search?rlz=1C1GCAB_enUS907US907&q=dfir+data')
        test.parse_queue()

        # Confirm that RLZ AP parsed
        ap_nodes = get_nodes_by_type(test, 'google.rlz.ap')
        self.assertEqual(1, len(ap_nodes))
        self.assertEqual('Application: C1', ap_nodes[0].label)

        # Language parses
        language_nodes = get_nodes_by_type(test, 'google.rlz.language')
        self.assertEqual(1, len(language_nodes))
        self.assertEqual('Language: English (en)', language_nodes[0].label)

        # Search cohort parses
        search_cohort_nodes = get_nodes_by_type(test, 'google.rlz.search_cohort')
        self.assertEqual(1, len(search_cohort_nodes))
        self.assertIn('United States the week of 2020-06-22', search_cohort_nodes[0].label)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())

    def test_google_search_with_rlz_different_weeks(self):
        """ Test a Google search URL with a RLZ param with different cohort weeks """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.google.com/search?rlz=1C1GCAB_esUS97US1007&q=dfir+data')
        test.parse_queue()

        # Confirm that RLZ AP parsed
        ap_nodes = get_nodes_by_type(test, 'google.rlz.ap')
        self.assertEqual(1, len(ap_nodes))
        self.assertEqual('Application: C1', ap_nodes[0].label)

        # Language parses
        language_nodes = get_nodes_by_type(test, 'google.rlz.language')
        self.assertEqual(1, len(language_nodes))
        self.assertEqual('Language: Spanish (es)', language_nodes[0].label)

        # Install cohort parses (2 digit week)
        install_cohort_nodes = get_nodes_by_type(test, 'google.rlz.install_cohort')
        self.assertEqual(1, len(install_cohort_nodes))
        self.assertIn('United States the week of 2004-12-13', install_cohort_nodes[0].label)

        # Search cohort parses (4 digit week)
        search_cohort_nodes = get_nodes_by_type(test, 'google.rlz.search_cohort')
        self.assertEqual(1, len(search_cohort_nodes))
        self.assertIn('United States the week of 2022-05-23', search_cohort_nodes[0].label)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())

    def test_google_search_with_aqs(self):
        """ Test a Google search URL with a AQS param """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.google.com/search?q=dfir&oq=dfir'
                  '&aqs=chrome.1.69i60j0i433i512j0i512j69i60l2j69i61j69i60j69i65.2855j0j7')
        test.parse_queue()

        # Confirm that clicked suggestion parsed
        clicked_suggestion_nodes = get_nodes_by_type(test, 'google.aqs.clicked_suggestion')
        self.assertEqual(1, len(clicked_suggestion_nodes))
        self.assertEqual('Clicked Suggestion: 1', clicked_suggestion_nodes[0].label)

        # Check that 1st autocomplete match parsed
        ac_match_0 = next(n for n in get_nodes_by_type(test, 'google.aqs.ac_match')
                          if n.key == 'Autocomplete Match (0)')
        self.assertEqual('Autocomplete Match (0): 69i60', ac_match_0.label)

        # Check that "Native Chrome" match type (used by autocomplete match 0) parsed
        suggest_type_labels = [n.label for n in get_nodes_by_type(test, 'omnibox.suggest_type')]
        self.assertIn('Type: Native Chrome', suggest_type_labels)

        # Check that "Omnibox History Title" subtype (used by autocomplete match 5) parsed
        suggest_subtype_labels = [n.label for n in get_nodes_by_type(test, 'omnibox.suggest_subtype')]
        self.assertIn('Subtype: Omnibox History Title', suggest_subtype_labels)

        # Check that Query Formulation Time parsed
        qft_nodes = get_nodes_by_type(test, 'google.aqs.query_formulation_time')
        self.assertEqual(1, len(qft_nodes))
        self.assertIn('2.855 seconds', qft_nodes[0].label)

        # Check that page classification was parsed and looked up
        pc_nodes = get_nodes_by_type(test, 'google.aqs.page_classification')
        self.assertEqual(1, len(pc_nodes))
        self.assertEqual('7', pc_nodes[0].value)
        pc_descriptors = [n for n in get_nodes_by_type(test, 'descriptor')
                          if '(with omnibox as starting focus)' in n.label]
        self.assertEqual(1, len(pc_descriptors))

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())

    def test_google_url_redirect(self):
        """Test that google.com/url redirects are parsed correctly.

        The q parameter should NOT be labeled as a search query; it is
        a redirect target URL. The hover text should explain this.
        """

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.google.com/url?q=https://example.org/landing'
                  '&sa=D&ust=1546552999624000&usg=AFQjCNGESR0jI6krt8QOg3NlJ0GS60RxJg')
        test.parse_queue()

        # confirm q is NOT labeled as "Search Query"
        google_q_nodes = [n for n in test.nodes.values() if n.data_type == 'google.q']
        self.assertEqual(0, len(google_q_nodes))

        # confirm q has the redirect hover text
        q_node = next(n for n in test.nodes.values()
                      if n.data_type == 'url.query.pair' and n.key == 'q')
        self.assertIn('redirect target', hover_text(q_node).lower())

        # confirm the destination URL is parsed
        dest_urls = [
            n for n in test.nodes.values()
            if n.data_type == 'url'
            and urlparse(str(n.value)).hostname == 'example.org'
        ]
        self.assertGreaterEqual(len(dest_urls), 1)

        # confirm sa has hover text
        sa_node = next(n for n in test.nodes.values()
                       if n.data_type == 'url.query.pair' and n.key == 'sa')
        self.assertIn('action type', hover_text(sa_node).lower())

        # confirm usg has hover text
        usg_node = next(n for n in test.nodes.values()
                        if n.data_type == 'url.query.pair' and n.key == 'usg')
        self.assertIn('signature', hover_text(usg_node).lower())

    def test_google_aclk_ad_click(self):
        """Test that google.com/aclk ad click URLs are parsed correctly.

        The adurl parameter is the advertiser's landing page and should be
        parsed as a URL. Tracking params (ai, sig, gclid, etc.) get hover text.
        """

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.google.com/aclk?sa=L&ai=DChcSEwiE4ujK09SFAxWYroMHHfGZAigYABAAGgJlZg'
                  '&sig=AOD64_01K4cZUGNjr9xJflXR3zH81_Do6w'
                  '&gclid=EAIaIQobChMIhOLoytPUhQMVmK6DBx3xmQIoEAMYASAAEgIYYfD_BwE'
                  '&adurl=https://example.com/landing-page%3Futm_source%3Dgoogle'
                  '&ved=2ahUKEwiE4ujK09SFAxWYroMHHfGZAigQgQ16BAgDEAE')
        test.parse_queue()

        # adurl should be parsed as a destination URL node
        adurl_nodes = [
            n for n in test.nodes.values()
            if n.data_type == 'url'
            and urlparse(str(n.value)).hostname == 'example.com'
        ]
        self.assertGreaterEqual(len(adurl_nodes), 1)

        # adurl child node should have "Ad Destination" label
        adurl_labeled = [n for n in test.nodes.values()
                         if 'Ad Destination' in (n.label or '')]
        self.assertGreaterEqual(len(adurl_labeled), 1)

        # ai should have hover text about ad metadata
        ai_node = next(n for n in test.nodes.values()
                       if n.data_type == 'url.query.pair' and n.key == 'ai')
        self.assertIsNotNone(ai_node.hover)
        self.assertIn('ad', hover_text(ai_node).lower())

        # sig should have hover text about signature
        sig_node = next(n for n in test.nodes.values()
                        if n.data_type == 'url.query.pair' and n.key == 'sig')
        self.assertIsNotNone(sig_node.hover)
        self.assertIn('signature', hover_text(sig_node).lower())

        # gclid should have hover text
        gclid_node = next(n for n in test.nodes.values()
                          if n.data_type == 'url.query.pair' and n.key == 'gclid')
        self.assertIsNotNone(gclid_node.hover)
        self.assertIn('click', hover_text(gclid_node).lower())


class TestGoogleAccountParams(unittest.TestCase):
    """Params seen on Google sign-in and multi-account URLs."""

    def parse(self, url):
        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value=url)
        test.parse_queue()
        return test

    def test_dsh_timestamp(self):
        """The second field of "dsh" dates the sign-in flow itself."""
        test = self.parse(
            'https://accounts.google.com/v3/signin/identifier?dsh=S2034035022%3A1749584429440685')

        raw = get_nodes_by_type(test, 'epoch-microseconds')
        self.assertEqual(1, len(raw))
        self.assertEqual(1749584429440685, raw[0].value)

        parsed = get_nodes_by_type(test, 'timestamp.epoch-microseconds')
        self.assertEqual(1, len(parsed))
        self.assertEqual('2025-06-10 19:40:29.440685+00:00', parsed[0].value)

    def test_dsh_first_field_may_be_negative(self):
        test = self.parse(
            'https://accounts.google.com/v3/signin/challenge/pwd?dsh=S-905808778%3A1750788381554893')

        parsed = get_nodes_by_type(test, 'timestamp.epoch-microseconds')
        self.assertEqual(1, len(parsed))
        self.assertEqual('2025-06-24 18:06:21.554893+00:00', parsed[0].value)

    def test_malformed_dsh_yields_no_timestamp(self):
        test = self.parse('https://accounts.google.com/v3/signin/identifier?dsh=nonsense')
        self.assertEqual([], get_nodes_by_type(test, 'epoch-microseconds'))

    def test_authuser_zero_is_the_default_account(self):
        test = self.parse('https://www.google.com/search?q=dfir&authuser=0')
        labels = [n.label for n in get_nodes_by_type(test, 'descriptor')]
        self.assertIn('Google account index 0 (default account)', labels)

    def test_authuser_above_zero_indicates_multiple_accounts(self):
        test = self.parse('https://www.google.com/search?q=dfir&authuser=1')
        labels = [n.label for n in get_nodes_by_type(test, 'descriptor')]
        self.assertIn('Google account index 1 (an additional signed-in account)', labels)


if __name__ == '__main__':
    unittest.main()
