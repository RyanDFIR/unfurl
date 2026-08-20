from unfurl.core import Unfurl
from unfurl.tests.http_mocks import FakeResponse, patch_requests_get
import unittest


def get_nodes_by_type(unfurl_instance, data_type):
    return [n for n in unfurl_instance.nodes.values() if n.data_type == data_type]


# Captured from the real APIs for handle "jay.bsky.team".
RESOLVE_HANDLE_RESPONSE = {'did': 'did:plc:oky5czdrnfjpqslsw2a5iclo'}

# plc.directory returns the full audit log; the parser reads record 0's createdAt. Only
# the fields the parser touches are reproduced, plus the record shape around them.
PLC_AUDIT_LOG_RESPONSE = [
    {
        'did': 'did:plc:oky5czdrnfjpqslsw2a5iclo',
        'operation': {'type': 'create'},
        'cid': 'bafyreiexamplecidvalueforthisrecord',
        'nullified': False,
        'createdAt': '2022-11-17T06:31:40.296Z',
    },
    {
        'did': 'did:plc:oky5czdrnfjpqslsw2a5iclo',
        'operation': {'type': 'plc_operation'},
        'cid': 'bafyreiexamplecidvalueforsecondrec',
        'nullified': False,
        'createdAt': '2023-05-02T18:04:11.001Z',
    },
]

BLUESKY_ROUTES = {
    'resolveHandle': FakeResponse(json=RESOLVE_HANDLE_RESPONSE),
    'plc.directory': FakeResponse(json=PLC_AUDIT_LOG_RESPONSE),
}


class TestBlueskyTids(unittest.TestCase):
    """TID decoding is pure arithmetic on the URL, so these need no network.

    They used to run with lookups enabled, which made two API calls per test that
    nothing asserted on -- the handle resolution and the audit log fetch were incidental
    to what was being tested. TestBlueskyRemoteLookups below covers those on purpose.
    """

    def test_bluesky_post(self):
        """ Test a typical Bluesky post URL """

        test = Unfurl(remote_lookups=False)
        test.add_to_queue(
            data_type='url', key=None,
            value='https://bsky.app/profile/jay.bsky.team/post/3lbd2ebt3wk2r')
        test.parse_queue()

        # confirm that TID was detected
        tid_node = next(n for n in get_nodes_by_type(test, 'epoch-microseconds')
                        if 'timestamp identifiers' in (n.hover or ''))
        self.assertEqual(1732040395098000, tid_node.value)

        # embedded timestamp parses correctly
        ts_node = next(iter(get_nodes_by_type(test, 'timestamp.epoch-microseconds')))
        self.assertEqual('2024-11-19 18:19:55.098000+00:00', ts_node.value)

    def test_bluesky_bare_tid(self):
        """ Test parsing a Bluesky/ATProto TID"""

        test = Unfurl(remote_lookups=False)
        test.add_to_queue(
            data_type='url', key=None,
            value='3laulgolrfz2f')
        test.parse_queue()

        # confirm that TID was detected
        tid_node = next(n for n in get_nodes_by_type(test, 'epoch-microseconds')
                        if 'timestamp identifiers' in (n.hover or ''))

        # confirm that TID was extracted correctly
        self.assertEqual(1731543333133695, tid_node.value)

        # embedded timestamp parses correctly
        ts_node = next(iter(get_nodes_by_type(test, 'timestamp.epoch-microseconds')))
        self.assertEqual('2024-11-14 00:15:33.133695+00:00', ts_node.value)

    def test_no_requests_are_made_without_lookups(self):
        with patch_requests_get(BLUESKY_ROUTES) as calls:
            test = Unfurl(remote_lookups=False)
            test.add_to_queue(
                data_type='url', key=None,
                value='https://bsky.app/profile/jay.bsky.team/post/3lbd2ebt3wk2r')
            test.parse_queue()

        self.assertEqual([], calls)
        self.assertEqual([], get_nodes_by_type(test, 'did.plc'))


class TestBlueskyRemoteLookups(unittest.TestCase):
    """The handle -> DID -> audit log chain, which nothing covered before."""

    def test_handle_resolves_to_did(self):
        with patch_requests_get(BLUESKY_ROUTES):
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(
                data_type='url', key=None,
                value='https://bsky.app/profile/jay.bsky.team/post/3lbd2ebt3wk2r')
            test.parse_queue()

        did_nodes = get_nodes_by_type(test, 'did.plc')
        self.assertEqual(1, len(did_nodes))
        # The parser stores the identifier without the "did:plc:" prefix.
        self.assertEqual('oky5czdrnfjpqslsw2a5iclo', did_nodes[0].value)

    def test_did_creation_time_comes_from_the_audit_log(self):
        with patch_requests_get(BLUESKY_ROUTES):
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(
                data_type='url', key=None,
                value='https://bsky.app/profile/jay.bsky.team/post/3lbd2ebt3wk2r')
            test.parse_queue()

        created = [n for n in get_nodes_by_type(test, 'timestamp.iso8601') if n.key == 'createdAt']
        self.assertEqual(1, len(created))
        # Record 0, not any later record -- the first entry is the account's creation.
        self.assertEqual('2022-11-17T06:31:40.296Z', created[0].value)

    def test_bare_did_is_looked_up_without_a_handle(self):
        """A did:plc string on its own should still reach the audit log."""

        with patch_requests_get(BLUESKY_ROUTES):
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(
                data_type='url', key=None, value='did:plc:oky5czdrnfjpqslsw2a5iclo')
            test.parse_queue()

        created = [n for n in get_nodes_by_type(test, 'timestamp.iso8601') if n.key == 'createdAt']
        self.assertEqual(1, len(created))
        self.assertEqual('2022-11-17T06:31:40.296Z', created[0].value)

    def test_failed_handle_resolution_is_survivable(self):
        """bsky.social answering with an error must not produce a DID node."""

        routes = dict(BLUESKY_ROUTES)
        routes['resolveHandle'] = FakeResponse(status_code=400, json={'error': 'InvalidRequest'})

        with patch_requests_get(routes):
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(
                data_type='url', key=None,
                value='https://bsky.app/profile/jay.bsky.team/post/3lbd2ebt3wk2r')
            test.parse_queue()

        self.assertEqual([], get_nodes_by_type(test, 'did.plc'))

        # The TID timestamp is independent of the lookup and must still be there.
        ts_node = next(iter(get_nodes_by_type(test, 'timestamp.epoch-microseconds')))
        self.assertEqual('2024-11-19 18:19:55.098000+00:00', ts_node.value)


if __name__ == '__main__':
    unittest.main()
