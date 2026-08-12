from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestDiscord(unittest.TestCase):

    def test_discord(self):
        """ Test a typical and a unique Discord url """

        # unit test for a unique Discord url.
        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://discordapp.com/channels/427876741990711298/551531058039095296')
        test.parse_queue()

        # both snowflake IDs (server & channel) should yield embedded timestamps
        epoch_nodes = get_nodes_by_type(test, 'epoch-milliseconds')
        epoch_values = [n.value for n in epoch_nodes]
        self.assertIn(1522084164856, epoch_values)
        self.assertIn(1551565651188, epoch_values)

        # the embedded timestamps should be converted to human-readable form
        timestamp_nodes = get_nodes_by_type(test, 'timestamp.epoch-milliseconds')
        timestamp_values = [n.value for n in timestamp_nodes]
        self.assertIn('2018-03-26 17:09:24.856+00:00', timestamp_values)
        self.assertIn('2019-03-02 22:27:31.188+00:00', timestamp_values)

        # the snowflakes should be labeled as Discord Server and Channel IDs
        description_labels = [n.label for n in get_nodes_by_type(test, 'description')]
        self.assertIn('Server ID', description_labels)
        self.assertIn('Channel ID', description_labels)

        # is processing finished empty
        self.assertTrue(test.queue.empty())


if __name__ == '__main__':
    unittest.main()
