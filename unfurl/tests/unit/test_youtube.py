from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestYouTube(unittest.TestCase):

    def test_youtube(self):
        """ Test a YouTube.com URL, with t in seconds"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.youtube.com/watch?v=LnhSTZgzKuY&list=PLlFGZ98XmfGfV6RAY9fQSeRfyIuhVGSdm&index=2&t=42s')
        test.parse_queue()

        # Test query parsing
        descriptor_labels = [n.label for n in get_nodes_by_type(test, 'descriptor')]
        self.assertIn('Video ID: LnhSTZgzKuY', descriptor_labels)
        self.assertIn('Video will start playing at 42 seconds', descriptor_labels)

        # is processing finished empty
        self.assertTrue(test.queue.empty())

    def test_youtu_be(self):
        """ Test a youtu.be URL, with t as int"""

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://youtu.be/LnhSTZgzKuY?list=PLlFGZ98XmfGfV6RAY9fQSeRfyIuhVGSdm&t=301')
        test.parse_queue()

        # Test query parsing
        descriptor_labels = [n.label for n in get_nodes_by_type(test, 'descriptor')]
        self.assertIn('Video ID: LnhSTZgzKuY', descriptor_labels)
        self.assertIn('Video will start playing at 05:01 (mm:ss)', descriptor_labels)

        # is processing finished empty
        self.assertTrue(test.queue.empty())


if __name__ == '__main__':
    unittest.main()
