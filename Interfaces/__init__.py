from octobot_tentacles_manager.api.inspector import check_tentacle_version
from octobot_commons.logging.logging_util import get_logger

if check_tentacle_version('1.2.0', 'web_interface', 'OctoBot-Default-Tentacles'):
    try:
        from .web_interface import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading web_interface: {e}')

if check_tentacle_version('1.2.0', 'telegram_bot_interface', 'OctoBot-Default-Tentacles'):
    try:
        from .telegram_bot_interface import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading telegram_bot_interface: {e}')
