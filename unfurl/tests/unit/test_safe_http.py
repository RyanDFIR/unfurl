import http.server
import os
import threading
import unittest
from unittest import mock

from unfurl import safe_http
from unfurl.tests.http_mocks import PUBLIC_ADDRESS, FakeResponse


class TestIsPublicAddress(unittest.TestCase):

    def test_public_addresses(self):
        for address in ('93.184.216.34', '8.8.8.8', '2606:4700:4700::1111'):
            with self.subTest(address=address):
                self.assertTrue(safe_http.is_public_address(address))

    def test_non_public_addresses(self):
        cases = {
            '127.0.0.1': 'loopback',
            '10.0.0.5': 'private',
            '172.16.0.1': 'private',
            '192.168.1.1': 'private',
            '169.254.169.254': 'link-local (cloud metadata)',
            '100.64.0.1': 'carrier-grade NAT',
            '0.0.0.0': 'unspecified',
            '::1': 'IPv6 loopback',
            'fe80::1': 'IPv6 link-local',
            'fd00::1': 'IPv6 unique local',
            '::ffff:10.0.0.1': 'private IPv4 written as IPv6',
            '::ffff:127.0.0.1': 'loopback IPv4 written as IPv6',
        }
        for address, kind in cases.items():
            with self.subTest(address=address, kind=kind):
                self.assertFalse(safe_http.is_public_address(address))

    def test_something_that_is_not_an_address(self):
        self.assertFalse(safe_http.is_public_address('example.com'))
        self.assertFalse(safe_http.is_public_address(''))


class TestLooksLikeIpAddress(unittest.TestCase):

    def test_forms_a_resolver_reads_as_an_address(self):
        # All of these but the last two are 127.0.0.1 or 10.0.0.1 to a resolver.
        for hostname in ('127.0.0.1', '127.1', '10.1', '0x7f.1', '0x7f000001', '2130706433',
                         '017700000001', '0', '1.2.3.4', '1.2.3.4.', '::1', 'fe80::1'):
            with self.subTest(hostname=hostname):
                self.assertTrue(safe_http.looks_like_ip_address(hostname))

    def test_names(self):
        for hostname in ('t.co', 'a.io', 'vault', '1drv.ms', '3.ly', 'x0.at', 'example.com', ''):
            with self.subTest(hostname=hostname):
                self.assertFalse(safe_http.looks_like_ip_address(hostname))


class TestCheckDestination(unittest.TestCase):

    def check(self, url, addresses):
        with mock.patch.object(safe_http, 'resolve_host', return_value=addresses):
            safe_http.check_destination(url)

    def test_public_host_is_allowed(self):
        self.check('https://t.co/abc', [PUBLIC_ADDRESS])

    def test_private_host_is_refused(self):
        with self.assertRaises(safe_http.RefusedDestination) as refused:
            self.check('https://intranet.example/abc', ['10.0.0.5'])
        self.assertIn('not on the public internet', refused.exception.reason)

    def test_one_private_address_among_public_ones_is_enough_to_refuse(self):
        """There is no saying which address the connection would pick."""

        with self.assertRaises(safe_http.RefusedDestination):
            self.check('https://mixed.example/abc', [PUBLIC_ADDRESS, '127.0.0.1'])

    def test_host_that_does_not_resolve_is_refused(self):
        with mock.patch.object(safe_http, 'resolve_host', side_effect=OSError('no such host')):
            with self.assertRaises(safe_http.RefusedDestination) as refused:
                safe_http.check_destination('https://nx.example/abc')
        self.assertIn('does not resolve', refused.exception.reason)

    def test_host_that_resolves_to_nothing_is_refused(self):
        with self.assertRaises(safe_http.RefusedDestination):
            self.check('https://empty.example/abc', [])

    def test_only_http_and_https_are_requested(self):
        for url in ('ftp://example.com/x', 'file:///etc/passwd', 'gopher://example.com/', 'example.com/x'):
            with self.subTest(url=url):
                with self.assertRaises(safe_http.RefusedDestination):
                    self.check(url, [PUBLIC_ADDRESS])

    def test_url_without_a_host_is_refused(self):
        with self.assertRaises(safe_http.RefusedDestination):
            self.check('https:///abc', [PUBLIC_ADDRESS])

    def test_the_port_in_the_url_is_the_one_resolved(self):
        with mock.patch.object(safe_http, 'resolve_host', return_value=[PUBLIC_ADDRESS]) as resolve:
            safe_http.check_destination('https://t.co:8443/abc')
            safe_http.check_destination('http://ow.ly/abc')
        self.assertEqual([mock.call('t.co', 8443), mock.call('ow.ly', 80)], resolve.call_args_list)


class TestGet(unittest.TestCase):

    def test_nothing_is_sent_when_the_destination_is_refused(self):
        with mock.patch.object(safe_http, 'resolve_host', return_value=['192.168.1.1']), \
                mock.patch.object(safe_http, '_send') as send:
            with self.assertRaises(safe_http.RefusedDestination):
                safe_http.get('https://router.example/admin', timeout=3)
        send.assert_not_called()

    def test_redirects_are_never_followed(self):
        """A redirect would lead to a second destination that nothing has checked."""

        with mock.patch.object(safe_http, 'resolve_host', return_value=[PUBLIC_ADDRESS]), \
                mock.patch.object(safe_http, '_send', return_value=FakeResponse()) as send:
            safe_http.get('https://t.co/abc', timeout=3, allow_redirects=True)
        send.assert_called_once_with('https://t.co/abc', timeout=3, allow_redirects=False)


class _CountingHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests_seen += 1
        self.send_response(200)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def log_message(self, *args):
        pass


class TestConnectedAddressIsChecked(unittest.TestCase):
    """The check on the socket itself, against a real server on loopback.

    This is the case the lookup-time check cannot catch: DNS says the host is public,
    and the connection goes somewhere private anyway (a DNS server that gives a
    different answer the second time it is asked). It is reproduced here by telling the
    lookup-time check that 127.0.0.1 is public, and then really connecting to it.
    """

    def setUp(self):
        self.server = http.server.HTTPServer(('127.0.0.1', 0), _CountingHandler)
        self.server.requests_seen = 0
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        # Keep a proxy configured on the machine running the tests out of the way; the
        # point is to connect straight to the loopback server.
        no_proxy = mock.patch.dict(os.environ, {'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'})
        no_proxy.start()
        self.addCleanup(no_proxy.stop)

        dns_says_public = mock.patch.object(safe_http, 'resolve_host', return_value=[PUBLIC_ADDRESS])
        dns_says_public.start()
        self.addCleanup(dns_says_public.stop)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_connection_to_a_private_address_is_dropped_before_anything_is_sent(self):
        for scheme in ('http', 'https'):
            with self.subTest(scheme=scheme):
                with self.assertRaises(safe_http.RefusedDestination) as refused:
                    safe_http.get(f'{scheme}://127.0.0.1:{self.port}/secret', timeout=3)
                self.assertIn('connection went to an address', refused.exception.reason)

        self.assertEqual(0, self.server.requests_seen,
                         msg='the server must not have received a request')

    def test_the_same_request_goes_through_when_the_address_is_acceptable(self):
        """Control for the test above: the refusal comes from the address check.

        Without this, a transport that was simply broken would pass that test too.
        """

        with mock.patch.object(safe_http, 'is_public_address', return_value=True):
            response = safe_http.get(f'http://127.0.0.1:{self.port}/ok', timeout=3)

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, self.server.requests_seen)


if __name__ == '__main__':
    unittest.main()
