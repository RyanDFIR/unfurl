from unfurl.core import Unfurl
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


class TestShortLinks(unittest.TestCase):

    def test_linkedin_shortlink(self):
        """ Test a LinkedIn shortlink; these work a little different from the rest"""

        test = Unfurl(remote_lookups=True)
        test.add_to_queue(data_type='url', key=None, value='https://lnkd.in/fDJnJ64')
        test.parse_queue()

        # Verify key structural elements
        self.assertTrue(has_node(test, value='/fDJnJ64'))
        self.assertTrue(has_node(test, value='thisweekin4n6.com'))
        self.assertTrue(has_node(test, data_type='url.path.segment', key=4))

        # is processing finished
        self.assertTrue(test.queue.empty())

    def test_shortlink_with_no_code(self):
        """ Test that a path of only slashes isn't "expanded".

        The short code is the path with its slashes stripped, so "///" leaves nothing.
        Requesting the bare base URL would follow the shortener's own front-page
        redirect and report it as this link's expansion. The guard also means this
        test makes no network request.
        """

        for url in ('https://t.co//', 'https://t.co///', 'https://bit.ly//'):
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(data_type='url', key=None, value=url)
            test.parse_queue()

            expanded = [n for n in test.nodes.values() if str(n.label).startswith('Expanded URL')]
            self.assertEqual([], expanded, msg=f'did not expect an expansion for {url}')

    def test_twitter_shortlink(self):
        """ Test a Twitter shortlink; these use 301 redirects like most shortlinks"""

        test = Unfurl(remote_lookups=True)
        test.add_to_queue(data_type='url', key=None, value='https://t.co/g6VWYYwY12')
        test.parse_queue()

        # Verify the shortlink resolved to a github.com URL
        self.assertTrue(has_node(test, value='/g6VWYYwY12'))
        self.assertTrue(has_node(test, value='github.com'))
        self.assertTrue(has_node(test, data_type='url.path.segment', key=1, value='obsidianforensics'))


        # is processing finished
        self.assertTrue(test.queue.empty())

    def test_no_lookups(self):
        """ Test a shortlink with remote lookups disabled"""

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(data_type='url', key=None, value='https://t.co/g6VWYYwY12')
        test.parse_queue()

        # Without remote lookups, the shortlink can't be expanded
        self.assertTrue(has_node(test, value='/g6VWYYwY12'))
        self.assertFalse(has_node(test, value='github.com'))


if __name__ == '__main__':
    unittest.main()