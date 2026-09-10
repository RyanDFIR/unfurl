import base64
import os

from unfurl.core import Unfurl
from unfurl import utils
import unittest


def _make_token(timestamp, ciphertext_blocks=1, version=0x80):
    """Build a structurally valid Fernet token with a chosen timestamp."""
    payload = (bytes([version]) + timestamp.to_bytes(8, 'big') + os.urandom(16)
               + os.urandom(16 * ciphertext_blocks) + os.urandom(32))
    return base64.urlsafe_b64encode(payload).decode()


def _fernet_nodes(test):
    return [n for n in test.nodes.values() if n.data_type.startswith('fernet')]


class TestFernet(unittest.TestCase):

    def test_fernet_token_in_query_parameter(self):
        """Parse a canonical Fernet token sitting in a query parameter.

        Test data source: a real SourceForge download link. The token's '=='
        padding is URL-encoded as %3D%3D.
        """

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://downloads.sourceforge.net/project/processhacker/processhacker2/'
                  'processhacker-2.39-bin.zip?ts=gAAAAABi9QhscGoj3QZ9QlP-IrSoilvRjEhlpGfcTMHR'
                  '-zrvaHtTCiFzmHxjRJYmUhM6010ob_LVv4ZquHSgHxcU1S3iYQMdLQ%3D%3D'
                  '&use_mirror=ixpeering&r=https%3A%2F%2Fprocesshacker.sourceforge.io%2F')
        test.parse_queue()

        node_values = [n.value for n in test.nodes.values()]

        # The creation time (2022-08-11 13:47:24 UTC) was decoded from bytes 1-8
        self.assertIn(1660225644, node_values)
        self.assertIn('2022-08-11 13:47:24+00:00', node_values)

        # Each part carries the bytes it actually holds, rather than a summary
        self.assertIn('0x80', node_values)
        self.assertIn('0x706a23dd067d4253fe22b4a88a5bd18c', node_values)
        self.assertIn('0x4865a467dc4cc1d1fb3aef687b530a21', node_values)

        # ...and what those bytes mean is described beneath them
        self.assertIn('Initialization vector (16 bytes) for the AES-128-CBC encryption',
                      node_values)
        self.assertIn('Encrypted contents: 16 bytes, 1 AES blocks', node_values)
        self.assertIn('HMAC-SHA256 (32 bytes) over every preceding byte', node_values)

        # A canonical token needs no rewriting, so no normalization node
        self.assertEqual(
            [], [n for n in test.nodes.values() if n.data_type == 'fernet.normalized'])

    def test_fernet_token_in_url_path(self):
        """Parse a Fernet token that is a URL path segment rather than a parameter.

        Test data source: a real northstarhockey.com email link.
        """

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.northstarhockey.com/email/gAAAAABp3C6O9v8TJ3YIClmnKuHKBsr1'
                  'YrZNFi6d4X5cEjeuSYYlakJzuo000QzXoJvMR0BBlLrUL7lbvJtB3o9stdWH1Tp4etpLfZZj'
                  '9-XjJlEYbx5uUSg=?to_name=Adam+Frutman')
        test.parse_queue()

        # The creation time (2026-04-12 23:45:18 UTC) was decoded
        self.assertIn(1776037518, [n.value for n in test.nodes.values()])
        self.assertIn('2026-04-12 23:45:18+00:00', [n.value for n in test.nodes.values()])

        # This one carries two blocks of ciphertext (an 89-byte payload)
        self.assertIn('Encrypted contents: 32 bytes, 2 AES blocks',
                      [n.value for n in test.nodes.values()])

    def test_chatgpt_ads_oppref_and_olref(self):
        """Parse OpenAI's ChatGPT Ads click IDs, which are Fernet tokens whose
        trailing '=' padding is written as a single 'w'.

        Both parameters are minted at the same instant for one ad click. oppref
        carries 32 bytes of ciphertext, olref 64.

        Test data source: live ChatGPT ad click on an Expedia landing page,
        captured 2026-09-10.
        """

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.expedia.com/Discovery-Cove-Orlando.d6068683.Vacation-Attraction'
                  '?oppref=gAAAAABqos5vVDWlTbIrMA0V3ZaokkilSh8qPsUPiM5EsyBxRPX8wkpICPef6hwmzAVy'
                  'iCh4f3RTRyM8OUPQZuUefoJ7hMywnrRJkOGU88GlquI4Pql60Xsw'
                  '&olref=gAAAAABqos5vZd7yc7z0rS3WdD5BCDF7yGDJZHABQrevHqnNO9t5pFpOLjWTJkK8cywp'
                  'Q5F-HtvPPNf1QUV3f2oQWXhCitnaqkln2A9PTYknSuUkvQZp5OOwMO33WtN8FG-7Nw1qIPh9faim'
                  'mTBthT8vIqbTvF_Ydgw')
        test.parse_queue()

        node_values = [n.value for n in test.nodes.values()]

        # Both click IDs decode to the same second (2026-09-10 15:36:15 UTC)
        self.assertEqual(2, node_values.count(1789054575))
        self.assertIn('2026-09-10 15:36:15+00:00', node_values)

        # The padding rewrite is shown as its own node, carrying the re-padded
        # token, rather than being applied silently. Once per token.
        normalized = [n for n in test.nodes.values() if n.data_type == 'fernet.normalized']
        self.assertEqual(2, len(normalized))
        for node in normalized:
            self.assertTrue(node.value.endswith('='))
            self.assertFalse(node.value.endswith('w='))

        # ...and the rewrite is explained on that node's hover rather than
        # costing an extra node
        for node in normalized:
            self.assertIn('trailing "w"', node.hover)
            self.assertIn('oppref', node.hover)

        # The parts are read out of the re-padded value, so they hang beneath
        # it rather than beneath the value as found. The token node's only
        # Fernet child is the normalized token itself.
        for node in normalized:
            children = {c.data_type for c in test.graph.successors(node)}
            self.assertEqual(
                {'fernet.version', 'epoch-seconds',
                 'fernet.iv', 'fernet.ciphertext', 'fernet.signature'},
                children)

        for token in [n for n in test.nodes.values() if n.key in ('oppref', 'olref')]:
            self.assertEqual(
                ['fernet.normalized'],
                [c.data_type for c in test.graph.successors(token)])

        # The two tokens differ only in ciphertext size
        self.assertIn('Encrypted contents: 32 bytes, 2 AES blocks', node_values)
        self.assertIn('Encrypted contents: 64 bytes, 4 AES blocks', node_values)

    def test_each_part_shows_its_bytes_and_is_described_beneath(self):
        """Every part split out of a token keeps its raw value as the node's own
        value, and its meaning hangs underneath it as a descriptor, rather than
        the meaning replacing the value in a label."""

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://downloads.sourceforge.net/f.zip?ts=gAAAAABi9QhscGoj3QZ9QlP-'
                  'IrSoilvRjEhlpGfcTMHR-zrvaHtTCiFzmHxjRJYmUhM6010ob_LVv4ZquHSgHxcU1S3i'
                  'YQMdLQ%3D%3D')
        test.parse_queue()

        parts = {n.data_type: n for n in test.nodes.values()
                 if n.data_type.startswith('fernet.')}
        self.assertEqual(
            {'fernet.version', 'fernet.iv', 'fernet.ciphertext', 'fernet.signature'},
            set(parts))

        for data_type, part in parts.items():
            # the node shows the bytes, not a summary of them. unfurl builds the
            # displayed label as "key: value", so the raw value has to survive
            # into it; setting a label of our own would replace it.
            self.assertTrue(part.value.startswith('0x'), f'{data_type} is not raw bytes')
            self.assertIn(part.value, part.label,
                          f'{data_type} hides its value behind a label')

        # The parts whose size is worth stating get a descriptor beneath them.
        for data_type in ('fernet.iv', 'fernet.ciphertext', 'fernet.signature'):
            children = list(test.graph.successors(parts[data_type]))
            self.assertEqual(
                ['descriptor'], [c.data_type for c in children],
                f'{data_type} is not described by a child descriptor')

        # The version byte has nothing derived to add, so its meaning lives on
        # its hover instead of costing a node.
        self.assertEqual([], list(test.graph.successors(parts['fernet.version'])))
        self.assertIn('only version ever defined', parts['fernet.version'].hover)
        self.assertIn('[ref]', parts['fernet.version'].hover)

    def test_google_iflsig_is_not_a_fernet_token(self):
        """Don't fire on values that merely contain 'gAAAAA' somewhere inside.

        Google's iflsig parameter embeds the substring, and is by far the most
        common way it appears in real URLs (75% of the URLs containing it, in a
        survey of a large corpus). Only a value that starts with it can be a
        Fernet token.
        """

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.google.com/search?q=test&source=hp&ei=HhzIaYDXDd6Txc8PzLiagQY'
                  '&iflsig=AFdpzrgAAAAAacgqLj2YwCGGJ6yfTnbv5YV-R3LuduQx')
        test.parse_queue()

        self.assertEqual([], _fernet_nodes(test))

    def test_implausible_timestamp_is_not_decoded(self):
        """A structurally valid token dated outside the plausible range is some
        other format that happens to share Fernet's leading bytes.

        Test data source: real-world URLs, where values of this shape are the
        most common reason a 'gAAAAA'-prefixed candidate is not a token.
        """

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://example.com/?k=gAAAAAJnAAsAAABSTlU2LTExNDlQABB0AA4AAAACdgAE')
        test.parse_queue()

        self.assertEqual([], _fernet_nodes(test))

    def test_wrong_ciphertext_length_is_not_decoded(self):
        """Fernet's ciphertext is AES-CBC, so the payload is always 57 + 16k
        bytes. A plausible-looking value of any other length is rejected."""

        token = _make_token(1660225644)
        # Drop four base64 characters (three bytes) to break the block alignment
        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(data_type='url', key=None,
                          value=f'https://example.com/?k={token.rstrip("=")[:-4]}')
        test.parse_queue()

        self.assertEqual([], _fernet_nodes(test))

    def test_wrong_version_byte_is_not_decoded(self):
        """Only version 0x80 has ever been defined."""

        token = _make_token(1660225644, version=0x81)
        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(data_type='url', key=None,
                          value=f'https://example.com/?k={token}')
        test.parse_queue()

        self.assertEqual([], _fernet_nodes(test))

    def test_far_future_token_is_not_decoded(self):
        """The upper plausibility bound is computed at run time (a year out),
        so unlike a hardcoded window it cannot silently expire. A token dated
        well beyond it is still rejected."""

        token = _make_token(utils.create_epoch_seconds_timestamp(days_ahead=800))
        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(data_type='url', key=None,
                          value=f'https://example.com/?k={token}')
        test.parse_queue()

        self.assertEqual([], _fernet_nodes(test))

    def test_token_predating_the_fernet_spec_is_not_decoded(self):
        """Fernet was published in 2013; a token cannot predate it."""

        token = _make_token(1041379200)  # 2003-01-01
        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(data_type='url', key=None,
                          value=f'https://example.com/?k={token}')
        test.parse_queue()

        self.assertEqual([], _fernet_nodes(test))

    def test_opaque_bytes_are_not_reparsed_as_other_formats(self):
        """The IV, ciphertext and HMAC are random bytes. Rendered as bare hex
        they would be misread downstream: 64 hex characters look like a SHA-256
        hash, and 32 with a plausible version nibble look like a UUID."""

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.expedia.com/x?oppref=gAAAAABqos5vVDWlTbIrMA0V3ZaokkilSh8qPsUP'
                  'iM5EsyBxRPX8wkpICPef6hwmzAVyiCh4f3RTRyM8OUPQZuUefoJ7hMywnrRJkOGU88GlquI4'
                  'Pql60Xsw')
        test.parse_queue()

        # The IV really would match parse_uuid's pattern if emitted as bare hex
        self.assertEqual(
            [], [n for n in test.nodes.values() if n.data_type.startswith(('uuid', 'hash'))])

        iv = [n for n in test.nodes.values() if n.data_type == 'fernet.iv']
        self.assertEqual(1, len(iv))
        self.assertTrue(iv[0].value.startswith('0x'))


if __name__ == '__main__':
    unittest.main()
