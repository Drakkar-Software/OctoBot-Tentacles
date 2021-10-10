#  Drakkar-Software OctoBot-Interfaces
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.

import flask
import urllib.parse as url_parse


def get_rest_reply(json_message, code=200, content_type="application/json"):
    resp = flask.make_response(json_message, code)
    resp.headers['Content-Type'] = content_type
    return resp


def get_next_url_or_redirect(default_redirect="home"):
    next_url = flask.request.args.get('next')
    if not is_safe_url(next_url):
        return flask.abort(400)
    return flask.redirect(next_url or flask.url_for(default_redirect))


def is_safe_url(target):
    ref_url = url_parse.urlparse(flask.request.host_url)
    test_url = url_parse.urlparse(url_parse.urljoin(flask.request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
        ref_url.netloc == test_url.netloc
