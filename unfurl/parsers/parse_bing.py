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

import re

bing_edge = {
    'color': {
        'color': '#228372'
    },
    'title': 'Bing-related Parsing Functions',
    'label': 'B'
}

# The "form" codes and their meanings come from the Lantern project's parameters.md
# (https://github.com/lanterntool/lantern/blob/main/parameters.md), the reference table
# published alongside Spear, Hawbecker & McElyea, "Lantern to the Underworld" (HICSS 2021).
# Upstream last verified these between 2021-05-21 and 2021-06-08, and the authors warn the
# codes change over time, so treat them as a snapshot rather than a current guarantee.
# Placeholder names are normalized to [searchString]/[initialSearch] to match this file.

# Five codes share one meaning: which one Bing emits depends on how far the user had
# scrolled when the "stickied" search bar appeared. Keeping them as one string keeps that
# deliberate grouping visible instead of looking like duplicated entries.
scrolled_suggestion_bar = \
    "Indicates the user arrived at results by having scrolled part way down a search results page until a " \
    "secondary \"stickied\" search bar appears at the top of the page and then selected a suggested search " \
    "term from the list of suggestions. Which of the five IRMH codes appears depends on how far down the " \
    "user had scrolled."

form_values = {
    "AWIR": "Indicates the user arrived at results by having selected \"Including results for [alternate version of initial search \"[searchString]\"]\" (i.e. user searched for \"Newyork\" and Bing includes additional results for \"New York\").",
    "AWRE": "Indicates the user arrived at results by having misspelled a term and then selected \"Including results for [correct spelling]\" ",
    "HDRSC1": "Indicates the user arrived at results by having performed a search for \"[searchString]\" not in the Bing web search and then clicking \"All\" to see all results.",
    "HDRSC2": "Indicates the user arrived at results by having manually typed the search term \"[searchString]\" into the main Bing search engine and then selecting \"Bing Images\" to view the image search results.",
    "HDRSC3": "Indicates the user arrived at results by having performed a search for \"[searchString]\" outside the \"Videos\" search (such as \"Images\" or \"All\") then clicking \"Videos\" to see only Video results.",
    "IDINTS": "Indicates the user arrived at Bing image results by having selected the Bing-suggested search term \"[searchString]\" located at the top of the page, which appeared as a result of the user having selected a thumbnail image on a previous result in order to view the full-size image within the browser.",
    "IDMHDL": "Indicates the user arrived at results by having scrolled part way down a previous image search results page until a secondary search bar dropped down from the top of the page. The user arrived at this URL by having selected [searchString] from the Bing suggestions in this secondary search bar.",
    "IGRE": "Indicates the user arrived at Bing image results by having typed a search term into the main Bing search engine then scrolled down the results page and selected the link \"Images of [searchString]\" to view the image search results.",
    "ILPMFT": "Indicates the user arrived at an image grid derived when a user is directed to a fresh Bing image search page. ",
    "ILPTRD": "Indicates the user navigated directly to the Bing Images page.",
    "ILPVIS": "Indicates the user navigated to the Bing Visual Search tool by selecting the \"Visual Search\" link on the Bing Images page.",
    "INLIRS": "Indicates the user arrived at Bing image results by having selected the Bing-suggested search term \"[searchString]\" located in the \"Related Content\" panel on the right, which appeared as a result of the user having selected a thumbnail image on a previous result in order to view the full-size image within the browser.",
    "IQFRML": "Indicates the user arrived at Bing image results by having typed a search term into the main Bing search engine then scrolled down the results page and selected the link \"See all images\" under the \"Images of [searchString]\" result.",
    "IQFRBA": "Indicates the user arrived at Bing image results by having manually typed a search term into the main Bing search engine then scrolled down the results page and selected a thumbnail image beneath the link \"Images of [searchString]\" to view the image search results. The URL string also provides a unique ID for the specific image selected by the user.",
    "IRBPRS": "Indicates the user arrived at Bing image results by having selected the suggested thumbnail of an image located at the bottom of the search results page and categorized by the Bing search engine as \"Top Suggestions for [initialSearch]\" ",
    "IRIBEP": "Indicates the user arrived at Bing image results by having selected the Bing-suggested link within a previous image search for \"People interested in [initialSearch] also searched for\".",
    "IRIBIP": "Indicates the user selected the thumbnail of an image categorized by the Bing search engine as \"Explore more searches like [initialSearch]\" ",
    "IRIBPC": "Indicates the user arrived at Bing image results by having selected the suggested thumbnail of an image categorized by the Bing search engine as \"Connected to [initialSearch]\" ",
    "IRIBQP": "Indicates the user arrived at Bing image results by having selected the suggested thumbnail of an image located at the top of the search results page and categorized by the Bing search engine as \"Top Suggestions for [initialSearch]\" ",
    "IRMHPC": "Indicates the user arrived at Bing image results by having Search results derived from a user manually typing a search term selecting \"see more images\" at the bottom of the page, then selecting a suggested search term at the top of the page.",
    "IRMHEP": scrolled_suggestion_bar,
    "IRMHIP": scrolled_suggestion_bar,
    "IRMHQP": scrolled_suggestion_bar,
    "IRMHRE": scrolled_suggestion_bar,
    "IRMHRS": scrolled_suggestion_bar,
    "IRMHTS": scrolled_suggestion_bar,
    "IRTRRL": "Indicates the user arrived at Bing image results by having selected the suggested thumbnail of an image categorized by the Bing search engine as \"Refine your search for [initialSearch]\".",
    "IRPRST": "Indicates the user clicked on a thumbnail image visible in the results page for search \"[searchString]\" in order to view the full-size image within the browser. The \"thid\" parameter identifies the thumbnail and records whether Bing had already indexed the image (OIP) or had indexed it recently (OIF); \"mediaurl\" holds the address of the full-size image.",
    "ISTRTH": "Indicates the user arrived at Bing image results by having selected \"[searchString]\" in Bing Images trending searches.",
    "QBILPG": "Indicates the user arrived at Bing image results by having manually searched for \"[searchString]\" from the Bing image search page.",
    "QBIR": "Indicates the user arrived at results by having manually input search string \"[searchString]\" on a current Bing image search result page.",
    "QBIRMH": "Indicates the user arrived at Bing image results by having manually typed an image search term and then scrolled down the page until a secondary search bar dropped down from the top of the page before having manually typed a search for \"[searchString]\" in this secondary search bar.",
    "R5FD2": "Indicates the user arrived at Bing image results by having selected the suggested thumbnail of an image located at the bottom of the search results page and categorized by the Bing search engine as \"People interested in [initialSearch] also searched for\" ",
    "RCIR": "Indicates the user arrived at results by having selected \"Do you want results only for [initialSearch]\".",
    "RESTAB": "Indicates the user arrived at results by having previously manually typed a search term and then selected the Bing-suggested search term \"[searchString]\" located at the top of the page.",
    "Z9LH": "Indicates the user arrived at the Bing image search page by going to bing.com and selecting the \"Bing Images\" link.",
    "Z9FD1": "Indicates the user arrived at the Bing image search page by having selected the \"Images\" link from the main bing.com web page.",
}

# Some "form" codes are a family: a documented prefix followed by the 1-based position of
# the item the user clicked. Looking these up by exact value alone would lose the position,
# which is the part that says *which* suggestion was taken.
indexed_form_values = {
    "QSRE": 'Indicates the user arrived at results by having selected related search suggestion '
            'number {index} from the list at the bottom of a previous results page.',
}

indexed_form_re = re.compile(r'([A-Z]+?)(\d+)')


def explain_form_value(form_value):
    """The documented meaning of a "form" code, or None if it isn't one Unfurl knows.

    Exact matches win over the indexed families so that a code like "HDRSC1", which has its
    own entry and is not "HDRSC" item #1, keeps its specific meaning.
    """

    normalized = form_value.upper()

    explanation = form_values.get(normalized)
    if explanation:
        return explanation

    indexed_match = indexed_form_re.fullmatch(normalized)
    if indexed_match:
        prefix, index = indexed_match.groups()
        template = indexed_form_values.get(prefix)
        if template:
            return template.format(index=int(index))

    return None


def run(unfurl, node):
    if node.data_type == 'url.query.pair':
        if unfurl.preceding_domain_matches(node, 'bing.com'):

            # Many of the corresponding names of these QSPs were found on bing.com/as/init?pt...
            # Their function is not completely understood.
            if node.key == 'pq':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'"Partial" Search Query: {node.value}',
                    hover='Partial search terms entered by the user; auto-complete or suggestions <br>'
                          'may have been used to reach the actual search terms (in <b>q</b>)',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'q':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Search Query: {node.value}',
                    hover='Terms used in the Bing search', parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'cp':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Cursor Position: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'cvid':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Conversation ID',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'sc':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Suggestion Count: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'sp':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Suggestion Position: {node.value}',
                    hover='An sp of "-1" indicates no suggestion was used for the search',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'qs':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Suggestion Type: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'qsc':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Preview Pane Suggestion Type: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'sk':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Skip Value: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'skc':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Preview Pane Skip Value: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'ghc':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Ghosting: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'ds':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Data Set: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'sid':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Session ID: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'qt':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Timestamp: {node.value}',
                    hover='The name comes from Bing\'s own autosuggest config, but the value is <br>'
                          'not decoded here. Horsman (2018) reported that no embedded time and <br>'
                          'date could be located in Bing search URLs, unlike Google\'s "ei" or <br>'
                          'Yahoo\'s "ylc", so this should not be relied on as a verified timestamp.',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'ig':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Impression GUID: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'bq':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Base Query: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'nclid':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Hashed MUID: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'hgr':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Home Geographic Region: {node.value}',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'first':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Starting Result: {node.value}',
                    hover='The index of the first result shown on the page, so higher values <br>'
                          'mean the user paged further through the results. Results per page <br>'
                          'varies by Bing vertical and has changed over time (Horsman (2018) <br>'
                          'observed 10 per page for web search), so prefer this offset over a <br>'
                          'page number derived from it.',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'thid':
                thid_prefixes = {
                    'OIP': 'an image Bing had already indexed',
                    'OIF': 'an image that had been posted and indexed by Bing recently, with its '
                           'age shown in the top left of the thumbnail',
                }
                thid_explanation = thid_prefixes.get(node.value.split('.')[0].upper())
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Thumbnail ID: {node.value}',
                    hover='Identifies the specific thumbnail image the user clicked; seen <br>'
                          'alongside "form=IRPRST" when a user opened a full-size image.'
                          + (f'<br><br>This is {thid_explanation}.' if thid_explanation else ''),
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'mediaurl':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value='Full-size Image URL',
                    hover='The address of the full-size image behind the clicked thumbnail. <br>'
                          'This is the image the user actually opened, and it usually points <br>'
                          'off Bing to the site hosting it.',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'sbifnm':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Uploaded Image Filename: {node.value}',
                    hover='The file name of the image the user uploaded to run a reverse image <br>'
                          'search. This is a file name from the user\'s own system, carried in <br>'
                          'the URL.',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'iss':
                iss_values = {
                    'sbiupload': 'the user uploaded an image file to search with',
                    'sbi': 'the user ran a search by image',
                }
                iss_explanation = iss_values.get(node.value.lower())
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'Image Search Source: {node.value}',
                    hover='How the image search was started'
                          + (f': {iss_explanation}.' if iss_explanation
                             else '. This specific value is not in Unfurl\'s list of known values.'),
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'view':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'View: {node.value}',
                    hover='Which Bing view rendered the page; "detailv2" is the expanded image <br>'
                          'detail pane rather than the results grid.',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'format' and node.value.lower() == 'snrjson':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value='Response Format: JSON',
                    hover='The page asked for JSON rather than HTML, which means this URL was <br>'
                          'fetched in the background by the page itself, not typed or clicked <br>'
                          'as a top-level navigation. Worth distinguishing when attributing a <br>'
                          'request to a deliberate user action.',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key == 'jsoncbid':
                unfurl.add_to_queue(
                    data_type='descriptor', key=None, value=f'JSON Callback ID: {node.value}',
                    hover='Ties a background JSON request to the callback that consumed it; <br>'
                          'seen alongside "format=snrjson".',
                    parent_id=node.node_id, incoming_edge_config=bing_edge)

            elif node.key.lower() == 'form':
                form_explanation = explain_form_value(node.value)
                if form_explanation:
                    unfurl.add_to_queue(
                        data_type='descriptor', key=None, value=f'Navigation Code: {node.value}',
                        hover='The "form" parameter records how the user navigated to this '
                              f'page. <br><br>{form_explanation}',
                        parent_id=node.node_id, incoming_edge_config=bing_edge)
                else:
                    unfurl.add_to_queue(
                        data_type='descriptor', key=None, value=f'Navigation Code: {node.value}',
                        hover='The "form" parameter records how the user navigated to this <br>'
                              'page (which link, suggestion, or search box they used). <br>'
                              'This specific code is not in Unfurl\'s list of known values.',
                        parent_id=node.node_id, incoming_edge_config=bing_edge)
