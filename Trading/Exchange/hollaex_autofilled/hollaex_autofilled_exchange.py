#  Drakkar-Software OctoBot-Tentacles
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
import requests

import octobot_commons.logging as commons_logging
import octobot_trading.exchanges as exchanges
import octobot_trading.errors as errors
from ..hollaex.hollaex_exchange import hollaex


class HollaexAutofilled(hollaex):
    HAS_FETCHED_DETAILS = True

    @staticmethod
    def supported_autofill_exchanges(tentacle_config):
        return list(tentacle_config["auto_filled"]) if tentacle_config else []

    @classmethod
    def init_user_inputs_from_class(cls, inputs: dict) -> None:
        pass

    @classmethod
    async def get_autofilled_exchange_details(cls, aiohttp_session, tentacle_config, exchange_name):
        kit_details = await aiohttp_session.get(HollaexAutofilled._get_kit_url(tentacle_config, exchange_name))
        return HollaexAutofilled._parse_autofilled_exchange_details(
            tentacle_config, await kit_details.json(), exchange_name
        )

    def _fetch_details(self, config, exchange_manager):
        try:
            exchange_kit_url = self._get_kit_url(self.tentacle_config, exchange_manager.exchange_name)
        except KeyError:
            raise errors.NotSupported(f"{exchange_manager.exchange_name} is not supported by {self.get_name()}")
        self._apply_config(
            self._parse_autofilled_exchange_details(
                self.tentacle_config,
                requests.get(exchange_kit_url).json(),
                exchange_manager.exchange_name
            )
        )

    def _supports_autofill(self, exchange_name):
        try:
            self._get_kit_url(self.tentacle_config, exchange_name)
            return True
        except KeyError:
            return False

    @staticmethod
    def _get_kit_url(tentacle_config, exchange_name):
        return HollaexAutofilled._get_autofilled_config(tentacle_config, exchange_name)["url"]

    @staticmethod
    def _has_websocket(tentacle_config, exchange_name):
        return HollaexAutofilled._get_autofilled_config(tentacle_config, exchange_name).get("websockets", False)

    @staticmethod
    def _get_autofilled_config(tentacle_config, exchange_name):
        return tentacle_config["auto_filled"][exchange_name]

    @classmethod
    def _parse_autofilled_exchange_details(cls, tentacle_config, kit_details, exchange_name):
        """
        use /kit to fill in exchange details
        format:
        {
            "api_name": "BitcoinRD Exchange",
            "black_list_countries": [],
            "captcha": {},
            "color": {
                "Black": {
                    "base_background": "#000000",
                    ...
                }
            },
            "defaults": {
                "country": "DO",
                "language": "es",
                "theme": "dark"
            },
            "description": "Primer Exchange 100% Dominicano.",
            "dust": {
                "maker_id": 1,
                "quote": "xht",
                "spread": 0
            },
            "email_verification_required": true,
            "features": {
                "chat": false,
                ...
            },
            "icons": {
                "dark": {
                    "DOP_ICON": "https://bitholla.s3.ap-northeast-2.amazonaws.com/exchange/bitcoinrdexchange/DOP_ICON__dark___1631209668172.png",
                    ...
                },
                "white": {
                    "EXCHANGE_FAV_ICON": "https://bitholla.s3.ap-northeast-2.amazonaws.com/exchange/bitcoinrdexchange/EXCHANGE_FAV_ICON__white___1615349464540.png",
                    ...
                }
            },
            "info": {
                "active": true,
                "collateral_level": "member",
                "created_at": "2021-03-09T14:12:49.012Z",
                "exchange_id": 1512,
                "expiry": "2023-08-27T23:59:59.000Z",
                "initialized": true,
                "is_trial": false,
                "name": "bitcoinrdexchange",
                "period": "year",
                "plan": "fiat",
                "status": true,
                "type": "Cloud",
                "url": "https://api.bitcoinrd.do",
                "user_id": 3536
            },
            "injected_html": {
                "body": "",
                "head": ""
            },
            "injected_values": [],
            "interface": {},
            "links": {
                "api": "https://api.bitcoinrd.do",
                "contact": "",
                "facebook": "",
                "github": "",
                "helpdesk": "mailto:soporte@bitcoinrd.do",
                "information": "",
                "instagram": "",
                "linkedin": "",
                "privacy": "https://bitcoinrd.online/privacy-policy/",
                "referral_label": "Powered by BitcoinRD",
                "referral_link": "https://bitcoinrd.online/",
                "section_1": {
                    "content": {
                        "instagram": "https://www.instagram.com/bitcoinrd/"
                    },
                    "header": {
                        "column_header_1": "RRSS"
                    }
                },
                "section_2": "",
                "telegram": "",
                "terms": "https://bitcoinrd.online/terms/",
                "twitter": "",
                "website": "",
                "whitepaper": ""
            },
            "logo_image": "https://bitholla.s3.ap-northeast-2.amazonaws.com/exchange/bitcoinrdexchange/EXCHANGE_LOGO__dark___1615345052424.png",
            "meta": {
                "default_digital_assets_sort": "change",
                ...
                },
                "versions": {
                    "color": "color-1681492596812",
                    ...
                }
            },
            "native_currency": "usdt",
            "new_user_is_activated": true,
            "offramp": {...},
            "onramp": {...},
            "setup_completed": true,
            "strings": {
                "en": { ...}
            },
            "title": "",
            "user_meta": {},
            "user_payments": {},
            "valid_languages": "en,es,fr"
        }
        """
        return exchanges.ExchangeDetails(
            exchange_name,
            kit_details["api_name"],
            kit_details["links"]["referral_link"],
            kit_details["links"]["api"],
            kit_details["logo_image"],
            HollaexAutofilled._has_websocket(
                tentacle_config,
                exchange_name
            )
        )

    def _apply_config(self, autofilled_exchange_details: exchanges.ExchangeDetails):
        self.logger = commons_logging.get_logger(autofilled_exchange_details.name)
        self.tentacle_config[self.REST_KEY] = autofilled_exchange_details.api
        self.tentacle_config[self.HAS_WEBSOCKETS_KEY] = autofilled_exchange_details.has_websocket

    @classmethod
    def is_supporting_sandbox(cls) -> bool:
        return False

    def get_rest_name(self):
        return hollaex.get_name()

    def get_associated_websocket_exchange_name(self):
        return self.get_name()

    @classmethod
    def get_name(cls):
        return cls.__name__
