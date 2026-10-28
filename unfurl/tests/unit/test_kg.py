from unfurl.core import Unfurl
from unittest.mock import patch, MagicMock
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestKnowledgeGraph(unittest.TestCase):

    def test_kg_no_lookups(self):
        """KG parser should not fire when remote_lookups is disabled."""
        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(data_type='proto', key='2', value='/m/050zjwr')
        test.parse_queue()

        # No KG lookup node should be added
        self.assertEqual(len(get_nodes_by_type(test, 'google.knowledge_graph')), 0)

    def test_kg_no_api_key(self):
        """KG parser should not fire when no API key is configured."""
        test = Unfurl()
        test.remote_lookups = True
        test.api_keys = {}
        test.add_to_queue(data_type='proto', key='2', value='/m/050zjwr')
        test.parse_queue()

        # No KG lookup node should be added
        self.assertEqual(len(get_nodes_by_type(test, 'google.knowledge_graph')), 0)

    def test_kg_non_matching_value(self):
        """KG parser should ignore values that don't start with /m/ or /g/."""
        test = Unfurl()
        test.remote_lookups = True
        test.api_keys = {'google_kg': 'fake_key'}
        test.add_to_queue(data_type='proto', key='5', value='MusicGroupToMember')
        test.parse_queue()

        # No KG node added
        kg_nodes = get_nodes_by_type(test, 'google.knowledge_graph')
        self.assertEqual(len(kg_nodes), 0)

    @patch('unfurl.parsers.parse_kg.requests.get')
    def test_kg_lookup_success(self, mock_get):
        """KG parser should resolve a /g/ ID to a name via the API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'itemListElement': [{
                'result': {
                    'name': 'File system forensic analysis',
                    'description': 'Book by Brian Carrier'
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        test = Unfurl()
        test.remote_lookups = True
        test.api_keys = {'google_kg': 'fake_key'}
        test.add_to_queue(data_type='proto', key='2', value='/m/050zjwr')
        test.parse_queue()

        # Should have the input node + the KG result node
        kg_nodes = get_nodes_by_type(test, 'google.knowledge_graph')
        self.assertEqual(len(kg_nodes), 1)
        self.assertIn('File system forensic analysis', kg_nodes[0].value)
        self.assertIn('Book by Brian Carrier', kg_nodes[0].value)

    @patch('unfurl.parsers.parse_kg.requests.get')
    def test_kg_lookup_api_error(self, mock_get):
        """KG parser should handle API errors gracefully."""
        mock_get.side_effect = Exception('API error')

        test = Unfurl()
        test.remote_lookups = True
        test.api_keys = {'google_kg': 'fake_key'}
        test.add_to_queue(data_type='proto', key='2', value='/m/050zjwr')
        test.parse_queue()

        # No KG node added on error
        kg_nodes = get_nodes_by_type(test, 'google.knowledge_graph')
        self.assertEqual(len(kg_nodes), 0)

    @patch('unfurl.parsers.parse_kg.requests.get')
    def test_kg_ignores_paths_that_only_start_like_an_id(self, mock_get):
        """A URL path such as ChatGPT's /g/g-p-.../c/... is not a KG ID and must not be sent to Google."""
        test = Unfurl()
        test.remote_lookups = True
        test.api_keys = {'google_kg': 'fake_key'}
        test.add_to_queue(
            data_type='url', key=None,
            value='https://chatgpt.com/g/g-p-6a00000012348191a1b2c3d4e5f60718/c/'
                  '6a0007d0-1234-83ec-9abc-0123456789ab')
        test.add_to_queue(data_type='proto', key='2', value='/g/g-673b43dbe89081918262b99d6aa366dc')
        test.add_to_queue(data_type='proto', key='2', value='/m/050zjwr/extra')
        test.parse_queue()

        mock_get.assert_not_called()

    @patch('unfurl.parsers.parse_kg.requests.get')
    def test_kg_lookup_accepts_g_ids(self, mock_get):
        """/g/ IDs (with digits and underscores) are still looked up."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'itemListElement': [{'result': {'name': 'Example'}}]}
        mock_get.return_value = mock_response

        test = Unfurl()
        test.remote_lookups = True
        test.api_keys = {'google_kg': 'fake_key'}
        test.add_to_queue(data_type='proto', key='2', value='/g/11c1xn_x4c')
        test.parse_queue()

        self.assertEqual(len(get_nodes_by_type(test, 'google.knowledge_graph')), 1)

    @patch('unfurl.parsers.parse_kg.requests.get')
    def test_kg_lookup_error_does_not_log_the_api_key(self, mock_get):
        """requests puts the full URL, key included, in its exception text; the log must not."""
        import requests
        mock_get.side_effect = requests.ConnectionError(
            'HTTPSConnectionPool: Max retries exceeded with url: /v1/entities:search?ids=%2Fm%2F050zjwr&key=SECRETKEY')

        test = Unfurl()
        test.remote_lookups = True
        test.api_keys = {'google_kg': 'SECRETKEY'}
        test.add_to_queue(data_type='proto', key='2', value='/m/050zjwr')
        with self.assertLogs('unfurl.parsers.parse_kg', level='WARNING') as logs:
            test.parse_queue()

        self.assertNotIn('SECRETKEY', '\n'.join(logs.output))

    @patch('unfurl.parsers.parse_kg.requests.get')
    def test_kg_lookup_empty_response(self, mock_get):
        """KG parser should handle empty API responses."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'itemListElement': []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        test = Unfurl()
        test.remote_lookups = True
        test.api_keys = {'google_kg': 'fake_key'}
        test.add_to_queue(data_type='proto', key='2', value='/m/0dl567')
        test.parse_queue()

        kg_nodes = get_nodes_by_type(test, 'google.knowledge_graph')
        self.assertEqual(len(kg_nodes), 0)


if __name__ == '__main__':
    unittest.main()
