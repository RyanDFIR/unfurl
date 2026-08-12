from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestTwitter(unittest.TestCase):

    def test_twitter(self):
        """ Test a typical and a unique Twitter url """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://twitter.com/_RyanBenson/status/1098230906194546688')
        test.parse_queue()

        # confirm that snowflake was detected
        snowflake_nodes = [
            n for n in get_nodes_by_type(test, 'url.path.segment')
            if n.value == '1098230906194546688']
        self.assertEqual(len(snowflake_nodes), 1)
        self.assertIn('Twitter Snowflakes', snowflake_nodes[0].hover)

        # embedded timestamp parses correctly
        timestamp_nodes = get_nodes_by_type(test, 'timestamp.epoch-milliseconds')
        self.assertEqual(len(timestamp_nodes), 1)
        self.assertIn('2019-02-20 14:40:26.837', timestamp_nodes[0].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())


if __name__ == '__main__':
    unittest.main()
