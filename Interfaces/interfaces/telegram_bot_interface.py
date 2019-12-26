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

from telegram.ext import CommandHandler, MessageHandler, Filters
from telegram.constants import MAX_MESSAGE_LENGTH

from octobot_services.constants import CONFIG_TELEGRAM
from octobot_interfaces.bots import EOL, UNAUTHORIZED_USER_MESSAGE
from octobot_interfaces.bots.abstract_bot_interface import AbstractBotInterface
from octobot_commons.pretty_printer import escape_markdown
from tentacles.Interfaces.services import TelegramService

# Telegram bot interface
# telegram markdown reminder: *bold*, _italic_, `code`, [text_link](http://github.com/)


class TelegramBotInterface(AbstractBotInterface):

    REQUIRED_SERVICE = TelegramService
    HANDLED_CHATS = ["private"]

    def __init__(self, config):
        super().__init__(config)
        self.telegram_service = None

    async def _post_initialize(self):
        self.telegram_service = TelegramService.instance()
        self.telegram_service.register_user(self.get_name())
        self.telegram_service.add_handlers(self.get_bot_handlers())
        self.telegram_service.add_error_handler(self.command_error)
        self.telegram_service.register_text_polling_handler(self.HANDLED_CHATS, self.echo)

    def start(self):
        self.telegram_service.start_dispatcher()

    def stop(self):
        self.telegram_service.stop()

    def get_bot_handlers(self):
        return [
            CommandHandler("start", self.command_start),
            CommandHandler("ping", self.command_ping),
            CommandHandler(["portfolio", "pf"], self.command_portfolio),
            CommandHandler(["open_orders", "oo"], self.command_open_orders),
            CommandHandler(["trades_history", "th"], self.command_trades_history),
            CommandHandler(["profitability", "pb"], self.command_profitability),
            CommandHandler(["fees", "fs"], self.command_fees),
            CommandHandler("sell_all", self.command_sell_all),
            CommandHandler("sell_all_currencies", self.command_sell_all_currencies),
            CommandHandler("set_risk", self.command_risk),
            CommandHandler(["market_status", "ms"], self.command_market_status),
            CommandHandler(["configuration", "cf"], self.command_configuration),
            CommandHandler(["refresh_real_trader", "rrt"], self.command_real_traders_refresh),
            CommandHandler(["version", "v"], self.command_version),
            CommandHandler("stop", self.command_stop),
            CommandHandler("help", self.command_help),
            CommandHandler(["pause", "resume"], self.command_pause_resume),
            MessageHandler(Filters.command, self.command_unknown)
        ]

    @staticmethod
    def command_unknown(update, _):
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, f"`Unfortunately, I don't know the command:` "
                                              f"{escape_markdown(update.effective_message.text)}.")

    @staticmethod
    def command_help(update, _):
        if TelegramBotInterface._is_valid_user(update):
            message = "* - My OctoBot skills - *" + EOL + EOL
            message += "/start: `Displays my startup message.`" + EOL
            message += "/ping: `Shows for how long I'm working.`" + EOL
            message += "/portfolio or /pf: `Displays my current portfolio.`" + EOL
            message += "/open\_orders or /oo: `Displays my current open orders.`" + EOL
            message += "/trades\_history or /th: `Displays my trades history since I started.`" + EOL
            message += "/profitability or /pb: `Displays the profitability I made since I started.`" + EOL
            message += "/market\_status or /ms: `Displays my understanding of the market and my risk parameter.`" + EOL
            message += "/fees or /fs: `Displays the total amount of fees I paid since I started.`" + EOL
            message += "/configuration or /cf: `Displays my traders, exchanges, evaluators, strategies and trading " \
                       "mode.`" + EOL
            message += "* - Trading Orders - *" + EOL
            message += "/sell\_all : `Cancels all my orders related to the currency in parameter and instantly " \
                       "liquidate my holdings in this currency for my reference market.`" + EOL
            message += "/sell\_all\_currencies : `Cancels all my orders and instantly liquidate all my currencies " \
                       "for my reference market.`" + EOL
            message += "* - Management - *" + EOL
            message += "/set\_risk: `Changes my current risk setting into your command's parameter.`" + EOL
            message += "/refresh\_real\_trader or /rrt: `Force OctoBot's real trader data refresh using exchange " \
                       "data. Should normally not be necessary.`" + EOL
            message += "/pause or /resume: `Pause or resume me.`" + EOL
            message += "/stop: `Stops me.`" + EOL
            message += "/version or /v: `Displays my current software version.`" + EOL
            message += "/help: `Displays this help.`"
            update.message.reply_markdown(message)
        elif TelegramBotInterface._is_authorized_chat(update):
            update.message.reply_text(UNAUTHORIZED_USER_MESSAGE)

    @staticmethod
    def get_command_param(command_name, update):
        return update.message.text.replace(command_name, "").strip()

    @staticmethod
    def command_start(update, _):
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, AbstractBotInterface.get_command_start(markdown=True))
        elif TelegramBotInterface._is_authorized_chat(update):
            TelegramBotInterface._send_message(update, UNAUTHORIZED_USER_MESSAGE)

    @staticmethod
    def command_stop(update, _):
        # TODO add confirmation
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, "_I'm leaving this world..._")
            AbstractBotInterface.set_command_stop()

    @staticmethod
    def command_version(update, _):
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, f"`{AbstractBotInterface.get_command_version()}`")

    def command_pause_resume(self, update, _):
        if TelegramBotInterface._is_valid_user(update):
            if self.paused:
                TelegramBotInterface._send_message(update,
                                          f"_Resuming..._{EOL}`I will restart trading when I see opportunities !`")
                self.set_command_resume()
            else:
                TelegramBotInterface._send_message(update, f"_Pausing..._{EOL}`I'm cancelling my orders.`")
                self.set_command_pause()

    @staticmethod
    def command_ping(update, _):
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, f"`{AbstractBotInterface.get_command_ping()}`")

    @staticmethod
    def command_risk(update, _):
        if TelegramBotInterface._is_valid_user(update):
            try:
                result_risk = AbstractBotInterface.set_command_risk(
                    float(TelegramBotInterface.get_command_param("/set_risk", update)))
                TelegramBotInterface._send_message(update, f"`Risk successfully set to {result_risk}.`")
            except Exception:
                TelegramBotInterface._send_message(update,
                                                   "`Failed to set new risk, please provide a number between 0 and 1.`")

    @staticmethod
    def command_profitability(update, _):
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, AbstractBotInterface.get_command_profitability(markdown=True))

    @staticmethod
    def command_fees(update, _):
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, AbstractBotInterface.get_command_fees(markdown=True))

    @staticmethod
    def command_sell_all_currencies(update, _):
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, f"`{AbstractBotInterface.get_command_sell_all_currencies()}`")

    @staticmethod
    def command_sell_all(update, _):
        if TelegramBotInterface._is_valid_user(update):
            currency = TelegramBotInterface.get_command_param("/sell_all", update)
            if not currency:
                TelegramBotInterface._send_message(update, "`Require a currency in parameter of this command.`")
            else:
                TelegramBotInterface._send_message(update, f"`{AbstractBotInterface.get_command_sell_all(currency)}`")

    @staticmethod
    def command_portfolio(update, _):
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, AbstractBotInterface.get_command_portfolio(markdown=True))

    @staticmethod
    def command_open_orders(update, _):
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, AbstractBotInterface.get_command_open_orders(markdown=True))

    @staticmethod
    def command_trades_history(update, _):
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, AbstractBotInterface.get_command_trades_history(markdown=True))

    # refresh current order lists and portfolios and reload tham from exchanges
    @staticmethod
    def command_real_traders_refresh(update, _):
        if TelegramBotInterface._is_valid_user(update):
            result = "Refresh"
            try:
                AbstractBotInterface.set_command_real_traders_refresh()
                TelegramBotInterface._send_message(update, f"`{result} successful`")
            except Exception as e:
                TelegramBotInterface._send_message(update, f"`{result} failure: {e}`")

    # Displays my trades, exchanges, evaluators, strategies and trading
    @staticmethod
    def command_configuration(update, _):
        if TelegramBotInterface._is_valid_user(update):
            try:
                TelegramBotInterface._send_message(update, AbstractBotInterface.get_command_configuration(markdown=True))
            except Exception:
                TelegramBotInterface._send_message(update,
                                                   "`I'm unfortunately currently unable to show you my configuration. "
                                                  "Please wait for my initialization to complete.`")

    @staticmethod
    def command_market_status(update, _):
        if TelegramBotInterface._is_valid_user(update):
            try:
                TelegramBotInterface._send_message(update,
                                                   AbstractBotInterface.get_command_market_status(markdown=True))
            except Exception:
                TelegramBotInterface._send_message(update, "`I'm unfortunately currently unable to show you my market "
                                                  "evaluations, please retry in a few seconds.`")

    @staticmethod
    def command_error(update, _, error=None):
        TelegramBotInterface.get_logger().exception(error)
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update,
                                      f"Failed to perform this command {update.message.text} : `{error}`")

    @staticmethod
    def echo(_, update):
        if TelegramBotInterface._is_valid_user(update):
            TelegramBotInterface._send_message(update, update.effective_message["text"], markdown=False)

    @staticmethod
    def enable(config, is_enabled, associated_config=CONFIG_TELEGRAM):
        AbstractBotInterface.enable(config, is_enabled, associated_config=associated_config)

    @staticmethod
    def is_enabled(config, associated_config=CONFIG_TELEGRAM):
        return AbstractBotInterface.is_enabled(config, associated_config=associated_config)

    @staticmethod
    def _is_authorized_chat(update):
        return update.effective_chat["type"] in TelegramBotInterface.HANDLED_CHATS

    @staticmethod
    def _is_valid_user(update, associated_config=CONFIG_TELEGRAM):

        # only authorize users from a private chat
        if not TelegramBotInterface._is_authorized_chat(update):
            return False

        update_username = update.effective_chat["username"]

        is_valid, white_list = AbstractBotInterface._is_valid_user(update_username, associated_config=associated_config)

        if white_list and not is_valid:
            TelegramBotInterface.get_logger().error(f"An unauthorized Telegram user is trying to talk to me: username: "
                                           f"{update_username}, first_name: {update.effective_chat['first_name']}, "
                                           f"text: {update.effective_message['text']}")

        return is_valid

    @staticmethod
    def _send_message(update, message, markdown=True):
        messages = AbstractBotInterface._split_messages_if_too_long(message, MAX_MESSAGE_LENGTH, EOL)
        for m in messages:
            if markdown:
                update.message.reply_markdown(m)
            else:
                update.message.reply_text(m)
