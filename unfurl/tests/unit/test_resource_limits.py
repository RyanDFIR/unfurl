import base64
import configparser
import importlib.util
import unittest
import zlib
from unittest import mock

from unfurl.core import Unfurl
from unfurl.parsers import parse_base58, parse_protobuf


def _deflated_query_url(data):
    """A URL with base64url(zlib(data)) in a query parameter, the shape parse_compressed inflates."""
    encoded = base64.urlsafe_b64encode(zlib.compress(data, 9)).decode().rstrip('=')
    return f'https://example.com/?d={encoded}'


class TestBase58Length(unittest.TestCase):

    def test_long_value_not_decoded(self):
        self.assertIsNone(parse_base58._b58_decode('A1' * 50_000))

    def test_value_at_limit_still_decodes(self):
        self.assertIsNotNone(parse_base58._b58_decode('2' * parse_base58.MAX_B58_LENGTH))


class TestProtobufLength(unittest.TestCase):

    def test_long_hex_value_not_decoded(self):
        # 0x08 0x0a repeated is a valid protobuf (field 1 = 10, many times over). It has
        # letters in it, since the parser skips all-digit values regardless of length.
        value = '080a' * (parse_protobuf.MAX_PROTOBUF_INPUT_LENGTH // 4 + 1)
        test = Unfurl(remote_lookups=False)
        test.add_to_queue(data_type='url.query.pair', key='d', value=value)
        test.parse_queue()

        self.assertFalse(
            [n for n in test.nodes.values() if n.data_type.startswith('proto')])


class TestQueueBudget(unittest.TestCase):

    def test_queue_stops_growing_at_node_limit(self):
        test = Unfurl(remote_lookups=False)
        for i in range(test.node_limit * 3):
            test.add_to_queue(data_type='string', key=None, value=f'item {i}')

        self.assertEqual(test.node_limit, test.queue.qsize())

    def test_queue_budget_counts_existing_nodes(self):
        test = Unfurl(remote_lookups=False)
        test.total_nodes = test.node_limit - 10
        for i in range(100):
            test.add_to_queue(data_type='string', key=None, value=f'item {i}')

        self.assertEqual(10, test.queue.qsize())


class TestDecompressedAmplification(unittest.TestCase):
    """A small URL that inflates to about 1 MB must not take minutes or exhaust memory.

    Before the caps, the first case ran for minutes (quadratic base58 and varint
    decoding) and the second queued hundreds of thousands of protobuf fields.
    """

    def test_inflated_base58_run(self):
        test = Unfurl(remote_lookups=False)
        test.add_to_queue(data_type='url', key=None, value=_deflated_query_url(b'A1' * 500_000))
        test.parse_queue()

        self.assertLessEqual(test.total_nodes, test.node_limit)

    def test_inflated_zero_bytes(self):
        test = Unfurl(remote_lookups=False)
        test.add_to_queue(data_type='url', key=None, value=_deflated_query_url(b'\x00' * 1_000_000))
        test.parse_queue()

        self.assertLessEqual(test.total_nodes, test.node_limit)
        self.assertLessEqual(test.queue.qsize(), test.node_limit)


@unittest.skipUnless(importlib.util.find_spec('flask'), 'web UI extras (requirements-ui.txt) not installed')
class TestWebAppDebugDefault(unittest.TestCase):
    """A config that sets only some values (as a pip install with an unfurl.local.ini
    does, since the wheel has no base unfurl.ini) must not turn the debugger on."""

    def _debug_for(self, config_text):
        from unfurl import app
        config = configparser.ConfigParser()
        config.read_string(config_text)
        with mock.patch.object(app, 'load_config', return_value=config), \
                mock.patch.object(app, 'preload_reference_data'), \
                mock.patch.object(app, 'UnfurlApp') as unfurl_app:
            app.web_app()
        return unfurl_app.call_args.kwargs['unfurl_debug']

    def test_partial_config_leaves_debug_off(self):
        self.assertFalse(self._debug_for('[UNFURL_APP]\nhost = 0.0.0.0\n'))

    def test_no_config_leaves_debug_off(self):
        self.assertFalse(self._debug_for(''))

    def test_debug_can_still_be_enabled(self):
        self.assertTrue(self._debug_for('[UNFURL_APP]\ndebug = true\n'))
