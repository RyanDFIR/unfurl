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

"""Fake HTTP responses, so parsers that reach out to a service can be tested offline.

Tests that make real requests are testing two different things at once: our code, and
whether some third party still behaves the way we assumed. Those deserve to fail
separately -- a LinkedIn markup change is not a regression in Unfurl, and a Unfurl
regression should not need LinkedIn to be reachable to show up. The mocks here cover the
first; `unfurl/tests/live/` covers the second.

Responses are modeled on captured real ones. Where a detail of the real response matters
to the code under test, it is reproduced rather than idealized -- see the note on header
case in `FakeResponse`.
"""

import json as json_module
from unittest import mock

import requests
from requests.structures import CaseInsensitiveDict


class FakeResponse:
    """A stand-in for requests.Response covering what Unfurl's parsers touch.

    Headers use requests' own CaseInsensitiveDict on purpose. Real shorteners send
    a lowercase "location" header, while `expand_url_via_redirect_header` reads
    `r.headers['Location']`. That only works because requests is case-insensitive, so a
    mock built on a plain dict would either hide the dependency or fail for a reason the
    real world never produces.
    """

    def __init__(self, status_code=200, headers=None, content=b'', json=None, url=''):
        self.status_code = status_code
        self.headers = CaseInsensitiveDict(headers or {})
        self.url = url

        if json is not None:
            content = json_module.dumps(json).encode('utf-8')
        if isinstance(content, str):
            content = content.encode('utf-8')

        self.content = content
        self._json = json

    @property
    def text(self):
        return self.content.decode('utf-8', errors='replace')

    def json(self):
        if self._json is not None:
            return self._json
        return json_module.loads(self.text)


def redirect(location, status_code=301):
    """A shortener's redirect response."""

    return FakeResponse(status_code=status_code, headers={'location': location})


def routed_get(routes, default=None):
    """Build a requests.get replacement that answers based on the requested URL.

    `routes` maps a substring of the URL to a FakeResponse. Anything unmatched gets
    `default`, which is a 404 unless given -- an unexpected outbound call should look
    like a miss rather than silently receiving another route's answer.

    Returns (replacement_callable, calls_list); calls_list records the URLs requested.
    """

    calls = []

    def fake_get(url, *args, **kwargs):
        calls.append(url)
        for fragment, response in routes.items():
            if fragment in url:
                return response
        return default if default is not None else FakeResponse(status_code=404)

    return fake_get, calls


def patch_requests_get(routes, default=None):
    """Context manager patching requests.get with a routed fake.

    Yields the list of requested URLs, so a test can assert on what was called -- and,
    just as usefully, on what was not.
    """

    fake_get, calls = routed_get(routes, default=default)

    class _Patch:
        def __enter__(self):
            self._patcher = mock.patch.object(requests, 'get', side_effect=fake_get)
            self._patcher.start()
            return calls

        def __exit__(self, *exc_info):
            self._patcher.stop()
            return False

    return _Patch()
