from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


def run_unfurl(value):
    test = Unfurl(remote_lookups=False)
    test.add_to_queue(data_type='url', key=None, value=value)
    test.parse_queue()
    return test


class TestEtag(unittest.TestCase):

    def test_nginx_quoted(self):
        """ nginx ETag pasted as it appears in a header: hex(mtime)-hex(size) """
        test = run_unfurl('"6ac46e19-13e7f8"')

        self.assertIn('hex(mtime)-hex(size)', get_nodes_by_type(test, 'etag.format')[0].label)
        self.assertEqual(1304568, get_nodes_by_type(test, 'etag.size')[0].value)
        self.assertEqual(0x6ac46e19, get_nodes_by_type(test, 'epoch-seconds')[0].value)
        self.assertIn('2026-10-06 03:42:17', get_nodes_by_type(test, 'timestamp.epoch-seconds')[0].label)

    def test_query_param_size_mtime_seconds(self):
        """ ETag copied into an etag= URL parameter: hex(size)-hex(mtime in seconds) """
        test = run_unfurl(
            'https://images.example.com/media/photo.jpg?etag=%22f4381-6385a594%22&quality=85')

        self.assertEqual(1000321, get_nodes_by_type(test, 'etag.size')[0].value)
        self.assertIn('2022-11-29 06:24:20', get_nodes_by_type(test, 'timestamp.epoch-seconds')[0].label)
        self.assertEqual([], get_nodes_by_type(test, 'etag.weak'))

    def test_query_param_weak_milliseconds(self):
        """ Weak Node.js-style ETag: W/"hex(size)-hex(mtime in milliseconds)" """
        test = run_unfurl(
            'https://images.example.com/media/photo.png?etag=W%2F%22f69d-19c3369f520%22')

        self.assertIn('milliseconds', get_nodes_by_type(test, 'etag.format')[0].label)
        self.assertEqual(63133, get_nodes_by_type(test, 'etag.size')[0].value)
        self.assertEqual(1, len(get_nodes_by_type(test, 'etag.weak')))
        self.assertIn('2026-02-', get_nodes_by_type(test, 'timestamp.epoch-milliseconds')[0].label)

    def test_query_param_mangled_weak_marker(self):
        """ Weak marker copied into a URL as its own quoted string: "W/" "..." """
        test = run_unfurl(
            'https://images.example.com/media/photo.jpg?etag=%22W%2F%22%20%222076f-5506003f%22')

        self.assertEqual(132975, get_nodes_by_type(test, 'etag.size')[0].value)
        self.assertEqual(1, len(get_nodes_by_type(test, 'etag.weak')))

    def test_apache_microseconds(self):
        """ Apache httpd 2.4 ETag: hex(size)-hex(mtime in microseconds) """
        test = run_unfurl('"1b68c-5db44839af051"')

        self.assertIn('Apache', get_nodes_by_type(test, 'etag.format')[0].label)
        self.assertEqual(112268, get_nodes_by_type(test, 'etag.size')[0].value)
        self.assertEqual(1, len(get_nodes_by_type(test, 'timestamp.epoch-microseconds')))

    def test_apache_inode_and_gzip_suffix(self):
        """ Apache ETag with the inode component and the -gzip suffix from mod_deflate """
        test = run_unfurl('"2c0a3f-1b68c-5db44839af051-gzip"')

        self.assertEqual(0x2c0a3f, get_nodes_by_type(test, 'etag.inode')[0].value)
        self.assertEqual(112268, get_nodes_by_type(test, 'etag.size')[0].value)
        self.assertEqual('gzip', get_nodes_by_type(test, 'etag.suffix')[0].value)

    def test_express_body_hash(self):
        """ Express ETag of a response body: W/"hex(length)-base64(SHA-1)" """
        test = run_unfurl('W/"7a3-4bqq729ReKBiCrqxznP/p7SzQfc"')

        self.assertEqual(1955, get_nodes_by_type(test, 'etag.size')[0].value)
        self.assertEqual('4bqq729ReKBiCrqxznP/p7SzQfc', get_nodes_by_type(test, 'etag.hash')[0].value)

    def test_s3_multipart(self):
        """ Amazon S3 multipart ETag: MD5 of part MD5s, then the part count """
        test = run_unfurl('"d41d8cd98f00b204e9800998ecf8427e-12"')

        self.assertEqual(12, get_nodes_by_type(test, 'etag.parts')[0].value)
        self.assertEqual('d41d8cd98f00b204e9800998ecf8427e', get_nodes_by_type(test, 'etag.hash')[0].value)
        # It's a hash of hashes, so it isn't handed to the hash parser as an MD5
        self.assertEqual([], get_nodes_by_type(test, 'hash.md5'))

    def test_unquoted_hex_pair_not_parsed(self):
        """ A bare hex-hex value outside an etag parameter is too ambiguous to decode """
        test = run_unfurl('6ac46e19-13e7f8')
        self.assertEqual([], get_nodes_by_type(test, 'etag.format'))

    def test_undecodable_etag_param(self):
        """ An etag parameter holding an opaque value adds no ETag nodes """
        test = run_unfurl('https://example.com/logo.svg?etag=1D8B889&w=200')
        self.assertEqual([], get_nodes_by_type(test, 'etag.format'))


if __name__ == '__main__':
    unittest.main()
