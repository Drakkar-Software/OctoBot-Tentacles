from octobot_tentacles_manager.api.inspector import check_tentacle_version
from octobot_commons.logging.logging_util import get_logger

if check_tentacle_version('1.2.0', 'telegram_service_feed', 'OctoBot-Default-Tentacles'):
    try:
        from .telegram_service_feed import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading telegram_service_feed: {e}')

if check_tentacle_version('1.2.0', 'reddit_service_feed', 'OctoBot-Default-Tentacles'):
    try:
        from .reddit_service_feed import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading reddit_service_feed: {e}')

if check_tentacle_version('1.2.0', 'twitter_service_feed', 'OctoBot-Default-Tentacles'):
    try:
        from .twitter_service_feed import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading twitter_service_feed: {e}')
