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

from tentacles.Services.Interfaces.web_interface.controllers import octobot_authentication
from tentacles.Services.Interfaces.web_interface.controllers import community_authentication
from tentacles.Services.Interfaces.web_interface.controllers import backtesting
from tentacles.Services.Interfaces.web_interface.controllers import commands
from tentacles.Services.Interfaces.web_interface.controllers import community
from tentacles.Services.Interfaces.web_interface.controllers import configuration
from tentacles.Services.Interfaces.web_interface.controllers import dashboard
from tentacles.Services.Interfaces.web_interface.controllers import errors
from tentacles.Services.Interfaces.web_interface.controllers import octobot_help
from tentacles.Services.Interfaces.web_interface.controllers import home
from tentacles.Services.Interfaces.web_interface.controllers import interface_settings
from tentacles.Services.Interfaces.web_interface.controllers import logs
from tentacles.Services.Interfaces.web_interface.controllers import medias
from tentacles.Services.Interfaces.web_interface.controllers import terms
from tentacles.Services.Interfaces.web_interface.controllers import trading
from tentacles.Services.Interfaces.web_interface.controllers import profiles


from tentacles.Services.Interfaces.web_interface.controllers.octobot_authentication import (
    LoginForm,
    login,
    logout,
)
from tentacles.Services.Interfaces.web_interface.controllers.community_authentication import (
    CommunityLoginForm,
    community_login,
    community_logout,
)
from tentacles.Services.Interfaces.web_interface.controllers.community import (
    community_metrics,
)
from tentacles.Services.Interfaces.web_interface.controllers.backtesting import (
    data_collector,
)
from tentacles.Services.Interfaces.web_interface.controllers.logs import (
    export_logs,
)
from tentacles.Services.Interfaces.web_interface.controllers.commands import (
    about,
)
from tentacles.Services.Interfaces.web_interface.controllers.configuration import (
    config,
    profile,
    profiles_management,
    accounts,
    config_tentacle,
    config_tentacles,
    metrics_settings,
    config_actions,
)
from tentacles.Services.Interfaces.web_interface.controllers.dashboard import (
    currency_price_graph_update,
    first_symbol,
    watched_symbol,
)
from tentacles.Services.Interfaces.web_interface.controllers.errors import (
    not_found,
    internal_error,
)
from tentacles.Services.Interfaces.web_interface.controllers.interface_settings import (
    watched_symbols,
)
from tentacles.Services.Interfaces.web_interface.controllers.medias import (
    tentacle_media,
    profile_media,
    exchange_logo,
)
from tentacles.Services.Interfaces.web_interface.controllers.trading import (
    portfolio,
    symbol_market_status,
    trades,
    utility_processor,
)
from tentacles.Services.Interfaces.web_interface.controllers.profiles import (
    profiles_selector,
)


__all__ = [
    "CommunityLoginForm",
    "community_login",
    "community_logout",
    "LoginForm",
    "login",
    "logout",
    "backtesting",
    "data_collector",
    "commands",
    "about",
    "community",
    "community_metrics",
    "profile",
    "profiles_management",
    "config",
    "accounts",
    "config_tentacle",
    "config_tentacles",
    "metrics_settings",
    "config_actions",
    "currency_price_graph_update",
    "first_symbol",
    "watched_symbol",
    "not_found",
    "internal_error",
    "home",
    "octobot_help",
    "watched_symbols",
    "logs",
    "export_logs",
    "tentacle_media",
    "profile_media",
    "exchange_logo",
    "terms",
    "portfolio",
    "symbol_market_status",
    "trading",
    "trades",
    "utility_processor",
    "profiles_selector",
]
