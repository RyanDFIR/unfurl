# Copyright 2022 Google LLC
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

utm_edge = {
    'color': {
        'color': '#7b0004'
    },
    'title': 'Analytics & Tracking Functions',
    'label': '👀'
}


def run(unfurl, node):
    # All analytics trackers in this parser are QSPs
    if node.data_type != 'url.query.pair':
        return

    # Google Analytics / Urchin Tracking Module
    # References:
    #   https://ga-dev-tools.web.app/campaign-url-builder/
    #   https://en.wikipedia.org/wiki/UTM_parameters
    #   https://support.google.com/urchin/answer/2633697

    elif node.key == 'utm_source':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Identifies which site sent the traffic (search engine, newsletter, etc)',
            hover='UTM (Urchin Tracking Module) parameters are used by websites to track effectiveness of '
                  'marketing campaigns. Unfurl\'s descriptions are of what each parameter is typically used '
                  'for, but site owners can customize them.',
            parent_id=node.node_id, incoming_edge_config=utm_edge)

    elif node.key == 'utm_medium':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Identifies the type of link clicked (email, cpc, etc)',
            hover='UTM (Urchin Tracking Module) parameters are used by websites to track effectiveness of '
                  'marketing campaigns. Unfurl\'s descriptions are of what each parameter is typically used '
                  'for, but site owners can customize them.',
            parent_id=node.node_id, incoming_edge_config=utm_edge)

    elif node.key == 'utm_campaign':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Identifies the specific product promotion or strategic campaign',
            hover='UTM (Urchin Tracking Module) parameters are used by websites to track effectiveness of '
                  'marketing campaigns. Unfurl\'s descriptions are of what each parameter is typically used '
                  'for, but site owners can customize them.',
            parent_id=node.node_id, incoming_edge_config=utm_edge)

    elif node.key == 'utm_content':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Identifies what the user clicked (text_link, top_banner, etc)',
            hover='UTM (Urchin Tracking Module) parameters are used by websites to track effectiveness of '
                  'marketing campaigns. Unfurl\'s descriptions are of what each parameter is typically used '
                  'for, but site owners can customize them.',
            parent_id=node.node_id, incoming_edge_config=utm_edge)

    elif node.key == 'utm_term':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Identifies search terms',
            hover='UTM (Urchin Tracking Module) parameters are used by websites to track effectiveness of '
                  'marketing campaigns. Unfurl\'s descriptions are of what each parameter is typically used '
                  'for, but site owners can customize them.',
            parent_id=node.node_id, incoming_edge_config=utm_edge)

    elif node.key == 'utm_id':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Single UTM "master" code used instead of multiple other utm_* parameters',
            hover='UTM (Urchin Tracking Module) parameters are used by websites to track effectiveness of '
                  'marketing campaigns. Unfurl\'s descriptions are of what each parameter is typically used '
                  'for, but site owners can customize them.',
            parent_id=node.node_id, incoming_edge_config=utm_edge)

    # Google Analytics
    # References:
    #  https://support.google.com/searchads/answer/6292795

    elif node.key == 'gclid':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Google Click ID',
            hover='Unique click ID appended by Google Ads. Contents appear to be a base64-encoded protobuf; one of '
                  'the values inside it appears to be a timestamp, but the exact meaning is unknown.',
            parent_id=node.node_id, incoming_edge_config=utm_edge)

    elif node.key == 'dclid':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Google Enhanced Attribution',
            hover='Used by Google\'s Campaign Manager 360 for "Enhanced Attribution". Contents appear to be a '
                  'base64-encoded protobuf; one of the values inside it appears to be a timestamp, but the exact '
                  'meaning is unknown.',
            parent_id=node.node_id, incoming_edge_config=utm_edge)

    # Microsoft
    # References:
    #  https://help.ads.microsoft.com/apex/index/3/en/60000

    elif node.key == 'msclkid':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Microsoft Click ID (unique)',
            hover='Unique Click ID added by Microsoft Advertising when auto-tagging is enabled. '
                  '<a href="https://help.ads.microsoft.com/#apex/ads/en/60000/2-500" target="_blank">[ref]</a>',
            parent_id=node.node_id, incoming_edge_config=utm_edge)

    # Adobe
    # References:
    #  https://experienceleague.adobe.com/docs/analytics/integration/advertising-analytics/advertising-analytics-
    #  workflow/aa-manual-vs-automatic-tracking.html?lang=en

    elif node.key == 's_kwcid':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Adobe Analytics Keyword Campaign ID',
            hover='Campaign tracking code for Adobe Analytics. Two known variations so far based on the 3rd value: '
                  '"3" for Google and "10" for Bing.',
            parent_id=node.node_id, incoming_edge_config=utm_edge)

    # Facebook
    elif node.key == 'fbclid':
        unfurl.add_to_queue(
            data_type='descriptor', key=None,
            value='Facebook Click ID',
            hover='This URL was likely the result of clicking an external link on Facebook or Instagram. '
                  '<b>fbclid</b> is a click identifier Meta adds to outgoing links for ad attribution and '
                  'analytics. Newer ones contain readable fields, including a timestamp.',
            parent_id=node.node_id, incoming_edge_config=utm_edge)
