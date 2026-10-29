from unfurl.core import Unfurl
import unittest

# Every ID below is synthetic: built to the documented layouts, not copied from real URLs.


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


def get_labels(unfurl_instance):
    return [n.label for n in unfurl_instance.nodes.values() if n.label]


def get_hovers(unfurl_instance):
    # Hovers are wrapped with <br> in place of spaces
    return ' '.join(str(n.hover).replace('<br>', ' ') for n in unfurl_instance.nodes.values() if n.hover)


def get_timestamps(unfurl_instance):
    return sorted(n.label for n in unfurl_instance.nodes.values() if n.data_type.startswith('timestamp.'))


def run_unfurl(value):
    test = Unfurl(remote_lookups=False)
    test.add_to_queue(data_type='url', key=None, value=value)
    test.parse_queue()
    return test


class TestChatGPT(unittest.TestCase):

    def test_conversation_id(self):
        """ Test a current conversation URL (UUIDv8, node 1002) """

        # 6a700000 = 2026-08-03 02:42:08 UTC; 1234 >> 2 = 1165 (0.0711 s); 3ea = node 1002
        test = run_unfurl('https://chatgpt.com/c/6a700000-1234-83ea-9abc-0123456789ab')
        labels = get_labels(test)

        self.assertIn('Conversation ID', labels)
        self.assertIn('ChatGPT ID: UUIDv8 with an embedded timestamp', labels)
        self.assertIn('Sub-second: 0.0711 (probable)', labels)
        self.assertIn('Node: 1002', labels)
        self.assertIn('Random: 9abc0123456789ab', labels)
        self.assertIn('2026-08-03 02:42:08', get_timestamps(test)[0])

        # The generic "vendor-specific" UUIDv8 note is replaced by the decoded layout
        self.assertFalse(any('implementation-defined' in label for label in labels))

    def test_share_id(self):
        """ Test a shared conversation URL """

        test = run_unfurl('https://chatgpt.com/share/6a700000-1234-83e8-9abc-0123456789ab')
        labels = get_labels(test)

        self.assertIn('Shared Conversation ID', labels)
        self.assertIn('Node: 1000', labels)
        self.assertIn('2026-08-03 02:42:08', get_timestamps(test)[0])

    def test_nanosecond_era_sub_second(self):
        """ Test an ID from before November 2024, when the sub-second field was nanoseconds >> 16 """

        # 0354 >> 2 = 213; 213 * 65.536 us = 13,959 us
        test = run_unfurl('https://chatgpt.com/c/66d5a000-0354-8005-9abc-0123456789ab')
        labels = get_labels(test)

        self.assertIn('Sub-second: 0.013959', labels)
        self.assertIn('Node: 5', labels)
        self.assertIn('2024-09-02 11:22:40', get_timestamps(test)[0])

    def test_project_and_conversation(self):
        """ Test a conversation inside a project; both IDs carry timestamps """

        # 6a000000 = 2026-05-10 03:48:16; the conversation (6a0007d0) is 2,000 s later on node 1004
        test = run_unfurl(
            'https://chatgpt.com/g/g-p-6a00000012348191a1b2c3d4e5f60718/c/6a0007d0-1234-83ec-9abc-0123456789ab')
        labels = get_labels(test)

        self.assertIn('Project ID: 6a00000012348191a1b2c3d4e5f60718', labels)
        self.assertIn('Conversation ID', labels)
        self.assertIn('Node: 401', labels)
        self.assertIn('Node: 1004', labels)

        timestamps = get_timestamps(test)
        self.assertIn('2026-05-10 03:48:16', timestamps[0])
        self.assertIn('2026-05-10 04:21:36', timestamps[1])

    def test_gpt_id(self):
        """ Test a custom GPT URL with a 32-hex ID and name slug """

        test = run_unfurl('https://chatgpt.com/g/g-6740000012348191a1b2c3d4e5f60718-example-gpt')
        labels = get_labels(test)

        self.assertIn('GPT ID: 6740000012348191a1b2c3d4e5f60718', labels)
        self.assertIn('Name: example-gpt', labels)
        self.assertIn('2024-11-22 03:52:32', get_timestamps(test)[0])

        # The hex inside the GPT ID shouldn't be re-parsed as a UUID or an MD5 hash
        self.assertEqual([], get_nodes_by_type(test, 'uuid'))
        self.assertEqual([], get_nodes_by_type(test, 'hash.md5'))

    def test_gpt_id_on_node_400(self):
        """ Test an early GPT ID on node 400, which GPT IDs used from 2024-11-10 to 2024-11-15 """

        test = run_unfurl('https://chatgpt.com/g/g-6731800012348190a1b2c3d4e5f60718-example-gpt')
        labels = get_labels(test)

        self.assertIn('Node: 400', labels)
        self.assertIn('2024-11-11 03:54:40', get_timestamps(test)[0])
        self.assertIn('used node 400 from 2024-11-10 to 2024-11-15', get_hovers(test))
        self.assertNotIn('is fixed', get_hovers(test))

    def test_legacy_gpt_id(self):
        """ Test an older GPT URL with a base62 ID (no timestamp) """

        test = run_unfurl('https://chat.openai.com/g/g-AbCdEfGh1-example-guide')
        labels = get_labels(test)

        self.assertIn('GPT ID: AbCdEfGh1', labels)
        self.assertIn('Name: example-guide', labels)
        self.assertEqual([], get_timestamps(test))

    def test_snippet_id(self):
        """ Test a shared text snippet URL """

        test = run_unfurl('https://chatgpt.com/s/t_6889ed8012348191a1b2c3d4e5f60718')
        labels = get_labels(test)

        self.assertIn('Shared Snippet ID: 6889ed8012348191a1b2c3d4e5f60718', labels)
        self.assertIn('2025-07-30 10:01:36', get_timestamps(test)[0])

    def test_share_link_prefixes(self):
        """ Test the other /s/ share types (m_, dr_) and bare /s/{hex} """

        test = run_unfurl('https://chatgpt.com/s/m_6a7000aa12348191a1b2c3d4e5f60718')
        self.assertIn('Share Link ID (m_): 6a7000aa12348191a1b2c3d4e5f60718', get_labels(test))
        self.assertIn('2026-08-03 02:44:58', get_timestamps(test)[0])

        test = run_unfurl('https://chatgpt.com/s/dr_6a7000aa12348191a1b2c3d4e5f60718')
        self.assertIn('Share Link ID (dr_): 6a7000aa12348191a1b2c3d4e5f60718', get_labels(test))

        test = run_unfurl('https://chatgpt.com/s/6a7000aa12348191a1b2c3d4e5f60718')
        labels = get_labels(test)
        self.assertIn('Share Link ID', labels)
        self.assertIn('ChatGPT object ID with an embedded timestamp', labels)
        self.assertIn('2026-08-03 02:44:58', get_timestamps(test)[0])
        self.assertEqual([], get_nodes_by_type(test, 'hash.md5'))

    def test_old_uuid4_share(self):
        """ Test a pre-v8 share URL; it is random, but its format still dates it """

        test = run_unfurl('https://chat.openai.com/share/e/0a1b2c3d-1234-4abc-9def-0123456789ab')
        labels = get_labels(test)

        self.assertIn('Shared Conversation ID (workspace)', labels)
        self.assertIn('Older ChatGPT ID format (random UUIDv4)', labels)
        self.assertIn('on or before 2024-11-06', get_hovers(test))
        self.assertEqual([], get_timestamps(test))

    def test_implausible_timestamp_flagged(self):
        """ Test a conversation ID whose embedded time predates the format """

        test = run_unfurl('https://chatgpt.com/c/05000000-1234-8322-9abc-0123456789ab')
        labels = get_labels(test)

        self.assertIn('Timestamp predates this ID format', labels)
        self.assertIn('Node: 802', labels)

    def test_bare_uuid_matching_layout(self):
        """ Test a bare dashed UUID with no URL that matches every fixed part of the ChatGPT layout """

        test = run_unfurl('6a700000-1234-83ea-9abc-0123456789ab')
        labels = get_labels(test)

        self.assertIn('UUIDv8 matching the structure of ChatGPT IDs', labels)
        self.assertIn('Node: 1002', labels)

    def test_bare_undashed_hex_not_claimed(self):
        """ Test that undashed hex outside a ChatGPT URL isn't decoded, even if it fits the layout

        ChatGPT writes conversation and share IDs with dashes. Undashed matches in the wild
        were all hashes (Gravatar avatars, for example).
        """

        test = run_unfurl('https://secure.gravatar.com/avatar/6a7000aa12348010a1b2c3d4e5f60718')
        labels = get_labels(test)

        self.assertFalse(any('ChatGPT' in label for label in labels))
        self.assertEqual([], get_timestamps(test))
        self.assertTrue(any('vendor-specific' in label for label in labels))

    def test_bare_uuid_not_matching_layout(self):
        """ Test that an unrelated UUIDv8 outside a ChatGPT URL is left to the generic UUID parser """

        # RFC 9562 example: 1991 timestamp, and the low sub-second bits aren't zero
        test = run_unfurl('320C3D4D-CC00-875B-8EC9-32D5F69181C0')
        labels = get_labels(test)

        self.assertFalse(any('ChatGPT' in label for label in labels))
        self.assertTrue(any('vendor-specific' in label for label in labels))

    def test_bare_gpt_id(self):
        """ Test a bare GPT ID with no URL around it """

        test = run_unfurl('g-6740000012348191a1b2c3d4e5f60718')
        labels = get_labels(test)

        self.assertIn('GPT ID: 6740000012348191a1b2c3d4e5f60718', labels)
        self.assertIn('2024-11-22 03:52:32', get_timestamps(test)[0])

    def test_bare_gpt_id_implausible_time_not_claimed(self):
        """ Test that a bare g- ID is not claimed when its time is before the format existed """

        test = run_unfurl('g-0500000012348191a1b2c3d4e5f60718')
        self.assertFalse(any('GPT ID' in label for label in get_labels(test)))

    def test_notification_id(self):
        """ Test a notification_id query value: decoded as a notification, not as an MD5 hash """

        test = run_unfurl(
            'https://chatgpt.com/c/6a700000-1234-83ea-9abc-0123456789ab'
            '?notification_id=6a7000aa12348191a1b2c3d4e5f60718&notification_channel_id=image_gen')
        labels = get_labels(test)

        self.assertIn('ChatGPT notification ID with an embedded timestamp', labels)
        self.assertIn('Channel of the notification that opened this link', labels)
        self.assertEqual([], get_nodes_by_type(test, 'hash.md5'))
        self.assertIn('2026-08-03 02:44:58', get_timestamps(test)[1])

    def test_codex_task(self):
        """ Test a Codex cloud task URL; its node comes from the 800-819 pool """

        test = run_unfurl('https://chatgpt.com/codex/tasks/task_e_6840000012348321a1b2c3d4e5f60718')
        labels = get_labels(test)

        self.assertIn('Codex Task ID (task_e_): 6840000012348321a1b2c3d4e5f60718', labels)
        self.assertIn('Node: 801', labels)
        self.assertIn('2025-06-04 08:12:48', get_timestamps(test)[0])
        self.assertIn('Codex cloud task IDs from 2025-06-01', get_hovers(test))

    def test_codex_environment(self):
        """ Test a Codex environment URL (undashed object ID in the path) """

        test = run_unfurl('https://chatgpt.com/codex/settings/environment/6840000012348191a1b2c3d4e5f60718')
        labels = get_labels(test)

        self.assertIn('Codex Environment ID', labels)
        self.assertIn('2025-06-04 08:12:48', get_timestamps(test)[0])
        self.assertEqual([], get_nodes_by_type(test, 'hash.md5'))

    def test_operator(self):
        """ Test Operator conversation and shared video URLs """

        test = run_unfurl('https://operator.chatgpt.com/c/6790000012348191a1b2c3d4e5f60718')
        labels = get_labels(test)
        self.assertIn('Operator Conversation ID', labels)
        self.assertNotIn('Conversation ID', labels)
        self.assertIn('2025-01-21 20:13:52', get_timestamps(test)[0])

        test = run_unfurl('https://operator.chatgpt.com/c/67900000-1234-8191-a1b2-c3d4e5f60718')
        labels = get_labels(test)
        self.assertIn('Operator Conversation ID', labels)
        self.assertNotIn('Conversation ID', labels)

        test = run_unfurl('https://operator.chatgpt.com/v/6790000012348192a1b2c3d4e5f60718')
        labels = get_labels(test)
        self.assertIn('Operator Shared Video ID', labels)
        self.assertIn('Node: 402', labels)

    def test_sora_post(self):
        """ Test a Sora 2 post URL (object layout) """

        test = run_unfurl('https://sora.chatgpt.com/p/s_6a7000aa12348191a1b2c3d4e5f60718')
        self.assertIn('Sora Post ID: 6a7000aa12348191a1b2c3d4e5f60718', get_labels(test))
        self.assertIn('2026-08-03 02:44:58', get_timestamps(test)[0])

    def test_sora_generation_ulid(self):
        """ Test a Sora generation ID, which is a lowercase ULID behind a gen_ prefix """

        test = run_unfurl('https://sora.chatgpt.com/g/gen_01k0000000abcdefghjkmnpqrs')
        labels = get_labels(test)

        self.assertIn('Sora Generation ID: 01k0000000abcdefghjkmnpqrs', labels)
        self.assertIn('Random: abcdefghjkmnpqrs', labels)
        self.assertIn('2025-07-12 18:57:36.768', get_timestamps(test)[0])

    def test_chat_completion_id(self):
        """ Test a chatcmpl- ID in a file name: base62 seconds since 2019-12-20 """

        # BdQPI = 171,936,000 s after 2019-12-20 = 2025-06-01 00:00:00
        test = run_unfurl('https://example.com/uploads/chatcmpl-BdQPIabcdefghijklmnopqrstuvwx.jpg')
        labels = get_labels(test)

        self.assertIn('OpenAI Chat Completions ID', labels)
        self.assertIn('2025-06-01 00:00:00', get_timestamps(test)[0])

    def test_chat_completion_id_other_shapes_ignored(self):
        """ Test that chatcmpl- IDs from other servers (other lengths, UUIDs) aren't dated """

        for value in ('chatcmpl-BdQPIabcdefghijklmnopqrstuv',
                      'chatcmpl-0a1b2c3d-1234-4abc-9def-0123456789ab'):
            test = run_unfurl(value)
            self.assertFalse(any('Completions ID' in label for label in get_labels(test)), value)

    def test_image_file_link(self):
        """ Test a ChatGPT image link: Azure region, zeroed timestamp, version era, SAS times """

        test = run_unfurl(
            'https://sdmntprwestus.oaiusercontent.com/files/00000000-1234-6208-9abc-0123456789ab/raw'
            '?se=2025-05-01T12%3A00%3A00Z&skt=2025-05-01T00%3A00%3A00Z&ske=2025-05-02T00%3A00%3A00Z')
        labels = get_labels(test)

        self.assertIn('Azure storage region: westus', labels)
        self.assertIn('Timestamp field is zeroed', labels)
        self.assertIn('Version 6: probably created no earlier than 2025-04', labels)
        self.assertIn('Node: 520', labels)
        self.assertIn('Link expiry (made about an hour earlier)', labels)
        self.assertIn('Signing key validity start', labels)

        # The generic UUID parser would read the zeroed v6 as a 1582 timestamp
        self.assertEqual([], get_timestamps(test))
        self.assertFalse(any('Version 6 UUID' in label for label in labels))

    def test_image_file_name(self):
        """ Test a downloaded ChatGPT image file name """

        test = run_unfurl('https://example.com/uploads/file_000000001234520fa1b2c3d4e5f60718-1a2b.png')
        labels = get_labels(test)

        self.assertEqual(1, labels.count('ChatGPT image file ID: 00000000-1234-520f-a1b2-c3d4e5f60718'))
        self.assertIn('Version 5: probably created no earlier than 2025-03', labels)
        self.assertEqual([], get_timestamps(test))

    def test_responses_api_ids(self):
        """ Test the 50-hex Responses API form, where the object ID starts at offset 18 """

        test = run_unfurl('resp_0123456789abcdef006a7000aa123487d0a1b2c3d4e5f60718')
        labels = get_labels(test)

        self.assertIn('Node: 2000', labels)
        self.assertIn('Unknown: 0123456789abcdef 00', labels)
        self.assertIn('2026-08-03 02:44:58', get_timestamps(test)[0])

    def test_other_api_ids(self):
        """ Test 48-hex container IDs and 32-hex vector store IDs """

        test = run_unfurl('cntr_6a7000aa12348198a1b2c3d4e5f607180123456789abcdef')
        labels = get_labels(test)
        self.assertIn('Node: 408', labels)
        self.assertIn('Unknown: 0123456789abcdef', labels)
        self.assertIn('2026-08-03 02:44:58', get_timestamps(test)[0])

        test = run_unfurl('vs_6a7000aa12348191a1b2c3d4e5f60718')
        self.assertIn('OpenAI API vector store ID: vs_6a7000aa12348191a1b2c3d4e5f60718', get_labels(test))

    def test_api_id_without_layout_ignored(self):
        """ Test that resp_ IDs failing one layout check each (variant, low bits, time, byte) aren't dated """

        for value in ('resp_6a7000aa12348191c1b2c3d4e5f60718',  # variant nibble c
                      'resp_6a7000aa12358191a1b2c3d4e5f60718',  # low sub-second bits not zero
                      'resp_0500000012348191a1b2c3d4e5f60718',  # time before the format
                      'resp_0123456789abcdef026a7000aa123487d0a1b2c3d4e5f60718'):  # 02, not 00/01
            test = run_unfurl(value)
            self.assertFalse(any('Responses API' in label for label in get_labels(test)), value)

    def test_hash_under_chatgpt_not_decoded(self):
        """ Test that an MD5-like value under chatgpt.com that fails the layout stays a hash """

        test = run_unfurl('https://chatgpt.com/?ref=a123456789ab8def0123456789abcdef')
        labels = get_labels(test)

        self.assertIn('Potential MD5 hash', labels)
        self.assertFalse(any('ChatGPT' in label for label in labels))
        self.assertEqual([], get_timestamps(test))

    def test_future_timestamp_flagged(self):
        """ Test that an embedded time later than now is flagged """

        test = run_unfurl('https://chatgpt.com/c/ffffffff-1234-83ea-9abc-0123456789ab')
        self.assertIn('Timestamp is in the future', get_labels(test))

    def test_nested_in_redirect(self):
        """ Test a ChatGPT URL inside a Google redirect """

        test = run_unfurl('https://www.google.com/url?q=https://chatgpt.com/c/6a700000-1234-83ea-9abc-0123456789ab')
        labels = get_labels(test)

        self.assertIn('Conversation ID', labels)
        self.assertTrue(any('2026-08-03 02:42:08' in t for t in get_timestamps(test)))

    def test_lookalike_host(self):
        """ Test that a lookalike host gets only the cautious bare-UUID label and no ChatGPT path labels """

        test = run_unfurl('https://chatgpt.com.example.net/c/6a700000-1234-83ea-9abc-0123456789ab?q=hello')
        labels = get_labels(test)

        self.assertNotIn('Conversation ID', labels)
        self.assertNotIn('Prefilled prompt', labels)
        self.assertIn('UUIDv8 matching the structure of ChatGPT IDs', labels)

    def test_conversation_label_not_on_sora(self):
        """ Test that /c/ paths on Sora hosts aren't called ChatGPT conversations """

        test = run_unfurl('https://sora.com/c/example')
        self.assertNotIn('Conversation ID', get_labels(test))

    def test_one_segment_path_decoded_once(self):
        """ Test that a path of just /{uuid} is decoded once, not once for the path and once for the segment """

        test = run_unfurl('https://chatgpt.com/6a700000-1234-83ea-9abc-0123456789ab')
        self.assertEqual(1, get_labels(test).count('Node: 1002'))

    def test_typed_label_needs_layout(self):
        """ Test that /s/ and Sora post IDs that fail the layout aren't labelled as timestamped IDs """

        test = run_unfurl('https://chatgpt.com/s/m_0123456789abcdef0123456789abcdef')
        self.assertFalse(any('Share Link ID' in label for label in get_labels(test)))

        test = run_unfurl('https://sora.chatgpt.com/p/s_0123456789abcdef0123456789abcdef')
        self.assertFalse(any('Sora Post ID' in label for label in get_labels(test)))

    def test_bare_gpt_id_wrong_node_not_claimed(self):
        """ Test that a bare g- ID outside the 400-447 node range isn't claimed """

        test = run_unfurl('g-6740000012348321a1b2c3d4e5f60718')
        self.assertFalse(any('GPT ID' in label for label in get_labels(test)))

    def test_base58_file_id(self):
        """ Test a base58 file- ID: decoded to the object layout, but no timestamp shown """

        test = run_unfurl('https://files09.oaiusercontent.com/file-3FPgp69HHCvLYGyMRuk4pF')
        labels = get_labels(test)

        self.assertIn('OpenAI file ID (base58): 1234abcd12348ff8a1b2c3d4e5f60718', labels)
        self.assertEqual([], get_timestamps(test))
        self.assertEqual([], get_nodes_by_type(test, 'uuid'))

    def test_avatar_link_expiry(self):
        """ Test the 100-year expiry on older files.oaiusercontent.com links """

        test = run_unfurl('https://files.oaiusercontent.com/file-AbCdEfGhIjKlMnOpQrStUvWx?se=2123-11-12T04%3A04%3A26Z')
        self.assertIn('Expiry is about 100 years out', get_labels(test))

    def test_query_parameters(self):
        """ Test descriptions of ChatGPT query parameters """

        test = run_unfurl('https://chatgpt.com/c/6a700000-1234-83ea-9abc-0123456789ab'
                          '?src=history_search&historySearchQuery=example+search')
        labels = get_labels(test)
        self.assertIn('Opened from ChatGPT history search', labels)
        self.assertIn('Text typed into ChatGPT history search', labels)

        test = run_unfurl('https://chatgpt.com/?q=Summarize+https%3A%2F%2Fexample.com&hints=search'
                          '&temporary-chat=true&model=gpt-4o')
        labels = get_labels(test)
        self.assertIn('Prefilled prompt', labels)
        self.assertIn('Web search enabled for the prompt', labels)
        self.assertIn('Temporary chat (not saved to history)', labels)
        self.assertIn('Model selected when the link was made', labels)

    def test_query_parameters_only_on_chatgpt(self):
        """ Test that a generic q= parameter on another site isn't called a ChatGPT prompt """

        test = run_unfurl('https://example.com/search?q=example')
        self.assertNotIn('Prefilled prompt', get_labels(test))

    def test_utm_source_chatgpt(self):
        """ Test the referral tag ChatGPT adds to links in its answers """

        test = run_unfurl('https://example.org/article?utm_source=chatgpt.com')
        self.assertIn('Visit came from a link in ChatGPT', get_labels(test))


if __name__ == '__main__':
    unittest.main()
