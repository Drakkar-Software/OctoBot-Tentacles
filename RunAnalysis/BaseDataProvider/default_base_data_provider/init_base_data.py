import octobot_commons.enums as commons_enums
from tentacles.RunAnalysis.BaseDataProvider.default_base_data_provider import (
    base_data_provider,
    future_base_data_provider,
    spot_base_data_provider,
)


async def get_metadata(run_database):
    try:
        return (
            await run_database.get_run_db().all(commons_enums.DBTables.METADATA.value)
        )[0]
    except IndexError as error:
        raise LiveMetaDataNotInitializedError from error


async def get_base_data(ctx):
    # load and generate unified base data
    async with ctx.backtesting_results() as (run_database, run_display):
        metadata = await get_metadata(run_database)
        if metadata["trading_type"] == "spot":
            run_data = spot_base_data_provider.SpotRunAnalysisBaseDataGenerator(
                ctx, run_database, run_display, metadata
            )
        elif metadata["trading_type"] == "future":
            run_data = future_base_data_provider.FutureRunAnalysisBaseDataGenerator(
                ctx, run_database, run_display, metadata
            )
        else:
            raise NotImplementedError(
                f"RunDataAnalysis is not supported for {metadata['trading_type']}"
            )
        await run_data.load_base_data()
        display_metadata(run_data)
        return run_data


def display_metadata(run_data: base_data_provider.RunAnalysisBaseDataGenerator):
    with run_data.run_display.part("metadata", "dictionary") as plotted_element:
        plotted_element.dictionary("metadata", dictionary=run_data.metadata)


class LiveMetaDataNotInitializedError(Exception):
    """
    raised when the live metadata isnt initialized yet
    """
