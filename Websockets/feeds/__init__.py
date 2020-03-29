from octobot_tentacles_manager.api.inspector import check_tentacle_version
from octobot_commons.logging.logging_util import get_logger

if check_tentacle_version('1.2.0', 'bitmex_feed', 'OctoBot-Default-Tentacles'):
    try:
        from .bitmex_feed import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading bitmex_feed: {e}')
