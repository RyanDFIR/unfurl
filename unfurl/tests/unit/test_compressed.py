import base64
import zlib
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


class TestCompressed(unittest.TestCase):

    def test_base32_then_zlib(self):
        """ A base32-encoded, zlib-compressed payload should inflate to a string."""

        payload = b'hello=world&a=b'
        value = base64.b32encode(zlib.compress(payload)).decode()

        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value=value)
        test.parse_queue()

        labels = _edge_labels(test)
        self.assertIn('b32+zip', labels)

        b32_zip_node = next(
            n for n in test.nodes.values()
            if getattr(n, 'incoming_edge_config', None)
            and n.incoming_edge_config.get('label') == 'b32+zip')
        self.assertEqual('hello=world&a=b', b32_zip_node.value)

    def test_base64_then_zlib(self):
        """ Regression: the long-standing base64+zlib chain still inflates."""

        payload = b'hello=world&a=b'
        value = base64.b64encode(zlib.compress(payload)).decode()

        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value=value)
        test.parse_queue()

        self.assertIn('b64+zip', _edge_labels(test))
        self.assertIn('hello=world&a=b', [n.value for n in test.nodes.values()])


if __name__ == '__main__':
    unittest.main()
