from octobot_tentacles_manager.api.inspector import check_tentacle_version
from octobot_commons.logging.logging_util import get_logger

if check_tentacle_version('1.2.0', 'exchange_history_collector', 'OctoBot-Default-Tentacles'):
    try:
        from .exchange_history_collector import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading exchange_history_collector: {e}')

if check_tentacle_version('1.2.0', 'exchange_live_collector', 'OctoBot-Default-Tentacles'):
    try:
        from .exchange_live_collector import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading exchange_live_collector: {e}')
