from octobot_tentacles_manager.api.inspector import check_tentacle_version
from octobot_commons.logging.logging_util import get_logger

if check_tentacle_version('1.2.0', 'generic_exchange_importer', 'OctoBot-Default-Tentacles'):
    try:
        from .generic_exchange_importer import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading generic_exchange_importer: {e}')
