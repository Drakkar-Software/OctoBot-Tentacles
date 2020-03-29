from octobot_tentacles_manager.api.inspector import check_tentacle_version
from octobot_commons.logging.logging_util import get_logger

if check_tentacle_version('1.2.0', 'mixed_strategies_evaluator', 'OctoBot-Default-Tentacles'):
    try:
        from .mixed_strategies_evaluator import *
    except Exception as e:
        get_logger('TentacleLoader').exception(e, True, f'Error when loading mixed_strategies_evaluator: {e}')
