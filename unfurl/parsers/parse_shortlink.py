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


# Shorteners expanded by requesting https://{domain}/{code} and reading the Location
# header, listed by name because nothing else will find them.
#
# Every domain here is popular enough to appear in a top-sites list, which means the
# length guess at the end of run() deliberately skips it, and none of them are in MISP's
# shortener list. Without this table they would silently stop being expanded -- which is
# exactly what happened when the popularity check was first added, and is why the list
# was audited into existence rather than guessed at.
#
# Verified 2026-08-20 against the top-sites union and the MISP list. When adding one,
# check both: if MISP already has it, it does not belong here.
additional_shortener_domains = frozenset({
    '0rz.tw',      # Taiwanese public shortener
    'aka.ms',      # Microsoft
    'amzn.eu',     # Amazon (EU counterpart to amzn.to)
    'arcg.is',     # Esri ArcGIS
    'bbc.in',      # BBC
    'chng.it',     # Change.org
    'cnn.io',      # CNN
    'dai.ly',      # Dailymotion
    'dwz.cn',      # Baidu
    'ffm.to',      # FeatureFM smart links
    'flic.kr',     # Flickr
    'g.page',      # Google Business Profile
    'geni.us',     # GeniusLink
    'gg.gg',       # public shortener
    'href.li',     # referrer-stripping redirector
    'hubs.ly',     # HubSpot
    'icio.us',     # del.icio.us
    'igg.me',      # Indiegogo
    'kck.st',      # Kickstarter
    'lin.ee',      # LINE
    'lnk.to',      # music smart links
    'lnks.gd',     # GovDelivery
    'm.me',        # Messenger; resolves a vanity name to the numeric page ID
    'on.aws',      # Amazon Web Services
    'ouo.io',      # ad-gated public shortener
    'pca.st',      # Pocket Casts
    'pin.it',      # Pinterest
    'prf.hn',      # Partnerize affiliate redirector
    'pxf.io',      # Impact affiliate redirector
    'rdcu.be',     # Springer Nature SharedIt
    'redd.it',     # Reddit
    'sjv.io',      # Sovrn affiliate redirector
    't.cn',        # Sina Weibo
    'tidd.ly',     # Awin affiliate redirector
    'tru.am',      # TrueAnthem
    'url.cn',      # Tencent / QQ
    'vk.cc',       # VK
    'wa.link',     # WhatsApp; resolves to api.whatsapp.com with the phone number
    'wapo.st',     # Washington Post
    'we.tl',       # WeTransfer
})


# Short domains checked and deliberately left out, so the question is not reopened from
# scratch. Behavior verified 2026-08-20 by requesting real captured URLs.
#
# Redirect, but reveal nothing:
#   line.me   deep links (/R/@handle, /R/app/...) 302 to "/" -- the site root
#   zalo.me   301 to the same path with a trailing slash; pure canonicalization
#   lu.ma     301 to luma.com with the path preserved; a domain rebrand, not a lookup
#   solo.to   200; a link-in-bio page, not a redirect at all
#
# Not a redirector at all:
#   trkn.us   carries its destination in the path as plaintext
#             (/click/process/partner=...;redirect=https://example.com). Nothing needs
#             fetching; this wants a parser, not an expander, and would be better for it
#             -- no request means nothing is tipped off and dead links still resolve.


# Redirectors whose token lives in the query string. These get the full URL passed
# through untouched, via expand_full_url_via_redirect_header(); the generic expander
# rebuilds the URL from the domain and path, dropping the token, and the tokenless URL
# answers 200 -- so it expands to nothing at all.
#
# Deliberately a short, evidenced list rather than a guess. Requesting one of these sends
# the tracking token back to its issuer, which for a per-recipient email token is a
# signal that the recipient engaged with the message -- during a phishing investigation
# that tells the sender their target clicked. Only add a domain after confirming both
# that it needs the full URL and that expanding it is worth that cost.
query_token_redirectors = {
    # Verified 2026-08-20: r20.rs6.net/tn.jsp?f=<token> -> files.constantcontact.com/...
    'rs6.net': 'Constant Contact',
}


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


REDIRECT_STATUS_CODES = (301, 302, 303, 307, 308)


def _location_header_from(url):
    """GET `url` without following redirects and return its Location header, or {}."""

    r = requests.get(url, allow_redirects=False, timeout=3)

    if r.status_code in REDIRECT_STATUS_CODES:
        return r.headers['Location']
    else:
        return {}


def expand_url_via_redirect_header(base_url, shortcode):
    """Expand a path-based short link, rebuilding the URL from a domain and a code.

    The generic, last-ditch expander: it assumes the whole link is
    {registered domain} + {path}, which is true of nearly every URL shortener and is
    what lets Unfurl guess about domains it has never seen.

    Use expand_full_url_via_redirect_header() when that assumption does not hold.
    """

    return _location_header_from(f'{base_url}{shortcode.rstrip("/")}')


def expand_full_url_via_redirect_header(url):
    """Expand a redirector by requesting the URL exactly as it was given.

    Some redirectors keep their token in the query string -- Constant Contact's is
    r20.rs6.net/tn.jsp?f=<token>. The generic expander rebuilds a URL from the domain and
    path, which drops the query, and a tokenless r20.rs6.net/tn.jsp answers 200: no
    Location header, so nothing is expanded and the analyst is told nothing. (A URL whose
    token has been truncated in transit does 302, to r20.rs6.net/error.jsp -- which would
    be reported as the destination.) Either way the token has to survive, so these need
    the original URL passed through untouched.

    Only for domains known to work this way. Sending a full URL somewhere is not
    something to do on a guess: the query string is exactly where per-recipient tracking
    tokens live, so the request can tell the sender their target engaged with the
    message. See the note on query_token_redirectors.
    """

    return _location_header_from(url)


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

    # Known shorteners handled by name. Anything listed here is expanded regardless of
    # how popular the domain is, which matters for a.co, g.co and 1drv.ms: all three are
    # real shorteners that also sit in top-sites lists, so the length heuristic below
    # would skip them. Naming them is better than widening the guess.
    redirect_expands = [
        {'domain': '1drv.ms', 'base_url': 'https://1drv.ms/'},
        {'domain': 'a.co', 'base_url': 'https://a.co/'},
        {'domain': 'bit.do', 'base_url': 'https://bit.do/'},
        {'domain': 'buff.ly', 'base_url': 'https://buff.ly/'},
        {'domain': 'cutt.ly', 'base_url': 'https://cutt.ly/'},
        {'domain': 'db.tt', 'base_url': 'https://db.tt/'},
        {'domain': 'dlvr.it', 'base_url': 'https://dlvr.it/'},
        {'domain': 'fb.me', 'base_url': 'https://fb.me/'},
        {'domain': 'g.co', 'base_url': 'https://g.co/'},
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

    # Matched with preceding_domain_matches() rather than a dict lookup: these are served
    # from a subdomain (r20.rs6.net), and find_preceding_domain returns the full hostname.
    redirector = next(
        (domain for domain in query_token_redirectors
         if unfurl.preceding_domain_matches(node, domain)), None)

    if redirector:
        service = query_token_redirectors[redirector]
        full_url = unfurl.find_preceding_url(node)

        if full_url:
            expanded_url = expand_full_url_via_redirect_header(full_url)
            if expanded_url:
                unfurl.add_to_queue(
                    data_type='url', key=None, value=expanded_url,
                    label=f'Expanded URL: {expanded_url}',
                    hover=f'Expanded URL, retrieved from {redirector} '
                          f'({service}) via "Location" header.<br><br>This is a click '
                          f'tracker: the token is unique to one recipient, so requesting '
                          f'it may have registered a click and told the sender their '
                          f'target engaged with the message.',
                    parent_id=node.node_id, incoming_edge_config=shortlink_edge)
        return

    if preceding_domain in additional_shortener_domains:
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
    #
    # Checked before the length heuristic below. It used to come after, and the heuristic
    # returned unconditionally, so this list -- the authoritative one -- was unreachable
    # for every domain shorter than eight characters, which is most shorteners.
    misp_shortener_domains = unfurl.known_domain_lists['List of known URL Shorteners domains'].list
    if preceding_domain in misp_shortener_domains:
        expanded_url = expand_url_via_redirect_header(f'https://{preceding_domain}/', short_code)
        if expanded_url:
            unfurl.add_to_queue(
                data_type='url', key=None, value=expanded_url,
                label=f'Expanded URL: {expanded_url}',
                hover=f'Expanded URL, retrieved from {preceding_domain} via "Location" header',
                parent_id=node.node_id, incoming_edge_config=shortlink_edge)
        return

    # Last resort: guess that a very short domain we know nothing else about is a link
    # shortener, and try to expand it via a 301/302 Location header.
    #
    # Length alone is a bad signal -- x.com, box.com, cnn.com, npr.org, ibm.com, ups.com,
    # vk.com, qq.com, ok.ru, t.me and wa.me are all under eight characters and none of
    # them are shorteners. Guessing sent a request to each of them, which for a forensics
    # tool is worse than a wasted round trip: fetching a URL tells that site someone is
    # looking at it.
    #
    # So the guess is now limited to domains that are not in a top-sites list. A domain
    # popular enough to land in one is a destination people visit; a shortener that
    # popular (t.co, bit.ly, youtu.be) is already in the MISP list or the table above.
    # Only the tighter lists count -- see Unfurl.TOP_SITES_LIST_PREFIXES.
    if preceding_domain and len(preceding_domain) < 8 \
            and not unfurl.domain_in_top_sites_list(preceding_domain):
        expanded_url = expand_url_via_redirect_header(f'https://{preceding_domain}/', short_code)
        if expanded_url:
            unfurl.add_to_queue(
                data_type='url', key=None, value=expanded_url,
                label=f'Expanded URL: {expanded_url}',
                hover=f'Expanded URL, retrieved from {preceding_domain} via "Location" header',
                parent_id=node.node_id, incoming_edge_config=shortlink_edge)
