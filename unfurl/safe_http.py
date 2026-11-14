#!/usr/bin/env python3

# Copyright 2026 Ryan Benson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""HTTP requests to hosts named by the input, restricted to the public internet.

Most of Unfurl's remote lookups go to a fixed service (VirusTotal, the Bitly API). A few
go wherever the input says: expanding a short link means requesting the link itself. On
a shared instance that is a request the server makes on a stranger's behalf, so without a
check the input can aim it at the server's own network ("https://127.1/",
"https://vault/") and read the answer out of the graph.

get() is requests.get() with two checks added:

1. Before connecting, the host is resolved and every address it resolves to must be
   public. One private address among several public ones is enough to refuse, since
   there is no saying which the connection would use.

2. After connecting, but before anything is sent, the address actually connected to is
   checked again. Resolving twice (once to check, once to connect) leaves a gap: a DNS
   server under the attacker's control can answer the first lookup with a public address
   and the second with a private one. Checking the connected socket closes that gap,
   because it looks at where the connection really went rather than at a lookup.

The second check does not apply when requests is using a proxy (HTTP_PROXY/HTTPS_PROXY).
The socket is then connected to the proxy, and the proxy does its own name resolution,
so only the first check stands in that setup.
"""

import ipaddress
import socket
import urllib.parse

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

DEFAULT_PORTS = {'http': 80, 'https': 443}


class RefusedDestination(Exception):
    """The request was not made, because it would not have gone to a public address.

    `reason` is a short phrase that reads after "because", for showing to the analyst.
    """

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def is_public_address(address):
    """Whether `address` (a string) is an IP address on the public internet."""

    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False

    # ::ffff:10.0.0.1 is 10.0.0.1 as far as the connection is concerned. Older Pythons
    # judge the IPv6 form on its own and call it global.
    mapped = getattr(ip, 'ipv4_mapped', None)
    if mapped is not None:
        ip = mapped

    return ip.is_global


def looks_like_ip_address(hostname):
    """Whether `hostname` would be read as an IP address rather than looked up as a name.

    Wider than "is a dotted quad": resolvers also accept "127.1", "0x7f.1", "017700000001"
    and a bare "2130706433", all of which are 127.0.0.1. The rule here is the one browsers
    use (WHATWG URL, "ends in a number"): a host whose last label is a number, in decimal
    or 0x hex, is an IPv4 address. Anything with a colon is IPv6.
    """

    if not hostname:
        return False

    if ':' in hostname:
        return True

    last_label = hostname.rstrip('.').rsplit('.', 1)[-1].lower()
    if last_label.isdigit():
        return True
    if last_label.startswith('0x') and all(c in '0123456789abcdef' for c in last_label[2:]):
        return True

    return False


def resolve_host(hostname, port):
    """The addresses `hostname` resolves to, as strings. Raises OSError if it does not."""

    results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    return sorted({result[4][0] for result in results})


def check_destination(url):
    """Raise RefusedDestination unless `url` is an http(s) URL to a public address."""

    parsed = urllib.parse.urlsplit(url)

    if parsed.scheme not in DEFAULT_PORTS:
        raise RefusedDestination(f'"{parsed.scheme}" is not a scheme Unfurl makes requests to')

    hostname = parsed.hostname
    if not hostname:
        raise RefusedDestination('the URL has no host')

    try:
        port = parsed.port or DEFAULT_PORTS[parsed.scheme]
    except ValueError:
        raise RefusedDestination('the URL has an invalid port') from None

    try:
        addresses = resolve_host(hostname, port)
    except (OSError, UnicodeError):
        raise RefusedDestination('the host does not resolve to an address') from None

    if not addresses:
        raise RefusedDestination('the host does not resolve to an address')

    if not all(is_public_address(address) for address in addresses):
        raise RefusedDestination('the host resolves to an address that is not on the public internet')


def _check_connected_socket(sock):
    peer_address = sock.getpeername()[0]
    if not is_public_address(peer_address):
        raise RefusedDestination('the connection went to an address that is not on the public internet')


class _GuardedHTTPConnection(HTTPConnection):
    def _new_conn(self):
        # _new_conn() returns the TCP socket once connected and before anything is
        # written to it (for HTTPS, before the TLS handshake as well).
        sock = super()._new_conn()
        try:
            _check_connected_socket(sock)
        except Exception:
            sock.close()
            raise
        return sock


class _GuardedHTTPSConnection(HTTPSConnection):
    def _new_conn(self):
        sock = super()._new_conn()
        try:
            _check_connected_socket(sock)
        except Exception:
            sock.close()
            raise
        return sock


class _GuardedHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = _GuardedHTTPConnection


class _GuardedHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _GuardedHTTPSConnection


class _GuardedAdapter(HTTPAdapter):
    """A requests adapter whose connections refuse to talk to a non-public address."""

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            'http': _GuardedHTTPConnectionPool,
            'https': _GuardedHTTPSConnectionPool,
        }


def _send(url, **kwargs):
    """Make the request over connections that check where they ended up.

    Kept separate from get() so tests can replace the network without replacing the
    destination check that runs in front of it.
    """

    with requests.Session() as session:
        session.mount('http://', _GuardedAdapter())
        session.mount('https://', _GuardedAdapter())
        return session.get(url, **kwargs)


def get(url, **kwargs):
    """requests.get(), for a URL whose host came from the input.

    Raises RefusedDestination, without sending anything, if the host is not on the
    public internet. Redirects are never followed: each hop would be a new destination
    that nothing has checked, and callers here want the Location header, not the page.
    """

    kwargs['allow_redirects'] = False

    check_destination(url)
    return _send(url, **kwargs)
