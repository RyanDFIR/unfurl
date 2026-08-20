from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestMacAddr(unittest.TestCase):

    def test_mac_addr(self):
        """ Test a MAC address with colons"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='00:B0:D0:63:C2:26')
        test.parse_queue()

        # confirm the MAC address is parsed
        mac_nodes = get_nodes_by_type(test, 'mac-address')
        self.assertEqual(1, len(mac_nodes))
        self.assertIn('MAC address', mac_nodes[0].label)

        # confirm the vendor is parsed
        vendor_nodes = get_nodes_by_type(test, 'mac-address.vendor')
        self.assertEqual(1, len(vendor_nodes))
        self.assertIn('Dell', vendor_nodes[0].label)

    def test_mac_addr_bare(self):
        """ Test a bare MAC address (no delimiters)"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='00B0D063C226')
        test.parse_queue()

        # confirm the MAC address is parsed
        mac_nodes = get_nodes_by_type(test, 'mac-address')
        self.assertEqual(1, len(mac_nodes))
        self.assertIn('MAC address', mac_nodes[0].label)

        # confirm the vendor is parsed
        vendor_nodes = get_nodes_by_type(test, 'mac-address.vendor')
        self.assertEqual(1, len(vendor_nodes))
        self.assertIn('Dell', vendor_nodes[0].label)

    def test_mac_addr_dashes(self):
        """ Test a MAC address with dashes"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='00-B0-D0-63-C2-26')
        test.parse_queue()

        # confirm the MAC address is parsed
        mac_nodes = get_nodes_by_type(test, 'mac-address')
        self.assertEqual(1, len(mac_nodes))
        self.assertIn('MAC address', mac_nodes[0].label)

        # confirm the vendor is parsed
        vendor_nodes = get_nodes_by_type(test, 'mac-address.vendor')
        self.assertEqual(1, len(vendor_nodes))
        self.assertIn('Dell', vendor_nodes[0].label)


if __name__ == '__main__':
    unittest.main()
