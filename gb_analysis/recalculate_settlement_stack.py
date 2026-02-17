import asyncio

import data_collection.elexon_interaction as elexon_interaction
import data_processing.stack_data_handler as stack_data_handler
import data_processing.bm_unit as bm_unit
import pandas as pd

from elexonpy.api_client import ApiClient

async def recalculate_stacks(
    api_client: ApiClient, 
    settlement_dates_with_periods_per_day : dict[str, int], 
    system_imbalance_with_and_without_npts_by_date_and_period : pd.DataFrame, 
    full_ascending_settlement_stack_by_date_and_period : dict[tuple[str, int], pd.DataFrame],
    missing_data: set[tuple[str, int]]
) -> dict:
    new_settlement_stacks_by_date_and_period = {}
    for settlement_date, settlement_periods_in_day in settlement_dates_with_periods_per_day.items():
        tasks = []
        for settlement_period in range(1, settlement_periods_in_day + 1):
            tasks.append(asyncio.create_task(process_settlement_period(api_client, settlement_date, settlement_period, system_imbalance_with_and_without_npts_by_date_and_period, full_ascending_settlement_stack_by_date_and_period, missing_data)))
        day_results = await asyncio.gather(*tasks)
        for (settlement_date, settlement_period), new_settlement_stack_one_period in day_results:
            new_settlement_stacks_by_date_and_period[(settlement_date, settlement_period)] = new_settlement_stack_one_period
        print(f"Recalculated stacks for {settlement_date}")   
    
    return new_settlement_stacks_by_date_and_period

async def process_settlement_period(
    api_client: ApiClient, 
    settlement_date: str, 
    settlement_period: int, 
    system_imbalance_df: pd.DataFrame, 
    full_settlement_stacks_by_date_and_period: dict[tuple[str, int], pd.DataFrame],
    missing_data: set[tuple[str, int]]
) -> tuple[tuple[str, int], pd.DataFrame]:
    system_imbalance_with_and_without_npts_one_period = system_imbalance_df[
        (system_imbalance_df['settlement_date'] == settlement_date) & 
        (system_imbalance_df['settlement_period'] == settlement_period)
    ]
    full_ascending_settlement_stack_one_period = full_settlement_stacks_by_date_and_period[(settlement_date, settlement_period)]
    new_settlement_stack = await get_new_settlement_stack_one_period(api_client, settlement_date, settlement_period, system_imbalance_with_and_without_npts_one_period, full_ascending_settlement_stack_one_period, missing_data)
    print(f"Recalculated stack for {settlement_date}, period {settlement_period}")
    
    return (settlement_date, settlement_period), new_settlement_stack

async def get_new_settlement_stack_one_period(
    api_client: ApiClient, 
    settlement_date: str, 
    settlement_period: int, 
    system_imbalance_with_and_without_npts_one_period: pd.DataFrame, 
    full_ascending_settlement_stack_one_period: pd.DataFrame,
    missing_data: set[tuple[str, int]]
) -> pd.DataFrame:
    if full_ascending_settlement_stack_one_period.empty:
        missing_data.add((settlement_date, settlement_period))
        return pd.DataFrame()
    
    bid_offer_data_one_period = await elexon_interaction.get_bid_offer_pairs_data_one_period(api_client, settlement_date, settlement_period)
    if bid_offer_data_one_period.empty:
        missing_data.add((settlement_date, settlement_period))
        return pd.DataFrame()
    grouped_bid_offer_data_one_period = bid_offer_data_one_period.groupby('bm_unit')
    bmus = grouped_bid_offer_data_one_period.groups.keys()
    physical_volumes_by_bmu = await elexon_interaction.get_physical_volumes_by_bmu(api_client, settlement_date, settlement_period, bmus)
    if not physical_volumes_by_bmu:
        missing_data.add((settlement_date, settlement_period))
        return pd.DataFrame()
    bmus = stack_data_handler.get_bmus_one_period(grouped_bid_offer_data_one_period, full_ascending_settlement_stack_one_period, physical_volumes_by_bmu)
    new_settlement_stack = recalculate_settlement_stack_one_period(system_imbalance_with_and_without_npts_one_period, full_ascending_settlement_stack_one_period, bid_offer_data_one_period, bmus)
    return new_settlement_stack
        
def recalculate_settlement_stack_one_period(
    system_imbalance_with_and_without_npts_one_period: pd.DataFrame, 
    full_ascending_settlement_stack_one_period: pd.DataFrame, 
    bid_offer_data_one_period: pd.DataFrame, 
    bmus: list[str]
) -> pd.DataFrame:
    system_imbalance_with_npts = system_imbalance_with_and_without_npts_one_period['net_imbalance_volume'].values[0]
    system_imbalance_without_npts = system_imbalance_with_and_without_npts_one_period['counterfactual_niv'].values[0]
    if(system_imbalance_with_npts > 0 and system_imbalance_without_npts > 0):
        return recalculate_settlement_stack_niv_with_and_without_positive(system_imbalance_with_npts, system_imbalance_without_npts, full_ascending_settlement_stack_one_period, 
                                                            bid_offer_data_one_period, bmus)
    elif(system_imbalance_with_npts < 0 and system_imbalance_without_npts < 0):
        return recalculate_settlement_stack_niv_with_and_without_negative(system_imbalance_with_npts, system_imbalance_without_npts, full_ascending_settlement_stack_one_period,
                                                            bid_offer_data_one_period, bmus)
    elif(system_imbalance_with_npts > 0 and system_imbalance_without_npts < 0):
        return recalculate_settlement_stack_niv_with_positive_and_without_negative(system_imbalance_with_npts, system_imbalance_without_npts, full_ascending_settlement_stack_one_period,
                                                                     bid_offer_data_one_period, bmus)
    else:
        return recalculate_settlement_stack_niv_with_negative_and_without_positive(system_imbalance_with_npts, system_imbalance_without_npts, full_ascending_settlement_stack_one_period,
                                                                     bid_offer_data_one_period, bmus)
    
    
def recalculate_settlement_stack_niv_with_and_without_positive(
    system_imbalance_with_npts: float, 
    system_imbalance_without_npts: float, 
    full_ascending_settlement_stack_one_period: pd.DataFrame, 
    bid_offer_data_one_period: pd.DataFrame, 
    bmus: list[bm_unit.BMUnit]
) -> pd.DataFrame:
    ascending_settlement_stack_for_calculation = full_ascending_settlement_stack_one_period.copy()
    if system_imbalance_without_npts > system_imbalance_with_npts:
        offer_stack = stack_data_handler.get_offer_stack_one_period(bid_offer_data_one_period)
        new_settlement_stack = stack_data_handler.accept_balancing_actions_until_quota_met(system_imbalance_with_npts, system_imbalance_without_npts, ascending_settlement_stack_for_calculation, offer_stack, bmus)
    else:
        new_settlement_stack, total_offer_volume_removed = stack_data_handler.remove_offers_until_quota_met(system_imbalance_with_npts, system_imbalance_without_npts, ascending_settlement_stack_for_calculation)
        if system_imbalance_with_npts - total_offer_volume_removed > system_imbalance_without_npts:
            bid_volume_to_accept = (system_imbalance_with_npts - total_offer_volume_removed) - system_imbalance_without_npts
            bid_stack = stack_data_handler.get_bid_stack_one_period(bid_offer_data_one_period)
            new_settlement_stack = stack_data_handler.accept_balancing_actions_until_quota_met(bid_volume_to_accept, 0, new_settlement_stack, bid_stack, bmus)

    return new_settlement_stack

def recalculate_settlement_stack_niv_with_and_without_negative(
    system_imbalance_with_npts: float, 
    system_imbalance_without_npts: float, 
    full_ascending_settlement_stack_one_period: pd.DataFrame, 
    bid_offer_data_one_period: pd.DataFrame, 
    bmus: list[bm_unit.BMUnit]
) -> pd.DataFrame:
    ascending_settlement_stack_for_calculation = full_ascending_settlement_stack_one_period.copy()
    if system_imbalance_without_npts < system_imbalance_with_npts:
        bid_stack = stack_data_handler.get_bid_stack_one_period(bid_offer_data_one_period)
        new_settlement_stack = stack_data_handler.accept_balancing_actions_until_quota_met(system_imbalance_with_npts, system_imbalance_without_npts, ascending_settlement_stack_for_calculation, bid_stack, bmus)
    else:
        new_settlement_stack, total_bid_volume_removed = stack_data_handler.remove_bids_until_quota_met(system_imbalance_with_npts, system_imbalance_without_npts, ascending_settlement_stack_for_calculation)
        if system_imbalance_with_npts - total_bid_volume_removed < system_imbalance_without_npts:
            offer_volume_to_accept = system_imbalance_without_npts - (system_imbalance_with_npts - total_bid_volume_removed)
            offer_stack = stack_data_handler.get_offer_stack_one_period(bid_offer_data_one_period)
            new_settlement_stack = stack_data_handler.accept_balancing_actions_until_quota_met(0, offer_volume_to_accept, new_settlement_stack, offer_stack, bmus)
    
    return new_settlement_stack

def recalculate_settlement_stack_niv_with_positive_and_without_negative(
    system_imbalance_with_npts: float, 
    system_imbalance_without_npts: float, 
    full_ascending_settlement_stack_one_period: pd.DataFrame, 
    bid_offer_data_one_period: pd.DataFrame, 
    bmus: list[bm_unit.BMUnit]
) -> pd.DataFrame:
    ascending_settlement_stack_for_calculation = full_ascending_settlement_stack_one_period.copy()
    stack_without_offers, total_offer_volume_removed = stack_data_handler.remove_offers_until_quota_met(system_imbalance_with_npts, 0, ascending_settlement_stack_for_calculation)
    remaining_volume_to_remove = system_imbalance_with_npts - total_offer_volume_removed
    bid_stack = stack_data_handler.get_bid_stack_one_period(bid_offer_data_one_period)
    new_settlement_stack = stack_data_handler.accept_balancing_actions_until_quota_met(remaining_volume_to_remove, system_imbalance_without_npts, stack_without_offers, bid_stack, bmus)

    return new_settlement_stack

def recalculate_settlement_stack_niv_with_negative_and_without_positive(
    system_imbalance_with_npts: float, 
    system_imbalance_without_npts: float, 
    full_ascending_settlement_stack_one_period: pd.DataFrame, 
    bid_offer_data_one_period: pd.DataFrame, 
    bmus: list[bm_unit.BMUnit]
) -> pd.DataFrame:
    ascending_settlement_stack_for_calculation = full_ascending_settlement_stack_one_period.copy()
    stack_without_bids, total_bid_volume_removed = stack_data_handler.remove_bids_until_quota_met(system_imbalance_with_npts, 0, ascending_settlement_stack_for_calculation)
    remaining_volume_to_remove = system_imbalance_with_npts - total_bid_volume_removed
    offer_stack = stack_data_handler.get_offer_stack_one_period(bid_offer_data_one_period)
    new_settlement_stack = stack_data_handler.accept_balancing_actions_until_quota_met(remaining_volume_to_remove, system_imbalance_without_npts, stack_without_bids, offer_stack, bmus)

    return new_settlement_stack
