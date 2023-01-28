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
import tentacles.RunAnalysis.BaseDataProvider.default_base_data_provider.base_data_provider as base_data_provider
import octobot_commons.enums as commons_enums


class FutureRunAnalysisBaseDataGenerator(
    base_data_provider.RunAnalysisBaseDataGenerator
):
    async def generate_transactions(self) -> None:
        # TODO generate portfolio balance histories 
        self.trading_transactions_history = await self.load_transactions()

    async def load_transactions(self, transaction_type=None, transaction_types=None):
        if transaction_type is not None:
            query = (
                await self.run_database.get_transactions_db().search()
            ).type == transaction_type
        elif transaction_types is not None:
            query = (
                await self.run_database.get_transactions_db().search()
            ).type.one_of(transaction_types)
        else:
            return await self.run_database.get_transactions_db().all(
                commons_enums.DBTables.TRANSACTIONS.value
            )
        return await self.run_database.get_transactions_db().select(
            commons_enums.DBTables.TRANSACTIONS.value, query
        )

    async def load_grouped_funding_fees(self):
        if not self.funding_fees_history_by_pair:
            funding_fees_history = await self.load_transactions(
                transaction_type=trading_enums.TransactionType.FUNDING_FEE.value,
            )
            funding_fees_history = sorted(
                funding_fees_history,
                key=lambda f: f[commons_enums.PlotAttributes.X.value],
            )
            self.funding_fees_history_by_pair = {}
            for funding_fee in funding_fees_history:
                try:
                    self.funding_fees_history_by_pair[
                        funding_fee[commons_enums.PlotAttributes.SYMBOL.value]
                    ].append(funding_fee)
                except KeyError:
                    self.funding_fees_history_by_pair[
                        funding_fee[commons_enums.PlotAttributes.SYMBOL.value]
                    ] = [funding_fee]
