from unfurl.core import Unfurl
import unittest


class TestProtobuf(unittest.TestCase):

    def test_b64_zip_protobuf(self):
        """ Test a protobuf that is zipped, then base64-encoded."""

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='eJzj4tLP1TcwNajKKi8yYPSSTcvMSVUoriwuSc1VSMsvSs0rzkxWSMxLzKksziwGADbBDzw')
        test.parse_queue()

        # Check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 5)
        self.assertEqual(test.total_nodes, 5)

        # Confirm that it was detected as bytes, not ascii
        self.assertEqual('bytes', test.nodes[2].data_type)

        # Confirm that bytes decoded correctly
        self.assertEqual(b'\n\n/m/050zjwr0\x01J\x1dfile system forensic analysis', test.nodes[2].value)

        # Confirm that text/bytes proto field decoded correctly
        self.assertEqual('file system forensic analysis', test.nodes[5].value)

        # Make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)

    def test_standard_b64_protobuf(self):
        """ Test a protobuf that is encoded with standard b64."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='CkQKCEpvaG4gRG9lENIJGhBqZG9lQGV4YW1wbGUuY29tIOr//////////wEoks28w/3B2LS5ATF90LNZ9TkSQDoEABI0Vg==')
        test.parse_queue()

        # check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 9)
        self.assertEqual(test.total_nodes, 9)

        self.assertEqual('proto.dict', test.nodes[2].data_type)
        self.assertEqual('jdoe@example.com', test.nodes[5].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)

    def test_urlsafe_b64_protobuf(self):
        """ Test a protobuf that is encoded with urlsafe b64."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='CkQKCEpvaG4gRG9lENIJGhBqZG9lQGV4YW1wbGUuY29tIOr__________wEoks28w_3B2LS5ATF90LNZ9TkSQDoEABI0Vg')
        test.parse_queue()

        # check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 9)
        self.assertEqual(test.total_nodes, 9)

        self.assertEqual('proto.dict', test.nodes[2].data_type)
        self.assertEqual('jdoe@example.com', test.nodes[5].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)

    def test_base32_protobuf(self):
        """ Test a protobuf that is encoded with base32."""

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='BJCAUCCKN5UG4ICEN5SRBUQJDIIGUZDPMVAGK6DBNVYGYZJOMNXW2IHK7777777'
                  '777776AJISLG3ZQ75YHMLJOIBGF65BM2Z6U4REQB2AQABENCW')
        test.parse_queue()

        # Confirm it was decoded from base32, then parsed as a protobuf
        self.assertEqual('proto.dict', test.nodes[2].data_type)
        self.assertEqual('b32+proto', test.nodes[2].incoming_edge_config['label'])
        self.assertEqual('jdoe@example.com', test.nodes[5].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)

    def test_hex_protobuf(self):
        """ Test a protobuf that is encoded as hex."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='0a440a084a6f686e20446f6510d2091a106a646f65406578616d706c652e636f6d20ea'
                  'ffffffffffffffff012892cdbcc3fdc1d8b4b901317dd0b359f53912403a0400123456')
        test.parse_queue()

        # check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 9)
        self.assertEqual(test.total_nodes, 9)

        self.assertEqual('proto.dict', test.nodes[2].data_type)
        self.assertEqual('jdoe@example.com', test.nodes[5].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)


if __name__ == '__main__':
    unittest.main()
