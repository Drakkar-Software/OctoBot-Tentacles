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
from functools import wraps
from flask_login import LoginManager, login_required

from octobot_commons.config_manager import get_password_hash
from tentacles.Services.Interfaces.web_interface.login.user import User

GENERIC_USER = User()
IS_LOGIN_REQUIRED = True
IP_TO_CONNECTION_ATTEMPTS = {}
MAX_CONNECTION_ATTEMPTS = 10


class WebLoginManager(LoginManager):
    def __init__(self, flask_app, requires_login, password_hash):
        LoginManager.__init__(self)
        global IS_LOGIN_REQUIRED
        IS_LOGIN_REQUIRED = requires_login
        self.init_app(flask_app)
        self.password_hash = password_hash
        # register login view to redirect to when login is required
        self.login_view = "login"
        self._register_callbacks()

    def is_valid_password(self, ip, password):
        return not is_banned(ip) and get_password_hash(password) == self.password_hash

    def _register_callbacks(self):
        @self.user_loader
        def load_user(_):
            # return None if user is invalid
            return GENERIC_USER


@login_required
def _login_required_func(func, *args, **kwargs):
    return func(*args, **kwargs)


def login_required_when_activated(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if IS_LOGIN_REQUIRED:
            return _login_required_func(func, *args, **kwargs)
        return func(*args, **kwargs)
    return decorated_view


def register_attempt(ip):
    if ip in IP_TO_CONNECTION_ATTEMPTS:
        IP_TO_CONNECTION_ATTEMPTS[ip] += 1
    else:
        IP_TO_CONNECTION_ATTEMPTS[ip] = 1
    return not is_banned(ip)


def is_banned(ip):
    if ip in set(IP_TO_CONNECTION_ATTEMPTS.keys()):
        return IP_TO_CONNECTION_ATTEMPTS[ip] >= 10
    return False


def reset_attempts(ip):
    IP_TO_CONNECTION_ATTEMPTS[ip] = 0
