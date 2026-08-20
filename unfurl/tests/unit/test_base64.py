from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestBase64(unittest.TestCase):

    def test_padded_b64_ascii(self):
        """ Test a simple ASCII string that is base64-encoded."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='dGVzdHl0ZXN0dGVzdA==')
        test.parse_queue()

        # confirm that it was decoded from b64 to a string
        # and that text decoded correctly
        decoded_node = next(iter(get_nodes_by_type(test, 'string')))
        self.assertEqual('testytesttest', decoded_node.value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())

    def test_unpadded_b64_ascii(self):
        """ Test a simple ASCII string that is base64-encoded, with padding removed."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='dGVzdHl0ZXN0dGVzdA')
        test.parse_queue()

        # confirm that it was decoded from b64 to a string
        # and that text decoded correctly
        decoded_node = next(iter(get_nodes_by_type(test, 'string')))
        self.assertEqual('testytesttest', decoded_node.value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())

    def test_incorrect_padded_b64_ascii(self):
        """ Test a simple ASCII string that is base64-encoded, with incorrect padding"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='dGVzdHl0ZXN0dGVzdA=')
        test.parse_queue()

        # confirm that it was decoded from b64 to a string
        # and that text decoded correctly
        decoded_node = next(iter(get_nodes_by_type(test, 'string')))
        self.assertEqual('testytesttest', decoded_node.value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())

    def test_explicit_base64_decodes_directly(self):
        """ A node explicitly labelled 'base64' decodes directly, bypassing the
        auto-detection heuristics."""

        test = Unfurl()
        test.add_to_queue(data_type='base64', key=None, value='dGVzdA==')
        test.parse_queue()

        decoded_node = next(iter(get_nodes_by_type(test, 'string')))
        self.assertEqual('test', decoded_node.value)
        self.assertEqual('b64', decoded_node.incoming_edge_config['label'])

    def test_explicit_base64_binary_emits_bytes(self):
        """ An explicitly-labelled base64 node whose decode is non-printable is
        surfaced as a bytes node (not dropped like in auto-detection)."""

        import base64

        test = Unfurl()
        value = base64.b64encode(bytes([0, 1, 2, 255])).decode()
        test.add_to_queue(data_type='base64', key=None, value=value)
        test.parse_queue()

        decoded_node = next(iter(get_nodes_by_type(test, 'bytes')))
        self.assertEqual(bytes([0, 1, 2, 255]), decoded_node.value)
        self.assertEqual('b64', decoded_node.incoming_edge_config['label'])


if __name__ == '__main__':
    unittest.main()
