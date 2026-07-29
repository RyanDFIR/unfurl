import base64
import zlib

from unfurl.core import Unfurl
import unittest


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def _make_token(payload: bytes, timestamp: int, sig_bytes: bytes = b'\x01' * 20, compress: bool = False) -> str:
    prefix = ''
    if compress:
        payload = zlib.compress(payload)
        prefix = '.'
    ts_bytes = timestamp.to_bytes((timestamp.bit_length() + 7) // 8, 'big')
    return f'{prefix}{_b64(payload)}.{_b64(ts_bytes)}.{_b64(sig_bytes)}'


def _edge_labels(test):
    labels = []
    for node in test.nodes.values():
        config = getattr(node, 'incoming_edge_config', None)
        if config:
            labels.append(config.get('label'))
    return labels


class TestItsDangerous(unittest.TestCase):

    def test_discord_verify_token(self):
        """ Test a real-world Discord email verification link, which contains an
        itsdangerous token whose payload holds a user ID (Snowflake) and email."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://discord.com/verify#token=eyJpZCI6MTM4MjA4MTIyMzQ2MzE0MTQ2OCwiZW1haWwiOiJvY3RvYm9iMjNAZ21ha'
                  'WwuY29tIn0.aEiJsA.YJXCGEC-sCDSwQAbMmF5NMsDFBg')
        test.parse_queue()

        node_values = [n.value for n in test.nodes.values()]

        # The signing timestamp (2025-06-10 19:38:24 UTC) was decoded
        self.assertIn(1749584304, node_values)

        # The payload was base64-decoded to the JSON it contains
        self.assertIn('{"id":1382081223463141468,"email":"octobob23@gmail.com"}', node_values)

        # The JSON was parsed into its fields
        self.assertIn('octobob23@gmail.com', node_values)

        # The user ID was recognized as a Discord Snowflake and its timestamp extracted
        self.assertIn(1749584241501, node_values)

        # The signature node shows the HMAC size (SHA-1 -> 20 bytes)
        node_labels = [getattr(n, 'label', None) for n in test.nodes.values()]
        self.assertIn('HMAC Signature (20 bytes)', node_labels)

    def test_modern_timestamp(self):
        """ Test a manually-built token with a modern (Unix epoch) timestamp."""

        token = _make_token(b'{"user": 123}', 1749584304)
        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value=token)
        test.parse_queue()

        node_values = [n.value for n in test.nodes.values()]
        self.assertIn(1749584304, node_values)
        self.assertIn('{"user": 123}', node_values)

    def test_legacy_timestamp(self):
        """ Test a token using the pre-2.0 itsdangerous epoch (2011-01-01); the
        decoded value should be normalized to Unix epoch seconds."""

        token = _make_token(b'{"user": 123}', 1749584304 - 1293840000)
        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value=token)
        test.parse_queue()

        node_values = [n.value for n in test.nodes.values()]
        self.assertIn(1749584304, node_values)

    def test_compressed_payload(self):
        """ Test a token with a zlib-compressed payload (leading '.'); the payload
        should be decompressed and its JSON parsed."""

        token = _make_token(b'{"purpose": "test-compression-in-itsdangerous"}', 1749584304, compress=True)
        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value=token)
        test.parse_queue()

        node_values = [n.value for n in test.nodes.values()]
        self.assertIn('{"purpose": "test-compression-in-itsdangerous"}', node_values)
        self.assertIn('test-compression-in-itsdangerous', node_values)
        self.assertIn(1749584304, node_values)

    def test_sha256_signature(self):
        """ Test a token signed with HMAC-SHA256 (32-byte signature)."""

        token = _make_token(b'{"user": 123}', 1749584304, sig_bytes=b'\x02' * 32)
        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value=token)
        test.parse_queue()

        node_labels = [getattr(n, 'label', None) for n in test.nodes.values()]
        self.assertIn('HMAC Signature (32 bytes)', node_labels)

    def test_jwt_not_claimed(self):
        """ A real JWT (long JSON middle segment) should be parsed as a JWT,
        not an itsdangerous token."""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0Ijox'
                  'NTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c')
        test.parse_queue()

        labels = _edge_labels(test)
        self.assertIn('JWT', labels)
        self.assertNotIn('🔏', labels)

    def test_implausible_timestamp_not_decoded(self):
        """ A three-part string whose middle segment isn't a plausible timestamp
        should not be treated as an itsdangerous token."""

        # Middle segment decodes to 6 bytes -> far larger than any plausible epoch
        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value='eyJ1c2VyIjogMTIzfQ.zzzzzzzz.YJXCGEC-sCDSwQAbMmF5NMsDFBg')
        test.parse_queue()

        self.assertNotIn('🔏', _edge_labels(test))

    def test_ordinary_dotted_string_not_decoded(self):
        """ Dotted strings like filenames or hostnames should not fire the parser."""

        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value='some.file.name')
        test.parse_queue()

        self.assertNotIn('🔏', _edge_labels(test))


if __name__ == '__main__':
    unittest.main()
