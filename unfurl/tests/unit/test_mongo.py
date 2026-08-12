from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestMongo(unittest.TestCase):

    def test_mongo_objectid(self):
        """ Test parsing of a MongoDB ObjectID submitted directly """

        # ObjectID breakdown:
        #   65920080   = 0x65920080 = 1704067200 = 2024-01-01 00:00:00 UTC
        #   aabbccddee = machine identifier (MongoDB < 4.0) or random value (MongoDB 4.0+)
        #   112233     = counter (0x112233 = 1122867)
        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None, value='65920080aabbccddee112233')
        test.parse_queue()

        # confirm MongoDB ObjectID is detected
        objectid_nodes = get_nodes_by_type(test, 'mongo.objectid')
        self.assertEqual(len(objectid_nodes), 1)
        self.assertIn('MongoDB ObjectID', objectid_nodes[0].label)

        # confirm timestamp is decoded correctly
        timestamp_nodes = get_nodes_by_type(test, 'timestamp.epoch-seconds')
        self.assertEqual(len(timestamp_nodes), 1)
        self.assertIn('2024-01-01 00:00:00', timestamp_nodes[0].label)

        # confirm counter is parsed correctly
        counter_nodes = get_nodes_by_type(test, 'integer')
        self.assertEqual(len(counter_nodes), 1)
        self.assertEqual('Counter: 1122867', counter_nodes[0].label)

    def test_mongo_objectid_in_url(self):
        """ Test that a MongoDB ObjectID embedded in a URL path is detected """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://example.com/api/products/65920080aabbccddee112233')
        test.parse_queue()

        # confirm MongoDB ObjectID is detected somewhere in the graph
        found_oid = any(
            node.label and 'MongoDB ObjectID' in node.label
            for node in test.nodes.values()
        )
        self.assertTrue(found_oid)

        # confirm timestamp is decoded somewhere in the graph
        found_ts = any(
            node.label and '2024-01-01 00:00:00' in node.label
            for node in test.nodes.values()
        )
        self.assertTrue(found_ts)

    def test_non_mongo_hex_ignored(self):
        """ Test that a 24-char hex string with a timestamp outside MongoDB's range is not parsed """

        # 00000001 = timestamp 1 (1970-01-01), well outside the 2009-2030 filter
        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None, value='00000001aabbccddee112233')
        test.parse_queue()

        # should produce only the initial node — not detected as a MongoDB ObjectID
        found_oid = any(
            node.label and 'MongoDB ObjectID' in node.label
            for node in test.nodes.values()
        )
        self.assertFalse(found_oid)


if __name__ == '__main__':
    unittest.main()
