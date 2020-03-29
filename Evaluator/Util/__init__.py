from octobot_tentacles_manager.api.inspector import check_tentacle_version
from octobot_commons.logging.logging_util import get_logger

if check_tentacle_version('1.2.0', 'pattern_analysis', 'OctoBot-Default-Tentacles'):
    try:
        from .pattern_analysis import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading pattern_analysis: {e}')

if check_tentacle_version('1.2.0', 'text_analysis', 'OctoBot-Default-Tentacles'):
    try:
        from .text_analysis import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading text_analysis: {e}')

if check_tentacle_version('1.2.0', 'trend_analysis', 'OctoBot-Default-Tentacles'):
    try:
        from .trend_analysis import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading trend_analysis: {e}')

if check_tentacle_version('1.2.0', 'overall_state_analysis', 'OctoBot-Default-Tentacles'):
    try:
        from .overall_state_analysis import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading overall_state_analysis: {e}')
