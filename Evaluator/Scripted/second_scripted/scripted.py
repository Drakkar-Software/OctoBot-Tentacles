#  Drakkar-Software OctoBot-Tentacles
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
import octobot_evaluators.evaluators as evaluators
import tentacles.Evaluator.Scripted.second_scripted.evaluator.evaluator_script as evaluator_script


class SecondScriptedEvaluator(evaluators.ScriptedEvaluator):
    def __init__(self, tentacles_setup_config):
        super().__init__(tentacles_setup_config)
        self.register_script_module(evaluator_script)

    @classmethod
    def use_cache(cls):
        return True

