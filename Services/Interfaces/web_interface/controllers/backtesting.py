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
import werkzeug

import tentacles.Services.Interfaces.web_interface as web_interface
import tentacles.Services.Interfaces.web_interface.login as login
import tentacles.Services.Interfaces.web_interface.models as models
import tentacles.Services.Interfaces.web_interface.util as util


@web_interface.server_instance.route("/backtesting")
@web_interface.server_instance.route('/backtesting', methods=['GET', 'POST'])
@login.login_required_when_activated
def backtesting():
    if flask.request.method == 'POST':
        action_type = flask.request.args["action_type"]
        success = False
        reply = "Action failed"
        if action_type == "start_backtesting":
            files = flask.request.get_json()
            source = flask.request.args["source"]
            run_on_common_part_only = flask.request.args.get("run_on_common_part_only", "true") == "true"
            reset_tentacle_config = flask.request.args.get("reset_tentacle_config", False)
            success, reply = models.start_backtesting_using_specific_files(files,
                                                                           source,
                                                                           reset_tentacle_config,
                                                                           run_on_common_part_only)
        if success:
            web_interface.send_backtesting_status()
            return util.get_rest_reply(flask.jsonify(reply))
        else:
            return util.get_rest_reply(reply, 500)

    elif flask.request.method == 'GET':
        if flask.request.args:
            target = flask.request.args["update_type"]
            if target == "backtesting_report":
                source = flask.request.args["source"]
                backtesting_report = models.get_backtesting_report(source)
                return flask.jsonify(backtesting_report)

        else:
            return flask.render_template('backtesting.html',
                                         activated_trading_mode=models.get_config_activated_trading_mode(),
                                         data_files=models.get_data_files_with_description())


@web_interface.server_instance.route("/data_collector")
@web_interface.server_instance.route('/data_collector', methods=['GET', 'POST'])
@login.login_required_when_activated
def data_collector():
    if flask.request.method == 'POST':
        action_type = flask.request.args["action_type"]
        success = False
        reply = "Action failed"
        if action_type == "delete_data_file":
            file = flask.request.get_json()
            success, reply = models.get_delete_data_file(file)
        elif action_type == "start_collector":
            details = flask.request.get_json()
            success, reply = models.collect_data_file(details["exchange"], details["symbol"])
        elif action_type == "import_data_file":
            if flask.request.files:
                file = flask.request.files['file']
                name = werkzeug.utils.secure_filename(flask.request.files['file'].filename)
                success, reply = models.save_data_file(name, file)
                alert = {"success": success, "message": reply}
            else:
                alert = {}
            current_exchange = models.get_current_exchange()

            # here return template to force page reload because of file upload via input form
            return flask.render_template('data_collector.html',
                                         data_files=models.get_data_files_with_description(),
                                         ccxt_exchanges=sorted(models.get_full_exchange_list()),
                                         current_exchange=models.get_current_exchange(),
                                         full_symbol_list=sorted(models.get_symbol_list([current_exchange])),
                                         alert=alert)
        if success:
            return util.get_rest_reply(flask.jsonify(reply))
        else:
            return util.get_rest_reply(reply, 500)

    elif flask.request.method == 'GET':
        origin_page = None
        if flask.request.args:
            action_type_key = "action_type"
            if action_type_key in flask.request.args:
                target = flask.request.args[action_type_key]
                if target == "symbol_list":
                    exchange = flask.request.args.get('exchange')
                    return flask.jsonify(sorted(models.get_symbol_list([exchange])))
            from_key = "from"
            if from_key in flask.request.args:
                origin_page = flask.request.args[from_key]

        current_exchange = models.get_current_exchange()
        return flask.render_template('data_collector.html',
                                     data_files=models.get_data_files_with_description(),
                                     ccxt_exchanges=sorted(models.get_full_exchange_list()),
                                     current_exchange=models.get_current_exchange(),
                                     full_symbol_list=sorted(models.get_symbol_list([current_exchange])),
                                     origin_page=origin_page,
                                     alert={})
