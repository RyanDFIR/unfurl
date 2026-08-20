from unfurl.core import Unfurl
from unfurl.parsers import parse_shortlink
import unittest
from unittest import mock


def build_chain(unfurl_instance, nodes):
    """Create a linear parent->child chain of (data_type, value) pairs.

    Returns the list of node ids, root first.
    """

    node_ids = []
    parent_id = None
    for data_type, value in nodes:
        parent_id = unfurl_instance.create_node(
            data_type=data_type, key=None, value=value, label=None, hover=None,
            parent_id=parent_id)
        node_ids.append(parent_id)
    return node_ids


class TestFindRepeatedAncestor(unittest.TestCase):
    """Unit tests for the cycle check itself, with no parsers involved."""

    def test_no_parent_is_never_a_repeat(self):
        test = Unfurl(remote_lookups=False)
        self.assertIsNone(test.find_repeated_ancestor('url', 'https://example.com', None))

    def test_unique_values_are_not_repeats(self):
        test = Unfurl(remote_lookups=False)
        chain = build_chain(test, [
            ('url', 'https://example.com/a'),
            ('url.path', '/a'),
            ('url', 'https://example.com/b'),
        ])

        self.assertIsNone(test.find_repeated_ancestor('url.path', '/b', chain[-1]))

    def test_a_single_repeat_is_allowed(self):
        """One repeat is a legitimate redirect chain, e.g. /x?a=1 -> /x?a=2."""

        test = Unfurl(remote_lookups=False)
        chain = build_chain(test, [
            ('url', 'https://example.com/x?a=1'),
            ('url.path', '/x'),
            ('url', 'https://example.com/x?a=2'),
        ])

        self.assertIsNone(test.find_repeated_ancestor('url.path', '/x', chain[-1]))

    def test_second_repeat_is_flagged(self):
        test = Unfurl(remote_lookups=False)
        chain = build_chain(test, [
            ('url', 'https://example.com/x?a=1'),
            ('url.path', '/x'),
            ('url', 'https://example.com/x?a=2'),
            ('url.path', '/x'),
            ('url', 'https://example.com/x?a=3'),
        ])

        repeated = test.find_repeated_ancestor('url.path', '/x', chain[-1])
        self.assertIsNotNone(repeated)
        self.assertEqual('url.path', repeated.data_type)
        self.assertEqual('/x', repeated.value)

    def test_same_value_with_different_data_type_is_not_a_repeat(self):
        test = Unfurl(remote_lookups=False)
        chain = build_chain(test, [
            ('url', 'https://example.com/x'),
            ('url.path', '/x'),
            ('url', 'https://example.com/x'),
            ('url.path', '/x'),
        ])

        self.assertIsNone(test.find_repeated_ancestor('string', '/x', chain[-1]))

    def test_threshold_is_configurable(self):
        test = Unfurl(remote_lookups=False)
        test.max_repeated_ancestors = 1
        chain = build_chain(test, [
            ('url', 'https://example.com/x?a=1'),
            ('url.path', '/x'),
        ])

        self.assertIsNotNone(test.find_repeated_ancestor('url.path', '/x', chain[-1]))


class TestRepeatedSiblingsAreKept(unittest.TestCase):
    """Repeats across branches are separate observations, not a loop."""

    def test_mediafire_path_with_two_file_segments(self):
        """mediafire.com/file/{key}/{name}/file has "file" at positions 1 and 4.

        Both are siblings under the same url.path, so neither is an ancestor of
        the other and both must survive.
        """

        test = Unfurl(remote_lookups=False)
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.mediafire.com/file/0000nmedi480w2n/hanyu.rar/file')
        test.parse_queue()

        file_segments = [node for node in test.nodes.values()
                         if node.data_type == 'url.path.segment' and node.value == 'file']
        self.assertEqual(2, len(file_segments))
        self.assertEqual({1, 4}, {node.key for node in file_segments})


class TestShortlinkExpansionLoop(unittest.TestCase):
    """End-to-end regression for the 1drv.ms expansion loop.

    A 1drv.ms link expands to a onedrive.live.com redirect whose "redeem"
    parameter is base64 of the original 1drv.ms URL. Decoding it hands the
    shortlink parser the same link again, so before the cycle check a single
    input produced a 500-node graph (the node_limit) and ~22 requests to
    1drv.ms.

    The redirect target below is a real captured response, so the loop is
    reproduced without making any network request.
    """

    REDIRECT_TARGET = (
        'https://onedrive.live.com/redir?resid=6C474039BCD4FBD8%215769'
        '&migratedtospo=true'
        '&redeem=aHR0cHM6Ly8xZHJ2Lm1zL3UvcyFBdGo3MUx3NVFFZHNyUW5UUkhNai1makdjNDlO')

    def run_with_mocked_redirect(self):
        with mock.patch.object(parse_shortlink, 'expand_url_via_redirect_header',
                               return_value=self.REDIRECT_TARGET) as expand:
            test = Unfurl(remote_lookups=True)
            test.add_to_queue(
                data_type='url', key=None,
                value='https://1drv.ms/u/s!Atj71Lw5QEdsrQnTRHMj-fjGc49N?e=hOB5gO')
            test.parse_queue()
        return test, expand

    def test_graph_does_not_run_away(self):
        test, _ = self.run_with_mocked_redirect()

        # The point of the fix: the graph terminates on its own rather than being
        # cut off by node_limit.
        self.assertLess(test.total_nodes, test.node_limit)
        self.assertTrue(test.queue.empty())

    def test_shortener_is_not_hit_repeatedly(self):
        _, expand = self.run_with_mocked_redirect()

        # Before the fix this was ~22. Two laps are allowed by
        # max_repeated_ancestors; what matters is that it is bounded and small.
        self.assertLessEqual(expand.call_count, 3)

    def test_expansion_still_happens(self):
        """Cycle protection must not stop the first, useful expansion."""

        test, _ = self.run_with_mocked_redirect()

        # Match the parsed hostname exactly rather than looking for the host as a
        # substring of the URL. "onedrive.live.com" appears in a URL that merely mentions
        # it -- https://evil.example/?next=onedrive.live.com would satisfy a substring
        # check -- so the exact comparison is the assertion actually meant here.
        self.assertTrue(any(node.data_type == 'url.hostname' and node.value == 'onedrive.live.com'
                            for node in test.nodes.values()))
        self.assertTrue(any(node.data_type == 'url' and node.value == self.REDIRECT_TARGET
                            for node in test.nodes.values()))
        self.assertTrue(any(node.data_type == 'url.query.pair' and node.key == 'resid'
                            for node in test.nodes.values()))

    def test_terminal_node_is_kept_and_explains_itself(self):
        """The repeated node stays in the graph; only its parsing stops."""

        test, _ = self.run_with_mocked_redirect()

        stopped = [node for node in test.nodes.values()
                   if node.hover and 'stopped expanding' in node.hover]
        self.assertTrue(stopped, 'expected at least one node marked as loop-terminated')

        for node in stopped:
            self.assertEqual([], test.get_successor_nodes(node))

    def test_original_hover_is_preserved(self):
        """The cycle note is appended to the node's own hover, not substituted."""

        test, _ = self.run_with_mocked_redirect()

        stopped = [node for node in test.nodes.values()
                   if node.hover and 'stopped expanding' in node.hover
                   and node.data_type == 'url.path']
        self.assertTrue(stopped)
        self.assertIn('RFC3986', stopped[0].hover)


if __name__ == '__main__':
    unittest.main()
