#  Drakkar-Software OctoBot-Trading
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
import datetime as datetime
import json as json
import tentacles.Meta.Keywords.scripting_library.backtesting.default_backtesting_run_analysis_script as default_backtesting_run_analysis_script

import tentacles.RunAnalysis.AnalysisEvaluator.Table as analysis_table
import tentacles.RunAnalysis.AnalysisEvaluator.Plot as analysis_plots
import octobot_trading.modes.script_keywords.context_management as context_management
import tentacles.RunAnalysis.BaseDataProvider.default_base_data_provider.init_base_data as init_base_data


class DefaultRunAnalysisMode:
    async def run_analysis_script(self, ctx: context_management.Context):

        # TODO tmp remove
        if (
            not "chart_location_unrealized_portfolio_value"
            in ctx.analysis_settings
        ):
            return await default_backtesting_run_analysis_script.default_backtesting_analysis_script(
                ctx
            )
        else:
            run_data = await init_base_data.get_base_data(ctx)

            # TODO add plot_candles and plot_trades and plot_cached_values and plot_withdrawals

            # TODO move chart location handling to frontend
            for chart_location in {
                run_data.analysis_settings["chart_location_unrealized_portfolio_value"],
                run_data.analysis_settings["chart_location_realized_portfolio_value"],
                run_data.analysis_settings["chart_location_realized_trade_gains"],
                run_data.analysis_settings["chart_location_best_case_growth"],
                run_data.analysis_settings["chart_location_wins_and_losses_count"],
                run_data.analysis_settings["chart_location_win_rate"],
            }:
                with run_data.run_display.part(chart_location) as plotted_element:
                    if (
                        run_data.analysis_settings["plot_unrealized_portfolio_value"]
                        and run_data.analysis_settings[
                            "chart_location_unrealized_portfolio_value"
                        ]
                    ):
                        await analysis_plots.plot_unrealized_portfolio_value(
                            run_data,
                            plotted_element,
                            own_yaxis=True,
                            all_coins_in_ref_market=run_data.analysis_settings.get(
                                "plot_unrealized_portfolio_value_for_each_asset"
                            ),
                            all_coins_amounts=run_data.analysis_settings.get(
                                "plot_unrealized_portfolio_amount_for_each_asset"
                            ),
                        )
                    if (
                        run_data.analysis_settings["plot_realized_portfolio_value"]
                        and run_data.analysis_settings[
                            "chart_location_realized_portfolio_value"
                        ]
                    ):
                        await analysis_plots.plot_realized_portfolio_value(
                            run_data,
                            plotted_element,
                            x_as_trade_count=False,
                            own_yaxis=True,
                        )
                    if (
                        run_data.analysis_settings["plot_realized_trade_gains"]
                        and run_data.analysis_settings[
                            "chart_location_realized_trade_gains"
                        ]
                    ):
                        await analysis_plots.plot_realized_trade_gains(
                            run_data,
                            plotted_element,
                            x_as_trade_count=False,
                            own_yaxis=True,
                        )

                    if (
                        run_data.analysis_settings["plot_best_case_growth"]
                        and run_data.analysis_settings[
                            "chart_location_best_case_growth"
                        ]
                    ):
                        await analysis_plots.plot_best_case_growth(
                            run_data,
                            plotted_element,
                            x_as_trade_count=False,
                            own_yaxis=False,
                        )
                    if (
                        run_data.analysis_settings["plot_funding_fees"]
                        and run_data.analysis_settings["chart_location_funding_fees"]
                    ):
                        await analysis_plots.plot_historical_fees(
                            run_data,
                            plotted_element,
                            own_yaxis=True,
                        )
                    if (
                        run_data.analysis_settings["plot_wins_and_losses_count"]
                        and run_data.analysis_settings[
                            "chart_location_wins_and_losses_count"
                        ]
                    ):
                        analysis_plots.plot_historical_wins_and_losses(
                            run_data,
                            plotted_element,
                            own_yaxis=True,
                            x_as_trade_count=False,
                        )
                    if (
                        run_data.analysis_settings["plot_win_rate"]
                        and run_data.analysis_settings["chart_location_win_rate"]
                    ):
                        analysis_plots.plot_historical_win_rates(
                            run_data,
                            plotted_element,
                            own_yaxis=True,
                            x_as_trade_count=False,
                        )
                    # if (
                    #     run_data.analysis_settings["plot_withdrawals"]
                    #     and run_data.analysis_settings["chart_location_withdrawals"]
                    # ):
                    #     await run_analysis_plots.plot_withdrawals(run_data, plotted_element)
            with run_data.run_display.part("list-of-trades-part", "table") as part:
                if run_data.analysis_settings["display_trades_and_positions"]:
                    await analysis_table.plot_trades_table(run_data.run_database, part)
                    await analysis_table.plot_positions_table(run_data, part)
                if run_data.analysis_settings["display_withdrawals_table"]:
                    await analysis_table.plot_withdrawals_table(
                        run_data, plotted_element
                    )

            # TODO allow to define cache keys via api
            # await plot_table(run_data, part, "SMA 1")  # plot any cache key as a table
            return run_data.run_display
