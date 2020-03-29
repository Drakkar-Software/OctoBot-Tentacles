from octobot_tentacles_manager.api.inspector import check_tentacle_version
from octobot_commons.logging.logging_util import get_logger

if check_tentacle_version('1.2.0', 'reddit_service', 'OctoBot-Default-Tentacles'):
    try:
        from .reddit_service import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading reddit_service: {e}')

if check_tentacle_version('1.2.0', 'telegram_service', 'OctoBot-Default-Tentacles'):
    try:
        from .telegram_service import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading telegram_service: {e}')

if check_tentacle_version('1.2.0', 'twitter_service', 'OctoBot-Default-Tentacles'):
    try:
        from .twitter_service import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading twitter_service: {e}')

if check_tentacle_version('1.2.0', 'web_service', 'OctoBot-Default-Tentacles'):
    try:
        from .web_service import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading web_service: {e}')
