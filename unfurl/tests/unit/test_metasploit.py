from unfurl.core import Unfurl
import unittest


class TestMetasploit(unittest.TestCase):

    def test_metasploit_payload_uuid(self):
        """ Test a Metasploit payload UUID url """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://test-example.com/4PGoVGYmx8l6F3sVI4Rc8g1wms758YNVXPczHlPobpJENARS'
                  'uSHb57lFKNndzVSpivRDSi5VH2U-w-pEq_CroLcB--cNbYRroyFuaAgCyMCJDpWbws/')
        test.parse_queue()

        # check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 11)
        self.assertEqual(test.total_nodes, 11)

        # confirm that unique id parsed
        self.assertIn('Unique ID: e0f1a8546626c7c9', test.nodes[7].label)

        # confirm that arch parsed
        self.assertIn('Architecture: X64', test.nodes[9].label)

        # confirm embedded timestamp parsed
        self.assertEqual(1502815973, test.nodes[10].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())
        self.assertEqual(len(test.edges), 0)

    def test_metasploit_checksum_url(self):
        """ Test a Metasploit checksum url """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://test-example.com/WsJH')
        test.parse_queue()

        # check the number of nodes
        self.assertEqual(len(test.nodes.keys()), 7)
        self.assertEqual(test.total_nodes, 7)

        # confirm that unique id parsed
        self.assertIn('Matches Metasploit URL checksum for Windows', test.nodes[7].label)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())

    def test_metasploit_checksum_url_stray_slashes(self):
        """ Test that stray slashes around a Metasploit checksum path don't hide it """

        for url in ('https://test-example.com//WsJH',
                    'https://test-example.com/WsJH/',
                    'https://test-example.com//WsJH//'):
            test = Unfurl()
            test.add_to_queue(data_type='url', key=None, value=url)
            test.parse_queue()

            checksum_nodes = [n for n in get_nodes_by_type(test, 'descriptor')
                              if 'Metasploit URL checksum' in str(n.label)]
            self.assertEqual(1, len(checksum_nodes), msg=f'expected a checksum match for {url}')
            self.assertIn('checksum for Windows', checksum_nodes[0].label)

    def test_metasploit_checksum_not_matched_in_longer_path(self):
        """ Test that the checksum is only matched against the whole path.

        The checksum is 8 bits and 30 of its 256 values map to a platform, so testing
        every 4-character path segment would false-positive on roughly 12% of them.
        """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None, value='https://test-example.com/blog/WsJH/comments')
        test.parse_queue()

        checksum_nodes = [n for n in get_nodes_by_type(test, 'descriptor')
                          if 'Metasploit URL checksum' in str(n.label)]
        self.assertEqual([], checksum_nodes)

    def test_metasploit_payload_uuid_in_sub_path(self):
        """ Test that a payload UUID is found when it isn't the only path segment """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://test-example.com/redirect/4PGoVGYmx8l6F3sVI4Rc8g1wms758YNVXPczHlPobpJENARS'
                  'uSHb57lFKNndzVSpivRDSi5VH2U-w-pEq_CroLcB--cNbYRroyFuaAgCyMCJDpWbws')
        test.parse_queue()

        unique_id_nodes = [n for n in get_nodes_by_type(test, 'descriptor') if n.key == 'Unique ID']
        self.assertEqual(1, len(unique_id_nodes))
        self.assertEqual('e0f1a8546626c7c9', unique_id_nodes[0].value)

        timestamp_nodes = get_nodes_by_type(test, 'epoch-seconds')
        self.assertEqual(1, len(timestamp_nodes))
        self.assertEqual(1502815973, timestamp_nodes[0].value)


if __name__ == '__main__':
    unittest.main()
