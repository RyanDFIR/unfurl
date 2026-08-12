from unfurl.core import Unfurl
import unittest


def search_types(url):
    test = Unfurl()
    test.add_to_queue(data_type='url', key=None, value=url)
    test.parse_queue()
    return [str(n.value) for n in test.nodes.values()
            if n.data_type == 'descriptor' and n.key == 'Search Type']


class TestBrave(unittest.TestCase):

    def test_brave_search_types(self):
        """ Test that each Brave search vertical is identified from the path """

        self.assertEqual(['Web Search'], search_types('https://search.brave.com/search?q=test'))
        self.assertEqual(['Image Search'], search_types('https://search.brave.com/images?q=test'))
        self.assertEqual(['News Search'], search_types('https://search.brave.com/news?q=test'))
        self.assertEqual(['Video Search'], search_types('https://search.brave.com/videos?q=test'))

    def test_brave_search_type_with_trailing_slash(self):
        """ Test that a trailing or doubled slash doesn't hide the search type.

        Matching the whole path exactly ("/search") missed the ordinary "/search/" form.
        """

        self.assertEqual(['Web Search'], search_types('https://search.brave.com/search/?q=test'))
        self.assertEqual(['Web Search'], search_types('https://search.brave.com//search?q=test'))

    def test_brave_unknown_path_not_matched(self):
        """ Test that an unrelated Brave path isn't given a search type """

        self.assertEqual([], search_types('https://search.brave.com/help/anonymous-local-results'))
        self.assertEqual([], search_types('https://search.brave.com/settings'))


if __name__ == '__main__':
    unittest.main()
