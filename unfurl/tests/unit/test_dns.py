from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestDNS(unittest.TestCase):

    def test_dns(self):
        """ Test a DNS DoH URL """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://dnsserver.example.net/dns-query?dns=AAABAAABAAAAAAAAA3d3dwdleGFtcGxlA2NvbQAAAQAB')
        test.parse_queue()

        # test that the fields parsed correctly, with no repr() quote artifacts
        fields = {n.key: n.value for n in get_nodes_by_type(test, 'dns.section.field')}
        self.assertEqual(fields['qname'], 'www.example.com.')
        self.assertEqual(fields['qtype'], 'A')
        self.assertEqual(fields['opcode'], 'QUERY')

        # is processing finished empty
        self.assertTrue(test.queue.empty())


if __name__ == '__main__':
    unittest.main()
