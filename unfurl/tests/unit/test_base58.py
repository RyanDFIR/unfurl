from unfurl.core import Unfurl
import unittest


def _edge_labels(test):
    """ Collect the incoming-edge labels for all nodes in the graph."""
    labels = []
    for node in test.nodes.values():
        config = getattr(node, 'incoming_edge_config', None)
        if config:
            labels.append(config.get('label'))
    return labels


class TestBase58(unittest.TestCase):

    def test_base58_ascii(self):
        """ Test a base58-encoded ASCII string ('hello=world&a=b')."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None, value='3vQB7B6PUmHD71EszE6W5')
        test.parse_queue()

        self.assertEqual('string', test.nodes[2].data_type)
        self.assertEqual('hello=world&a=b', test.nodes[2].value)
        self.assertEqual('b58', test.nodes[2].incoming_edge_config['label'])

    def test_all_letters_not_decoded(self):
        """ All-letter values are filtered out as likely words, not base58."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None, value='abcdefghijkmnopq')
        test.parse_queue()

        self.assertNotIn('b58', _edge_labels(test))

    def test_too_short_not_decoded(self):
        """ Values shorter than the base58 minimum length are ignored (noise control)."""

        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value='3vQB7B6PUm')
        test.parse_queue()

        self.assertNotIn('b58', _edge_labels(test))

    def test_binary_base58_not_emitted_as_string(self):
        """ A real base58 payload that decodes to binary (a Bitcoin address) is
        non-printable and intentionally not surfaced as a string."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2')
        test.parse_queue()

        self.assertNotIn('b58', _edge_labels(test))


    def test_explicit_base58_decodes_short_value(self):
        """ A node explicitly labelled 'base58' decodes even when below the
        auto-detect minimum length (heuristics are bypassed)."""

        test = Unfurl()
        # 'test' base58-encodes to '3yZe7d' (6 chars, under the auto-detect floor).
        test.add_to_queue(data_type='base58', key=None, value='3yZe7d')
        test.parse_queue()

        self.assertEqual('b58', test.nodes[2].incoming_edge_config['label'])
        self.assertEqual('test', test.nodes[2].value)

    def test_explicit_base58_binary_emits_bytes(self):
        """ An explicitly-labelled base58 node whose decode is non-printable is
        surfaced as a bytes node (not dropped)."""

        test = Unfurl()
        test.add_to_queue(
            data_type='base58', key=None,
            value='1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2')
        test.parse_queue()

        self.assertEqual('bytes', test.nodes[2].data_type)
        self.assertEqual('b58', test.nodes[2].incoming_edge_config['label'])


if __name__ == '__main__':
    unittest.main()
