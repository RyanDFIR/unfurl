from unfurl.core import Unfurl
import unittest


class TestJWT(unittest.TestCase):

    def test_jwt_simple(self):
        """Parse a sole JWT with few claims.

        Test data source: https://datatracker.ietf.org/doc/html/rfc7519#section-3.1
        """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='eyJ0eXAiOiJKV1QiLA0KICJhbGciOiJIUzI1NiJ9.'
                  'eyJpc3MiOiJqb2UiLA0KICJleHAiOjEzMDA4MTkzODAsDQogImh0dHA6Ly9leGFtcGxlLmNvbS9pc19yb290Ijp0cnVlfQ.'
                  'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk')
        test.parse_queue()

        # confirm the encoded header was separated out
        self.assertEqual('jwt.header.enc', test.nodes[2].data_type)

        # confirm that the encoded header decoded correctly
        self.assertIn('HS256', test.nodes[5].value)

        # confirm that the explanation of the standard "typ" parameter was added
        self.assertIn('declare the media type', test.nodes[12].label)

    def test_jwt_iat_timestamp(self):
        """Parse a sole JWT with an iat field that is parsed as a timestamp.

        Test data source: https://en.wikipedia.org/wiki/JSON_Web_Token#Standard_fields
        """

        test = Unfurl()
        test.add_to_queue(
            data_type='url', key=None,
            value='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.'
                  'eyJsb2dnZWRJbkFzIjoiYWRtaW4iLCJpYXQiOjE0MjI3Nzk2Mzh9.'
                  'gzSraSYS8EXBxLN_oWnFSRgCzcmJmMjLiuyu5CSpyHI')
        test.parse_queue()

        # confirm the encoded payload was separated out
        self.assertEqual('jwt.payload.enc', test.nodes[3].data_type)

        # confirm that the encoded payload decoded correctly
        self.assertIn('admin', test.nodes[6].value)

        # confirm that the claims were parsed as JSON
        self.assertEqual(1422779638, test.nodes[10].value)

        # confirm that the "iat" claim was detected and parsed as a timestamp
        self.assertEqual('2015-02-01 08:33:58+00:00', test.nodes[14].value)

    def test_jwt_as_url_segment(self):
        """Parse a JWT that is part of the URL.

        Test data source: Link in email (send by GovDelivery)
        """

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://lnks.gd/l/eyJhbGciOiJIUzI1NiJ9.eyJidWxsZXRpbl9saW5rX2lkIjoxMDAsInVyaSI6ImJwMjpjbGl'
                  'jayIsImJ1bGxldGluX2lkIjoiMjAyMDA3MjcuMjQ5MTYwOTEiLCJ1cmwiOiJodHRwczovL3ZvdGVyc3RhdHVzLnNvc'
                  'y5jYS5nb3YvP3V0bV9jb250ZW50PSZ1dG1fbWVkaXVtPWVtYWlsJnV0bV9zb3VyY2U9Z292ZGVsaXZlcnkifQ.3oRvU'
                  '4vPXukD9yDoJYKVgmI9FwEtaRgvCIN5Xl9mUc0/s/1113920505/br/81525199996-l')
        test.parse_queue()

        # confirm the JWT was separated out
        self.assertEqual('eyJhbGciOiJIUzI1NiJ9.eyJidWxsZXRpbl9saW5rX2lkIjoxMDAsInVyaSI6ImJwMjpjbGljayIsImJ1bGxl'
                         'dGluX2lkIjoiMjAyMDA3MjcuMjQ5MTYwOTEiLCJ1cmwiOiJodHRwczovL3ZvdGVyc3RhdHVzLnNvcy5jYS5nb'
                         '3YvP3V0bV9jb250ZW50PSZ1dG1fbWVkaXVtPWVtYWlsJnV0bV9zb3VyY2U9Z292ZGVsaXZlcnkifQ.3oRvU4v'
                         'PXukD9yDoJYKVgmI9FwEtaRgvCIN5Xl9mUc0', test.nodes[8].value)

        # confirm that the encoded signature was split off correctly
        self.assertIn('Signature', test.nodes[16].key)

        # confirm that the header was parsed as JSON
        self.assertEqual('alg', test.nodes[19].key)

    def test_dotted_url_path_is_not_a_jwt(self):
        """Don't treat a dotted URL path segment as a JWT.

        Three dot-separated base64url-ish runs are a common shape for URL path
        segments; only a decodable JOSE header makes one a JWT.

        Test data source: ChatGPT ad landing URL (Expedia)
        """

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='https://www.expedia.com/Discovery-Cove-Orlando.d6068683.Vacation-Attraction')
        test.parse_queue()

        # confirm no part of the path was claimed as a JWT
        self.assertEqual(
            [], [node.data_type for node in test.nodes.values()
                 if node.data_type.startswith('jwt.')])

        # confirm the path segment survived intact rather than being split up
        self.assertIn(
            'Discovery-Cove-Orlando.d6068683.Vacation-Attraction',
            [node.value for node in test.nodes.values()])

    def test_non_json_header_is_not_a_jwt(self):
        """Don't treat a value as a JWT when its header decodes to non-JSON.

        The three segments here are all valid base64url of the right length, so
        only the header check rejects them.
        """

        test = Unfurl()
        test.remote_lookups = False
        test.add_to_queue(
            data_type='url', key=None,
            value='bm90LWEtaGVhZGVy.bm90LWEtcGF5bG9hZA.bm90LWEtc2lnbmF0dXJl')
        test.parse_queue()

        self.assertEqual(
            [], [node.data_type for node in test.nodes.values()
                 if node.data_type.startswith('jwt.')])


if __name__ == '__main__':
    unittest.main()
