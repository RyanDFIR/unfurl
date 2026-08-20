from unfurl.core import Unfurl
import unittest


def has_node(unfurl_instance, **criteria):
    """Check if a node matching all given criteria exists."""
    for node in unfurl_instance.nodes.values():
        if all(getattr(node, attr, None) == val for attr, val in criteria.items()):
            return True
    return False


class TestGitHub(unittest.TestCase):

    def _unfurl(self, url):
        u = Unfurl(remote_lookups=False)
        u.add_to_queue(data_type='url', key=None, value=url)
        u.parse_queue()
        return u

    def test_repo_url(self):
        """Basic owner/repo URL"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl')
        self.assertTrue(has_node(u, data_type='github.owner', value='obsidianforensics'))
        self.assertTrue(has_node(u, data_type='github.repo', value='unfurl'))

    def test_commit_url(self):
        """Commit URL parses the SHA"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/commit/f321e58a413fb31868fb6dacc80cae8e96bad67a')
        self.assertTrue(has_node(u, data_type='github.owner', value='obsidianforensics'))
        self.assertTrue(has_node(u, data_type='github.repo', value='unfurl'))
        self.assertTrue(has_node(u, data_type='github.commit_hash',
                                 value='f321e58a413fb31868fb6dacc80cae8e96bad67a'))

    def test_issue_url(self):
        """Issue URL parses the issue number"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/issues/42')
        self.assertTrue(has_node(u, data_type='github.issue_number', value='42'))

    def test_pr_url(self):
        """Pull request URL parses the PR number"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/pull/456')
        self.assertTrue(has_node(u, data_type='github.pr_number', value='456'))

    def test_blob_url(self):
        """File view URL parses the branch/ref"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/blob/main/unfurl/core.py')
        self.assertTrue(has_node(u, data_type='github.ref', value='main'))

    def test_tree_url(self):
        """Directory view URL parses the branch/ref"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/tree/develop/unfurl/parsers')
        self.assertTrue(has_node(u, data_type='github.ref', value='develop'))

    def test_release_tag(self):
        """Release tag URL"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/releases/tag/v2021.12')
        self.assertTrue(has_node(u, data_type='github.release_tag', value='v2021.12'))

    def test_release_download(self):
        """Release download URL parses tag and asset"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/releases/download/v2021.12/unfurl.zip')
        self.assertTrue(has_node(u, data_type='github.release_tag', value='v2021.12'))
        self.assertTrue(has_node(u, data_type='github.release_asset', value='unfurl.zip'))

    def test_compare_url(self):
        """Compare URL parses the range"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/compare/main...develop')
        self.assertTrue(has_node(u, data_type='github.compare_range', value='main...develop'))

    def test_blame_url(self):
        """Blame URL parses the ref"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/blame/main/unfurl/core.py')
        self.assertTrue(has_node(u, data_type='github.ref', value='main'))

    def test_actions_run(self):
        """Actions run URL"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/actions/runs/12345')
        self.assertTrue(has_node(u, data_type='github.actions_run_id', value='12345'))

    def test_org_url(self):
        """Organization URL"""
        u = self._unfurl('https://github.com/orgs/obsidianforensics/packages')
        self.assertTrue(has_node(u, data_type='github.org', value='obsidianforensics'))

    def test_line_reference_range(self):
        """Fragment with line range"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/blob/main/unfurl/core.py#L10-L20')
        self.assertTrue(has_node(u, data_type='github.line_reference'))

    def test_line_reference_single(self):
        """Fragment with single line"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/blob/main/unfurl/core.py#L42')
        self.assertTrue(has_node(u, data_type='github.line_reference'))

    def test_diff_fragment(self):
        """Fragment with diff reference"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/pull/123/files#diff-abc123def')
        self.assertTrue(has_node(u, data_type='github.diff_reference'))

    def test_issue_comment_fragment(self):
        """Fragment with issue comment ID"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/issues/42#issuecomment-1234567')
        self.assertTrue(has_node(u, data_type='github.issue_comment_id'))

    def test_review_comment_fragment(self):
        """Fragment with review comment ID"""
        u = self._unfurl('https://github.com/obsidianforensics/unfurl/pull/123/files#discussion_r9876543')
        self.assertTrue(has_node(u, data_type='github.review_comment_id'))

    def test_oauth_url(self):
        """OAuth authorize URL parses client_id and scope"""
        u = self._unfurl('https://github.com/login/oauth/authorize?client_id=abc123&scope=repo,user')
        self.assertTrue(has_node(u, data_type='github.oauth_client_id', value='abc123'))
        self.assertTrue(has_node(u, data_type='github.oauth_scope', value='repo,user'))
        # login should NOT be labeled as owner
        self.assertFalse(has_node(u, data_type='github.owner', value='login'))

    def test_oauth_redirect_uri(self):
        """OAuth redirect_uri gets parsed as a URL"""
        u = self._unfurl('https://github.com/login/oauth/authorize?redirect_uri=https://example.com/callback')
        # The redirect URI should be further parsed as a URL
        self.assertTrue(has_node(u, value='example.com'))

    def test_user_profile_no_repo(self):
        """User profile URL should not produce github.repo"""
        u = self._unfurl('https://github.com/obsidianforensics')
        self.assertFalse(has_node(u, data_type='github.repo'))

    def test_notification_ref(self):
        """Notification referrer ID query param"""
        u = self._unfurl('https://github.com/owner/repo/issues/1?notification_referrer_id=NT_abc123')
        self.assertTrue(has_node(u, data_type='github.notification_ref', value='NT_abc123'))


if __name__ == '__main__':
    unittest.main()
