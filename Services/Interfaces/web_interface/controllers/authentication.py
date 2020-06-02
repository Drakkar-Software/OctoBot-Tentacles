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
from flask import request, abort, url_for, redirect, render_template
from flask_login import login_user, logout_user, login_required
from flask_wtf import FlaskForm
from wtforms import PasswordField, BooleanField

from tentacles.Services.Interfaces.web_interface import server_instance
from tentacles.Services.Interfaces.web_interface.login.web_login_manager import GENERIC_USER, reset_attempts, \
    register_attempt
from tentacles.Services.Interfaces.web_interface.security import is_safe_url


@server_instance.route('/login', methods=['GET', 'POST'])
def login():
    # use default constructor to apply default values when no form in request
    form = LoginForm(request.form) if request.form else LoginForm()
    if form.validate_on_submit():
        if server_instance.login_manager.is_valid_password(request.remote_addr, form.password.data):
            GENERIC_USER.is_authenticated = True
            login_user(GENERIC_USER, remember=form.remember_me.data)
            reset_attempts(request.remote_addr)

            return _get_next_url_or_home_redirect()
        if register_attempt(request.remote_addr):
            form.password.errors.append('Invalid password')
        else:
            form.password.errors.append('Too many attempts. Please restart your OctoBot to be able to login.')
    return render_template('login.html', form=form)


@server_instance.route("/logout")
@login_required
def logout():
    logout_user()
    return _get_next_url_or_home_redirect()


def _get_next_url_or_home_redirect():
    next_url = request.args.get('next')
    if not is_safe_url(next_url):
        return abort(400)
    return redirect(next_url or url_for('home'))


class LoginForm(FlaskForm):
    password = PasswordField('Password')
    remember_me = BooleanField('Remember me', default=True)
