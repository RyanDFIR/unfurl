#!/usr/bin/env python3

# Copyright 2024 Ryan Benson
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


from flask import Flask, render_template, request, redirect, url_for
from flask_cors import CORS
from flask_restx import Api, Namespace, Resource
from urllib.parse import unquote
from unfurl.core import load_config, resolve_remote_lookups, run

unfurl_app_host = None
unfurl_app_port = None
unfurl_remote_lookups = None
app = Flask(__name__)
CORS(app)


class UnfurlApp:
    def __init__(self, unfurl_debug=False, unfurl_host='localhost', unfurl_port=5000, remote_lookups=False):
        self.unfurl_debug = unfurl_debug
        self.unfurl_host = unfurl_host
        self.unfurl_port = unfurl_port
        self.remote_lookups = remote_lookups

        global unfurl_app_host
        global unfurl_app_port
        global unfurl_remote_lookups
        unfurl_app_host = self.unfurl_host
        unfurl_app_port = self.unfurl_port
        unfurl_remote_lookups = self.remote_lookups

        app.config['remote_lookups'] = remote_lookups
        app.run(debug=unfurl_debug, host=unfurl_host, port=unfurl_port)


@app.route('/')
@app.route('/<path:path>')
def index(path=''):
    url_to_unfurl = ''
    if path:
        # backward compatibility, it is preferable to use the graph route and a quoted URL instead
        if f':{unfurl_app_port}/' in request.url:
            url_to_unfurl = unquote(request.url.split(f':{unfurl_app_port}/', 1)[1])
        else:
            # for tests, the port isn't in the URL, take everything after the domain
            url_to_unfurl = unquote(request.url.split('/', 3)[-1])
        return redirect(url_for('graph', url=url_to_unfurl))
    return render_template('graph.html',
                           unfurl_host=unfurl_app_host,
                           unfurl_port=unfurl_app_port)


@app.route('/graph')
def graph():
    if 'url' not in request.args:
        return redirect(url_for('index'))
    return render_template('graph.html',
                           unfurl_host=unfurl_app_host,
                           unfurl_port=unfurl_app_port)


restx_api = Api(app, title='Unfurl API',
                description='API to submit URLs to expand to an unfurl instance.',
                doc='/doc/')
namespace = Namespace('GenericAPI', description='Generic unfurl API', path='/')
restx_api.add_namespace(namespace)


@namespace.route('/json/visjs')
@namespace.doc(description='Expand a URL and returns the JSON expansion in the vis.js format')
class JsonVisJS(Resource):

    @namespace.param('url', 'The URL to expand', required=False)
    def get(self):
        if 'url' not in request.args:
            return {}
        unfurl_this = request.args['url']
        return run(
            unfurl_this,
            return_type='json',
            remote_lookups=app.config['remote_lookups'],
            extra_options={'widthConstraint': {'maximum': 1200}})


def web_app(host='localhost', port='5000', debug='True', remote_lookups=False):

    config = load_config()
    remote_lookups = resolve_remote_lookups(explicit=remote_lookups, config=config)

    if config.has_section('UNFURL_APP'):
        # Fall back to the caller's values for anything the config doesn't set, rather
        # than overriding them with None.
        host = config['UNFURL_APP'].get('host', host)
        port = config['UNFURL_APP'].get('port', port)
        debug = config['UNFURL_APP'].getboolean('debug', debug)

    UnfurlApp(
        unfurl_debug=debug,
        unfurl_host=host,
        unfurl_port=port,
        remote_lookups=remote_lookups)
