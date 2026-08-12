from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestBing(unittest.TestCase):

    def test_bing(self):
        """ Test a typical and a unique Bing url """

        # test a Bing search url
        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.bing.com/search?q=digital+forensics&qs=n&form=QBLH&sp=-1'
                  '&pq=digital+forensic&sc=8-16&sk=&cvid=77BF13B59CF84B98B13C067AAA3DB701')
        test.parse_queue()

        # Test query parsing
        query_pairs = {n.key: n.value for n in get_nodes_by_type(test, 'url.query.pair')}
        self.assertEqual('digital forensics', query_pairs['q'])
        self.assertEqual('digital forensic', query_pairs['pq'])

        # is processing finished empty
        self.assertTrue(test.queue.empty())


if __name__ == '__main__':
    unittest.main()
