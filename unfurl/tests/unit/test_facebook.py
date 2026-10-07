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
        """Modern fbclid (IwZX format) extracts the extn map and AEM hash"""
        u = self._unfurl(
            'https://www.eventbrite.com/e/pitttsburgh-balloon-glow-tickets-882726989187'
            '?fbclid=IwZXh0bgNhZW0CMTAAAR08WkoWnFZTweGu-0q0ewW1Sb7Y8mCHmEWJj1c_tD8LNQ0fBMStjzt_TPo'
            '_aem_Ab2eTPHa-b2DTYiz')
        self.assertTrue(has_node(u, data_type='facebook.fbclid.aem', value='10',
                                 label='AEM Flags: 10 (bit 1 set)'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.aem_value'))

    def test_fbclid_structure(self):
        """The fbclid splits into header, payload, and suffix, and values hang off the part they came from"""
        u = self._unfurl(
            'http://example.com/?fbclid=IwY2xjawRHIChleHRuA2FlbQIxMQBzcnRjBmFwcF9pZBAyMjIwMzkxNzg4MjAwODkyAAEe'
            'SrOIwedpPOsVFYx6K_0LJNBn9kgA89IDYJ4VuJh0BY0MG1HG9gKq1gjYbuU_aem_LrxkLDAS8wyPt0OpHXlIqw')

        def parent_type(**criteria):
            for node in u.nodes.values():
                if all(getattr(node, attr, None) == val for attr, val in criteria.items()):
                    return u.nodes[node.parent_id].data_type
            self.fail(f'no node matching {criteria}')

        self.assertEqual(parent_type(data_type='facebook.fbclid.header', value='Iw'), 'url.query.pair')
        self.assertEqual(parent_type(data_type='facebook.fbclid.platform'), 'facebook.fbclid.header')
        self.assertEqual(parent_type(data_type='fbclid-seconds', key='clck'), 'facebook.fbclid.payload')
        # Map labels show entries readably; the value keeps the raw bytes
        self.assertTrue(has_node(u, data_type='facebook.fbclid.map', label='extn: {aem: 11}'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.map', label='srtc: {app_id: 2220391788200892}'))
        self.assertEqual(parent_type(data_type='facebook.fbclid.map', value='0x0361656d02313100'),
                         'facebook.fbclid.payload')
        self.assertEqual(parent_type(data_type='facebook.fbclid.aem'), 'facebook.fbclid.map')
        self.assertEqual(parent_type(data_type='facebook.fbclid.app_id'), 'facebook.fbclid.map')
        self.assertEqual(parent_type(data_type='facebook.fbclid.trailer'), 'facebook.fbclid.payload')
        self.assertEqual(parent_type(data_type='facebook.fbclid.aem_suffix', value='LrxkLDAS8wyPt0OpHXlIqw'),
                         'url.query.pair')
        self.assertEqual(parent_type(data_type='facebook.fbclid.aem_value',
                                     value='0x2ebc642c3012f30c8fb743a91d7948ab'), 'facebook.fbclid.aem_suffix')

    def test_fbclid_trailer(self):
        """The trailer is shown in full, starting with 0x01 and its version byte"""
        u = self._unfurl(
            'http://example.com/?fbclid=IwY2xjawRHIChleHRuA2FlbQIxMQBzcnRjBmFwcF9pZBAyMjIwMzkxNzg4MjAwODkyAAEe'
            'SrOIwedpPOsVFYx6K_0LJNBn9kgA89IDYJ4VuJh0BY0MG1HG9gKq1gjYbuU')
        trailers = [n for n in u.nodes.values() if n.data_type == 'facebook.fbclid.trailer']
        self.assertEqual(len(trailers), 1)
        self.assertTrue(trailers[0].value.startswith('0x011e'))
        self.assertEqual(len(trailers[0].value), 2 + 46 * 2)

    def test_fbclid_click_timestamp(self):
        """clck is a 4-byte timestamp counted from the fbclid epoch"""
        u = self._unfurl(
            'http://example.com/?fbclid=IwY2xjawRHIChleHRuA2FlbQIxMQBzcnRjBmFwcF9pZBAyMjIwMzkxNzg4MjAwODkyAAEe'
            'SrOIwedpPOsVFYx6K_0LJNBn9kgA89IDYJ4VuJh0BY0MG1HG9gKq1gjYbuU_aem_LrxkLDAS8wyPt0OpHXlIqw')
        self.assertTrue(has_node(u, data_type='fbclid-seconds', key='clck', value=71770152))
        # Converted with the fbclid epoch (not as Unix seconds), showing the math
        converted = [n for n in u.nodes.values() if n.data_type == 'timestamp.fbclid-seconds']
        self.assertEqual(len(converted), 1)
        self.assertEqual(converted[0].value, '2026-04-11 12:38:48+00:00')
        self.assertIn('71,770,152 + 1,704,140,976 = Unix 1,775,911,128',
                      converted[0].hover.replace('<br>', ' '))
        self.assertFalse(has_node(u, data_type='timestamp.epoch-seconds'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.aem', value='11',
                                 label='AEM Flags: 11 (bits 0 and 1 set)'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.app_id', value='WWW (Comet) (2220391788200892)'))

    def test_fbclid_clck_matches_known_click(self):
        """clck from a test click logged at 2026-10-07T03:29:03.255Z decodes to that second"""
        u = self._unfurl(
            'https://www.musicscenemedia.com/?fbclid=IwY2xjawUym89leHRuA2FlbQIxMABwZG9mAWJyaWQRMTJYWnZNM2ZRYUJGM0xq'
            'QmhzcnRjBmFwcF9pZBAyMjIwMzkxNzg4MjAwODkyAAEeXgG_giiwT8vq30UPIKnq7O_OepOAn9a7WOgvlA_TUszkb7nKfsN6uLAzN9Y'
            '_aem_29h9_pUZnYADc_La6huOtA')
        self.assertTrue(has_node(u, data_type='timestamp.fbclid-seconds', value='2026-10-07 03:29:03+00:00'))

    def test_fbclid_brid_and_pdof(self):
        """brid is a length-prefixed string; pdof is a single byte"""
        u = self._unfurl(
            'http://example.com/?fbclid=IwY2xjawT4zZRwZG9mAWV4dG4DYWVtAjEwAGJyaWQRMURtN09aQ0dVTEN0Uk5tNlVzcnRj'
            'BmFwcF9pZA81NDE2Mzk0OTM4ODkwMjUAAR7tNH02HR7WojnkDgBf1VcKHTyncfckbJO-3V3HCAhl5Ir21LFEe9tcd6iXkQ'
            '_aem_HgjQ7W92zhYk2G1O_iW6UQ')
        self.assertTrue(has_node(u, data_type='facebook.fbclid.brid', value='1Dm7OZCGULCtRNm6U'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.pdof', value='1'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.app_id', value='541639493889025'))
        # An unresolved App ID is a plain number; it must not be guessed as a timestamp
        self.assertFalse(any(n.data_type.startswith('timestamp.') for n in u.nodes.values()
                             if u.nodes.get(n.parent_id) is not None
                             and u.nodes[n.parent_id].data_type == 'facebook.fbclid.app_id'))

    def test_fbclid_ad_id(self):
        """adid is an 8-byte number, shown in decimal"""
        u = self._unfurl(
            'http://example.com/?fbclid=IwdHNhZgAAAAJhZGlkAas0Hqd1-ylzcnRjBmFwcF9pZAwyNTYyODEwNDA1NTgAAR7vo5Ae6LUK'
            'CRJDL10zPBQqwU1-S_jC7f3vBmtI2aBNnSjyfDN-UNY8D1BuGQ_wapm_r7RRhv4NQlioqk1FiJSIew_waaem_I1hKYu4gj4jL4vJQtdKpsg')
        self.assertTrue(has_node(u, data_type='facebook.fbclid.adid', value='120247121318640425',
                                 label='Ad-related ID: 120247121318640425'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.tsaf', value=2))
        self.assertFalse(has_node(u, data_type='fbclid-seconds', key='tsaf'))

    def test_fbclid_placeholder_not_decoded(self):
        """A value that doesn't start with a field name produces no fields"""
        u = self._unfurl('http://example.com/?fbclid=fbclid')
        self.assertFalse(any(n.data_type.startswith('facebook.fbclid') for n in u.nodes.values()))

    def test_fbclid_old_format(self):
        """Old fbclid (IwAR format) shows only the platform from its header"""
        u = self._unfurl(
            'https://nyc.streetsblog.org/2020/01/08/nypd-targets-blacks-and-latinos-for-jaywalking-tickets'
            '/?fbclid=IwAR054Z27sI8LALyasatpqO8a0LdH4-PiLp41TZiUrgxq1fUCg7Pyynm7kRA')
        self.assertTrue(has_node(u, data_type='facebook.fbclid.platform', value='Facebook'))
        self.assertTrue(has_node(u, data_type='descriptor', value='Legacy fbclid format'))
        self.assertFalse(has_node(u, data_type='facebook.fbclid.aem'))
        self.assertFalse(has_node(u, data_type='facebook.fbclid.brid'))
        self.assertFalse(has_node(u, data_type='fbclid-seconds'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.trailer'))
        # The payload is already decoded; no protobuf guesses should hang off it
        self.assertFalse(has_node(u, data_type='proto'))

    def test_fbclid_bare(self):
        """An fbclid pasted on its own, without a URL, is decoded the same way"""
        u = self._unfurl(
            'IwY2xjawRHIChleHRuA2FlbQIxMQBzcnRjBmFwcF9pZBAyMjIwMzkxNzg4MjAwODkyAAEeSrOIwedpPOsVFYx6K_0LJNBn9kgA89IDYJ4V'
            'uJh0BY0MG1HG9gKq1gjYbuU_aem_LrxkLDAS8wyPt0OpHXlIqw')
        self.assertTrue(has_node(u, data_type='facebook.fbclid.platform', value='Facebook'))
        self.assertTrue(has_node(u, data_type='timestamp.fbclid-seconds', value='2026-04-11 12:38:48+00:00'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.aem_suffix', value='LrxkLDAS8wyPt0OpHXlIqw'))

    def test_fbclid_bare_legacy(self):
        """A bare legacy fbclid is recognized too"""
        u = self._unfurl('IwAR054Z27sI8LALyasatpqO8a0LdH4-PiLp41TZiUrgxq1fUCg7Pyynm7kRA')
        self.assertTrue(has_node(u, data_type='descriptor', value='Legacy fbclid format'))

    def test_fbclid_bare_lookalike_not_decoded(self):
        """A bare string with an fbclid-like start but no fbclid structure is left alone"""
        for value in ('PAssword', 'IwasHereAndThisIsJustALongStringOfLettersNotAnFbclid',
                      'iwy2xjawrhichlehrua2flbqixmqbzcnrjbmfwcf9pzbaymjiwmzkxnzg4mjawodkyaaeesroiwedp'):
            u = self._unfurl(value)
            self.assertFalse(any(n.data_type.startswith('facebook.fbclid') for n in u.nodes.values()), value)
            self.assertFalse(has_node(u, data_type='descriptor', value='Lowercased fbclid'), value)

    def test_fbclid_instagram_platform(self):
        """A PA header means the fbclid came from Instagram"""
        u = self._unfurl(
            'http://example.com/?fbclid=PAdGRzdgTR25FhZmRrCTRKamV4bFZleWV4dG4DYWVtAjExAHNydGMGYXBwX2lkDzU2NzA2'
            'NzM0MzM1MjQyNwABp2-swMmjW_owTGvJhj6D8LKRlCHENrJ7STncSpaZ1_530pgpsH6ELYWy-78H_aem_onZfzquejZyOjDU0qpPxrw')
        self.assertTrue(has_node(u, data_type='facebook.fbclid.platform', value='Instagram'))
        self.assertTrue(has_node(u, data_type='fbclid-seconds', key='tdsv'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.afdk', value='4JjexlVey'))

    def test_fbclid_lowercased(self):
        """An all-lowercase fbclid is flagged rather than decoded"""
        u = self._unfurl(
            'http://example.com/?fbclid=iwy2xjawrhichlehrua2flbqixmqbzcnrjbmfwcf9pzbaymjiwmzkxnzg4mjawodkyaaeesroiwedp')
        self.assertTrue(has_node(u, data_type='descriptor', value='Lowercased fbclid'))
        self.assertFalse(has_node(u, data_type='facebook.fbclid.platform'))

    def test_fbclid_unknown_field(self):
        """An unknown field name stops parsing and is shown"""
        # The example fbclid with its extn field renamed to "xxxx"
        u = self._unfurl(
            'http://example.com/?fbclid=IwY2xjawRHICh4eHh4A2FlbQIxMQBzcnRjBmFwcF9pZBAyMjIwMzkxNzg4MjAwODkyAAEe'
            'SrOIwedpPOsVFYx6K_0LJNBn9kgA89IDYJ4VuJh0BY0MG1HG9gKq1gjYbuU')
        self.assertTrue(has_node(u, data_type='fbclid-seconds', key='clck'))
        self.assertTrue(has_node(u, data_type='facebook.fbclid.unknown_field', value='xxxx'))
        self.assertFalse(has_node(u, data_type='facebook.fbclid.app_id'))

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
