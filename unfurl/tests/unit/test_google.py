from unfurl.core import Unfurl
from urllib.parse import urlparse
import unittest


class TestGoogle(unittest.TestCase):

    def test_google_search_with_rlz(self):
        """ Test a Google search URL with a RLZ param """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.google.com/search?rlz=1C1GCAB_enUS907US907&q=dfir+data')
        test.parse_queue()

        # Check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 22)
        self.assertEqual(test.total_nodes, 22)

        # Confirm that RLZ AP parsed
        self.assertEqual('Application: C1', test.nodes[15].label)

        # Language parses
        self.assertEqual('Language: English (en)', test.nodes[18].label)

        # Search cohort parses
        self.assertIn('United States the week of 2020-06-22', test.nodes[20].label)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)

    def test_google_search_with_rlz_different_weeks(self):
        """ Test a Google search URL with a RLZ param with different cohort weeks """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.google.com/search?rlz=1C1GCAB_esUS97US1007&q=dfir+data')
        test.parse_queue()

        # Check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 22)
        self.assertEqual(test.total_nodes, 22)

        # Confirm that RLZ AP parsed
        self.assertEqual('Application: C1', test.nodes[15].label)

        # Language parses
        self.assertEqual('Language: Spanish (es)', test.nodes[18].label)

        # Install cohort parses (2 digit week)
        self.assertIn('United States the week of 2004-12-13', test.nodes[19].label)

        # Search cohort parses (4 digit week)
        self.assertIn('United States the week of 2022-05-23', test.nodes[20].label)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)

    def test_google_search_with_aqs(self):
        """ Test a Google search URL with a AQS param """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.google.com/search?q=dfir&oq=dfir'
                  '&aqs=chrome.1.69i60j0i433i512j0i512j69i60l2j69i61j69i60j69i65.2855j0j7')
        test.parse_queue()

        # Check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 44)
        self.assertEqual(test.total_nodes, 44)

        # Confirm that clicked suggestion parsed
        self.assertEqual('Clicked Suggestion: 1', test.nodes[17].label)

        # Check that 1st autocomplete match parsed
        self.assertEqual('Autocomplete Match (0): 69i60', test.nodes[18].label)

        # Check that match type of 1st autocomplete match parsed
        self.assertIn('Type: Native Chrome', test.nodes[28].label)

        # Check that match subtype of autocomplete match 5 parsed
        self.assertIn('Subtype: Omnibox History Title', test.nodes[39].label)

        # Check that Query Formulation Time parsed
        self.assertIn('2.855 seconds', test.nodes[25].label)

        # Check that page classification was parsed and looked up
        self.assertIn('(with omnibox as starting focus)', test.nodes[44].label)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)


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
        self.assertIn('redirect target', q_node.hover.lower())

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
        self.assertIn('action type', sa_node.hover.lower())

        # confirm usg has hover text
        usg_node = next(n for n in test.nodes.values()
                        if n.data_type == 'url.query.pair' and n.key == 'usg')
        self.assertIn('signature', usg_node.hover.lower())


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
        self.assertIn('ad', ai_node.hover.lower())

        # sig should have hover text about signature
        sig_node = next(n for n in test.nodes.values()
                        if n.data_type == 'url.query.pair' and n.key == 'sig')
        self.assertIsNotNone(sig_node.hover)
        self.assertIn('signature', sig_node.hover.lower())

        # gclid should have hover text
        gclid_node = next(n for n in test.nodes.values()
                          if n.data_type == 'url.query.pair' and n.key == 'gclid')
        self.assertIsNotNone(gclid_node.hover)
        self.assertIn('click', gclid_node.hover.lower())


if __name__ == '__main__':
    unittest.main()
