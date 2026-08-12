from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestSonyflake(unittest.TestCase):

    def test_sonyflake(self):
        """ Test of a Sonyflake """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None, value='45eec4a4600041b')
        test.parse_queue()

        # confirm the machine ID is parsed correctly
        machine_id_nodes = [
            n for n in get_nodes_by_type(test, 'integer')
            if n.label.startswith('Machine ID')]
        self.assertEqual(len(machine_id_nodes), 1)
        self.assertIn('4.27', machine_id_nodes[0].label)

        # confirm the time is parsed correctly
        timestamp_nodes = get_nodes_by_type(test, 'timestamp.epoch-centiseconds')
        self.assertEqual(len(timestamp_nodes), 1)
        self.assertIn('2020-08-12 17:35:29.98', timestamp_nodes[0].label)


if __name__ == '__main__':
    unittest.main()
