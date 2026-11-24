from unfurl.core import Unfurl
import unittest

# Share IDs below are taken from public Wayback Machine captures of kimi.com share links,
# except where marked synthetic.


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


def get_labels(unfurl_instance):
    return [n.label for n in unfurl_instance.nodes.values() if n.label]


def get_timestamps(unfurl_instance):
    return sorted(n.label for n in unfurl_instance.nodes.values() if n.data_type.startswith('timestamp.'))


def run_unfurl(value):
    test = Unfurl(remote_lookups=False)
    test.add_to_queue(data_type='url', key=None, value=value)
    test.parse_queue()
    return test


class TestKimi(unittest.TestCase):

    def test_uuid_share_id(self):
        """ Test a current UUIDv8 share link (Unix ms in the first 11 hex chars) """

        test = run_unfurl('https://www.kimi.com/share/19a6cdb5-fe52-83ce-8000-00009fe6eafd')
        labels = get_labels(test)

        self.assertIn('Kimi share ID', labels)
        self.assertIn('Kimi share ID: UUIDv8 with an embedded timestamp', labels)
        self.assertIn('Unknown: 3ce', labels)
        self.assertIn('Random: 9fe6eafd', labels)
        self.assertEqual(['2025-11-10 08:21:47.621+00:00'], get_timestamps(test))
        self.assertFalse(any('implementation-defined' in str(label) for label in labels))

    def test_uuid_share_id_with_locale(self):
        """ Test the /share/en/ form """

        test = run_unfurl('https://www.kimi.com/share/en/19a6cdb5-fe52-83ce-8000-00009fe6eafd')
        self.assertEqual(['2025-11-10 08:21:47.621+00:00'], get_timestamps(test))

    def test_random_tail_not_redecoded(self):
        """ The random tail is not re-read as a hex timestamp, Cisco Type 7 text or a protobuf """

        # Synthetic: the tail 6205d501 is also a plausible hex Unix time (2022-02-11)
        test = run_unfurl('https://www.kimi.com/share/19a6cdb5-fe52-83ce-8000-00006205d501')
        self.assertIn('Random: 6205d501', get_labels(test))
        self.assertEqual(['2025-11-10 08:21:47.621+00:00'], get_timestamps(test))
        self.assertEqual([], get_nodes_by_type(test, 'text'))
        self.assertFalse(any(n.data_type.startswith('proto') for n in test.nodes.values()))

        # Synthetic: the tail b350e355 decodes as base64 to printable junk
        test = run_unfurl('https://www.kimi.com/share/19a6cdb5-fe52-83ce-8000-0000b350e355')
        self.assertIn('Random: b350e355', get_labels(test))
        self.assertEqual([], get_nodes_by_type(test, 'string'))

    def test_xid_share_id(self):
        """ Test an older xid share link """

        test = run_unfurl('https://kimi.moonshot.cn/share/co3q59pkqq4leau1fgug')
        labels = get_labels(test)

        self.assertIn('Kimi share ID (xid)', labels)
        self.assertIn('Machine ID: 34d689', labels)
        self.assertIn('Process ID: 22315', labels)  # 0x572b
        self.assertEqual(['2024-03-30 05:27:03+00:00'], get_timestamps(test))

    def test_wrong_layout_not_claimed(self):
        """ A UUIDv8 without Kimi's fixed bits only gets the generic note (synthetic) """

        test = run_unfurl('https://www.kimi.com/share/19a6cdb5-fe53-83ce-8000-00009fe6eafd')
        labels = get_labels(test)

        self.assertNotIn('Kimi share ID: UUIDv8 with an embedded timestamp', labels)
        self.assertTrue(any('implementation-defined' in str(label) for label in labels))

    def test_not_decoded_outside_share_path(self):
        """ The same ID outside /share/ or off Kimi's hosts is not decoded """

        for url in ('https://www.kimi.com/chat/19a6cdb5-fe52-83ce-8000-00009fe6eafd',
                    'https://example.com/share/19a6cdb5-fe52-83ce-8000-00009fe6eafd',
                    'https://example.com/share/co3q59pkqq4leau1fgug'):
            test = run_unfurl(url)
            self.assertFalse(any('Kimi' in str(label) for label in get_labels(test)), url)

    def test_xid_bad_padding(self):
        """ A 20-char value whose padding bits aren't zero is not an xid (synthetic) """

        test = run_unfurl('https://www.kimi.com/share/co3q59pkqq4leau1fguh')
        self.assertNotIn('Kimi share ID (xid)', get_labels(test))


if __name__ == '__main__':
    unittest.main()
