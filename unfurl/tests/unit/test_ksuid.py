from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestKsuid(unittest.TestCase):

    def test_ksuid(self):
        """ Test of a typical ksuid """

        # unit test for a unique ksuid.
        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None, value='0o5Fs0EELR0fUjHjbCnEtdUwQe3')
        test.parse_queue()

        # confirm the value was recognized as a KSUID
        ksuid_nodes = get_nodes_by_type(test, 'ksuid')
        self.assertEqual(1, len(ksuid_nodes))
        self.assertEqual('0o5Fs0EELR0fUjHjbCnEtdUwQe3', ksuid_nodes[0].value)

        # confirm the embedded timestamp was extracted and decoded
        epoch_nodes = get_nodes_by_type(test, 'epoch-seconds')
        self.assertEqual(1, len(epoch_nodes))
        self.assertEqual(1494985761, epoch_nodes[0].value)

        timestamp_nodes = get_nodes_by_type(test, 'timestamp.epoch-seconds')
        self.assertEqual(1, len(timestamp_nodes))
        self.assertEqual('2017-05-17 01:49:21+00:00', timestamp_nodes[0].value)

        # is processing finished empty
        self.assertTrue(test.queue.empty())


if __name__ == '__main__':
    unittest.main()
