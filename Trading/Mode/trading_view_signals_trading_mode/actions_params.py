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
import decimal
import math
import typing
import json
import copy
import enum
import dataclasses

import async_channel.channels as channels
import octobot_commons.symbols.symbol_util as symbol_util
import octobot_commons.enums as commons_enums
import octobot_commons.constants as commons_constants
import octobot_commons.signals as commons_signals
import octobot_commons.tentacles_management as tentacles_management
import octobot_commons.dataclasses
import octobot_services.api as services_api
import octobot_trading.personal_data as trading_personal_data
try:
    import tentacles.Services.Services_feeds.trading_view_service_feed as trading_view_service_feed
except ImportError:
    if commons_constants.USE_MINIMAL_LIBS:
        # mock trading_view_service_feed imports
        class TradingViewServiceFeedImportMock:
            class TradingViewServiceFeed:
                def get_name(self, *args, **kwargs):
                    raise ImportError("trading_view_service_feed not installed")
    trading_view_service_feed = TradingViewServiceFeedImportMock()
import tentacles.Trading.Mode.daily_trading_mode.daily_trading as daily_trading_mode
import octobot_trading.constants as trading_constants
import octobot_trading.enums as trading_enums
import octobot_trading.exchanges as trading_exchanges
import octobot_trading.modes as trading_modes
import octobot_trading.errors as trading_errors
import octobot_trading.modes.script_keywords as script_keywords
import octobot_trading.blockchain_wallets as blockchain_wallets


@dataclasses.dataclass
class EnsureExchangeBalanceParams(octobot_commons.dataclasses.FlexibleDataclass):
    asset: str
    holdings: float


@dataclasses.dataclass
class EnsureBlockchainWalletBalanceParams(octobot_commons.dataclasses.FlexibleDataclass):
    asset: str
    holdings: float
    wallet_details: blockchain_wallets.BlockchainWalletParameters # details of the wallet to transfer from


@dataclasses.dataclass
class WithdrawFundsParams(octobot_commons.dataclasses.FlexibleDataclass):
    asset: str
    amount: float
    address: str # recipient address of the withdrawal
    tag: str = ""
    params: dict = dataclasses.field(default_factory=dict) # extra parameters specific to the exchange API endpoint


@dataclasses.dataclass
class TransferFundsParams(octobot_commons.dataclasses.FlexibleDataclass):
    asset: str
    amount: float
    address: str # recipient address of the transfer
    wallet_details: blockchain_wallets.BlockchainWalletParameters # details of the wallet to transfer from
