from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestFirebase(unittest.TestCase):

    def test_push_id(self):
        """ Test of a bare Firebase Push ID """

        # Example from https://gist.github.com/mikelehen/3596a30bd69384624c11
        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value='-JhLeOlGIEjaIOFHR0xd')
        test.parse_queue()

        push_id_nodes = get_nodes_by_type(test, 'firebase.push_id')
        self.assertEqual(1, len(push_id_nodes))
        self.assertEqual('-JhLeOlGIEjaIOFHR0xd', push_id_nodes[0].value)

        timestamp_nodes = get_nodes_by_type(test, 'timestamp.epoch-milliseconds')
        self.assertEqual(1, len(timestamp_nodes))
        self.assertEqual('2015-02-04 22:15:31.153+00:00', timestamp_nodes[0].value)

        random_nodes = [n for n in get_nodes_by_type(test, 'descriptor') if n.value == 'IEjaIOFHR0xd']
        self.assertEqual(1, len(random_nodes))

        self.assertTrue(test.queue.empty())

    def test_push_id_in_url_path(self):
        """ Test of a Firebase Push ID as a URL path segment """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://example.firebaseio.com/messages/-JhQ76OEK_848CkIFhAq.json')
        test.parse_queue()

        push_id_nodes = get_nodes_by_type(test, 'firebase.push_id')
        self.assertEqual(1, len(push_id_nodes))
        self.assertEqual('-JhQ76OEK_848CkIFhAq', push_id_nodes[0].value)

        timestamp_nodes = get_nodes_by_type(test, 'timestamp.epoch-milliseconds')
        self.assertEqual(1, len(timestamp_nodes))
        self.assertEqual('2015-02-05 19:03:49.071+00:00', timestamp_nodes[0].value)

    def test_push_id_in_query_value(self):
        """ Test of a Firebase Push ID as a query parameter value """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None, value='https://example.com/view?id=-JhQ7APk0UtyRTFO9-TS')
        test.parse_queue()

        push_id_nodes = get_nodes_by_type(test, 'firebase.push_id')
        self.assertEqual(1, len(push_id_nodes))
        self.assertEqual('-JhQ7APk0UtyRTFO9-TS', push_id_nodes[0].value)

    def test_google_ei_not_push_id(self):
        """ Google's 'ei' has the same alphabet and length, and must not be read as a Push ID """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.google.com/search?q=unfurl&ei=-LKnWOCPKMnh0gLv0bhg')
        test.parse_queue()

        self.assertEqual(0, len(get_nodes_by_type(test, 'firebase.push_id')))

    def test_hyphenated_page_names_not_push_id(self):
        """ Hyphenated page names can fit the Push ID shape, but their pieces are words """

        for value in ('-Onze-nieuwe-schepen', '-Patrimoine-naturel-', '-P2000-alarmeringen-',
                      '-Lawrence_S_-Wittner', '-Mesnier------------', '-MMX-133-MHz-66-MHz-'):
            test = Unfurl()
            test.add_to_queue(data_type='url', key=None, value=f'https://example.com/{value}')
            test.parse_queue()
            self.assertEqual(0, len(get_nodes_by_type(test, 'firebase.push_id')), value)

    def test_push_id_with_separators(self):
        """ The random part of a Push ID can contain '-' and '_' """

        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value='https://example.com/-JhLeOlG_q8-DEF9xyZw')
        test.parse_queue()

        self.assertEqual(1, len(get_nodes_by_type(test, 'firebase.push_id')))

    def test_out_of_range_not_push_id(self):
        """ A Push ID shape whose timestamp falls outside 2015 to 2030 is not matched """

        # '-J000000...' decodes to mid-2013, before Push IDs existed.
        test = Unfurl()
        test.add_to_queue(data_type='url', key=None, value='https://example.com/-J000000abcdefghijkl')
        test.parse_queue()

        self.assertEqual(0, len(get_nodes_by_type(test, 'firebase.push_id')))

    def test_wrong_length_not_push_id(self):
        """ 19 and 21 character values are not Push IDs """

        for value in ('-JhLeOlGIEjaIOFHR0x', '-JhLeOlGIEjaIOFHR0xdd'):
            test = Unfurl()
            test.add_to_queue(data_type='url', key=None, value=f'https://example.com/{value}')
            test.parse_queue()
            self.assertEqual(0, len(get_nodes_by_type(test, 'firebase.push_id')), value)


if __name__ == '__main__':
    unittest.main()
