from unfurl.core import Unfurl
import re
import unittest


def hover_text(node):
    """A node's hover with markup removed and whitespace collapsed.

    Hover text is wrapped for display, which inserts <br> at positions that depend on the
    exact wording. Matching against the raw value makes an assertion pass or fail on where
    a line break happened to land, so match against what the reader actually sees.
    """
    return ' '.join(re.sub(r'<[^>]+>', ' ', node.hover or '').split())


def has_node(unfurl_instance, **criteria):
    """Check if a node matching all given criteria exists."""
    for node in unfurl_instance.nodes.values():
        if all(getattr(node, attr, None) == val for attr, val in criteria.items()):
            return True
    return False


class TestFacebook(unittest.TestCase):

    def _unfurl(self, url):
        u = Unfurl(remote_lookups=False)
        u.add_to_queue(data_type='url', key=None, value=url)
        u.parse_queue()
        return u

    def test_redirect_l_php(self):
        """l.facebook.com/l.php params get hover only; URL is still parsed by parse_url."""
        u = self._unfurl(
            'https://l.facebook.com/l.php?u=https%3A%2F%2Fdata.austintexas.gov'
            '%2FGovernment%2FAustin-311-Public-Data%2Fxwdj-i9he&h=NAQFbBxGv')
        # u and h get hover text only from our parser
        for node in u.nodes.values():
            if node.data_type == 'url.query.pair' and node.key == 'h':
                self.assertIn('verification hash', hover_text(node))
                break
        for node in u.nodes.values():
            if node.data_type == 'url.query.pair' and node.key == 'u':
                self.assertIn('destination URL', hover_text(node))
                break

    def test_redirect_lsr_php_hover(self):
        """lsr.php ext param gets hover only"""
        u = self._unfurl(
            'http://l.facebook.com/lsr.php?u=https%3A%2F%2Fdata.cityofnewyork.us'
            '%2FCity-Government%2F1-foot-Digital-Elevation-Model-DEM-%2Fdpc8-z3jc'
            '&ext=1442879836&hash=AcnnZ5k0wBh4ZaGZFmBXimGK')
        for node in u.nodes.values():
            if node.data_type == 'url.query.pair' and node.key == 'ext':
                self.assertIn('timestamp', hover_text(node).lower())
                break

    def test_profile_php_id(self):
        """profile.php?id= extracts user ID"""
        u = self._unfurl('https://www.facebook.com/profile.php?id=100066300129450')
        self.assertTrue(has_node(u, data_type='facebook.user_id', value='100066300129450'))

    def test_profile_username_with_post(self):
        """Vanity URL extracts username and post ID"""
        u = self._unfurl('https://ja-jp.facebook.com/BWIairport/posts/1176825889031565')
        self.assertTrue(has_node(u, data_type='facebook.username', value='BWIairport'))
        self.assertTrue(has_node(u, data_type='facebook.post_id', value='1176825889031565'))

    def test_group_url(self):
        """Group URL extracts group ID"""
        u = self._unfurl('https://www.facebook.com/groups/563959120410492/')
        self.assertTrue(has_node(u, data_type='facebook.group_id', value='563959120410492'))

    def test_story_php(self):
        """story.php extracts story_fbid and user id"""
        u = self._unfurl(
            'https://m.facebook.com/story.php?story_fbid=858120630879651&id=100000451660358')
        self.assertTrue(has_node(u, data_type='facebook.story_fbid', value='858120630879651'))
        self.assertTrue(has_node(u, data_type='facebook.user_id', value='100000451660358'))

    def test_share_with_type(self):
        """Share URL with type prefix (/share/p/ID/)"""
        u = self._unfurl('https://www.facebook.com/share/p/1E8garP5Dy/')
        self.assertTrue(has_node(u, data_type='facebook.share_id', value='1E8garP5Dy'))
        self.assertFalse(has_node(u, data_type='facebook.share_id', value='p'))

    def test_comment_and_notification(self):
        """Post URL with comment_id and notif_t params"""
        u = self._unfurl(
            'https://www.facebook.com/user/posts/123?comment_id=456&notif_t=mentions_reply')
        self.assertTrue(has_node(u, data_type='facebook.comment_id', value='456'))
        self.assertTrue(has_node(u, data_type='facebook.notification_type', value='mentions_reply'))

    def test_event_url(self):
        """Event URL extracts event ID"""
        u = self._unfurl('https://www.facebook.com/events/1234567890/')
        self.assertTrue(has_node(u, data_type='facebook.event_id', value='1234567890'))

    def test_fbclid_modern(self):
        """Modern fbclid (IwZX format) extracts browser ID and app ID"""
        u = self._unfurl(
            'https://www.eventbrite.com/e/pitttsburgh-balloon-glow-tickets-882726989187'
            '?fbclid=IwZXh0bgNhZW0CMTAAAR08WkoWnFZTweGu-0q0ewW1Sb7Y8mCHmEWJj1c_tD8LNQ0fBMStjzt_TPo'
            '_aem_Ab2eTPHa-b2DTYiz')
        self.assertTrue(has_node(u, data_type='facebook.fbclid.extn', value='aem'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.aem_hash'))

    def test_fbclid_old_format(self):
        """Old fbclid (IwAR format) should not produce decoded fields"""
        u = self._unfurl(
            'https://nyc.streetsblog.org/2020/01/08/nypd-targets-blacks-and-latinos-for-jaywalking-tickets'
            '/?fbclid=IwAR054Z27sI8LALyasatpqO8a0LdH4-PiLp41TZiUrgxq1fUCg7Pyynm7kRA')
        self.assertFalse(has_node(u, data_type='facebook.fbclid.extn'))
        self.assertFalse(has_node(u, data_type='facebook.fbclid.brid'))

    def test_mibextid_hover(self):
        """mibextid param gets hover text but no child node"""
        u = self._unfurl(
            'https://www.facebook.com/profile.php?id=100015308826341&mibextid=ZbWKwL')
        self.assertFalse(has_node(u, data_type='facebook.mibextid'))
        for node in u.nodes.values():
            if node.data_type == 'url.query.pair' and node.key == 'mibextid':
                self.assertIn('Mobile', hover_text(node))
                break
        else:
            self.fail('mibextid query pair node not found')

    def test_no_profile_on_static_pages(self):
        """Static pages should not be labeled as profiles"""
        u = self._unfurl('https://www.facebook.com/groups/mygroup/')
        self.assertFalse(has_node(u, data_type='facebook.username', value='groups'))

    def test_stories_url(self):
        """Stories URL extracts story ID"""
        u = self._unfurl('https://www.facebook.com/stories/287202590802695')
        self.assertTrue(has_node(u, data_type='facebook.story_id', value='287202590802695'))


if __name__ == '__main__':
    unittest.main()