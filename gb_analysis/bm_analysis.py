import pandas as pd
import data_collection.elexon_interaction as elexon_interaction
import ancillary_files.datetime_functions as datetime_functions
import ancillary_files.excel_interaction as excel_interaction
import calendar

from elexonpy.api_client import ApiClient

async def calculate_balancing_costs_breakdown(
    output_file_directory: str,
    output_file_name: str,
    years: list[int]
) -> None:
    api_client = ApiClient()
    all_results = []
    missing_data = set()
    for year in years:
        for month in range(1, 13):
            month_start_date = f"{year}-{month:02d}-01"
            month_end_date = f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
            settlement_dates_with_periods_per_day = datetime_functions.get_settlement_dates_and_settlement_periods_per_day(
                month_start_date,
                month_end_date
            )
            settlement_stacks = await elexon_interaction.get_full_settlement_stacks_by_date_and_period(
                api_client,
                settlement_dates_with_periods_per_day,
                missing_data
            )
            for (settlement_date, settlement_period), settlement_stack in settlement_stacks.items():
                if settlement_stack.empty:
                    continue
                supply_demand_balance_actions = settlement_stack[settlement_stack['so_flag'] == False]
                system_balance_actions = settlement_stack[settlement_stack['so_flag'] == True]
                supply_demand_balance_cost = (supply_demand_balance_actions['volume'] * supply_demand_balance_actions['original_price']).sum()
                system_balance_cost = (system_balance_actions['volume'] * system_balance_actions['original_price']).sum() 
                all_results.append({
                    'settlement_date': settlement_date,
                    'settlement_period': settlement_period,
                    'supply_demand_balance_cost': supply_demand_balance_cost,
                    'system_balance_cost': system_balance_cost
                })
            print(f"Calculated balancing costs breakdown for {year}-{month:02d}")
    
    all_results_df = pd.DataFrame(all_results)
    excel_interaction.dataframes_to_excel([all_results_df], output_file_directory, output_file_name)

async def get_bm_offer_volume_by_wind(
    output_file_directory: str,
    output_file_name: str,
    years: list[int]
) -> None:
    api_client = ApiClient()
    bm_units = pd.read_json('/Users/josephcary/Library/CloudStorage/OneDrive-Nexus365/First Year/Papers/NIV Chasing/Supporting Data/BM_Units.json')
    wind_bmu_set = set(bm_units[bm_units['fuelType'] == 'WIND']['elexonBmUnit'].to_list())
    all_results = []
    for year in years:
        for month in range(1, 13):
            month_start_date = f"{year}-{month:02d}-01"
            month_end_date = f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
            settlement_dates_with_periods_per_day = datetime_functions.get_settlement_dates_and_settlement_periods_per_day(
                month_start_date,
                month_end_date
            )
            offer_stacks = await elexon_interaction.get_accepted_offers_by_date_and_period(
                api_client,
                settlement_dates_with_periods_per_day
            )
            results = [
                calculate_wind_offer_and_all_volume_one_period(
                offer_stack, wind_bmu_set
                ) for offer_stack in offer_stacks
            ]
            results_df = pd.DataFrame(
                results,
                columns=[
                    'settlement_date',
                    'settlement_period',
                    'wind_accepted_offer_volume',
                    'all_accepted_offer_volume',
                    'wind_offer_percentage'
                ]
            )
            all_results.append(results_df)
            print(f"Calculated wind offer volume for {year}-{month:02d}")
    
    all_results_df = pd.concat(all_results, ignore_index=True)
    excel_interaction.dataframes_to_excel([all_results_df], output_file_directory, output_file_name)
    
async def get_bm_volume_by_ccgt(
    output_file_directory: str,
    output_file_name: str,
    years: list[int]
) -> None:
    api_client = ApiClient()
    bm_units = pd.read_json('/Users/josephcary/Library/CloudStorage/OneDrive-Nexus365/First Year/Papers/NIV Chasing/Supporting Data/BM_Units.json')
    ccgt_set = set(bm_units[bm_units['fuelType'] == 'CCGT']['elexonBmUnit'].to_list())
    all_results = []
    missing_data = set()
    for year in years:
        for month in range(1, 13):
            month_start_date = f"{year}-{month:02d}-01"
            month_end_date = f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
            settlement_dates_with_periods_per_day = datetime_functions.get_settlement_dates_and_settlement_periods_per_day(
                month_start_date,
                month_end_date
            )
            full_settlement_stacks_by_date_and_period = await elexon_interaction.get_full_settlement_stacks_by_date_and_period(
                api_client,
                settlement_dates_with_periods_per_day,
                missing_data
            )
            
            results = [
                calculate_ccgt_bid_offer_volume_one_period(
                bid_offer_stack, ccgt_set
                ) for bid_offer_stack in full_settlement_stacks_by_date_and_period.values()  
            ]
            results_df = pd.DataFrame(
                results,
                columns=[
                    'settlement_date',
                    'settlement_period',
                    'ccgt_bid_volume',
                    'ccgt_offer_volume'
                ]
            )
            all_results.append(results_df)
            print(f"Calculated ccgt bid and offer volume for {year}-{month:02d}")
    
    all_results_df = pd.concat(all_results, ignore_index=True)
    excel_interaction.dataframes_to_excel([all_results_df], output_file_directory, output_file_name)

def calculate_wind_offer_and_all_volume_one_period(
    offer_stack: pd.DataFrame,
    wind_bmu_set: set[str]
) -> tuple[str, int, float, float, float]:
    wind_offer_volume = offer_stack[offer_stack['id'].isin(wind_bmu_set)]['volume'].sum()
    all_offer_volume = offer_stack['volume'].sum()
    settlement_date = offer_stack.iloc[0]['settlement_date']
    settlement_period = offer_stack.iloc[0]['settlement_period']
    
    if all_offer_volume == 0:
        return settlement_date, settlement_period, 0.0, 0.0, None
    
    wind_offer_percentage = wind_offer_volume / all_offer_volume
    return (
        settlement_date,
        settlement_period,
        wind_offer_volume,
        all_offer_volume,
        wind_offer_percentage
    )
    
def calculate_ccgt_bid_offer_volume_one_period(
    bid_offer_stack: pd.DataFrame,
    ccgt_bmu_set: set[str]
) -> tuple[str, int, float, float]:
    if bid_offer_stack.empty:
        return None, None, 0.0, 0.0
    ccgt_bid_offer_accepted_volume = bid_offer_stack[bid_offer_stack['id'].isin(ccgt_bmu_set)]
    if ccgt_bid_offer_accepted_volume.empty:
        return bid_offer_stack.iloc[0]['settlement_date'], bid_offer_stack.iloc[0]['settlement_period'], 0.0, 0.0
    
    ccgt_offer_volume = ccgt_bid_offer_accepted_volume[ccgt_bid_offer_accepted_volume['volume'] > 0]['volume'].sum()
    ccgt_bid_volume = ccgt_bid_offer_accepted_volume[ccgt_bid_offer_accepted_volume['volume'] < 0]['volume'].sum()
    settlement_date = bid_offer_stack.iloc[0]['settlement_date']
    settlement_period = bid_offer_stack.iloc[0]['settlement_period']
    
    return (
        settlement_date,
        settlement_period,
        ccgt_bid_volume,
        ccgt_offer_volume
    )

async def calculate_number_of_boa_before_settlement_period(
    output_file_directory: str,
    output_file_name: str,
    years: list[int]
) -> None:
    api_client = ApiClient()
    all_results = []
    for year in years:
        for month in range(1, 13):
            month_start_date = f"{year}-{month:02d}-01"
            month_end_date = f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"
            settlement_dates_with_periods_per_day = datetime_functions.get_settlement_dates_and_settlement_periods_per_day(
                month_start_date,
                month_end_date
            )
            date_and_period_to_start_time = datetime_functions.get_settlement_date_period_to_utc_start_time_mapping(
                years
            )
            
            for settlement_date, settlement_dates_with_periods_per_day in settlement_dates_with_periods_per_day.items():
                bid_offer_acceptance_data_by_date_and_period = await elexon_interaction.get_bid_offer_acceptance_data(
                    settlement_date,
                    settlement_dates_with_periods_per_day,
                    api_client
                )
                
                pre_settlement_boa_count_df = get_number_of_boa_before_settlement_period(
                    date_and_period_to_start_time,
                    bid_offer_acceptance_data_by_date_and_period
                )
                
                all_results.append(pre_settlement_boa_count_df)
            print(f'Calculated pre-settlement BOA count for {year}-{month:02d}')
            
    all_results_df = pd.concat(all_results, ignore_index=True)
    excel_interaction.dataframes_to_excel([all_results_df], output_file_directory, output_file_name)

def get_number_of_boa_before_settlement_period(
    date_and_period_to_start_time: dict[tuple[str, int], str],
    bid_offer_acceptance_data_by_date_and_period: dict[tuple[str, int], pd.DataFrame]
) -> pd.DataFrame:
    results = []
    for (settlement_date, settlement_period), bid_offer_acceptance_data in bid_offer_acceptance_data_by_date_and_period.items():
        if bid_offer_acceptance_data.empty:
            continue
        period_start_time = date_and_period_to_start_time[(settlement_date, settlement_period)]
        pre_settlement_boas = bid_offer_acceptance_data[bid_offer_acceptance_data['acceptance_time'] < period_start_time]
        committed_boas = pre_settlement_boas[pre_settlement_boas['time_from'] < period_start_time]
        pre_settlement_boa_count = pre_settlement_boas.shape[0]
        so_flag_pre_settlement_boas_count = pre_settlement_boas[pre_settlement_boas['so_flag'] == True].shape[0]
        committed_boas_count = committed_boas.shape[0]
        so_flag_or_committed_boas_count = pre_settlement_boas[
            (pre_settlement_boas['so_flag'] == True) | 
            (pre_settlement_boas['time_from'] < period_start_time)
        ].shape[0]
        all_acceptance_count = bid_offer_acceptance_data.shape[0]
        percent_acceptance = pre_settlement_boa_count / all_acceptance_count if all_acceptance_count > 0 else None
        percent_acceptance_of_which_so_flag_or_committed = so_flag_or_committed_boas_count / all_acceptance_count if all_acceptance_count > 0 else None
        results.append((settlement_date, settlement_period, pre_settlement_boa_count, so_flag_pre_settlement_boas_count, committed_boas_count, so_flag_or_committed_boas_count, all_acceptance_count, percent_acceptance, percent_acceptance_of_which_so_flag_or_committed))
    
    pre_settlement_boa_count_df = pd.DataFrame(results, columns=['settlement_date', 'settlement_period', 'pre_settlement_boa_count', 'so_flag_pre_settlement_boas_count', 'committed_boas_count', 'so_flag_or_committed_boas_count', 'all_acceptance_count', 'percent_acceptance', 'percent_acceptance_of_which_so_flag_or_committed'])
    
    return pre_settlement_boa_count_df
    
async def get_settlement_sate_and_period_to_start_time_mapping(
    settlement_dates_with_periods_per_day: dict[str, int],
    api_client: ApiClient
) -> dict[tuple[str, int], str]:
    auxiliary_niv_data = await elexon_interaction.get_niv_data(
    settlement_dates_with_periods_per_day,
    api_client
    )
    auxiliary_niv_data['settlement_date'] = pd.to_datetime(auxiliary_niv_data['settlement_date']).dt.strftime('%Y-%m-%d')
    settlement_date_and_period_to_start_time_dict = {
        (row['settlement_date'], row['settlement_period']): row['start_time']
        for _, row in auxiliary_niv_data.iterrows()
    }
    
    return settlement_date_and_period_to_start_time_dict
