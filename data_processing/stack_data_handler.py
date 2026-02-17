import datetime

import pandas as pd
import numpy as np

import data_processing.bm_unit as bm_unit
import data_processing.boa as boa

def get_bmus_one_period(
    grouped_bid_offer_data_one_period, 
    full_settlement_stack_one_period: pd.DataFrame, 
    physical_volumes_by_bmu: dict[str, pd.Series]
) -> dict[str, bm_unit.BMUnit]:
    grouped_full_settlement_stack = full_settlement_stack_one_period.groupby('id')
    bmus = populate_bmu_objects_one_period(grouped_bid_offer_data_one_period, grouped_full_settlement_stack, physical_volumes_by_bmu)
    
    return bmus

def populate_bmu_objects_one_period(
    grouped_bid_offer_data_one_period, 
    grouped_full_settlement_stack_one_period, 
    physical_volumes_by_bmu):
    bmus = {}
    acceptance_volumes_by_bmu_by_pair = get_acceptance_volumes_by_bmu_by_pair(grouped_full_settlement_stack_one_period)
    for bm_unit_id, bid_offer_pairs_df in grouped_bid_offer_data_one_period:
        bid_offer_pairs = bid_offer_pairs_df.set_index('pair_id').to_dict('index')
        factual_acceptance_volumes_by_pair = {pair_id: 0 for pair_id in bid_offer_pairs.keys()}
        if bm_unit_id in acceptance_volumes_by_bmu_by_pair:
            for pair_id, acceptance_volume in acceptance_volumes_by_bmu_by_pair[bm_unit_id].items():
                factual_acceptance_volumes_by_pair[pair_id] = acceptance_volume
                
        bmu = bm_unit.BMUnit(bm_unit_id, bid_offer_pairs, factual_acceptance_volumes_by_pair, physical_volumes_by_bmu[bm_unit_id])
        bmus[bm_unit_id] = bmu
    
    return bmus

def get_acceptance_volumes_by_bmu_by_pair(grouped_full_settlement_stack):
    acceptance_volumes_by_bmu_by_pair = {}
    for bm_unit_id, boa_data_df in grouped_full_settlement_stack:
        acceptance_volumes_by_pair = {}
        for pair_id, pair_acceptances in boa_data_df.groupby('bid_offer_pair_id'):
            acceptance_volumes_by_pair[pair_id] = pair_acceptances['volume'].sum()
        acceptance_volumes_by_bmu_by_pair[bm_unit_id] = acceptance_volumes_by_pair
    
    return acceptance_volumes_by_bmu_by_pair
    
def get_marginal_boa(
    full_ascending_settlement_stack: pd.DataFrame, 
    bid_or_offer_stack: pd.DataFrame
) -> boa.Boa:
    ordered_unflagged_actions = full_ascending_settlement_stack[full_ascending_settlement_stack['so_flag'] == False]
    if (bid_or_offer_stack['pair_id'] > 0).any():
        ordered_unflagged_offers = ordered_unflagged_actions[ordered_unflagged_actions['bid_offer_pair_id'] > 0]
        if ordered_unflagged_offers.empty:
            marginal_boa = boa.Boa(0, 1, 0)
            return marginal_boa
        marginal_plant_row = get_marginal_plant_offer_row(ordered_unflagged_offers)
        if marginal_plant_row is None:
            marginal_boa = boa.Boa(0, 1, 0)
            return marginal_boa
    else:
        ordered_unflagged_bids = ordered_unflagged_actions[ordered_unflagged_actions['bid_offer_pair_id'] < 0]
        if ordered_unflagged_bids.empty:
            marginal_boa = boa.Boa(0, -1, 0)
            return marginal_boa
        marginal_plant_row = get_marginal_plant_bid_row(ordered_unflagged_bids)
        if marginal_plant_row is None:
            marginal_boa = boa.Boa(0, -1, 0)
            return marginal_boa
    
    marginal_plant_id = marginal_plant_row['id']
    marginal_plant_bid_offer_pair_id = marginal_plant_row['bid_offer_pair_id']
    marginal_plant_accepted_price = marginal_plant_row['original_price']
    marginal_boa = boa.Boa(marginal_plant_id, marginal_plant_bid_offer_pair_id, marginal_plant_accepted_price)
    
    return marginal_boa

def get_marginal_plant_offer_row(
    ordered_unflagged_offers: pd.DataFrame
) -> pd.Series:
    for i in range(len(ordered_unflagged_offers) - 1, -1, -1):
        row = ordered_unflagged_offers.iloc[i]
        plant_id = row['id']
        plant_offer_id = row['bid_offer_pair_id']
        dmat_adjusted_volume = row['dmat_adjusted_volume']
        if plant_id is not None and plant_offer_id is not None and dmat_adjusted_volume > 0:
            return row
    
    return None

def get_marginal_plant_bid_row(
    ordered_unflagged_bids: pd.DataFrame
) -> pd.Series:
    for i in range(len(ordered_unflagged_bids)):
        row = ordered_unflagged_bids.iloc[i]
        plant_id = row['id']
        plant_bid_id = row['bid_offer_pair_id']
        dmat_adjusted_volume = row['dmat_adjusted_volume']
        if plant_id is not None and plant_bid_id is not None and dmat_adjusted_volume < 0:
            return row
    
    return None

def get_offer_stack_one_period(
    bid_offer_data_one_period: pd.DataFrame
) -> pd.DataFrame:
    offer_data = bid_offer_data_one_period[bid_offer_data_one_period['pair_id'] > 0]
    ordered_offer_data = offer_data.sort_values(by=['offer', 'pair_id'], ascending=[True, True])
    ordered_offer_data.reset_index(drop=True, inplace=True)
    
    return ordered_offer_data

def get_bid_stack_one_period(
    bid_offer_data_one_period: pd.DataFrame
) -> pd.DataFrame:
    bid_data = bid_offer_data_one_period[bid_offer_data_one_period['pair_id'] < 0]
    ordered_bid_data = bid_data.sort_values(by=['bid', 'pair_id'], ascending=[False, False])
    ordered_bid_data.reset_index(drop=True, inplace=True)
    
    return ordered_bid_data

def accept_balancing_actions_until_quota_met(
    energy_before: float, 
    energy_after: float, 
    full_ascending_settlement_stack_one_period: pd.DataFrame,
    bid_or_offer_stack: pd.DataFrame, 
    bmus: list[bm_unit.BMUnit]
) -> pd.DataFrame:
    energy_target = energy_after - energy_before
    
    marginal_boa = get_marginal_boa(full_ascending_settlement_stack_one_period, bid_or_offer_stack)
    marginal_plant_index = set_marginal_plant_index(marginal_boa, bid_or_offer_stack)
    new_acceptances = add_new_bid_offer_acceptances(marginal_plant_index, bid_or_offer_stack, bmus, energy_target)
    ordered_settlement_stack = get_new_ordered_settlement_stack(new_acceptances, full_ascending_settlement_stack_one_period) 
     
    return ordered_settlement_stack

def set_marginal_plant_index(
    marginal_boa: boa.Boa, 
    bid_or_offer_stack : pd.DataFrame
) -> int:
    if marginal_boa.plant_id == 0:
        marginal_plant_index = marginal_boa.plant_id #If all actions are for system balancing, we then start accepting offers in merit order
    else:
        marginal_boa_df = bid_or_offer_stack[
            (bid_or_offer_stack['bm_unit'] == marginal_boa.plant_id) &
            (bid_or_offer_stack['pair_id'] == marginal_boa.bid_offer_pair_id)
        ]
        if not marginal_boa_df.empty:
            marginal_plant_index = marginal_boa_df.index[0]
        else:
            if bid_or_offer_stack['pair_id'].iloc[0] > 0:
                higher_offers = bid_or_offer_stack[bid_or_offer_stack['offer'] > marginal_boa.accepted_price]
                diff = higher_offers['offer'] - marginal_boa.accepted_price
                marginal_plant_index = higher_offers[diff == diff.min()].index[0]
            else:
                lower_bids = bid_or_offer_stack[bid_or_offer_stack['bid'] < marginal_boa.accepted_price]
                diff = marginal_boa.accepted_price - lower_bids['bid']
                marginal_plant_index = lower_bids[diff == diff.min()].index[0]
        
    return marginal_plant_index

def add_new_bid_offer_acceptances(
    marginal_plant_index: int, 
    bid_or_offer_stack: pd.DataFrame, 
    bmus: list[bm_unit.BMUnit], 
    energy_target: float
) -> list[pd.DataFrame]:
    total_additional_volume_accepted = 0
    new_acceptances = []
    
    for i in range(marginal_plant_index, len(bid_or_offer_stack)):
        row = bid_or_offer_stack.iloc[i]
        bm_unit_id = row['bm_unit']
        if bm_unit_id is None: 
            continue
        pair_id = row['pair_id']
        bm_unit = bmus[bm_unit_id]
        remaining_volume_in_pair = bm_unit.remaining_volume_by_pair[pair_id]
        
        if pair_id < 0:
            volume_to_accept = max(remaining_volume_in_pair, energy_target - total_additional_volume_accepted) #Both values will always be negative
            pair_price = bm_unit.bid_offer_pairs_submitted[pair_id]['bid']
        else:
            volume_to_accept = min(remaining_volume_in_pair, energy_target - total_additional_volume_accepted) #Both values will always be positive
            pair_price = bm_unit.bid_offer_pairs_submitted[pair_id]['offer']
        
        total_additional_volume_accepted += volume_to_accept
        if volume_to_accept != 0:
            new_acceptance = pd.DataFrame([{'id': bm_unit_id, 
                                            'bid_offer_pair_id': pair_id, 
                                            'so_flag': False,
                                            'original_price': pair_price, 
                                            'volume': volume_to_accept}])
            new_acceptances.append(new_acceptance)
        if abs(total_additional_volume_accepted) >= abs(energy_target):
            break
        
    return new_acceptances

def get_new_ordered_settlement_stack(
    new_acceptances: pd.DataFrame, 
    full_ascending_settlement_stack_one_period: pd.DataFrame
) -> pd.DataFrame:
    non_empty_new_acceptances = [acceptance for acceptance in new_acceptances if acceptance.empty == False]
    if len(non_empty_new_acceptances) == 0:
        return full_ascending_settlement_stack_one_period.copy()
    new_acceptances_df = pd.concat(non_empty_new_acceptances, ignore_index=True)
    new_acceptances_df = new_acceptances_df.reindex(columns=full_ascending_settlement_stack_one_period.columns, fill_value=np.nan)
    new_settlement_stack = pd.concat([full_ascending_settlement_stack_one_period, new_acceptances_df], ignore_index=True)
    ordered_settlement_stack = new_settlement_stack.sort_values(by=['original_price', 'bid_offer_pair_id'], ascending=[True, True])
    ordered_settlement_stack.reset_index(drop=True, inplace=True)
    
    return ordered_settlement_stack

def remove_offers_until_quota_met(
    niv_with_npts: float, 
    niv_without_npts: float, 
    ordered_settlement_stack_one_period : pd.DataFrame
) -> tuple[pd.DataFrame, float]:
    energy_surplus = niv_with_npts - niv_without_npts
    total_offer_volume_removed = 0
    row_indices_to_remove = []
    
    for i in range(len(ordered_settlement_stack_one_period) -1, -1, -1):
        row = ordered_settlement_stack_one_period.iloc[i]
        if row['volume'] == True:
            continue
        
        accepted_offer_volume = ordered_settlement_stack_one_period.at[ordered_settlement_stack_one_period.index[i], 'volume']
        
        volume_to_remove = min(accepted_offer_volume, energy_surplus - total_offer_volume_removed)
        total_offer_volume_removed += volume_to_remove
        
        if total_offer_volume_removed >= energy_surplus:
            ordered_settlement_stack_one_period.at[ordered_settlement_stack_one_period.index[i], 'volume'] -= volume_to_remove
            break
        else:
            row_indices_to_remove.append(ordered_settlement_stack_one_period.index[i])
        
    new_settlement_stack = ordered_settlement_stack_one_period.drop(index=row_indices_to_remove)
    
    return new_settlement_stack, total_offer_volume_removed

def remove_bids_until_quota_met(
    niv_with_npts: float, 
    niv_without_npts: float, 
    ordered_settlement_stack_one_period : pd.DataFrame
) -> tuple[pd.DataFrame, float]:
    energy_deficit = niv_with_npts - niv_without_npts
    total_bid_volume_removed = 0
    row_indices_to_remove = []
    
    for i in range(len(ordered_settlement_stack_one_period)):
        row = ordered_settlement_stack_one_period.iloc[i]
        if row['so_flag'] == True:
            continue
        
        accepted_bid_volume = ordered_settlement_stack_one_period.at[ordered_settlement_stack_one_period.index[i], 'volume']
        
        volume_to_remove = max(accepted_bid_volume, energy_deficit - total_bid_volume_removed) #Both values will always be negative
        total_bid_volume_removed += volume_to_remove
        
        if total_bid_volume_removed <= energy_deficit:
            ordered_settlement_stack_one_period.at[ordered_settlement_stack_one_period.index[i], 'volume'] -= volume_to_remove
            break
        else:
            row_indices_to_remove.append(ordered_settlement_stack_one_period.index[i])
        
    new_settlement_stack = ordered_settlement_stack_one_period.drop(row_indices_to_remove, axis=0)

    return new_settlement_stack, total_bid_volume_removed

def check_missing_data(
    dataframe_to_check: pd.DataFrame,
    settlement_dates_with_periods_per_day: dict[str, int]
) -> set[tuple[str, int]]:
    dataframe_to_check_copy = dataframe_to_check.copy()
    dataframe_to_check_copy['settlement_date'] = pd.to_datetime(dataframe_to_check_copy['settlement_date']).dt.date
    complete_dates_and_periods = [
        (datetime.datetime.strptime(settlement_date, '%Y-%m-%d').date(), settlement_period) 
        for settlement_date, periods_per_day in settlement_dates_with_periods_per_day.items() 
        for settlement_period in range(1, periods_per_day + 1)
    ]
    complete_dates_and_periods_set = set(complete_dates_and_periods)
    present_dates_and_periods = set(zip(dataframe_to_check_copy['settlement_date'], dataframe_to_check_copy['settlement_period']))
    missing_dates_and_periods = complete_dates_and_periods_set - present_dates_and_periods
    nan_rows = dataframe_to_check_copy[dataframe_to_check_copy.isna().any(axis=1)]
    nan_tuples = set(zip(nan_rows['settlement_date'], nan_rows['settlement_period']))
    missing_dates_and_periods.update(nan_tuples)
    return missing_dates_and_periods