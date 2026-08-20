from unfurl.core import Unfurl
from unfurl.parsers import parse_gmail
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


def parse_url(url):
    test = Unfurl()
    test.add_to_queue(data_type='url', key=None, value=url)
    test.parse_queue()
    return test


class TestGmailTokenDecoding(unittest.TestCase):
    """Tests of the new-style Gmail web token decoder.

    The decoder returns the payload exactly as decoded. It must not invent a "thread-"
    keyword: no observed token contains one, and adding it hides every reference after
    the first in a multi-draft compose token.

    Vectors marked "captured" came from real Gmail URLs. Constructed vectors were built by
    encoding a payload in a shape those captures confirm.
    """

    def test_decode_captured_view_token(self):
        """Ground truth: decodes to a thread whose timestamp is when the message arrived."""
        decoded = parse_gmail.decode_new_style_token('FMfcgzQbffcMwhxlgVgQNtfsQngqqzMQ')
        self.assertEqual(decoded, 'f:1834473457053461654')

    def test_decode_captured_one_draft_compose_token(self):
        """A compose token holds the draft's thread and message IDs, joined by "+".

        Both are client-assigned, so both are negative.
        """
        decoded = parse_gmail.decode_new_style_token(
            'GTvVlcSKjDPsKDHWvqZCTKmmgKbhqgbxKlfhjNjPKtqMrDXmxjvJDlprDkjgXFpGnCmFpRcRHHcQf')
        self.assertEqual(decoded, 'a:r-7217035772637032756+msg-a:r-8051540162134737577')

    def test_decode_captured_two_draft_compose_token(self):
        """Two drafts open at once: one "thread+message" group per draft, comma-separated.

        Only the first group would carry a keyword the canonical ID regex can match, so a
        decoder that prepends "thread-" reports 3 of these 4 IDs.
        """
        decoded = parse_gmail.decode_new_style_token(
            'FNSXwzPZgrkmzfHgRnCzjkTXdpRNKmnKBVFdrmGRHlNdnkNkTjrpsQKxZvgKDPZTQmJbhwPnkvvFmrzb'
            'XSLKcjQLPWGSKfZBjJHffNGvgskvzkQRQZxPffLdvVFLfMtHvrqgsnDgDSRsjdHGxhrrzCSrFRjV')
        self.assertEqual(
            decoded,
            'a:r-2185233177584497971+msg-a:r-4574659139915391891,'
            'a:r-3186403482298088288+msg-a:r-3812694900594247056')

    def test_no_captured_token_contains_a_thread_keyword(self):
        """Guards the fix: "thread-" is canonical Gmail notation, but not what a token holds."""
        for token in ('FMfcgzQbffcMwhxlgVgQNtfsQngqqzMQ',
                      'GTvVlcSKjDPsKDHWvqZCTKmmgKbhqgbxKlfhjNjPKtqMrDXmxjvJDlprDkjgXFpGnCmFpRcRHHcQf'):
            with self.subTest(token=token[:12]):
                self.assertNotIn('thread', parse_gmail.decode_new_style_token(token))

    def test_token_outside_alphabet_returns_none(self):
        """Vowels and digits are not in the 40-character alphabet.

        run() gates on new_token_re before calling this, but the function is public and
        must not raise on input that never passed that gate.
        """
        self.assertIsNone(parse_gmail.decode_new_style_token('FMfcgzQbffcMwhxlgVgQNtfsQngqqzMa'))
        self.assertIsNone(parse_gmail.decode_new_style_token('FMfcgzQbffcMwhxlgVgQNtfsQngqqzM1'))


class TestDecodedPayloadParsing(unittest.TestCase):
    """A payload names the style and ID for a thread, and adds "msg-" for a message."""

    def test_view_payload_is_a_thread(self):
        self.assertEqual(
            parse_gmail.parse_decoded_payload('f:1834473457053461654'),
            ['thread-f:1834473457053461654'])

    def test_draft_payload_yields_thread_then_message(self):
        self.assertEqual(
            parse_gmail.parse_decoded_payload('a:r-72+msg-a:r-80'),
            ['thread-a:r-72', 'msg-a:r-80'])

    def test_every_draft_is_reported(self):
        self.assertEqual(
            parse_gmail.parse_decoded_payload('a:r-1+msg-a:r-2,a:r-3+msg-a:r-4,a:r-5+msg-a:r-6'),
            ['thread-a:r-1', 'msg-a:r-2', 'thread-a:r-3',
             'msg-a:r-4', 'thread-a:r-5', 'msg-a:r-6'])

    def test_unrecognized_payload_yields_nothing(self):
        """All or nothing: emitting the half we recognize is how an ID went missing before."""
        for payload in ('f:123+something-else', 'not an id at all', 'x:123', ''):
            with self.subTest(payload=payload):
                self.assertEqual(parse_gmail.parse_decoded_payload(payload), [])


class TestGmailUrls(unittest.TestCase):

    def test_legacy_view_url(self):
        """Legacy hex thread ID in the URL fragment.

        Expected values are from Metaspike's published research:
        https://www.metaspike.com/dates-gmail-message-id-thread-id-timestamps/
        """
        test = parse_url('https://mail.google.com/mail/u/0/#inbox/172ed79b0337c14f')

        gmail_ids = get_nodes_by_type(test, 'gmail.id')
        self.assertEqual(len(gmail_ids), 1)
        self.assertEqual(gmail_ids[0].value, 'thread-f:1670509572574921039')

        # A hex ID is split in hex, so its timestamp is decoded from the hex form.
        timestamps = get_nodes_by_type(test, 'timestamp.epoch-milliseconds-hex')
        self.assertEqual(len(timestamps), 1)
        self.assertEqual(timestamps[0].value, '2020-06-25 21:54:34.675+00:00')

    def test_legacy_th_query_param(self):
        test = parse_url('https://mail.google.com/mail/?ui=2&view=btop&th=172ed79b0337c14f')

        gmail_ids = get_nodes_by_type(test, 'gmail.id')
        self.assertEqual(len(gmail_ids), 1)
        self.assertEqual(gmail_ids[0].value, 'thread-f:1670509572574921039')

    def test_new_style_view_url(self):
        """Constructed "f:<id>" token; the FMfcg prefix falls out of the real payload shape."""
        test = parse_url(
            'https://mail.google.com/mail/u/0/#inbox/FMfcgxwJWXcxTwrHDtwgrlxcmNBnhwXw')

        gmail_ids = get_nodes_by_type(test, 'gmail.id')
        self.assertEqual(len(gmail_ids), 1)
        self.assertEqual(gmail_ids[0].value, 'thread-f:1670936980932986545')

        timestamps = get_nodes_by_type(test, 'timestamp.epoch-milliseconds')
        self.assertEqual(len(timestamps), 1)
        self.assertEqual(timestamps[0].value, '2020-06-30 15:08:03.049+00:00')

    def test_new_style_search_url(self):
        test = parse_url(
            'https://mail.google.com/mail/u/0/#search/from%3Asomeone/FMfcgxwJWXcxTwrHDtwgrlxcmNBnhwXw')

        gmail_ids = get_nodes_by_type(test, 'gmail.id')
        self.assertEqual(len(gmail_ids), 1)
        self.assertEqual(gmail_ids[0].value, 'thread-f:1670936980932986545')

    def test_raw_decoded_payload_gets_its_own_node(self):
        """The canonical ID is derived, so the form the URL actually held stays on the graph."""
        test = parse_url(
            'https://mail.google.com/mail/u/0/#inbox/FMfcgxwJWXcxTwrHDtwgrlxcmNBnhwXw')

        payloads = get_nodes_by_type(test, 'gmail.token.payload')
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0].value, 'f:1670936980932986545')

    def test_legacy_hex_id_gets_its_own_node(self):
        """The hex-to-decimal conversion is a step, so both forms are on the graph."""
        test = parse_url('https://mail.google.com/mail/u/0/#inbox/172ed79b0337c14f')

        hex_ids = get_nodes_by_type(test, 'gmail.id.hex')
        self.assertEqual(len(hex_ids), 1)
        self.assertEqual(hex_ids[0].value, '172ed79b0337c14f')

    def test_hex_id_splits_into_timestamp_and_low_bits(self):
        """In hex the split is just "drop the last 5 digits", and the halves reassemble.

        The timestamp half is handed to parse_timestamp still in hex, rather than being
        converted inside the Gmail parser.
        """
        test = parse_url('https://mail.google.com/mail/u/0/#inbox/172ed79b0337c14f')

        hex_timestamps = get_nodes_by_type(test, 'epoch-hex-milliseconds')
        self.assertEqual(len(hex_timestamps), 1)
        self.assertEqual(hex_timestamps[0].value, '172ed79b033')

        labels = [n.label for n in get_nodes_by_type(test, 'descriptor')]
        self.assertIn('Low 20 bits: 7c14f', labels)

        # The two halves are the original ID, in order and with nothing left over.
        self.assertEqual('172ed79b033' + '7c14f', '172ed79b0337c14f')

    def test_hex_id_is_not_also_split_in_decimal(self):
        """The split is shown once, in the representation the URL used."""
        test = parse_url('https://mail.google.com/mail/u/0/#inbox/172ed79b0337c14f')
        self.assertEqual(get_nodes_by_type(test, 'epoch-milliseconds'), [])

    def test_client_assigned_compose_url(self):
        """A captured single-draft compose token: thread and message, both client-assigned."""
        test = parse_url(
            'https://mail.google.com/mail/u/0/#inbox?compose='
            'GTvVlcSKjDPsKDHWvqZCTKmmgKbhqgbxKlfhjNjPKtqMrDXmxjvJDlprDkjgXFpGnCmFpRcRHHcQf')

        gmail_ids = sorted(n.value for n in get_nodes_by_type(test, 'gmail.id'))
        self.assertEqual(
            gmail_ids,
            ['msg-a:r-8051540162134737577', 'thread-a:r-7217035772637032756'])

        # Client-assigned ("-a:") IDs do not embed a timestamp
        self.assertEqual(get_nodes_by_type(test, 'timestamp.epoch-milliseconds'), [])
        descriptions = [n for n in get_nodes_by_type(test, 'description')
                        if n.label == 'Client-assigned Message ID']
        self.assertEqual(len(descriptions), 1)

    def test_two_draft_compose_url_reports_all_four_ids(self):
        """Regression: this captured token reported 3 of its 4 IDs.

        Prepending "thread-" to the payload gave the first draft's thread reference a
        keyword the canonical ID regex could match, while every later draft's went
        unmatched and was silently dropped.
        """
        test = parse_url(
            'https://mail.google.com/mail/u/0/#drafts?compose='
            'FNSXwzPZgrkmzfHgRnCzjkTXdpRNKmnKBVFdrmGRHlNdnkNkTjrpsQKxZvgKDPZTQmJbhwPnkvvFmrzb'
            'XSLKcjQLPWGSKfZBjJHffNGvgskvzkQRQZxPffLdvVFLfMtHvrqgsnDgDSRsjdHGxhrrzCSrFRjV')

        gmail_ids = sorted(n.value for n in get_nodes_by_type(test, 'gmail.id'))
        self.assertEqual(
            gmail_ids,
            ['msg-a:r-3812694900594247056', 'msg-a:r-4574659139915391891',
             'thread-a:r-2185233177584497971', 'thread-a:r-3186403482298088288'])

        # Every reference is client-assigned, so none carries a timestamp.
        self.assertEqual(get_nodes_by_type(test, 'timestamp.epoch-milliseconds'), [])
        labels = [n.label for n in get_nodes_by_type(test, 'description')]
        self.assertIn('Client-assigned Thread ID', labels)
        self.assertIn('Client-assigned Message ID', labels)

    def test_three_draft_compose_token_generalizes(self):
        """Constructed from the captured two-draft shape, to confirm the loop is not fixed at two."""
        test = parse_url(
            'https://mail.google.com/mail/u/0/#inbox?compose='
            'CbTKJnxzVpPjBdStgkjkwvwlWQLvXGchHJSxMsFRlptrshBvCWFQhfQTCVcVzNgTkrSzJLxZrWqtrwXz'
            'PKcCtRmvGbxfTKnsltgkwQhMJbtxTNfJWgZMBRlfldFBxCbtgfDcJBsRzGdnbkGdQXPpLgnKfNmDFvQw'
            'rzGGGBjVVswVGgZczGkHNMBJplmNHLqpCLbpDxQHCCsDpnLjcWTwqqjdLQFXmcvDlLbDFwllPq')

        gmail_ids = get_nodes_by_type(test, 'gmail.id')
        self.assertEqual(len(gmail_ids), 6)

    def test_legacy_compose_list(self):
        """Multiple drafts open at once produce a comma-separated compose token list."""
        test = parse_url(
            'https://mail.google.com/mail/u/0/#inbox?compose=172ed79b0337c14f%2Cffff3432161af8b')

        gmail_ids = sorted(n.value for n in get_nodes_by_type(test, 'gmail.id'))
        self.assertEqual(gmail_ids, ['msg-f:1152907499278544779', 'msg-f:1670509572574921039'])

        # Both are hex IDs, so both are split and decoded in hex. The 15-digit ID drops the
        # same 5 digits as the 16-digit one, leaving a shorter timestamp.
        hex_timestamps = sorted(n.value for n in get_nodes_by_type(test, 'epoch-hex-milliseconds'))
        self.assertEqual(hex_timestamps, ['172ed79b033', 'ffff343216'])

        timestamps = sorted(
            n.value for n in get_nodes_by_type(test, 'timestamp.epoch-milliseconds-hex'))
        self.assertEqual(timestamps, ['2004-11-03 16:11:11.254+00:00', '2020-06-25 21:54:34.675+00:00'])

    def test_permmsgid_query_param(self):
        test = parse_url(
            'https://mail.google.com/mail/u/0/?ui=2&view=pt&search=all&permmsgid=msg-f%3A1670936980932986545')

        gmail_ids = get_nodes_by_type(test, 'gmail.id')
        self.assertEqual(len(gmail_ids), 1)
        self.assertEqual(gmail_ids[0].value, 'msg-f:1670936980932986545')

        timestamps = get_nodes_by_type(test, 'timestamp.epoch-milliseconds')
        self.assertEqual(len(timestamps), 1)
        self.assertEqual(timestamps[0].value, '2020-06-30 15:08:03.049+00:00')

    def test_real_captured_url(self):
        test = parse_url('https://mail.google.com/mail/u/0/#inbox/FMfcgzQbffcMwhxlgVgQNtfsQngqqzMQ')

        gmail_ids = get_nodes_by_type(test, 'gmail.id')
        self.assertEqual(len(gmail_ids), 1)
        self.assertEqual(gmail_ids[0].value, 'thread-f:1834473457053461654')

        timestamps = get_nodes_by_type(test, 'timestamp.epoch-milliseconds')
        self.assertEqual(len(timestamps), 1)
        self.assertEqual(timestamps[0].value, '2025-06-09 17:30:20.120+00:00')

    def test_projector_marks_an_opened_attachment(self):
        """"projector=1" distinguishes viewing an attachment from opening the message."""
        test = parse_url(
            'https://mail.google.com/mail/u/0/#inbox/FMfcgzQbffcMwhxlgVgQNtfsQngqqzMQ?projector=1')

        labels = [n.label for n in get_nodes_by_type(test, 'descriptor')]
        self.assertIn('Attachment preview was open', labels)

        # The thread token in the same fragment still parses.
        gmail_ids = get_nodes_by_type(test, 'gmail.id')
        self.assertEqual(len(gmail_ids), 1)
        self.assertEqual(gmail_ids[0].value, 'thread-f:1834473457053461654')

    def test_thread_url_without_projector_has_no_attachment_node(self):
        test = parse_url('https://mail.google.com/mail/u/0/#inbox/FMfcgzQbffcMwhxlgVgQNtfsQngqqzMQ')
        labels = [n.label for n in get_nodes_by_type(test, 'descriptor')]
        self.assertNotIn('Attachment preview was open', labels)

    def test_non_gmail_domain_is_ignored(self):
        test = parse_url('https://example.com/mail/u/0/#inbox/172ed79b0337c14f')
        self.assertEqual(get_nodes_by_type(test, 'gmail.id'), [])

    def test_implausible_hex_id_is_ignored(self):
        # 15 hex digits, but the embedded timestamp would be pre-Gmail (1970s)
        test = parse_url('https://mail.google.com/mail/u/0/#inbox/00000432161af8b')
        self.assertEqual(get_nodes_by_type(test, 'gmail.id'), [])


class TestGmailIdStyles(unittest.TestCase):
    """The style letter ("-f:" vs "-a:"), not the "r" prefix, says who assigned an ID."""

    def parse_id(self, gmail_id):
        test = Unfurl()
        test.add_to_queue(data_type='gmail.id', key=None, value=gmail_id)
        test.parse_queue()
        return test

    def test_client_assigned_id_is_labeled(self):
        test = self.parse_id('msg-a:r1234567890123456789')
        labels = [n.label for n in get_nodes_by_type(test, 'description')]
        self.assertIn('Client-assigned Message ID', labels)

    def test_server_assigned_id_with_r_prefix_is_not_called_client_assigned(self):
        """An "-f:" ID is server-assigned regardless of an "r" prefix on the digits.

        No timestamp can be read from that shape, but mislabeling the ID's origin would
        be an affirmatively wrong forensic claim.
        """
        test = self.parse_id('thread-f:r1670936980932986545')
        labels = [n.label for n in get_nodes_by_type(test, 'description')]
        self.assertNotIn('Client-assigned Thread ID', labels)
        self.assertEqual(get_nodes_by_type(test, 'timestamp.epoch-milliseconds'), [])


if __name__ == '__main__':
    unittest.main()
