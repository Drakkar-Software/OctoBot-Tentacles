from octobot_tentacles_manager.api.inspector import check_tentacle_version
from octobot_commons.logging.logging_util import get_logger

if check_tentacle_version('1.2.0', 'legacy_data_converter', 'OctoBot-Default-Tentacles'):
    try:
        from .legacy_data_converter import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading legacy_data_converter: {e}')
