from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestBluesky(unittest.TestCase):

    def test_bluesky_post(self):
        """ Test a typical Bluesky post URL """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://bsky.app/profile/jay.bsky.team/post/3lbd2ebt3wk2r')
        test.parse_queue()

        # confirm that TID was detected
        tid_node = next(n for n in get_nodes_by_type(test, 'epoch-microseconds')
                        if 'timestamp identifiers' in (n.hover or ''))
        self.assertEqual(1732040395098000, tid_node.value)

        # embedded timestamp parses correctly
        ts_node = next(iter(get_nodes_by_type(test, 'timestamp.epoch-microseconds')))
        self.assertEqual('2024-11-19 18:19:55.098000+00:00', ts_node.value)

    def test_bluesky_bare_tid(self):
        """ Test parsing a Bluesky/ATProto TID"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='3laulgolrfz2f')
        test.parse_queue()

        # confirm that TID was detected
        tid_node = next(n for n in get_nodes_by_type(test, 'epoch-microseconds')
                        if 'timestamp identifiers' in (n.hover or ''))

        # confirm that TID was extracted correctly
        self.assertEqual(1731543333133695, tid_node.value)

        # embedded timestamp parses correctly
        ts_node = next(iter(get_nodes_by_type(test, 'timestamp.epoch-microseconds')))
        self.assertEqual('2024-11-14 00:15:33.133695+00:00', ts_node.value)

if __name__ == '__main__':
    unittest.main()
