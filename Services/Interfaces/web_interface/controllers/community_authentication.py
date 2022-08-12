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
import wtforms.fields

import octobot_commons.authentication as authentication
import octobot_services.interfaces.util as interfaces_util
import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models


@web_interface.server_instance.route('/community_login', methods=['GET', 'POST'])
@login.login_required_when_activated
def community_login():
    authenticator = authentication.Authenticator.instance()
    logged_in_email = form = None
    try:
        logged_in_email = authenticator.get_logged_in_email()
    except authentication.AuthenticationRequired:
        pass
    except Exception as e:
        flask.flash(f"Error when contacting the community server: {e}", "error")
    if logged_in_email is None:
        form = CommunityLoginForm(flask.request.form) if flask.request.form else CommunityLoginForm()
        if form.validate_on_submit():
            try:
                interfaces_util.run_in_bot_main_loop(
                    authenticator.login(form.email.data, form.password.data),
                    log_exceptions=False
                )
                logged_in_email = form.email.data
                return flask.redirect('community')
            except authentication.FailedAuthentication:
                flask.flash(f"Invalid email or password", "error")
            except Exception as e:
                flask.flash(f"Error during authentication: {e}", "error")
    return flask.render_template('community_login.html',
                                 form=form,
                                 current_logged_in_email=logged_in_email,
                                 current_bots_stats=models.get_current_octobots_stats())


@web_interface.server_instance.route("/community_logout")
@login.login_required_when_activated
def community_logout():
    if authentication.Authenticator.instance().must_be_authenticated_through_authenticator():
        # can't logout when authentication is required
        return flask.redirect(flask.url_for('community'))
    authentication.Authenticator.instance().logout()
    return flask.redirect(flask.url_for('community_login'))


class CommunityLoginForm(flask_wtf.FlaskForm):
    email = wtforms.fields.EmailField('Email', [wtforms.validators.InputRequired()])
    password = wtforms.PasswordField('Password', [wtforms.validators.InputRequired()])
    remember_me = wtforms.BooleanField('Remember me', default=True)
