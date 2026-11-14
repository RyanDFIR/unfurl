from unfurl.core import Unfurl
import unittest


class TestHashDetection(unittest.TestCase):

    def test_md5_hash_no_lookups(self):
        """ Test detecting a MD5 in a URL with lookups disabled """

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='http://test-hashes.com/test?1=5f4dcc3b5aa765d61d8327deb882cf99')
        test.parse_queue()

        # confirm that detected as MD5
        md5_node = next(n for n in test.nodes.values() if n.data_type == 'hash.md5')
        self.assertIn('Potential MD5 hash', md5_node.label)

    def test_hashes_starting_with_two_digits(self):
        """ A hash that starts with two digits has the Cisco "Type 7" shape, but is still labeled a hash """

        for value, data_type in (
                ('098f6bcd4621d373cade4e832627b4f6', 'hash.md5'),
                ('40bd001563085fc35165329ea1ff5c5ecbdbbeef', 'hash.sha-1'),
                ('9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08', 'hash.sha-256')):
            with self.subTest(value=value):
                test = Unfurl(remote_lookups=False)
                test.add_to_queue(data_type='url', key=None, value=f'http://test-hashes.com/test?1={value}')
                test.parse_queue()

                self.assertEqual(1, len([n for n in test.nodes.values() if n.data_type == data_type]))

    def test_cisco_type_7_still_decoded(self):
        """ A real Cisco "Type 7" value is decoded, and is not also labeled a hash """

        test = Unfurl(remote_lookups=False)
        test.add_to_queue(data_type='url', key=None, value='http://test-hashes.com/test?1=02050D480809')
        test.parse_queue()

        text_nodes = [n for n in test.nodes.values() if n.data_type == 'text']
        self.assertEqual(['cisco'], [n.value for n in text_nodes])
        self.assertEqual([], [n for n in test.nodes.values() if n.data_type.startswith('hash')])


if __name__ == '__main__':
    unittest.main()
