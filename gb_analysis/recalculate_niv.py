import pandas as pd
from data_collection import elexon_interaction
from elexonpy.api_client import ApiClient
from data_processing.stack_data_handler import check_missing_data

async def recalculate_niv(
    settlement_dates_and_periods_per_day: dict[str, int],
    mr1b_df: pd.DataFrame,
    bsc_roles_to_npt_mapping: str,
    missing_data: set[tuple[str, int]]
) -> pd.DataFrame:
    api_client = ApiClient()
    niv_data = await elexon_interaction.get_niv_data(settlement_dates_and_periods_per_day, api_client)
    npt_imbalances = get_npt_imbalance_data(mr1b_df, bsc_roles_to_npt_mapping)
    niv_data.drop(columns=['start_time'], inplace=True)
    
    outturn_system_length = standardize_merge_columns(niv_data)
    npt_imbalances = standardize_merge_columns(npt_imbalances)
    
    combined_data = outturn_system_length.merge(
        npt_imbalances, 
        on=['settlement_date', 'settlement_period'], 
        how='outer'
    )
    combined_data['counterfactual_niv'] = combined_data['net_imbalance_volume'] + combined_data['npt_total_imbalance']
    missing_dates_and_periods = check_missing_data(combined_data, settlement_dates_and_periods_per_day)
    missing_data.update(missing_dates_and_periods)

    return combined_data

async def recalculate_niv_zero_metered_volume(
    settlement_dates_and_periods_per_day: dict[str, int],
    mr1b_df: pd.DataFrame,
    bsc_roles_to_npt_mapping: str,
    missing_data: set[tuple[str, int]],
    api_client: ApiClient
) -> pd.DataFrame:
    niv_data = await elexon_interaction.get_niv_data(settlement_dates_and_periods_per_day, api_client)
    niv_data.drop(columns=['start_time'], inplace=True)
    npt_zero_mv_imbalances = get_npt_imbalance_data_zero_metered_volume(
        mr1b_df,
        bsc_roles_to_npt_mapping
    )
    # npt_imbalance = get_npt_imbalance_data(
    #     mr1b_df,
    #     bsc_roles_to_npt_mapping
    # )
    
    outturn_system_length = standardize_merge_columns(niv_data)
    npt_zero_mv_imbalances = standardize_merge_columns(npt_zero_mv_imbalances)
    # npt_imbalance = standardize_merge_columns(npt_imbalance)
    combined_data = outturn_system_length.merge(
        npt_zero_mv_imbalances, 
        on=['settlement_date', 'settlement_period'], 
        how='outer')
    # .merge(
    #     npt_imbalance,
    #     on=['settlement_date', 'settlement_period'],
    #     how='outer'
    # )
    combined_data['counterfactual_niv'] = combined_data['net_imbalance_volume'] + combined_data['npt_total_imbalance']
    # combined_data['counterfactual_niv'] = combined_data['net_imbalance_volume'] + combined_data['npt_total_imbalance']
    missing_dates_and_periods = check_missing_data(combined_data, settlement_dates_and_periods_per_day)
    missing_data.update(missing_dates_and_periods)

    return combined_data

def get_bsc_id_to_npt_mapping(
    bsc_roles_filepath: str,
    strict_npt_mapping: bool
) -> dict[str, bool]:
    bsc_roles_df = pd.read_excel(bsc_roles_filepath)
    
    if strict_npt_mapping:
        mask = bsc_roles_df['TN'] & ~bsc_roles_df['TS'] & ~bsc_roles_df['TG']
    else:
        mask = bsc_roles_df['TN']
    
    bsc_id_to_npt_mapping = dict(zip(bsc_roles_df['BSC_ID'], mask))
    
    return bsc_id_to_npt_mapping

def get_bsc_roles_to_supplier_mapping(
    bsc_roles_filepath: str,
    strict_supplier_mapping: bool
) -> dict[str, bool]:
    bsc_roles_df = pd.read_excel(bsc_roles_filepath)
    bsc_id_to_supplier_mapping = {}
    for _, row in bsc_roles_df.iterrows():
        is_supplier = row['TS']
        is_strict_supplier = is_supplier and not row['TN'] and not row['TG']
        bsc_id_to_supplier_mapping[row['BSC_ID']] = is_strict_supplier if strict_supplier_mapping else is_supplier
        
    return bsc_id_to_supplier_mapping

def get_bsc_roles_to_generator_mapping(
    bsc_roles_filepath: str,
    strict_generator_mapping: bool
) -> dict[str, bool]:
    bsc_roles_df = pd.read_excel(bsc_roles_filepath)
    bsc_id_to_generator_mapping = {}
    for _, row in bsc_roles_df.iterrows():
        is_generator = row['TG']
        is_strict_generator = is_generator and not row['TN'] and not row['TS']
        bsc_id_to_generator_mapping[row['BSC_ID']] = is_strict_generator if strict_generator_mapping else is_generator
        
    return bsc_id_to_generator_mapping

def get_bsc_roles_to_mixed_role_mapping(
    bsc_roles_filepath: str
) -> dict[str, bool]:
    bsc_roles_df = pd.read_excel(bsc_roles_filepath)
    bsc_id_to_mixed_role_mapping = {}
    for _, row in bsc_roles_df.iterrows():
        is_mixed_role = (row['TN'] and row['TS']) or (row['TN'] and row['TG']) or (row['TS'] and row['TG'])
        bsc_id_to_mixed_role_mapping[row['BSC_ID']] = is_mixed_role
        
    return bsc_id_to_mixed_role_mapping

def get_npt_imbalance_data(
    mr1b_df: pd.DataFrame,
    bsc_roles_to_npt_mapping: dict
) -> pd.DataFrame:
    mr1b_df = mr1b_df.map(lambda x: x.strip() if isinstance(x, str) else x)
    mr1b_df_npts_only = mr1b_df[mr1b_df['Party ID'].map(bsc_roles_to_npt_mapping) == True]
    # settlement_dates = []
    # settlement_periods = []
    # energy_imbalances = []
    # for settlement_date, group in mr1b_df_npts_only.groupby('Settlement Date'):
    #     for settlement_period, group_by_period in group.groupby('Settlement Period'):
    #         energy_imbalance = group_by_period['Energy Imbalance Vol'].sum()
    #         settlement_dates.append(settlement_date)
    #         settlement_periods.append(settlement_period)
    #         energy_imbalances.append(energy_imbalance)
    grouped = mr1b_df_npts_only.groupby(['Settlement Date', 'Settlement Period'])['Energy Imbalance Vol'].sum().reset_index()
    grouped.columns = ['settlement_date', 'settlement_period', 'npt_total_imbalance']
    
    return grouped

def get_npt_imbalance_data_zero_metered_volume(
    mr1b_df: pd.DataFrame,
    bsc_roles_to_npt_mapping: dict
) -> pd.DataFrame:
    mr1b_df = mr1b_df.map(lambda x: x.strip() if isinstance(x, str) else x)
    mr1b_df_npts_only = mr1b_df[mr1b_df['Party ID'].map(bsc_roles_to_npt_mapping) == True]
    credited_energy_vol_column_name = 'Credited Energy Vol' if 'Credited Energy Vol' in mr1b_df_npts_only.columns else 'CreditedEnergyVol'
    mr1b_df_npts_zero_metered_vol_only = mr1b_df_npts_only[mr1b_df_npts_only[credited_energy_vol_column_name] == 0]
    grouped = mr1b_df_npts_zero_metered_vol_only.groupby(['Settlement Date', 'Settlement Period'])['Energy Imbalance Vol'].sum().reset_index()
    grouped.columns = ['settlement_date', 'settlement_period', 'npt_total_imbalance']
    
    return grouped

def standardize_merge_columns(
    df: pd.DataFrame
):
    df = df.copy()
    df['settlement_date'] = pd.to_datetime(df['settlement_date']).dt.date.astype(str)
    df['settlement_period'] = df['settlement_period'].astype(int)
    return df