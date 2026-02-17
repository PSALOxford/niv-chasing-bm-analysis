import numpy as np
import pandas as pd

from ancillary_files.excel_interaction import get_csv_filepaths, dataframes_to_excel
from data_collection.elexon_interaction import get_full_midp_data, get_price_adjustment_data
from elexonpy.api_client import ApiClient
from data_processing.stack_data_handler import check_missing_data

async def get_ancillary_price_data_for_sp_calculation(
    api_client: ApiClient,
    settlement_dates_with_periods_per_day: dict[str, int],
    missing_data = set[tuple[str, int]]
):
    mid_data = await get_market_index_price_data(settlement_dates_with_periods_per_day, api_client)
    missing_mid_data = check_missing_data(mid_data, settlement_dates_with_periods_per_day)
    missing_data.update(missing_mid_data)
    
    price_adjustment_data = await get_price_adjustment_data(['settlement_date', 'settlement_period', 'buy_price_price_adjustment', 'sell_price_price_adjustment'], settlement_dates_with_periods_per_day, api_client)
    if price_adjustment_data.empty: 
        combined_price_data = mid_data.copy()
        combined_price_data['buy_price_price_adjustment'] = 0
        combined_price_data['sell_price_price_adjustment'] = 0
    else:
        combined_price_data = mid_data.merge(
            price_adjustment_data,
            on=['settlement_date', 'settlement_period'],
            how='outer'
        )
        combined_price_data[['buy_price_price_adjustment', 'sell_price_price_adjustment']] = combined_price_data[['buy_price_price_adjustment', 'sell_price_price_adjustment']].fillna(0)
    
    return combined_price_data
    
async def get_market_index_price_data(
    settlement_dates_with_periods_per_day: dict[str, int], 
    api_client: ApiClient
) -> pd.DataFrame:
    combined_market_index_data = await get_full_midp_data(api_client, settlement_dates_with_periods_per_day)
    n2ex_data = combined_market_index_data[combined_market_index_data['data_provider'] == 'N2EXMIDP']
    apx_data = combined_market_index_data[combined_market_index_data['data_provider'] == 'APXMIDP']
    combined_market_index_data = pd.concat([n2ex_data, apx_data])
    combined_market_index_data['weighted_price'] = combined_market_index_data['price'] * combined_market_index_data['volume']
    grouped_data = combined_market_index_data.groupby(['settlement_date', 'settlement_period']).agg(
        total_volume=pd.NamedAgg(column='volume', aggfunc='sum'),
        total_weighted_price=pd.NamedAgg(column='weighted_price', aggfunc='sum')
    )
    grouped_data['vwap_midp'] = grouped_data['total_weighted_price'] / grouped_data['total_volume']
    result = grouped_data.reset_index()[['settlement_date', 'settlement_period', 'vwap_midp']]
    result = result.drop_duplicates()
    
    return result

def calculate_best_buy_and_sell_prices_by_delivery_period(
    folder_directory: str,
    output_folder_directory: str,
    output_filename: str
) -> None:
    csv_filepaths = get_csv_filepaths(folder_directory)
    headers = ['boundary_time', 'high_pr', 'low_pr', 'buy_best_1mw', 'buy_best_10mw', 
               'buy_best_25mw', 'sell_best_1mw', 'sell_best_10mw', 'sell_best_25mw', 
               'total_qty', 'start_time']
    
    all_dataframes = []
    for filepath in csv_filepaths:
        df = pd.read_csv(filepath, names=headers)
        df['start_time'] = pd.to_datetime(df['start_time'], errors='coerce', utc=True)
        all_dataframes.append(df)
    
    combined_df = pd.concat(all_dataframes, ignore_index=True)
    combined_df = combined_df.dropna(subset=['start_time'])
    results_df = combined_df.groupby('start_time').agg({
        'buy_best_1mw': 'mean',
        'sell_best_1mw': 'mean', 
        'buy_best_10mw': 'mean',
        'sell_best_10mw': 'mean',
        'buy_best_25mw': 'mean',
        'sell_best_25mw': 'mean',
        'high_pr': lambda x: np.divide(
        (x * combined_df.loc[x.index, 'total_qty']).sum(), 
        combined_df.loc[x.index, 'total_qty'].sum(),
        out=np.full(1, np.nan), 
        where=combined_df.loc[x.index, 'total_qty'].sum()!=0
    )[0],
    'low_pr': lambda x: np.divide(
        (x * combined_df.loc[x.index, 'total_qty']).sum(), 
        combined_df.loc[x.index, 'total_qty'].sum(),
        out=np.full(1, np.nan), 
        where=combined_df.loc[x.index, 'total_qty'].sum()!=0
    )[0]
    }).reset_index()
    
    results_df.columns = [
        'start_time',
        'average_best_buy_1mw',
        'average_best_sell_1mw',
        'average_best_buy_10mw',
        'average_best_sell_10mw',
        'average_best_buy_25mw',
        'average_best_sell_25mw',
        'vwap_high_price',
        'vwap_low_price'
    ]
    
    results_df = results_df[[
        'start_time',
        'vwap_high_price',
        'vwap_low_price',
        'average_best_buy_1mw',
        'average_best_buy_10mw',
        'average_best_buy_25mw',
        'average_best_sell_1mw',
        'average_best_sell_10mw',
        'average_best_sell_25mw'
    ]]
    results_df['start_time'] = results_df['start_time'].dt.tz_localize(None)
    dataframes_to_excel([results_df], output_folder_directory, output_filename)
        
