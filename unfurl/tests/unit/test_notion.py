from unfurl.core import Unfurl
import unittest

# IDs from the 40d91aa6-e786-... workspace were made in the author's own test account. The
# 25b9814e-... image block ID is from a public Common Crawl capture; the rest are synthetic,
# built to the documented layout.


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


def get_labels(unfurl_instance):
    return [n.label for n in unfurl_instance.nodes.values() if n.label]


def get_dates(unfurl_instance):
    return [n.label for n in get_nodes_by_type(unfurl_instance, 'timestamp.notion-days')]


def run_unfurl(value):
    test = Unfurl(remote_lookups=False)
    test.add_to_queue(data_type='url', key=None, value=value)
    test.parse_queue()
    return test


class TestNotion(unittest.TestCase):

    def test_page_id_bare(self):
        """ Test a bare 32-hex page URL: day, workspace, origin and block type """

        # 25b = 603 days after 2024-01-01 = 2025-08-26
        test = run_unfurl('https://www.notion.so/25b9814e5cff804cb328f91fe223cd69')
        labels = get_labels(test)

        self.assertIn('Notion ID: UUIDv8 with an embedded creation date', labels)
        self.assertEqual(['2025-08-26'], get_dates(test))
        self.assertIn('Workspace short ID: 9814e5cff', labels)
        self.assertIn('Minted by: client (browser or app)', labels)
        self.assertTrue(any(str(label).startswith('Record type: Block') for label in labels))

        # One uuid node (the path-and-segment duplicate is gone) and no generic v8 note
        self.assertEqual(1, len(get_nodes_by_type(test, 'uuid')))
        self.assertFalse(any('implementation-defined' in str(label) for label in labels))

    def test_no_md5_for_notion_ids(self):
        """ Bare 32-hex Notion IDs (path and ?v=) are not called potential MD5 hashes on Notion hosts """

        test = run_unfurl(
            'https://app.notion.com/p/example/25b9814e5cff804cb328f91fe223cd69'
            '?v=40d91aa6e78680eeba09000c39e510c8')
        self.assertEqual([], get_nodes_by_type(test, 'hash.md5'))
        self.assertEqual(['2025-08-26', '2026-11-03'], sorted(get_dates(test)))

        # The same lone value on an unrelated host isn't attributed to Notion, so the MD5 note stays
        test = run_unfurl('https://example.com/files/25b9814e5cff804cb328f91fe223cd69')
        self.assertEqual(1, len(get_nodes_by_type(test, 'hash.md5')))

    def test_page_slug_view_and_anchor(self):
        """ Test a published page with a title slug, a ?v= view, a peek mode and a block anchor """

        test = run_unfurl(
            'https://eight-helmet-df9.notion.site/ID-test-page-40d91aa6e7868013accadc1acdce0bf4'
            '?v=40d91aa6e78680eeba09000c39e510c8&pm=s#40d91aa6e78680b499bed74be46ec829')
        labels = get_labels(test)

        self.assertIn('Page title (from the URL): ID-test-page', labels)
        self.assertIn('Database view ID', labels)
        self.assertIn('Peek mode: side peek', labels)
        self.assertIn('Record type: Database view', labels)
        # 40d = 1037 days = 2026-11-03, for the page, the view and the anchored block
        self.assertEqual(['2026-11-03'] * 3, get_dates(test))
        self.assertEqual(3, labels.count('Workspace short ID: 91aa6e786'))

    def test_server_minted(self):
        """ Test an ID with the server origin bit """

        test = run_unfurl('https://www.notion.so/25b9814e5cff81a68282f75cb24607ad')
        self.assertIn('Minted by: Notion server', get_labels(test))
        self.assertEqual(['2025-08-26'], get_dates(test))

    def test_image_url_ids(self):
        """ Test the block, workspace and user IDs in an in-app image URL """

        test = run_unfurl(
            'https://www.notion.so/image/attachment:e938d566-8b86-4b3a-ad1e-cc89438ffd28:note.png'
            '?table=block&id=40d91aa6-e786-80de-943d-f8632634020e&spaceId=a4091aa6-e786-81ed-8c61-000337066246'
            '&userId=40dd872b-594c-817a-8a68-000248c6ba19')
        labels = get_labels(test)

        self.assertIn('Notion workspace ID (no date)', labels)
        self.assertIn('Record type: Workspace', labels)
        self.assertIn('Viewer\'s user ID', labels)
        self.assertIn('Record type: User', labels)
        self.assertIn('Workspace: none (Notion "main" value)', labels)
        # The block and the user are dated; the workspace ID's top bits are random
        self.assertEqual(['2026-11-03', '2026-11-03'], get_dates(test))

    def test_deterministic_id(self):
        """ Test a hash-based (82/83) ID, which has no date """

        test = run_unfurl('https://www.notion.so/7da91aa6e786832b8d33013bcf630b1b')
        labels = get_labels(test)

        self.assertIn('Notion deterministic ID (no date)', labels)
        self.assertIn('Most likely a copy (duplicate or template)', labels)
        self.assertIn('Workspace short ID: 91aa6e786', labels)
        self.assertTrue(any(str(label).startswith('Record type: Block') for label in labels))
        self.assertEqual([], get_dates(test))

    def test_testing_prefix(self):
        """ Test an fff "testing" ID, which has no date """

        test = run_unfurl('https://www.notion.so/abc?v=fff12345678981119e9b000cb9630e5c')
        labels = get_labels(test)

        self.assertIn('Notion "testing" ID (no date)', labels)
        self.assertIn('Record type: Database view', labels)
        self.assertEqual([], get_dates(test))

    def test_uuid_v4(self):
        """ Test an older random UUIDv4 page ID """

        test = run_unfurl('https://www.notion.so/My-Page-3f6c2b1e9a4d4c2f8e1b5d7a9c0b2e4f')
        labels = get_labels(test)

        self.assertIn('Older Notion ID format (random UUIDv4)', labels)
        self.assertEqual([], get_dates(test))

    def test_uuid_v4_not_laravel(self):
        """ A Notion v4 page ID whose first byte is in Laravel's "Ordered UUID" range gets no timestamp """

        test = run_unfurl('https://example.notion.site/My-Page-9a1b2c3d4e5f4a6b8c7d9e0f1a2b3c4d')
        self.assertIn('Older Notion ID format (random UUIDv4)', get_labels(test))
        self.assertEqual([], get_nodes_by_type(test, 'epoch-ten-microseconds'))

        # Off Notion's hosts the generic UUID handling (including the Laravel guess) is unchanged
        test = run_unfurl('https://example.com/item/9a1b2c3d4e5f4a6b8c7d9e0f1a2b3c4d')
        self.assertEqual(1, len(get_nodes_by_type(test, 'epoch-ten-microseconds')))

    def test_all_digit_short_id_not_a_timestamp(self):
        """ A workspace short ID that is all decimal digits is not decoded as a timestamp """

        # 1cd = 461 days after 2024-01-01 = 2025-04-06; short ID 123456789
        test = run_unfurl('https://www.notion.so/1cd12345678980ab8123c456789abcde')
        short_ids = get_nodes_by_type(test, 'notion.short-id')
        self.assertEqual(['123456789'], [n.value for n in short_ids])
        self.assertEqual(['2025-04-06'], get_dates(test))
        timestamps = [n for n in test.nodes.values()
                      if n.data_type.startswith('timestamp.') and n.data_type != 'timestamp.notion-days']
        self.assertEqual([], timestamps)

    def test_future_day(self):
        """ Test an ID whose day is after today (synthetic) """

        # ffe = 4094 days = 2035-03-18
        test = run_unfurl('https://www.notion.so/ffe9814e5cff804cb328f91fe223cd69')
        self.assertIn('Day is in the future', get_labels(test))

    def test_not_decoded_off_notion(self):
        """ The same ID on another site only gets the generic UUIDv8 note """

        test = run_unfurl('https://example.com/25b9814e5cff804cb328f91fe223cd69')
        labels = get_labels(test)

        self.assertEqual([], get_dates(test))
        self.assertTrue(any('implementation-defined' in str(label) for label in labels))
        self.assertFalse(any('Notion' in str(label) for label in labels))

    def test_builder_oopy(self):
        """ Oopy's image proxy carries the Notion block ID in blockId= (synthetic file ID) """

        test = run_unfurl('https://oopy.lazyrockets.com/api/v2/notion/image?src=attachment%3A3f6c2b1e-9a4d-4c2f-'
                          '8e1b-5d7a9c0b2e4f%3Aimage.png&blockId=25b9814e-5cff-804c-b328-f91fe223cd69')
        labels = get_labels(test)

        self.assertIn('Notion ID passed through by Oopy (a Notion site builder)', labels)
        self.assertEqual(['2025-08-26'], get_dates(test))

    def test_builder_wraptas_s3(self):
        """ Wraptas keeps the Notion block ID in its S3 image paths (synthetic site and file names) """

        test = run_unfurl('https://s3.ap-northeast-1.amazonaws.com/wraptas-prod/example/'
                          '25b9814e-5cff-804c-b328-f91fe223cd69/0123456789abcdef0123456789abcdef.png')
        self.assertEqual(['2025-08-26'], get_dates(test))

        # The same ID in another bucket is not decoded
        test = run_unfurl('https://s3.ap-northeast-1.amazonaws.com/other-bucket/example/'
                          '25b9814e-5cff-804c-b328-f91fe223cd69/0123456789abcdef0123456789abcdef.png')
        self.assertEqual([], get_dates(test))

    def test_builder_notioncms_encoded(self):
        """ NotionCMS's proxy-2 form, with encoded slashes after the block ID (synthetic file ID) """

        test = run_unfurl('https://api-prod.usenotioncms.com/v1/proxy-2/block/25b9814e-5cff-804c-b328-f91fe223cd69'
                          '%2F3f6c2b1e-9a4d-4c2f-8e1b-5d7a9c0b2e4f%2Fimage.png')
        self.assertEqual(['2025-08-26'], get_dates(test))

    def test_shared_workspace_off_notion(self):
        """ Two IDs sharing a workspace short ID are decoded on any host """

        test = run_unfurl('https://help.example.com/Getting-Started-25b9814e5cff804cb328f91fe223cd69'
                          '#25b9814e5cff81a68282f75cb24607ad')
        labels = get_labels(test)

        self.assertIn('Page title (from the URL): Getting-Started', labels)
        self.assertEqual(2, labels.count('Matches Notion\'s ID layout; 2 IDs here share a workspace'))
        self.assertEqual(['2025-08-26', '2025-08-26'], get_dates(test))

    def test_lone_id_off_notion_not_decoded(self):
        """ One Notion-shaped ID on another host, or two from different workspaces, is not decoded """

        for url in ('https://help.example.com/Getting-Started-25b9814e5cff804cb328f91fe223cd69',
                    'https://help.example.com/25b9814e5cff804cb328f91fe223cd69#40d91aa6e7868013accadc1acdce0bf4'):
            test = run_unfurl(url)
            self.assertEqual([], get_dates(test), url)
            self.assertFalse(any('Notion' in str(label) for label in get_labels(test)), url)

    def test_deterministic_ids_alone_are_not_evidence(self):
        """ Two hash-based IDs sharing a short ID don't count without a dated one """

        test = run_unfurl('https://help.example.com/7da91aa6e786832b8d33013bcf630b1b'
                          '#26f91aa6e78683ad8d33013bcf630b1b')
        self.assertFalse(any('Notion' in str(label) for label in get_labels(test)))

    def test_invalid_type_code_not_claimed(self):
        """ A v8 ID with a type code Notion doesn't use is not decoded as Notion """

        # Last group starts with 8: neither the block marker nor a table code (top bit set)
        test = run_unfurl('https://www.notion.so/25b9814e5cff804cb328891fe223cd69')
        labels = get_labels(test)

        self.assertEqual([], get_dates(test))
        self.assertTrue(any('implementation-defined' in str(label) for label in labels))


if __name__ == '__main__':
    unittest.main()
