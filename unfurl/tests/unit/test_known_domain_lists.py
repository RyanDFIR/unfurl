from unfurl.core import Unfurl, is_reserved_domain_name
import unittest

DNS_RESOLVER_DESCRIPTOR = 'Domain is on list of known public DNS resolvers expressed as hostname'


def descriptor_values(unfurl_instance):
    return [n.value for n in unfurl_instance.nodes.values() if n.data_type == 'descriptor']


def unfurl_url(url):
    test = Unfurl(remote_lookups=False)
    test.add_to_queue(data_type='url', key=None, value=url)
    test.parse_queue()
    return test


class TestKnownDomainLists(unittest.TestCase):

    def test_example_com_is_not_a_dns_resolver(self):
        """The MISP DNS resolver list contains example.com by mistake; it must not surface."""
        test = unfurl_url('https://example.com/some/path')
        self.assertNotIn(DNS_RESOLVER_DESCRIPTOR, descriptor_values(test))

    def test_real_dns_resolver_still_tagged(self):
        """Removing reserved names must leave genuine resolver entries in place."""
        test = unfurl_url('https://dns.google/dns-query')
        self.assertIn(DNS_RESOLVER_DESCRIPTOR, descriptor_values(test))

    def test_reserved_entries_removed_from_dns_resolver_list(self):
        test = Unfurl(remote_lookups=False)
        resolvers = test.known_domain_lists['List of known public DNS resolvers expressed as hostname'].list
        self.assertNotIn('example.com', resolvers)
        self.assertNotIn('host3.example.com', resolvers)
        self.assertNotIn('node1.local', resolvers)
        self.assertIn('dns.quad9.net', resolvers)

    def test_is_reserved_domain_name(self):
        for name in ('example.com', 'host3.example.com', 'EXAMPLE.ORG.', 'node1.local',
                     'undefined.hostname.localhost', 'foo.test', 'a.invalid', 'example'):
            self.assertTrue(is_reserved_domain_name(name), name)
        for name in ('dns.google', 'notexample.com', 'example.com.au', 'local.com', 'testing.net'):
            self.assertFalse(is_reserved_domain_name(name), name)


if __name__ == '__main__':
    unittest.main()
