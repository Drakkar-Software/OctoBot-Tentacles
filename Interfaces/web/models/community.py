#  Drakkar-Software OctoBot-Interfaces
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

from octobot_interfaces.util.bot import get_edited_config
# TODO: find a way to handle metrics
# from tools.metrics.metrics_analysis import can_read_metrics, get_community_metrics


def get_community_metrics_to_display():
    # TODO: find a way to handle metrics
    # return get_community_metrics()
    return {}


def can_get_community_metrics():
    # TODO: find a way to handle metrics
    # return can_read_metrics(get_edited_config())
    return True
