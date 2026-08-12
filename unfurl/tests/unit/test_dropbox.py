from unfurl.core import Unfurl
import unittest


def viewing_descriptors(unfurl_instance):
    return [str(n.value) for n in unfurl_instance.nodes.values()
            if n.data_type == 'descriptor' and str(n.value).startswith('Viewing ')]


def parse(url):
    test = Unfurl()
    test.add_to_queue(data_type='url', key=None, value=url)
    test.parse_queue()
    return test


class TestDropbox(unittest.TestCase):

    def test_dropbox_home_pages(self):
        """ Test the two Dropbox landing pages, with and without a directory """

        self.assertEqual(
            ['Viewing the user\'s "All Files" page'],
            viewing_descriptors(parse('https://www.dropbox.com/home')))

        self.assertEqual(
            ['Viewing directory "Documents" from the user\'s "All Files" page'],
            viewing_descriptors(parse('https://www.dropbox.com/home/Documents')))

        self.assertEqual(
            ['Viewing directory "Documents/Work" from the user\'s "All Files" page'],
            viewing_descriptors(parse('https://www.dropbox.com/home/Documents/Work')))

    def test_dropbox_retired_home_page(self):
        """ Test that "/h" still parses, even though the path is dead on dropbox.com.

        URLs recovered from browser history and other artifacts are routinely older
        than the site they came from, so retiring a path upstream is not a reason to
        stop parsing it. The hover says the path is no longer live.
        """

        self.assertEqual(
            ['Viewing the user\'s Dropbox "Home" page'],
            viewing_descriptors(parse('https://www.dropbox.com/h')))

        self.assertEqual(
            ['Viewing directory "Photos" from the user\'s Dropbox "Home" page'],
            viewing_descriptors(parse('https://www.dropbox.com/h/Photos')))

    def test_dropbox_trailing_slash(self):
        """ Test that a trailing slash isn't reported as a directory """

        self.assertEqual(
            ['Viewing the user\'s "All Files" page'],
            viewing_descriptors(parse('https://www.dropbox.com/home/')))

        self.assertEqual(
            ['Viewing the user\'s Dropbox "Home" page'],
            viewing_descriptors(parse('https://www.dropbox.com/h/')))

    def test_dropbox_other_paths_not_matched(self):
        """ Test that unrelated Dropbox paths aren't mistaken for the "Home" page.

        The first path segment has to match exactly. Matching on a "/h" prefix caught
        real paths like "/help", and reported a mangled directory name that was never
        in the URL.
        """

        for url in ('https://www.dropbox.com/help/desktop',
                    'https://www.dropbox.com/hm/personal',
                    'https://www.dropbox.com/homework',
                    'https://www.dropbox.com/scl/fi/abc123'):
            self.assertEqual(
                [], viewing_descriptors(parse(url)),
                msg=f'did not expect a "Viewing ..." descriptor for {url}')


if __name__ == '__main__':
    unittest.main()
