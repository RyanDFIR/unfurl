from unfurl.core import Unfurl
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


class TestLinkedIn(unittest.TestCase):

    def test_linkedin_profile_id(self):
        """ Test parsing of a LinkedIn Profile ID"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://linkedin.com/in/charolette-pare-93b3a220a')
        test.parse_queue()

        # embedded ID parses correctly
        profile_id_nodes = [
            n for n in get_nodes_by_type(test, 'description')
            if n.key == 'LinkedIn Profile ID']
        self.assertEqual(len(profile_id_nodes), 1)
        self.assertEqual(890781887, profile_id_nodes[0].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())

    def test_linkedin_id(self):
        """ Test parsing of a LinkedIn ID"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.linkedin.com/messaging/thread/6685980502161199104/')
        test.parse_queue()

        # embedded timestamp parses correctly
        epoch_nodes = get_nodes_by_type(test, 'epoch-milliseconds')
        self.assertEqual(len(epoch_nodes), 1)
        self.assertEqual(1594061971226, epoch_nodes[0].value)

        timestamp_nodes = get_nodes_by_type(test, 'timestamp.epoch-milliseconds')
        self.assertEqual(len(timestamp_nodes), 1)
        self.assertIn('2020-07-06 18:59:31.226', timestamp_nodes[0].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())

    def test_linkedin_message_id_v2(self):
        """ Test parsing of a LinkedIn Message ID v2"""

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.linkedin.com/messaging/thread/2-ODEzNDk4YWQtMzA3Mi01NjlmLWE0M2YtY2YwNzFhMjM1YTAzXzAxMw==/')
        test.parse_queue()

        # embedded message ID decodes correctly
        message_id_nodes = [
            n for n in get_nodes_by_type(test, 'description')
            if n.key == 'LinkedIn Message ID']
        self.assertEqual(len(message_id_nodes), 1)
        self.assertEqual('813498ad-3072-569f-a43f-cf071a235a03_013', message_id_nodes[0].value)

        # make sure the queue finished empty
        self.assertTrue(test.queue.empty())


if __name__ == '__main__':
    unittest.main()
