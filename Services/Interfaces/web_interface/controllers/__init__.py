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

from tentacles.Services.Interfaces.web_interface.controllers import authentication
from tentacles.Services.Interfaces.web_interface.controllers import backtesting
from tentacles.Services.Interfaces.web_interface.controllers import commands
from tentacles.Services.Interfaces.web_interface.controllers import community
from tentacles.Services.Interfaces.web_interface.controllers import configuration
from tentacles.Services.Interfaces.web_interface.controllers import dashboard
from tentacles.Services.Interfaces.web_interface.controllers import errors
from tentacles.Services.Interfaces.web_interface.controllers import home
from tentacles.Services.Interfaces.web_interface.controllers import interface_settings
from tentacles.Services.Interfaces.web_interface.controllers import logs
from tentacles.Services.Interfaces.web_interface.controllers import medias
from tentacles.Services.Interfaces.web_interface.controllers import tentacles
from tentacles.Services.Interfaces.web_interface.controllers import terms
from tentacles.Services.Interfaces.web_interface.controllers import trading


from tentacles.Services.Interfaces.web_interface.controllers.authentication import (
    LoginForm,
    login,
    logout,
)
from tentacles.Services.Interfaces.web_interface.controllers.backtesting import (
    backtesting,
    data_collector,
)
from tentacles.Services.Interfaces.web_interface.controllers.commands import (
    commands,
)
from tentacles.Services.Interfaces.web_interface.controllers.community import (
    community,
)
from tentacles.Services.Interfaces.web_interface.controllers.configuration import (
    config,
    config_tentacle,
    metrics_settings,
    config_actions,
    is_dict,
    is_list,
    is_bool,
    tentacles_utils,
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
from tentacles.Services.Interfaces.web_interface.controllers.home import (
    home,
)
from tentacles.Services.Interfaces.web_interface.controllers.interface_settings import (
    watched_symbols,
)
from tentacles.Services.Interfaces.web_interface.controllers.logs import (
    logs,
)
from tentacles.Services.Interfaces.web_interface.controllers.medias import (
    tentacle_media,
    exchange_logo,
)
from tentacles.Services.Interfaces.web_interface.controllers.tentacles import (
    tentacles,
    tentacle_packages,
)
from tentacles.Services.Interfaces.web_interface.controllers.terms import (
    terms,
)
from tentacles.Services.Interfaces.web_interface.controllers.trading import (
    portfolio,
    portfolio_holdings,
    symbol_market_status,
    trading,
    trades,
    utility_processor,
)


__all__ = [
    "LoginForm",
    "login",
    "logout",
    "backtesting",
    "data_collector",
    "commands",
    "community",
    "config",
    "config_tentacle",
    "metrics_settings",
    "config_actions",
    "is_dict",
    "is_list",
    "is_bool",
    "tentacles_utils",
    "currency_price_graph_update",
    "first_symbol",
    "watched_symbol",
    "not_found",
    "internal_error",
    "home",
    "watched_symbols",
    "logs",
    "tentacle_media",
    "exchange_logo",
    "tentacles",
    "tentacle_packages",
    "terms",
    "portfolio",
    "portfolio_holdings",
    "symbol_market_status",
    "trading",
    "trades",
    "utility_processor",
]


def load_routes():
    from . import authentication
    from . import errors
    from . import tentacles
    from . import backtesting
    from . import commands
    from . import configuration
    from . import home
    from . import dashboard
    from . import trading
    from . import logs
    from . import interface_settings
    from . import community
    from . import medias
    from . import terms
