from unfurl.core import Unfurl
import unittest


class TestMailto(unittest.TestCase):
    def test_mailto(self):
        """ Test a typical mailto URL """

        # test a Bing search url
        test = Unfurl()
        test.add_to_queue(
            data_type="url",
            key=None,
            value="mailto:to@example.com?cc=cc@second.example&bcc=bcc@third.example&subject=Big%20News",
        )
        test.parse_queue()

        self.assertEqual(test.nodes[2].label, "to: to@example.com")

        self.assertEqual(test.nodes[3].label, "cc: cc@second.example")
        self.assertEqual(test.nodes[3].key, "cc")
        self.assertEqual(test.nodes[3].value, "cc@second.example")

        self.assertEqual(test.nodes[4].key, "bcc")
        self.assertEqual(test.nodes[4].value, "bcc@third.example")

        self.assertEqual(test.nodes[5].key, "subject")
        self.assertEqual(test.nodes[5].value, "subject=Big%20News")

        # is processing finished empty
        self.assertTrue(test.queue.empty())


if __name__ == "__main__":
    unittest.main()
