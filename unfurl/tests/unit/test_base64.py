from unfurl.core import Unfurl
import unittest


class TestBase64(unittest.TestCase):

    def test_padded_b64_ascii(self):
        """ Test a simple ASCII string that is base64-encoded."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='dGVzdHl0ZXN0dGVzdA==')
        test.parse_queue()

        # check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 2)
        self.assertEqual(test.total_nodes, 2)

        # confirm that it was decoded from b64 to a string
        self.assertEqual('string', test.nodes[2].data_type)

        # confirm that text decoded correctly
        self.assertEqual('testytesttest', test.nodes[2].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)

    def test_unpadded_b64_ascii(self):
        """ Test a simple ASCII string that is base64-encoded, with padding removed."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='dGVzdHl0ZXN0dGVzdA')
        test.parse_queue()

        # check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 2)
        self.assertEqual(test.total_nodes, 2)

        # confirm that it was decoded from b64 to a string
        self.assertEqual('string', test.nodes[2].data_type)

        # confirm that text decoded correctly
        self.assertEqual('testytesttest', test.nodes[2].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)

    def test_incorrect_padded_b64_ascii(self):
        """ Test a simple ASCII string that is base64-encoded, with incorrect padding"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='dGVzdHl0ZXN0dGVzdA=')
        test.parse_queue()

        # check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 2)
        self.assertEqual(test.total_nodes, 2)

        # confirm that it was decoded from b64 to a string
        self.assertEqual('string', test.nodes[2].data_type)

        # confirm that text decoded correctly
        self.assertEqual('testytesttest', test.nodes[2].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)


    def test_explicit_base64_decodes_directly(self):
        """ A node explicitly labelled 'base64' decodes directly, bypassing the
        auto-detection heuristics."""

        test = Unfurl()
        test.add_to_queue(data_type='base64', key=None, value='dGVzdA==')
        test.parse_queue()

        self.assertEqual('string', test.nodes[2].data_type)
        self.assertEqual('test', test.nodes[2].value)
        self.assertEqual('b64', test.nodes[2].incoming_edge_config['label'])

    def test_explicit_base64_binary_emits_bytes(self):
        """ An explicitly-labelled base64 node whose decode is non-printable is
        surfaced as a bytes node (not dropped like in auto-detection)."""

        import base64

        test = Unfurl()
        value = base64.b64encode(bytes([0, 1, 2, 255])).decode()
        test.add_to_queue(data_type='base64', key=None, value=value)
        test.parse_queue()

        self.assertEqual('bytes', test.nodes[2].data_type)
        self.assertEqual(bytes([0, 1, 2, 255]), test.nodes[2].value)
        self.assertEqual('b64', test.nodes[2].incoming_edge_config['label'])


if __name__ == '__main__':
    unittest.main()
