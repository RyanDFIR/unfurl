from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestIp(unittest.TestCase):

    def test_ip(self):
        """ Test a generic IP with a scheme and path"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://216.58.199.78/test')
        test.parse_queue()

        # confirm the scheme is parsed
        scheme_nodes = get_nodes_by_type(test, 'url.scheme')
        self.assertEqual(len(scheme_nodes), 1)
        self.assertIn('https', scheme_nodes[0].label)

        # confirm the IP is parsed as the hostname
        hostname_nodes = get_nodes_by_type(test, 'url.hostname')
        self.assertEqual(len(hostname_nodes), 1)
        self.assertEqual('216.58.199.78', hostname_nodes[0].label)

        # confirm the path is parsed
        path_nodes = get_nodes_by_type(test, 'url.path')
        self.assertEqual(len(path_nodes), 1)
        self.assertIn('path', path_nodes[0].hover)

    def test_almost_ip(self):
        """ Test a domain that looks almost like an IP, with a scheme and path"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://216.58.199.com/test')
        test.parse_queue()

        # confirm the scheme is parsed
        scheme_nodes = get_nodes_by_type(test, 'url.scheme')
        self.assertEqual(len(scheme_nodes), 1)
        self.assertIn('https', scheme_nodes[0].label)

        # confirm the domain is parsed
        domain_nodes = get_nodes_by_type(test, 'url.domain')
        self.assertEqual(len(domain_nodes), 1)
        self.assertEqual('Domain Name: 199.com', domain_nodes[0].label)

        # confirm it was not treated as an IP
        self.assertEqual(len(get_nodes_by_type(test, 'ip')), 0)

        # confirm the path is parsed
        path_nodes = get_nodes_by_type(test, 'url.path')
        self.assertEqual(len(path_nodes), 1)
        self.assertIn('path', path_nodes[0].hover)

    def test_int_ip(self):
        """ Test an IP represented as an integer, with a scheme and path"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://3627730766/test')
        test.parse_queue()

        # confirm the scheme is parsed
        scheme_nodes = get_nodes_by_type(test, 'url.scheme')
        self.assertEqual(len(scheme_nodes), 1)
        self.assertIn('https', scheme_nodes[0].label)

        # confirm the integer is converted to an IP
        ip_nodes = get_nodes_by_type(test, 'ip')
        self.assertEqual(len(ip_nodes), 1)
        self.assertEqual('216.58.199.78', ip_nodes[0].label)

        # confirm the path is parsed
        path_nodes = get_nodes_by_type(test, 'url.path')
        self.assertEqual(len(path_nodes), 1)
        self.assertIn('path', path_nodes[0].hover)

    def test_hex_ip(self):
        """ Test an IP represented as hex, with a scheme and path"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://0xD83AC74E/test')
        test.parse_queue()

        # confirm the scheme is parsed
        scheme_nodes = get_nodes_by_type(test, 'url.scheme')
        self.assertEqual(len(scheme_nodes), 1)
        self.assertIn('https', scheme_nodes[0].label)

        # confirm the hex value is converted to an IP
        ip_nodes = get_nodes_by_type(test, 'ip')
        self.assertEqual(len(ip_nodes), 1)
        self.assertEqual('216.58.199.78', ip_nodes[0].label)

        # confirm the path is parsed
        path_nodes = get_nodes_by_type(test, 'url.path')
        self.assertEqual(len(path_nodes), 1)
        self.assertIn('path', path_nodes[0].hover)

    def test_octal_ip(self):
        """ Test an IP represented as octal, with a scheme and path"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://0330.0072.0307.0116/test')
        test.parse_queue()

        # confirm the scheme is parsed
        scheme_nodes = get_nodes_by_type(test, 'url.scheme')
        self.assertEqual(len(scheme_nodes), 1)
        self.assertIn('https', scheme_nodes[0].label)

        # confirm the octal value is converted to an IP
        ip_nodes = get_nodes_by_type(test, 'ip')
        self.assertEqual(len(ip_nodes), 1)
        self.assertEqual('216.58.199.78', ip_nodes[0].label)

        # confirm the path is parsed
        path_nodes = get_nodes_by_type(test, 'url.path')
        self.assertEqual(len(path_nodes), 1)
        self.assertIn('path', path_nodes[0].hover)


if __name__ == '__main__':
    unittest.main()
