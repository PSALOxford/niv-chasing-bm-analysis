import pandas as pd
from ancillary_files.datetime_functions import get_settlement_date_period_to_utc_start_time_mapping
from ancillary_files.excel_interaction import dataframes_to_excel

def calculate_id_position(
    system_imbalance_with_and_without_npts_df: pd.DataFrame,
    ancillary_price_data_df: pd.DataFrame
) -> pd.DataFrame:
    npt_aggregate_imbalance = system_imbalance_with_and_without_npts_df[['settlement_date', 'settlement_period']].copy()
    npt_aggregate_imbalance['npt_net_id_position'] = -system_imbalance_with_and_without_npts_df['npt_total_imbalance']
    mid_price_df = ancillary_price_data_df[['settlement_date', 'settlement_period', 'vwap_midp']].copy()
    mid_price_df['settlement_date'] = pd.to_datetime(mid_price_df['settlement_date']).dt.strftime('%Y-%m-%d')
    npt_aggregate_imbalance = npt_aggregate_imbalance.merge(
        mid_price_df, 
        on=['settlement_date', 'settlement_period'], 
        how='outer'
    )
    npt_aggregate_imbalance['id_cashflow'] = npt_aggregate_imbalance['npt_net_id_position'] * npt_aggregate_imbalance['vwap_midp']
    npt_aggregate_imbalance = npt_aggregate_imbalance[['settlement_date', 'settlement_period', 'id_cashflow']]
    
    return npt_aggregate_imbalance

def calculate_npt_welfare_midp(
    npt_cashflows_df: pd.DataFrame,
    npt_intraday_position: pd.DataFrame
) -> pd.DataFrame:
    npt_cashflows_df['settlement_date'] = pd.to_datetime(npt_cashflows_df['settlement_date']).dt.strftime('%Y-%m-%d')
    npt_intraday_position['settlement_date'] = pd.to_datetime(npt_intraday_position['settlement_date']).dt.strftime('%Y-%m-%d')
    npt_welfare = npt_cashflows_df.merge(
        npt_intraday_position, 
        on=['settlement_date', 'settlement_period'], 
        how='outer'
    )
    npt_welfare['npt_welfare'] = npt_welfare['npt_imbalance_cashflow'] + npt_welfare['id_cashflow']
    
    return npt_welfare

def calculate_npt_welfare_from_id_prices(
    id_price_filepath: str,
    system_imbalance_filepath: str,
    output_file_directory: str,
    output_file_name: str
) -> None:
    id_prices_df = pd.read_excel(id_price_filepath)
    id_prices_df['start_time'] = pd.to_datetime(id_prices_df['start_time'], errors='coerce', utc=True)
    id_prices_df.drop(columns=['vwap_high_price', 'vwap_low_price'], inplace=True)
    system_imbalance_df = pd.read_excel(system_imbalance_filepath)
    years = system_imbalance_df['settlement_date'].dt.year.unique()
    system_imbalance_df['settlement_date'] = pd.to_datetime(system_imbalance_df['settlement_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    settlement_date_period_to_utc_start_time_mapping = get_settlement_date_period_to_utc_start_time_mapping(years)
    settlement_date_period_to_utc_start_time_mapping_df = pd.DataFrame([
        (key[0], key[1], value) 
        for key, value in settlement_date_period_to_utc_start_time_mapping.items()
    ])
    settlement_date_period_to_utc_start_time_mapping_df.columns = ['settlement_date', 'settlement_period', 'start_time']
    system_imbalance_df = system_imbalance_df.merge(
        settlement_date_period_to_utc_start_time_mapping_df,
        on=['settlement_date', 'settlement_period'],
        how='left'
    )
    
    system_imbalance_df = system_imbalance_df[['settlement_date', 'settlement_period', 'start_time', 'npt_total_imbalance', 'SP']]
    
    combined_df = system_imbalance_df.merge(
        id_prices_df,
        on=['start_time']
    )
    combined_df['applicable_1mw_price'] = combined_df.apply(
        lambda row: row['average_best_sell_1mw'] if row['npt_total_imbalance'] < 0 else row['average_best_buy_1mw'], axis=1
    )
    combined_df['applicable_10mw_price'] = combined_df.apply(
        lambda row: row['average_best_sell_10mw'] if row['npt_total_imbalance'] < 0 else row['average_best_buy_10mw'], axis=1
    )
    combined_df['applicable_25mw_price'] = combined_df.apply(
        lambda row: row['average_best_sell_25mw'] if row['npt_total_imbalance'] < 0 else row['average_best_buy_25mw'], axis=1
    )
    combined_df['1mw_value'] = combined_df['applicable_1mw_price'] * combined_df['npt_total_imbalance'] * 2 / 100 #Multiple by 2 as best price values given for a MW hour; divide by 100 as given in pence]
    combined_df['10mw_value'] = combined_df['applicable_10mw_price'] * combined_df['npt_total_imbalance'] * 2 / 100
    combined_df['25mw_value'] = combined_df['applicable_25mw_price'] * combined_df['npt_total_imbalance'] * 2 / 100
    
    combined_df['npt_imbalance_cashflow'] = combined_df['npt_total_imbalance'] * combined_df['SP']
    
    combined_df['1mw_profit'] = combined_df['npt_imbalance_cashflow'] - combined_df['1mw_value']
    combined_df['10mw_profit'] = combined_df['npt_imbalance_cashflow'] - combined_df['10mw_value']
    combined_df['25mw_profit'] = combined_df['npt_imbalance_cashflow'] - combined_df['25mw_value']
    
    combined_df = combined_df.dropna()
    combined_df['start_time'] = combined_df['start_time'].dt.tz_localize(None)
    
    dataframes_to_excel(
        [combined_df],
        output_file_directory,
        output_file_name
    )
    