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

import datetime

import json
import pycountry
import zlib
import struct
import re
from unfurl import utils

import logging
log = logging.getLogger(__name__)

google_edge = {
    'color': {
        'color': 'green'
    },
    'title': 'Google-related Parsing Functions',
    'label': 'G'
}

known_sources = {
    'hp': 'Home Page',
    'serp': 'Search Engine Results Page',
    'img': 'Image Search',
    'psy-ab': 'Address Bar',
    'hangouts': 'Hangouts Chat'
}


def decode_varint(source):
    result = 0
    number_of_bytes = 0
    for read in source:
        result |= ((read & 0x7F) << (number_of_bytes * 7))
        number_of_bytes += 1
        if (read & 0x80) != 0x80:
            return result, number_of_bytes


def split_exactly(to_split, delimiter, times):
    x = to_split.split(delimiter, times)
    while len(x) < times+1:
        x.append(None)
    return x


def parse_aqs(aqs: str) -> dict:
    parsed = {}
    parsed['Device Type'], parsed['clicked_suggestion'], remainder = aqs.split('.', 2)
    autocompletion_str, timing_str = split_exactly(remainder, '.', 1)
    parsed['autocompletion_entries'] = autocompletion_str.split('j')

    if timing_str:
        parsed['query_formulation_time'], parsed['field_trial_triggered'], parsed['page_classification'] = \
            timing_str.split('j', 2)

    return parsed


def parse_ei(decoded):
    """Parse (base64-decoded) ei parameters from Google searches.

    Based on work by:
      Adrian Leong (cheeky4n6monkey@gmail.com) -
        https://github.com/cheeky4n6monkey/4n6-scripts/blob/master/google-ei-time.py
      Kevin Jones - https://deedpolloffice.com/blog/articles/decoding-ei-parameter
    """

    # grab 1st 4 bytes and treat as LE unsigned int
    timestamp = struct.unpack('<i', decoded[0:4])[0]
    parsed = [timestamp]

    varint_offset = 4  # First 4 (0-3) bytes are the timestamp
    for _ in [1, 2, 3]:
        try:
            value, bytes_used = decode_varint(decoded[varint_offset:])
            parsed.append(value)
            varint_offset += bytes_used
        except TypeError as e:
            log.warning(f'Unable to decode varint from {decoded}: {e}')
            return

    return parsed


def parse_rlz(rlz_string):
    # Reference: https://github.com/rogerta/rlz/blob/wiki/HowToReadAnRlzString.md
    rlz_re = re.compile(r'1(?P<ap>[A-Za-z0-9]{2})(?P<brand_code>[A-Za-z0-9]{4})(?P<cannibal>[c_])(?P<language_code>[A-Za-z]{2}'
                        r'(-[A-Za-z]{2})?)(?P<install_cohort>[A-Za-z]{2}\d{1,4})?(?P<search_cohort>[A-Za-z]{2}\d{1,4})?')
    rlz_m = rlz_re.fullmatch(rlz_string)
    if not rlz_m:
        return

    rlz = {
        'version': {
            'data_type': 'google.rlz.version',
            'key': 'RLZ version',
            'value': '1',
            'hover': 'Only v1 of RLZ is known'
        },
        'ap': {
            'data_type': 'google.rlz.ap',
            'key': 'Application',
            'value': rlz_m.group('ap'),
            'hover': 'Application (or "access point") used to do the Google Search'
        },
        'brand_code': {
            'data_type': 'google.rlz.brand_code',
            'key': 'Brand Code',
            'value': rlz_m.group('brand_code'),
            'hover': 'The brand code identifies the distribution channel (it may be a partner or internal marketing). '
                     'This correlates to how the user got the software (ie. they downloaded it by itself vs. it came '
                     'pre-installed on their new computer vs. it came with a partner\'s software.'
        }
    }

    cannibal_string = rlz_m.group('cannibal')
    if cannibal_string == 'c':
        cannibal_value = 'Yes'
    elif cannibal_string == '_':
        cannibal_value = 'No'
    else:
        raise ValueError(f'Invalid "cannibal" value in RLZ string: {cannibal_string}')

    rlz['cannibal'] = {
        'data_type': 'google.rlz.cannibal',
        'key': 'Cannibalized',
        'value': cannibal_value,
        'hover': '"Cannibal" tells if the library has evidence that the user was a user prior <br>'
                 'to installing the software, and thus "cannibalized" a previous installation.'}

    # Examples of longer RLZ values (2- and 5-char lang codes):
    #   1C1CHBF_en-GBGB901GB901
    #   1C1GCEU_enUS820US820

    language_code = rlz_m.group('language_code')
    # langcodes was having install issues on macOS; not using it for now in
    # order to not complicate Unfurl's install. Pycountry's languages isn't
    # as good (only alpha_2 and alpha_3) but better than nothing for now.
    # Old implementation:
    # language_name = langcodes.Language.get(language_code).language_name()
    language_name = pycountry.languages.get(alpha_2=language_code[:2]).name

    rlz['language'] = {
        'data_type': 'google.rlz.language',
        'key': 'Language',
        'value': f'{language_name} ({language_code})',
        'hover': 'The two- (en) or five-character (zh-CN) language code of the application. <br>'
                 'Valid values depend on the specific app.'}

    # The cohorts are optional; example of RLZ value without cohorts: 1C1GCEV_en
    if not rlz_m.group('install_cohort'):
        return rlz

    install_cohort = rlz_m.group('install_cohort')
    install_country_code = install_cohort[:2]
    install_country = pycountry.countries.get(alpha_2=install_country_code).name
    install_date = datetime.timedelta(weeks=int(install_cohort[2:])) + datetime.date(year=2003, month=2, day=3)

    rlz['install_cohort'] = {
        'data_type': 'google.rlz.install_cohort',
        'key': 'Install Cohort',
        'value': f'Installed in {install_country} the week of {install_date}',
        'hover': 'The country and week of the user\'s installation event. <br>'
                 'Country is determined by the server, using IP address. <br>'
                 'Week is measured as number of weeks since Feb 3, 2003.'}

    # Both cohorts do not need to be present, so if the 2nd one (search) is missing, return what we have
    # Example: 1CAGZLV_enGB898
    if not rlz_m.group('search_cohort'):
        return rlz

    search_cohort = rlz_m.group('search_cohort')
    search_country_code = search_cohort[:2]
    pycountry_object = pycountry.countries.get(alpha_2=search_country_code)
    search_country = search_country_code
    if pycountry_object:
        search_country = pycountry_object.name
    search_date = datetime.timedelta(weeks=int(search_cohort[2:])) + datetime.date(year=2003, month=2, day=3)

    rlz['search_cohort'] = {
        'data_type': 'google.rlz.search_cohort',
        'key': 'Search Cohort',
        'value': f'First search was in {search_country} the week of {search_date}',
        'hover': 'The country and week of the user\'s first search. <br>'
                 'Country is determined by the server, using IP address. <br>'
                 'Week is measured as number of weeks since Feb 3, 2003.'}

    return rlz

def run(unfurl, node):
    if node.data_type == 'url.query.pair' and unfurl.preceding_domain_contains(node, 'google'):

        if node.key == 'biw':
            unfurl.add_to_queue(
                data_type='google.biw', key='Browser Width', value=node.value,
                label=f'Browser width: {node.value}px',
                hover='Inner width of the browser window',
                parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'bih':
            unfurl.add_to_queue(
                data_type='google.bih', key='Browser Height', value=node.value,
                label=f'Browser height: {node.value}px',
                hover='Inner height of the browser window',
                parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'aqs':
            parsed_aqs = parse_aqs(node.value)
            for key, value in parsed_aqs.items():
                if key == 'autocompletion_entries':
                    repeated_count_offset = 0
                    for index, match in enumerate(value):
                        adjusted_start = index + repeated_count_offset
                        if 'l' in match:
                            _, repeated_count = split_exactly(match, 'l', 1)
                            repeated_count = int(repeated_count) - 1
                            repeated_count_offset += repeated_count
                            unfurl.add_to_queue(
                                data_type='google.aqs.ac_match',
                                key=f'Autocomplete Matches ({adjusted_start}-{adjusted_start + repeated_count})',
                                value=match, parent_id=node.node_id, incoming_edge_config=google_edge)
                        else:
                            unfurl.add_to_queue(
                                data_type='google.aqs.ac_match',
                                key=f'Autocomplete Match ({adjusted_start})',
                                value=match, parent_id=node.node_id, incoming_edge_config=google_edge)

                elif key == 'page_classification':
                    unfurl.add_to_queue(
                        data_type='google.aqs.page_classification', key='Page Classification', value=value,
                        hover='The type of page currently displayed when the user used the omnibox',
                        parent_id=node.node_id, incoming_edge_config=google_edge)

                elif key == 'query_formulation_time':
                    unfurl.add_to_queue(
                        data_type='google.aqs.query_formulation_time', key='Query Formulation Time',
                        value=f'{int(value)/1000} seconds',
                        hover='Query formulation time (time from when the user first typed a character into the '
                              'omnibox to when the user selected a query)',
                        parent_id=node.node_id, incoming_edge_config=google_edge)

                elif key == 'field_trial_triggered':
                    unfurl.add_to_queue(
                        data_type='google.aqs.field_trial_triggered', key='Field Trial Triggered',
                        value=str(bool(int(value))),  # converts the '0' or '1' (strings) into True or False strings
                        hover='Whether a field trial (of zero suggest or search provider) was triggered in the '
                              'session',
                        parent_id=node.node_id, incoming_edge_config=google_edge)

                elif key == 'clicked_suggestion':
                    if value:
                        unfurl.add_to_queue(
                            data_type='google.aqs.clicked_suggestion', key='Clicked Suggestion',
                            value=value, hover='The index (starting at 0) of the accepted suggestion',
                            parent_id=node.node_id, incoming_edge_config=google_edge)
                    else:
                        unfurl.add_to_queue(
                            data_type='google.aqs.clicked_suggestion', key='Clicked Suggestion',
                            value='None', hover='The user did not click one of the offered suggestions',
                            parent_id=node.node_id, incoming_edge_config=google_edge)
                else:
                    unfurl.add_to_queue(
                        data_type='google.aqs', key=key, value=value,
                        parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'authuser':
            # Seen across Google properties; identifies which of the browser profile's
            # signed-in accounts the request is for, by the order they were added.
            position = str(node.value)
            if position.isdigit():
                index = int(position)
                qualifier = 'default account' if index == 0 else 'an additional signed-in account'
                label = f'Google account index {index} ({qualifier})'
                hover = ('Google\'s "authuser" selects between accounts signed in to the same '
                         'browser profile, numbered from 0 in the order they were added. A '
                         'value above 0 means more than one account was signed in.')
            else:
                # Some flows use the account's email address rather than an index.
                label = f'Account: {node.value}'
                hover = ('Google\'s "authuser" selects between accounts signed in to the same '
                         'browser profile; here it names the account directly.')
            unfurl.add_to_queue(
                data_type='descriptor', key=None, value=None, label=label, hover=hover,
                parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'dsh':
            # Ex: dsh=S2034035022:1749584429440685 (sign-in flows on accounts.google.com).
            # The second field is the time the flow started, in epoch microseconds.
            dsh_match = re.fullmatch(r'S?(-?\d+):(\d{13,19})', str(node.value))
            if dsh_match:
                dsh_timestamp = int(dsh_match.group(2))
                unfurl.add_to_queue(
                    data_type='epoch-microseconds', key=None, value=dsh_timestamp,
                    label=f'dsh Timestamp: {dsh_timestamp}',
                    hover='Google sign-in URLs carry a "dsh" value whose second field is the '
                          'time the sign-in flow was started, as epoch microseconds. This dates '
                          'the sign-in attempt itself, not the account or the page content.',
                    parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'ei':
            decoded_ei = utils.try_urlsafe_b64_decode(node.value, min_length=8)
            if decoded_ei is None:
                return

            try:
                parsed_ei = parse_ei(decoded_ei)
            except Exception as e:
                log.exception(f'Exception running parse_ei() on {node.value}: {e}')
                return

            if not parsed_ei:
                return

            node.hover = 'The \'<b>ei</b>\' parameter is base64-encoded and contains four values. ' \
                         '<br>The first two are thought to be the timestamp of when the session started ' \
                         '<br>(first value is full seconds, second is microsecond component)' \
                         '<br>This may be seconds (but could be days!) before the URL was generated.' \
                         '<br><br>References:<ul>' \
                         '<li><a href="https://deedpolloffice.com/blog/articles/decoding-ei-parameter" ' \
                         'target="_blank">Kevin Jones: How to decode the ei parameter in Google search</a></li>' \
                         '<li><a href="http://cheeky4n6monkey.blogspot.com/2014/10/google-eid.html" ' \
                         'target="_blank">Cheeky4n6Monkey: Google-ei\'d ?!</a></li>' \
                         '<li><a href="https://github.com/obsidianforensics/unfurl/issues/56" ' \
                         'target="_blank">Rasmus-Riis: Search Experiment with ei parameter</a></li>'\
                         '<li>Adam Mazack: noticed the 2nd ei value contained fractional seconds ' \
                         '<br> that match the ved</li></ul>'
            node.extra_options = {'widthConstraint': {'maximum': 300}}

            assert len(parsed_ei) == 4, \
                f'There should be 4 decoded ei values, but we have {len(parsed_ei)}!'

            unfurl.add_to_queue(
                data_type='google.ei', key=0, value=parsed_ei[0],
                label=f'ei-0: {parsed_ei[0]}',
                hover='The first <b>ei</b> value is thought to be part of the timestamp'
                      ' (seconds) of when the session began.',
                parent_id=node.node_id, incoming_edge_config=google_edge)

            unfurl.add_to_queue(
                data_type='google.ei', key=1, value=parsed_ei[1],
                label=f'ei-1: {parsed_ei[1]:06d}',
                hover='The second <b>ei</b> value is thought to be part of the timestamp'
                      ' (fractional seconds) of when the session began.',
                parent_id=node.node_id, incoming_edge_config=google_edge)

            unfurl.add_to_queue(
                data_type='google.ei', key=2, value=parsed_ei[2],
                label=f'ei-2: {parsed_ei[2]}',
                hover='The meaning of the third <b>ei</b> value is not known.',
                parent_id=node.node_id, incoming_edge_config=google_edge)

            unfurl.add_to_queue(
                data_type='google.ei', key=3, value=parsed_ei[3],
                label=f'ei-3: {parsed_ei[3]}',
                hover='The meaning of the fourth <b>ei</b> value is not known, '
                      'but it matches the <b>ved</b> "13-3" value.',
                parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'gs_l':
            node.hover = 'The <b>gs_l</b> parameter contains multiple values, delimited by <b>.</b>. <br>' \
                         'We only know the meaning of 7 (of the 26+) parameters.'
            node.extra_options = {'widthConstraint': {'maximum': 1400}}

            params = node.value.split('.')

            known_params = [0, 1, 2, 4, 5, 7, 8, 26]
            for known_param in known_params:
                if len(params) > known_param and len(params[known_param]) > 0:
                    unfurl.add_to_queue(
                        data_type='google.gs_l', key=str(known_param), value=params[known_param],
                        label=f'Parameter {str(known_param)}: {params[known_param]}',
                        parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'oq':
            unfurl.add_to_queue(
                data_type='google.oq', key=None, value=f'"Original" Search Query: {node.value}',
                hover='Original terms entered by the user; auto-complete or suggestions <br>'
                      'may have been used to reach the actual search terms (in <b>q</b>)',
                parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'q':
            # On /url redirect pages, q is the destination URL, not a search query.
            # Skip here and let the google site_def handle it with the correct label.
            if unfurl.find_preceding_path(node) == '/url':
                return

            unfurl.add_to_queue(
                data_type='google.q', key=None, value=f'Search Query: {node.value}',
                hover='Terms used in the Google search', parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'source':
            if node.value in known_sources.keys():
                unfurl.add_to_queue(
                    data_type='google.source', key=None, value=f'Source: {known_sources[node.value]}',
                    hover='Source of the Google search', parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'start':
            unfurl.add_to_queue(
                data_type='google.start', key=None, value=f'Starting Result: {node.value}',
                hover='Google search by default shows 10 results per page; higher <br>'
                      '"start" values may indicate browsing more subsequent results pages.',
                parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'sxsrf':
            node.extra_options = {'widthConstraint': {'maximum': 400}}
            sxs_0, sxs_1 = node.value.split(':', 1)
            unfurl.add_to_queue(data_type='google.sxsrf', key=1, value=sxs_0,
                                parent_id=node.node_id, incoming_edge_config=google_edge)
            unfurl.add_to_queue(
                data_type='epoch-milliseconds', key=2, value=sxs_1,
                hover='The <b>sxsrf</b> parameter contains a timestamp, believed<br>'
                      ' to correspond to the previous page load. <br><br>Refernces:<ul><li>'
                      '<a href="https://twitter.com/phillmoore/status/1169846359509233664" target="_blank">'
                      'Phill Moore on Twitter</a></li></ul>', parent_id=node.node_id,
                incoming_edge_config=google_edge)

        elif node.key == 'tbm':
            tbm_mappings = {
                'bks': 'Google Books',
                'fin': 'Google Finance',
                'flm': 'Google Flights',
                'isch': 'Google Images',
                'nws': 'Google News',
                'shop': 'Google Shopping',
                'vid': 'Google Videos',
            }

            value = tbm_mappings.get(node.value, 'Unknown')
            unfurl.add_to_queue(
                data_type='google.tbm', key=None, value=f'Search Type: {value}',
                hover='Google Search Type', parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'udm':
            # UDM _might_ be URL Data Manager?
            # https://source.chromium.org/chromium/chromium/src/+/main:content/browser/webui/url_data_manager.h
            udm_mappings = {
                '1': 'All',
                '2': 'Images',
                '3': 'Products',
                '6': 'Learn',
                '7': 'Videos',
                '8': 'Jobs',
                '12': 'News',
                '14': 'Web',
                '15': 'Things to do',
                '18': 'Forums',
                '28': 'Shopping',
                '36': 'Books',
                '37': 'Products',
                '38': 'Videos',
                '44': 'Visual matches',
                '47': 'Web (+"Refine Results" panel)',
                '48': 'Exact matches',
                '51': 'Homework'
                # Manually setting 56 and above results in a redirect with the udm parameter stripped off
                # (at least until 65, then I stopped testing)
            }
            value = udm_mappings.get(node.value, 'Unknown')
            unfurl.add_to_queue(
                data_type='google.udm', key=None, value=f'Results Page Type: {value}',
                hover='Google Results Page Type', parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'uule':
            # https://moz.com/ugc/geolocation-the-ultimate-tip-to-emulate-local-search
            location_string = utils.try_standard_b64_decode(node.value[10:])
            if location_string is None:
                return
            unfurl.add_to_queue(
                data_type='google.uule', key=None, value=location_string, label=location_string,
                parent_id=node.node_id, incoming_edge_config=google_edge)

        elif node.key == 'rlz':
            unfurl.add_to_queue(
                data_type='descriptor', key=None,
                value='RLZ used for grouping promotion event signals and anonymous user cohorts',
                parent_id=node.node_id, incoming_edge_config=google_edge)

            try:
                rlz = parse_rlz(node.value)
                if rlz:
                    for component in rlz.values():
                        unfurl.add_to_queue(
                            data_type=component['data_type'], key=component['key'],
                            value=component['value'], hover=component['hover'],
                            parent_id=node.node_id, incoming_edge_config=google_edge)

            except ValueError as e:
                print(f'Exception parsing RLZ: {e}')

        elif node.key == 'stick':
            # Tag this node so parse_protobuf can look up friendly field names
            # when it decodes the stick protobuf (via parse_compressed → parse_protobuf).
            unfurl.add_to_stash('proto_context', {node.node_id: {'context': 'google.stick'}})

        elif node.key == 'ved':
            node.extra_options = {'widthConstraint': {'maximum': 400}}
            if node.value[0] not in ['0', '2']:
                return
            ved_version = node.value[0]
            encoded_ved = node.value[1:]

            ved_version_descriptions = {
                '0': 'Version 0: older ved format, not base64-encoded',
                '2': 'Version 2: current ved format, base64-encoded protobuf'
            }

            unfurl.add_to_queue(
                data_type='google.ved.version', key='Ved Version', value=ved_version,
                label=f'Ved Version: {ved_version}',
                hover=ved_version_descriptions.get(ved_version),
                parent_id=node.node_id, incoming_edge_config=google_edge)

            # Skip b64 decoding on this node — the value has a version byte prefix
            # that would produce garbage proto fields. The child node below has
            # the cleaned value.
            unfurl.add_to_stash('proto_context', {node.node_id: {'context': 'google.ved', 'skip': True}})
            unfurl.add_to_queue(
                data_type='proto.ved_raw', key=None, value=encoded_ved,
                parent_id=node.node_id, incoming_edge_config=google_edge,
                hover='The ved parameter value (base64-encoded protobuf)')

        elif node.key == 'gs_lcrp':
            unfurl.add_to_stash('proto_context', {node.node_id: {'context': 'google.gs_lcrp'}})

    # Expand and interpret gs_lcrp (ChromeSearchboxStats) fields.
    if node.data_type == 'google.gs_lcrp':
        if isinstance(node.value, list):
            for item in node.value:
                if isinstance(item, dict):
                    unfurl.add_to_queue(
                        data_type='google.gs_lcrp', key=node.key, value=item,
                        label=f'Suggestion {item.get("index", "?")}',
                        parent_id=node.node_id, incoming_edge_config=google_edge)
                else:
                    unfurl.add_to_queue(
                        data_type='google.gs_lcrp', key=node.key, value=item,
                        parent_id=node.node_id, incoming_edge_config=google_edge)
        elif isinstance(node.value, dict):
            for key, value in node.value.items():
                if key == 'type':
                    unfurl.add_to_queue(
                        data_type='omnibox.suggest_type', key='Type', value=value,
                        parent_id=node.node_id, incoming_edge_config=google_edge)
                elif key == 'subtypes':
                    for subtype in value:
                        unfurl.add_to_queue(
                            data_type='omnibox.suggest_subtype', key='Subtype', value=subtype,
                            parent_id=node.node_id, incoming_edge_config=google_edge)
                else:
                    unfurl.add_to_queue(
                        data_type='google.gs_lcrp', key=key, value=value,
                        label=f'{key}: {value}',
                        parent_id=node.node_id, incoming_edge_config=google_edge)

    if node.data_type == 'google.aqs.ac_match':
        entry, count = split_exactly(node.value, 'l', 1)
        ac_type, subtype_str = split_exactly(entry, 'i', 1)

        unfurl.add_to_queue(
            data_type='omnibox.suggest_type', key='Type', value=int(ac_type),
            parent_id=node.node_id, incoming_edge_config=google_edge)

        if subtype_str:
            for subtype in subtype_str.split('i'):
                unfurl.add_to_queue(
                    data_type='omnibox.suggest_subtype', key='Subtype', value=int(subtype),
                    parent_id=node.node_id, incoming_edge_config=google_edge)

        if count:
            unfurl.add_to_queue(
                data_type='descriptor', key='Count', value=count,
                parent_id=node.node_id, incoming_edge_config=google_edge)

    elif node.data_type == 'google.aqs.page_classification':
        # Source: https://source.chromium.org/chromium/chromium/src/+/main:third_party/
        #         metrics_proto/omnibox_event.proto;l=97
        classifications = {
            0: {
                'name': 'Invalid Spec',
                'description': 'An invalid URL; shouldn\'t happen'
            },

            1: {
                'name': 'New Tab Page',
                'description': 'The New Tab Page (chrome://newtab/). For modern versions of Chrome, this is only '
                               'reported when an extension is replacing the new tab page. Otherwise, new tab page '
                               'interactions will be as one of the other "New Tab Page" types. For old versions of '
                               'Chrome, this was reported for the default New Tab Page.',
            },

            2: {
                'name': 'Blank Page',
                'description': 'about:blank'
            },

            3: {
                'name': 'Home Page',
                'description': 'The user\'s home page. Note that if the home page is set to any of the new tab page '
                               'versions or to about:blank, then we\'ll classify the page into those categories, '
                               'not "Home Page".'
            },

            4: {
                'name': 'Other',
                'description': 'The catch-all entry of everything not included somewhere else on this list.'
            },

            5: {
                'name': '(Obsolete) Instant New Tab Page',
                'description': 'The instant new tab page enum value was deprecated on August 2, 2013.'
            },

            6: {
                'name': 'Search Result Page (with search term replacement)',
                'description': 'The user is on a search result page that does search term replacement. This means the '
                               'search terms are shown in the omnibox instead of the URL. In other words: Query in '
                               'Omnibox is Active for this SRP.'
            },

            7: {
                'name': 'Instant New Tab Page (with omnibox as starting focus)',
                'description': 'The new tab page in which this omnibox interaction first started with the user having '
                               'focus in the omnibox.'
            },

            8: {
                'name': 'Instant New Tab Page (with fakebox as starting focus)',
                'description': 'The new tab page in which this omnibox interaction first started with the user having '
                               'focus in the fakebox. Note that this started being replaced by NTP_REALBOX in Aug 2020 '
                               'and will eventually be obsolete.'
            },

            9: {
                'name': 'Search Results Page (no search term replacement)',
                'description': 'The user is on a search result page that does not do search term replacement. This '
                               'means the URL of the SRP is shown in the omnibox. In other words: Query in Omnibox is '
                               'Inactive for this SRP.'
            },

            10: {
                'name': 'Home Screen',
                'description': 'The user is on the home screen.'
            },

            11: {
                'name': 'Search App',
                'description': 'The user is in the search app.'
            },

            12: {
                'name': 'Maps App',
                'description': 'The user is in the maps app.'
            },

            13: {
                'name': 'Search Button',
                'description': 'This omnibox interaction started with the user tapping the search button.'
            },

            14: {
                'name': 'ChromeOS App List',
                'description': 'This interaction started with the user focusing or typing in the search box of the '
                               'ChromeOS app list (a.k.a., launcher).'
            },

            15: {
                'name': 'New Tab Page (realbox)',
                'description': 'The new tab page in which this omnibox interaction started with the user having focus '
                               'in the realbox.'
            },

            16: {
                'name': 'Android Search Widget',
                'description': 'Android\'s Search Widget started directly from Launcher.'
            },

            17: {
                'name': 'Android Start surface homepage',
                'description': 'Android\'s Start surface homepage.'
            },

            18: {
                'name': 'Android Start surface New Tab',
                'description': 'New Tab with Omnibox focused when Android\'s start surface finale is enabled.'
            },

            19: {
                'name': 'Android Shortcuts Widget',
                'description': 'Android\'s improved Search Widget with new suggestions'
            }
        }

        known = classifications.get(int(node.value), None)
        if not known:
            return

        unfurl.add_to_queue(
            data_type='descriptor', key=None, value=f'{node.value}: {known["name"]}', hover=known['description'],
            parent_id=node.node_id, incoming_edge_config=google_edge)

    elif node.data_type == 'google.gs_l':
        known_values = {
            '0': known_sources,
            '1': {
                '1': 'mouse-click on suggestion',
                '3': 'keyboard [enter] key',
                '10': 'Google Instant Search (untested)'
            }
        }
        if node.key == '0':
            if node.value in known_values[node.key].keys():
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=known_values[node.key][node.value],
                    label=f'Searcher came from {known_values[node.key][node.value]}',
                    parent_id=node.node_id, incoming_edge_config=google_edge)

        if node.key == '1':
            if node.value in known_values[node.key].keys():
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=known_values[node.key][node.value],
                    label=f'Searcher selected search terms by {known_values[node.key][node.value]}',
                    parent_id=node.node_id, incoming_edge_config=google_edge)

        if node.key == '2':
            unfurl.add_to_queue(
                data_type='descriptor', key=None, value=node.value,
                label=f'Selected option {node.value} from suggestion list',
                parent_id=node.node_id, incoming_edge_config=google_edge)

        if node.key == '4':
            if node.value == '0':
                param_text = 'User clicked on a suggestion'
            else:
                param_text = f'{str(float(node.value) / 1000)} seconds before the user selected the search box'

            unfurl.add_to_queue(
                data_type='descriptor', key=None, value=node.value, label=param_text,
                parent_id=node.node_id, incoming_edge_config=google_edge)

        if node.key == '5':
            if node.value == '0':
                param_text = 'User clicked on a suggestion'
            else:
                param_text = f'{str(float(node.value) / 1000)} seconds on page before the user completed typing.'

            unfurl.add_to_queue(
                data_type='descriptor', key=None, value=node.value, label=param_text,
                parent_id=node.node_id, incoming_edge_config=google_edge)

        if node.key == '7':
            if node.value != '0':
                param_text = f'User spent {str(float(node.value) / 1000)} seconds on page in total.'
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=node.value, label=param_text,
                    parent_id=node.node_id, incoming_edge_config=google_edge)

        if node.key == '8':
            if node.value == '0':
                param_text = 'No characters typed'
            else:
                param_text = f'{node.value} keys pressed while user was typing.'

            unfurl.add_to_queue(
                data_type='descriptor', key=None, value=node.value, label=param_text,
                hover='If the search was done in Chrome, this value may be +1.',
                parent_id=node.node_id, incoming_edge_config=google_edge)

        if node.key == '26':
            if node.value == '1':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=node.value, label='User typed in query',
                    parent_id=node.node_id, incoming_edge_config=google_edge)

    elif node.data_type == 'google.ved':
        known_link_types = {
            22: 'web',
            152: 'blog search result',
            232: 'book or patent search result',
            235: 'book or patent search result thumbnail',
            244: 'image result in standard SERPs',
            245: 'image search result in basic (non-javascript) image search, or image result in universal search',
            288: 'local search result',
            295: 'news result thumbnail',
            297: 'news result',
            300: 'more results link (listed mainly for Q&A websites)',
            311: 'video result',
            312: 'video result thumbnail',
            338: 'one-line sitelink',
            371: 'shopping search result',
            429: 'image search result [probably not in use any more]',
            586: '"Jump to" link',
            612: 'map search result website link',
            646: 'map search result thumbnail',
            706: 'adword sitelink',
            745: 'breadcrumb',
            1107: 'patent result "Overview" / "Related" / "Discuss" link',
            1140: 'book search result author link',
            1146: 'normal result thumbnail (e.g. for an application, recipe, etc.)',
            1150: 'normal result thumbnail (e.g. for an application, recipe, etc.)',
            1455: 'local search result marker pin icon',
            1532: 'news sub-result (i.e. the same story from a different site)',
            1617: 'adword (i.e. sponsored search result)',
            1701: 'map search result',
            1732: 'knowledge graph repeated sub-link (e.g. football team squad players, album track listings)',
            1907: 'sponsored shopping result thumbnail (in right-hand column of universal search results)',
            1908: 'sponsored shopping result (in right-hand column of universal search results)',
            1986: 'sponsored shopping result thumbnail (in main column of universal search results)',
            1987: 'sponsored shopping result (in main column of universal search results)',
            2060: 'sitelink',
            2237: 'news result video thumbnail',
            2459: 'knowledge graph link',
            2847: 'authorship "by [author]" link',
            2937: 'authorship thumbnail link',
            3588: 'image search result (thumbnail)',
            3596: 'image search result preview "View image" link',
            3597: 'image search result preview thumbnail',
            3598: 'image search result preview title link',
            3599: 'image search result preview "Visit page" link',
            3724: 'image search result preview grey website link underneath title',
            3836: 'knowledge graph main image',
            5077: 'in-depth article result',
            5078: 'in-depth article result thumbnail',
            5158: 'adword one-line sitelink',
            5497: 'dictionary definition link'
        }

        # Field 2 in the ved protobuf is the link type.
        # This is scoped to data_type=='google.ved' so '2' won't match other protos.
        if node.key == '2':
            try:
                link_type_int = int(node.value)
            except (ValueError, TypeError):
                link_type_int = node.value
            if known_link_types.get(link_type_int):
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=node.value, label=known_link_types.get(link_type_int),
                    hover='There are tens of thousands of these values; the \'known\'<br> ones in Unfurl are based on '
                          '<a href="https://github.com/beschulz/ved-decoder" target="_blank">'
                          'Benjamin Schulz\'s work</a>',
                    parent_id=node.node_id, incoming_edge_config=google_edge)

    elif node.data_type == 'google.rlz.ap':
        # From https://source.chromium.org/chromium/chromium/src/+/master:rlz/lib/lib_values.cc
        rlz_aps = {
            # 'I7': 'IE_DEFAULT_SEARCH',
            'I7': 'IE Default search',
            # 'W1': 'IE_HOME_PAGE',
            'W1': 'IE Home Page',
            # 'T4': 'IETB_SEARCH_BOX',
            'T4': 'IE Toolbar Search Box',
            'Q1': 'QUICK_SEARCqH_BOX',
            'D1': 'GD_DESKBAND',
            'D2': 'GD_SEARCH_GADGET',
            'D3': 'GD_WEB_SERVER',
            'D4': 'GD_OUTLOOK',
            # 'C1': 'CHROME_OMNIBOX',
            'C1': 'Chrome Omnibox',
            # 'C2': 'CHROME_HOME_PAGE',
            'C2': 'Chrome Home Page',
            # 'B2': 'FFTB2_BOX',
            'B2': 'Firefox Toolbar v2',
            # 'B3': 'FFTB3_BOX',
            'B3': 'Firefox Toolbar v3',
            'N1': 'PINYIN_IME_BHO',
            'G1': 'IGOOGLE_WEBPAGE',
            'H1': 'MOBILE_IDLE_SCREEN_BLACKBERRY',
            'H2': 'MOBILE_IDLE_SCREEN_WINMOB',
            'H3': 'MOBILE_IDLE_SCREEN_SYMBIAN',
            # 'R0': 'FF_HOME_PAGE',
            'R0': 'Firefox Home Page',
            # 'R1': 'FF_SEARCH_BOX',
            'R1': 'Firefox Search box',
            'R2': 'IE_BROWSED_PAGE',
            'R3': 'QSB_WIN_BOX',
            'R4': 'WEBAPPS_CALENDAR',
            'R5': 'WEBAPPS_DOCS',
            'R6': 'WEBAPPS_GMAIL',
            'R7': 'IETB_LINKDOCTOR',
            'R8': 'FFTB_LINKDOCTOR',
            'T7': 'IETB7_SEARCH_BOX',
            'T8': 'TB8_SEARCH_BOX',
            'C3': 'CHROME_FRAME',
            'V1': 'PARTNER_AP_1',
            'V2': 'PARTNER_AP_2',
            'V3': 'PARTNER_AP_3',
            'V4': 'PARTNER_AP_4',
            'V5': 'PARTNER_AP_5',
            # 'C5': 'CHROME_MAC_OMNIBOX',
            'C5': 'Chrome Omnibox on Mac',
            # 'C6': 'CHROME_MAC_HOME_PAGE',
            'C6': 'Chrome home page on Mac',
            # 'CA': 'CHROMEOS_OMNIBOX',
            'CA': 'ChromeOS Omnibox',
            # 'CB': 'CHROMEOS_HOME_PAGE',
            'CB': 'ChromeOS Home Page',
            'CC': 'CHROMEOS_APP_LIST',
            # 'C9': 'CHROME_IOS_OMNIBOX_TABLET',
            'C9': 'Chrome Omnibox on iOS Tablet',
            # 'CD': 'CHROME_IOS_OMNIBOX_MOBILE',
            'CD': 'Chrome Omnibox on iOS Mobile',
            'C7': 'CHROME_APP_LIST',
            'C8': 'CHROME_MAC_APP_LIST',
            'RQ': 'UNDEFINED_AP_Q',
            'RR': 'UNDEFINED_AP_R',
            'RS': 'UNDEFINED_AP_S',
            'RT': 'UNDEFINED_AP_T',
            'RU': 'UNDEFINED_AP_U',
            'RV': 'UNDEFINED_AP_V',
            'RW': 'UNDEFINED_AP_W',
            'RX': 'UNDEFINED_AP_X',
            'RY': 'UNDEFINED_AP_Y',
            'RZ': 'UNDEFINED_AP_Z',
            'U0': 'PACK_AP0',
            'U1': 'PACK_AP1',
            'U2': 'PACK_AP2',
            'U3': 'PACK_AP3',
            'U4': 'PACK_AP4',
            'U5': 'PACK_AP5',
            'U6': 'PACK_AP6',
            'U7': 'PACK_AP7',
            'U8': 'PACK_AP8',
            'U9': 'PACK_AP9',
            'UA': 'PACK_AP10',
            'UB': 'PACK_AP11',
            'UC': 'PACK_AP12',
            'UD': 'PACK_AP13'
        }

        unfurl.add_to_queue(
            data_type='descriptor', key=node.value, value=rlz_aps.get(node.value, 'Unknown'),
            label=f'Search performed using {rlz_aps.get(node.value, "unknown application")}',
            parent_id=node.node_id, incoming_edge_config=google_edge)

    elif node.data_type == 'google.ei' and node.key == 1:
        ei0_node = unfurl.check_sibling_nodes(node, data_type='google.ei', key=0, return_node=True)

        if ei0_node:
            # The first ei value is epoch seconds, the second has the fractional (micro) seconds.
            # Concatenating them here as strings lets the timestamp parser convert it later.
            ei_timestamp = f'{ei0_node.value}{node.value:06d}'

            unfurl.add_to_queue(
                data_type='epoch-microseconds', key=None, value=ei_timestamp, label=f'ei Timestamp: {ei_timestamp}',
                hover='The first two values combined in the <b>ei</b> parameter are thought to be the timestamp of '
                      'when the session began. The first (ei-0) contains the full seconds portion of the timestamp '
                      'and the second (ei-1) contains the fractional seconds.',
                # Commenting this out as the two parents breaks the "tree" for text_tree
                # parent_id=[node.node_id, ei0_node.node_id],
                parent_id=ei0_node.node_id,
                incoming_edge_config=google_edge)
