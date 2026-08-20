# Copyright 2020 Google LLC
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

import logging
import requests
import json

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


shortlink_edge = {
    'color': {
        'color': '#E7572C'
    },
    'title': 'URL Shortener Parser',
    'label': '🔗'
}
  

def expand_bitly_url(bitlink_id, api_key):
    # Ref: https://dev.bitly.com/v4/

    r = requests.post(
        'https://api-ssl.bitly.com/v4/expand',
        data=json.dumps({'bitlink_id': f'bit.ly/{bitlink_id.rstrip("/")}'}),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'})

    if r.status_code == 200:
        return r.json()
    else:
        return {}

def parse_linkedin_slink_url(shortcode):
    """Expand a LinkedIn short link by scraping its interstitial page.

    LinkedIn serves an "are you sure you want to leave" page rather than redirecting, so
    the destination has to be read out of the markup. That makes this the most brittle
    expander here: the selector depends on LinkedIn's page structure, which carries no
    compatibility promise and is not served at all to a client LinkedIn declines to
    answer -- a sign-in wall, a rate limit, or a datacenter IP being turned away.

    Every one of those cases has to return empty rather than raise. `run_plugins`
    catches exceptions, so raising here still "worked", but it logged a traceback and
    told an analyst nothing about whether the link failed to expand or was never tried.
    """

    r = requests.get(url=f'https://www.linkedin.com/slink?code={shortcode}', timeout=3)

    if r.status_code != 200:
        # 999 is LinkedIn's own "no thanks" status for clients it declines to serve.
        log.warning(
            f'LinkedIn returned HTTP {r.status_code} for short link "{shortcode}"; '
            f'cannot expand it.')
        return {}

    soup = BeautifulSoup(r.content, 'html.parser')

    # Scoped to <main> on purpose: LinkedIn puts a "learn more" link with the same
    # artdeco-button class elsewhere on the page, and expanding to that would report
    # LinkedIn's own help article as this link's destination.
    link = soup.select_one('main a.artdeco-button')
    if link is None:
        log.warning(
            f'No destination link found on the LinkedIn interstitial for "{shortcode}". '
            f'LinkedIn may have changed the page, or declined to serve it.')
        return {}

    href = link.get('href')
    if not href:
        log.warning(f'LinkedIn interstitial for "{shortcode}" had a link with no href.')
        return {}

    return href


def expand_vdg_url(shortcode):
    # Ref: https://v.gd/apilookupreference.php
    r = requests.get(url='https://v.gd/forward.php', params={'shorturl': shortcode, 'format': 'json'}, timeout=3)
    if r.status_code == 200:
        return r.json().get('url')
    return {}


def expand_url_via_redirect_header(base_url, shortcode):
    r = requests.get(f'{base_url}{shortcode.rstrip("/")}', allow_redirects=False, timeout=3)

    if r.status_code in [301, 302, 303, 307, 308]:
        return r.headers['Location']
    else:
        return {}


def run(unfurl, node):
    if not unfurl.remote_lookups:
        return

    preceding_domain = unfurl.find_preceding_domain(node)

    # LinkedIn has another method of URL shortening that's different from how most others do it; I can
    # refactor this in the future to be more flexible if I find more sites that operate this way, but for now
    # this works.
    if node.data_type == 'url.query.pair' and node.key == 'code':
        if unfurl.preceding_domain_matches(node, 'linkedin.com'):
            expanded_url = parse_linkedin_slink_url(node.value)
            if expanded_url:
                unfurl.add_to_queue(
                    data_type='url', key=None, value=expanded_url,
                    label=f'Expanded URL: {expanded_url}',
                    hover='Expanded URL, retrieved from linkedin.com via "Location" header',
                    parent_id=node.node_id, incoming_edge_config=shortlink_edge)
            return

    # Substack inserts a redirect
    if 'substack.com' == preceding_domain and node.key == 2 and \
            unfurl.check_sibling_nodes(node, data_type='url.path.segment', key=1, value='redirect'):
        expanded_url = expand_url_via_redirect_header('https://substack.com/redirect/', node.value)

        if expanded_url:
            unfurl.add_to_queue(
                data_type='url', key=None, value=expanded_url,
                label=f'Expanded URL: {expanded_url}',
                hover=f'Expanded URL, retrieved from {preceding_domain} via "Location" header',
                parent_id=node.node_id, incoming_edge_config=shortlink_edge)

    if node.data_type != 'url.path':
        return

    short_code = node.value.strip('/')
    if not short_code:
        return

    if 'lnkd.in' == preceding_domain:
        expanded_url = parse_linkedin_slink_url(short_code)
        if expanded_url:
            unfurl.add_to_queue(
                data_type='url', key=None, value=expanded_url,
                label=f'Expanded URL: {expanded_url}',
                hover='Expanded URL, retrieved from linkedin.com via redirect page',
                parent_id=node.node_id, incoming_edge_config=shortlink_edge)
        return

    if 'v.gd' == preceding_domain:
        expanded_url = expand_vdg_url(short_code)
        if expanded_url:
            unfurl.add_to_queue(
                data_type='url', key=None, value=expanded_url,
                label=f'Expanded URL: {expanded_url}',
                hover='Expanded URL, retrieved from v.gd via their API',
                parent_id=node.node_id, incoming_edge_config=shortlink_edge)

    bitly_domains = ['bit.ly', 'bitly.com', 'j.mp']
    if any(unfurl.preceding_domain_matches(node, d) for d in bitly_domains):
        expanded_info = expand_bitly_url(short_code, unfurl.get_api_key('bitly'))

        if not expanded_info:
            return

        node.hover = 'Bitly Short Links can be expanded via the Bitly API to show the ' \
                     '"long" URL and the creation time of the short-link.' \
                     '<a href="https://dev.bitly.com/v4/#operation/expandBitlink" ' \
                     'target="_blank">[ref]</a>'

        if expanded_info['created_at'].endswith('+0000'):
            expanded_info['created_at'] = expanded_info['created_at'][:-5]

        if expanded_info['created_at'][10] == 'T':
            expanded_info['created_at'] = f'{expanded_info["created_at"][:10]} {expanded_info["created_at"][11:]}'

        unfurl.add_to_queue(
            data_type='description', key=None, value=expanded_info['created_at'],
            label=f'Creation Time:\n{expanded_info["created_at"]}',
            hover='Short-link creation time, retrieved from Bitly API',
            parent_id=node.node_id, incoming_edge_config=shortlink_edge)

        unfurl.add_to_queue(
            data_type='url', key=None, value=expanded_info['long_url'],
            label=f'Expanded URL: {expanded_info["long_url"]}', hover='Expanded URL, retrieved from Bitly API',
            parent_id=node.node_id, incoming_edge_config=shortlink_edge)

        return

    redirect_expands = [
        {'domain': 'bit.do', 'base_url': 'https://bit.do/'},
        {'domain': 'buff.ly', 'base_url': 'https://buff.ly/'},
        {'domain': 'cutt.ly', 'base_url': 'https://cutt.ly/'},
        {'domain': 'db.tt', 'base_url': 'https://db.tt/'},
        {'domain': 'dlvr.it', 'base_url': 'https://dlvr.it/'},
        {'domain': 'fb.me', 'base_url': 'https://fb.me/'},
        {'domain': 'flip.it', 'base_url': 'https://flip.it/'},
        {'domain': 'goo.gl', 'base_url': 'https://goo.gl/'},
        {'domain': 'ift.tt', 'base_url': 'https://ift.tt/'},
        {'domain': 'is.gd', 'base_url': 'https://is.gd/'},
        {'domain': 'lc.chat', 'base_url': 'https://lc.chat/'},
        {'domain': 'nyti.ms', 'base_url': 'https://nyti.ms/'},
        {'domain': 'okt.to', 'base_url': 'https://okt.to/'},
        {'domain': 'ow.ly', 'base_url': 'http://ow.ly/'},
        {'domain': 'reut.rs', 'base_url': 'https://reut.rs/'},
        {'domain': 'rb.gy', 'base_url': 'https://rb.gy/'},
        {'domain': 'sansurl.com', 'base_url': 'https://sansurl.com/'},
        {'domain': 's.id', 'base_url': 'https://s.id/'},
        {'domain': 'snip.ly', 'base_url': 'https://snip.ly/'},
        {'domain': 't.co', 'base_url': 'https://t.co/'},
        {'domain': 't.ly', 'base_url': 'https://t.ly/'},
        {'domain': 'tinyurl.com', 'base_url': 'https://tinyurl.com/'},
        {'domain': 'tr.im', 'base_url': 'https://tr.im/'},
        {'domain': 'trib.al', 'base_url': 'https://trib.al/'},
        {'domain': 'urlwee.com', 'base_url': 'https://urlwee.com/'},
        {'domain': 'urlzs.com', 'base_url': 'https://urlzs.com/'}
    ]

    for redirect_expand in redirect_expands:
        if redirect_expand['domain'] == preceding_domain:
            expanded_url = expand_url_via_redirect_header(redirect_expand['base_url'], short_code)
            if expanded_url:
                unfurl.add_to_queue(
                    data_type='url', key=None, value=expanded_url,
                    label=f'Expanded URL: {expanded_url}',
                    hover=f'Expanded URL, retrieved from {redirect_expand["domain"]} via "Location" header',
                    parent_id=node.node_id, incoming_edge_config=shortlink_edge)
            return

    # Guess that any domain + tld that is less than eight characters is a link shortener, and try to
    # expand it via a 301/302 Location header.
    if preceding_domain and len(preceding_domain) < 8:
        expanded_url = expand_url_via_redirect_header(f'https://{preceding_domain}/', short_code)
        if expanded_url:
            unfurl.add_to_queue(
                data_type='url', key=None, value=expanded_url,
                label=f'Expanded URL: {expanded_url}',
                hover=f'Expanded URL, retrieved from {preceding_domain} via "Location" header',
                parent_id=node.node_id, incoming_edge_config=shortlink_edge)
        return

    # Get the list of "known" URL shortener domains from MISP; many of these seem to be deprecated.
    # Try to expand the shortlink via a 301/302 Location header; if the site uses something like a meta refresh,
    # this won't work.
    misp_shortener_domains = unfurl.known_domain_lists['List of known URL Shorteners domains'].list
    if preceding_domain in misp_shortener_domains:
        expanded_url = expand_url_via_redirect_header(f'https://{preceding_domain}/', short_code)
        if expanded_url:
            unfurl.add_to_queue(
                data_type='url', key=None, value=expanded_url,
                label=f'Expanded URL: {expanded_url}',
                hover=f'Expanded URL, retrieved from {preceding_domain} via "Location" header',
                parent_id=node.node_id, incoming_edge_config=shortlink_edge)
