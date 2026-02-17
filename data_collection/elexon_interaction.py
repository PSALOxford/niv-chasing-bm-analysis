import asyncio

import pandas as pd

from elexonpy.api_client import ApiClient
from elexonpy.api.indicative_imbalance_settlement_api import IndicativeImbalanceSettlementApi
from elexonpy.api.bid_offer_api import BidOfferApi
from elexonpy.api.balancing_mechanism_physical_api import BalancingMechanismPhysicalApi
from elexonpy.api.market_index_api import MarketIndexApi
from elexonpy.api.balancing_services_adjustment___net_api import BalancingServicesAdjustmentNetApi
from elexonpy.api.bid_offer_acceptances_api import BidOfferAcceptancesApi
from elexonpy.api.reference_api import ReferenceApi
from elexonpy.rest import ApiException

from data_processing.bm_physical_data_handler import get_physical_volume

async def fetch_data_by_settlement_date(
    settlement_dates: list[str], 
    api_function, 
    column_headers_to_keep: list[str] = None
) -> list[pd.DataFrame]:
    data_dfs = []
    tasks = [api_function(date, format = 'dataframe', async_req=True) 
             for date in settlement_dates]
    
    results = await asyncio.gather(*[asyncio.to_thread(task.get) for task in tasks])

    for df in results:
        data = df.copy()
        if data.empty:
            continue
        if column_headers_to_keep is not None:
            data = data[column_headers_to_keep]
        data_dfs.append(data)
    
    return data_dfs

async def fetch_data_from_and_to_date(
    settlement_dates_with_periods_per_day: dict[str, int], 
    api_function, 
    column_headers: list[str] = None
) -> list[pd.DataFrame]:
    data_dfs = []
    tasks = [
        api_function(settlement_date, settlement_date, settlement_period_from = 1, settlement_period_to = settlement_periods_in_day, format='dataframe', async_req=True)
        for settlement_date, settlement_periods_in_day in settlement_dates_with_periods_per_day.items()
    ]
    
    results = await asyncio.gather(*[asyncio.to_thread(task.get) for task in tasks])

    for df in results:
        data = df.copy()
        if data.empty:
            continue
        if column_headers is not None:
            data = data[column_headers]
        data_dfs.append(data)
    
    return data_dfs    

async def get_niv_data(
    settlement_dates_and_periods_per_day: dict,
    api_client: ApiClient
) -> pd.DataFrame:
    imbalance_api = IndicativeImbalanceSettlementApi(api_client)
    niv_data_dfs = await fetch_data_by_settlement_date(
        settlement_dates_and_periods_per_day.keys(),
        imbalance_api.balancing_settlement_system_prices_settlement_date_get,
        column_headers_to_keep=['start_time', 'settlement_date', 'settlement_period', 'net_imbalance_volume', 'system_sell_price']
    )
    
    niv_data = pd.concat(niv_data_dfs, ignore_index=True)
    
    return niv_data

async def get_full_settlement_stacks_by_date_and_period(
    api_client: ApiClient, 
    settlement_dates_with_periods_per_day: dict[str, int],
    missing_data: set[tuple[str, int]]
) -> dict[tuple[str, int], pd.DataFrame]:
    full_settlement_stacks_by_date_and_period = {}
    tasks = [get_full_ascending_settlement_stack_one_period(api_client, settlement_date, settlement_period, missing_data) 
             for settlement_date, settlement_periods_in_day in settlement_dates_with_periods_per_day.items() for settlement_period in range(1, settlement_periods_in_day + 1)]
    results = await asyncio.gather(*tasks)
    
    full_settlement_stacks_by_date_and_period = dict(results)
    
    return full_settlement_stacks_by_date_and_period  

async def get_full_ascending_settlement_stack_one_period(
    api_client: ApiClient, 
    settlement_date: str, 
    settlement_period: int,
    missing_data: set[tuple[str, int]]
) -> tuple[tuple[str, int], pd.DataFrame]:
    imbalance_settlement_api = IndicativeImbalanceSettlementApi(api_client)
    tasks = [
        imbalance_settlement_api.balancing_settlement_stack_all_bid_offer_settlement_date_settlement_period_get(
            'offer', settlement_date, settlement_period, format='dataframe', async_req=True), 
        imbalance_settlement_api.balancing_settlement_stack_all_bid_offer_settlement_date_settlement_period_get(
            'bid', settlement_date, settlement_period, format='dataframe', async_req=True)
        ]
    results = await asyncio.gather(*[asyncio.to_thread(task.get) for task in tasks])
    offer_settlement_stack, bid_settlement_stack = results
    
    non_empty_stacks = [df for df in [offer_settlement_stack, bid_settlement_stack] if not df.empty]
    
    if non_empty_stacks:
        full_settlement_stack_one_period = pd.concat(non_empty_stacks)
        full_ordered_settlement_stack_one_period = full_settlement_stack_one_period.sort_values(by=['original_price', 'bid_offer_pair_id'], ascending=[True, True])
        full_ordered_settlement_stack_one_period.reset_index(drop=True, inplace=True)
    else:
        full_ordered_settlement_stack_one_period = pd.DataFrame()
        missing_data.add((settlement_date, settlement_period))
    
    return ((settlement_date, settlement_period), full_ordered_settlement_stack_one_period)

async def get_accepted_offers_by_date_and_period(
    api_client: ApiClient,
    settlement_dates_with_periods_per_day: dict[str, int]
) -> list[pd.DataFrame]:
    imbalance_settlement_api = IndicativeImbalanceSettlementApi(api_client)
    tasks = [
        imbalance_settlement_api.balancing_settlement_stack_all_bid_offer_settlement_date_settlement_period_get(
            'offer', settlement_date, settlement_period, format='dataframe', async_req=True)
        for settlement_date, settlement_periods_in_day in settlement_dates_with_periods_per_day.items()
        for settlement_period in range(1, settlement_periods_in_day + 1)
    ]
    results = await asyncio.gather(*[asyncio.to_thread(task.get) for task in tasks])
    accepted_offers_by_date_and_period = []
    for df in results:
        if not df.empty:
            accepted_offers = df[
                (df['bid_offer_pair_id'] > 0) &
                (df['volume'] > 0)
            ]
            if not accepted_offers.empty:
                accepted_offers_by_date_and_period.append(accepted_offers)
    
    return accepted_offers_by_date_and_period

async def get_bid_offer_pairs_data_one_period(
    api_client: ApiClient, 
    settlement_date: str, 
    settlement_period: int
) -> pd.DataFrame:
    bid_offer_api = BidOfferApi(api_client)
    task = bid_offer_api.balancing_bid_offer_all_get(settlement_date, settlement_period, format='dataframe', async_req=True)
    bid_offer_data_one_period = await retry_api_call(task)
    if bid_offer_data_one_period.empty:
        return pd.DataFrame()
    bid_offer_useful_data_one_period = bid_offer_data_one_period[['bm_unit', 'level_from', 'bid', 'offer', 'pair_id']]
    
    return bid_offer_useful_data_one_period

async def get_physical_volumes_by_bmu(
    api_client: ApiClient, 
    settlement_date: str, 
    settlement_period: int, 
    bmus: list[str]):
    balancing_mechanism_physical_api = BalancingMechanismPhysicalApi(api_client)
    tasks = [balancing_mechanism_physical_api.balancing_physical_all_get(
        'PN', settlement_date, settlement_period, format='dataframe', async_req=True),
             balancing_mechanism_physical_api.balancing_physical_all_get(
        'MELS', settlement_date, settlement_period, format='dataframe', async_req=True),
                balancing_mechanism_physical_api.balancing_physical_all_get(
        'MILS', settlement_date, settlement_period, format='dataframe', async_req=True)]
    results = await asyncio.gather(*[retry_api_call(task) for task in tasks])
    full_PN_data_one_period, full_MELS_data_one_period, full_MILS_data_one_period = results
    if full_PN_data_one_period.empty or full_MELS_data_one_period.empty or full_MILS_data_one_period.empty:
        return {}
    physical_volumes_by_bmu = {}
    for bmu in bmus:
        PN_data = full_PN_data_one_period[full_PN_data_one_period['bm_unit'] == bmu]
        MELS_data = full_MELS_data_one_period[full_MELS_data_one_period['bm_unit'] == bmu]
        MILS_data = full_MILS_data_one_period[full_MILS_data_one_period['bm_unit'] == bmu]
        
        scheduled_energy_delivery = get_physical_volume(PN_data)
        max_energy_delivery = get_physical_volume(MELS_data)
        max_energy_import = get_physical_volume(MILS_data)
        physical_volumes_by_bmu[bmu] = pd.Series({
            'PN': scheduled_energy_delivery,
            'MELS': max_energy_delivery,
            'MILS': max_energy_import
        })
        
    return physical_volumes_by_bmu

async def get_full_midp_data(
    api_client: ApiClient,
    settlement_dates_with_periods_per_day: dict[str, int]
) -> pd.DataFrame:
    market_index_api = MarketIndexApi(api_client)
    market_index_data = await fetch_data_from_and_to_date(settlement_dates_with_periods_per_day, market_index_api.balancing_pricing_market_index_get)
    combined_market_index_data = pd.concat(market_index_data)
    
    return combined_market_index_data

async def get_price_adjustment_data(
    columns_to_download_from_api: list[str], 
    settlement_dates_with_periods_per_day: dict[str, int], 
    api_client: ApiClient
) -> pd.DataFrame:
    net_bsad_api = BalancingServicesAdjustmentNetApi(api_client)
    price_adjustment_data = await fetch_data_from_and_to_date(settlement_dates_with_periods_per_day, net_bsad_api.balancing_nonbm_netbsad_get, columns_to_download_from_api)
    if all(df.empty for df in price_adjustment_data):
        return pd.DataFrame()
    combined_price_adjustment_data = pd.concat(price_adjustment_data)
    
    return combined_price_adjustment_data

async def get_bid_offer_acceptance_data(
    settlement_date: str,
    settlement_periods_in_day: int,
    api_client: ApiClient
) -> dict[tuple[str, int], pd.DataFrame]:
    bid_offer_accpetance_api = BidOfferAcceptancesApi(api_client)
    tasks = [
        bid_offer_accpetance_api.balancing_acceptances_all_get(
            settlement_date, settlement_period, format='dataframe', async_req=True
        )
        for settlement_period in range(1, settlement_periods_in_day + 1)
    ]
    results = await asyncio.gather(*[asyncio.to_thread(task.get) for task in tasks])
    bid_offer_acceptances_by_date_and_period = {
        (settlement_date, settlement_period): df for settlement_period, df in enumerate(results, start=1)
    }
    
    return bid_offer_acceptances_by_date_and_period
    

async def retry_api_call(task, max_retries=3, backoff=2):
    for attempt in range(1, max_retries + 1):
        try:
            return await asyncio.to_thread(task.get)
        except ApiException as e:
            if attempt == max_retries:
                raise e
            else:
                sleep_time = backoff ** attempt
                print(f"API call failed. Retrying in {sleep_time} seconds.")
                await asyncio.sleep(sleep_time)
                