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
import flask_wtf
import wtforms.fields.html5

import octobot.constants as constants
import octobot.community as community
import octobot_services.interfaces.util as interfaces_util
import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.login as login


@web_interface.server_instance.route('/community_login', methods=['GET', 'POST'])
@login.login_required_when_activated
def community_login():
    authenticator = interfaces_util.get_bot_api().get_community_auth()
    logged_in_email = form = None
    try:
        logged_in_email = authenticator.get_logged_in_email()
    except community.AuthenticationRequired:
        pass
    except Exception as e:
        flask.flash(f"Error when contacting the community server: {e}", "error")
    if logged_in_email is None:
        form = CommunityLoginForm(flask.request.form) if flask.request.form else CommunityLoginForm()
        if form.validate_on_submit():
            try:
                authenticator.login(form.email.data, form.password.data)
                logged_in_email = form.email.data
                flask.flash(f"Authenticated as {form.email.data}", "success")
            except community.FailedAuthentication:
                flask.flash(f"Invalid email or password", "error")
            except Exception as e:
                flask.flash(f"Error during authentication: {e}", "error")
    return flask.render_template('community_login.html',
                                 form=form,
                                 current_logged_in_email=logged_in_email,
                                 community_url=constants.OCTOBOT_COMMUNITY_URL)


@web_interface.server_instance.route("/community_logout")
@login.login_required_when_activated
def community_logout():
    interfaces_util.get_bot_api().get_community_auth().logout()
    return flask.redirect(flask.url_for('community_login'))


class CommunityLoginForm(flask_wtf.FlaskForm):
    email = wtforms.fields.html5.EmailField('Email', [wtforms.validators.InputRequired()])
    password = wtforms.PasswordField('Password', [wtforms.validators.InputRequired()])
    remember_me = wtforms.BooleanField('Remember me', default=True)
