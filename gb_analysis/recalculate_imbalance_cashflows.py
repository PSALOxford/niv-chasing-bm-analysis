import pandas as pd
import gb_analysis.recalculate_niv as recalculate_niv
import ancillary_files.excel_interaction as excel_interaction

def get_recalculated_imbalance_cashflows_SO(
    recalculated_system_price_df: pd.DataFrame, 
    mr1b_data_df : pd.DataFrame,
    npt_ids: list[str],
    zero_metered_volume_only: bool,
    recalculated_system_price_column_name: str = 'recalculated_system_price'
) -> pd.DataFrame:
    current_net_cashflow_df = calculate_current_net_cashflow(mr1b_data_df) #Positive implies revenue for SO
    recalculated_mr1b_data = set_npt_imbalance_volume_to_zero(mr1b_data_df, npt_ids, zero_metered_volume_only)
    recalculated_system_price_by_date_and_period = recalculated_system_price_df.set_index(
        ['settlement_date', 'settlement_period'])[recalculated_system_price_column_name].to_dict()
    recalculated_imbalance_cashflows = recalculate_imbalance_cashflows_SO(recalculated_mr1b_data, recalculated_system_price_by_date_and_period)
    current_net_cashflow_df['settlement_date'] = pd.to_datetime(current_net_cashflow_df['settlement_date']).dt.strftime('%Y-%m-%d')
    cashflows_df = current_net_cashflow_df.merge(recalculated_imbalance_cashflows, on=['settlement_date', 'settlement_period'])
    
    return cashflows_df

def calculate_current_net_cashflow(
    mr1b_data_df: pd.DataFrame
) -> pd.DataFrame:
    imbalance_cashflow_by_date_and_period = []
    mr1b_data_df_copy = mr1b_data_df.copy()
    for settlement_date, mr1b_data_by_date in mr1b_data_df_copy.groupby('Settlement Date'):
        for settlement_period, mr1b_data_by_period in mr1b_data_by_date.groupby('Settlement Period'):
            imbalance_cashflow = mr1b_data_by_period['Imbalance Charge'].sum()
            imbalance_cashflow_by_date_and_period.append((settlement_date, settlement_period, imbalance_cashflow))
    
    imbalance_cashflow_by_date_and_period_df = pd.DataFrame(imbalance_cashflow_by_date_and_period, columns=['settlement_date', 'settlement_period', 'energy_imbalance_cashflow'])
    
    return imbalance_cashflow_by_date_and_period_df

def set_npt_imbalance_volume_to_zero(
    mr1b_raw_data: pd.DataFrame,
    npt_ids: list[str],
    zero_metered_volume_only: bool
) -> pd.DataFrame:
    recalculated_mr1b_data = mr1b_raw_data.copy()
    npt_ids_set = set(npt_ids)
    if zero_metered_volume_only:
        credited_energy_vol_column_name = 'Credited Energy Vol' if 'Credited Energy Vol' in recalculated_mr1b_data.columns else 'CreditedEnergyVol'
        zero_mv_npt_mask = (recalculated_mr1b_data['Party ID'].isin(npt_ids_set)) & (recalculated_mr1b_data[credited_energy_vol_column_name] == 0)
        recalculated_mr1b_data.loc[zero_mv_npt_mask, 'Energy Imbalance Vol'] = 0
    else:
        recalculated_mr1b_data.loc[recalculated_mr1b_data['Party ID'].isin(npt_ids_set), 'Energy Imbalance Vol'] = 0
    
    return recalculated_mr1b_data

def recalculate_imbalance_cashflows_SO(
    recalculated_mr1b_data: pd.DataFrame, 
    recalculated_system_price_by_date_and_period : dict[tuple[str, int], float]
) -> pd.DataFrame:
    recalculated_imbalance_cashflow_by_date_and_period = []
    for settlement_date, recalclated_mr1b_data_by_settlement_date in recalculated_mr1b_data.groupby('Settlement Date'):
        for settlement_period, recalculated_mr1b_data_by_settlement_period in recalclated_mr1b_data_by_settlement_date.groupby('Settlement Period'):
            if type(settlement_date) is not str: settlement_date = settlement_date.strftime('%Y-%m-%d')
            if (settlement_date, settlement_period) not in recalculated_system_price_by_date_and_period:
                continue
            recalculated_system_price = recalculated_system_price_by_date_and_period[(settlement_date, settlement_period)]
            recalculated_imbalance_cashflow = -(recalculated_mr1b_data_by_settlement_period['Energy Imbalance Vol']*recalculated_system_price).sum()
            recalculated_imbalance_cashflow_by_date_and_period.append((settlement_date, settlement_period, recalculated_imbalance_cashflow))
    
    recalculated_imbalance_cashflow_by_date_and_period_df = pd.DataFrame(recalculated_imbalance_cashflow_by_date_and_period, columns=['settlement_date', 'settlement_period', 'recalculated_energy_imbalance_cashflow'])
    
    return recalculated_imbalance_cashflow_by_date_and_period_df

def recalculate_imbalance_cashflows_by_bsc_party_type(
    bsc_party_ids_to_type_mapping: dict[str, bool], 
    recalculated_system_price_df: pd.DataFrame, 
    mr1b_data_df : pd.DataFrame,
    npt_ids: list[str],
    zero_metered_volume_only: bool,
    recalculated_system_price_column_name: str = 'recalculated_system_price'
) -> pd.DataFrame:
    mr1b_df_bsc_type_only = mr1b_data_df[mr1b_data_df['Party ID'].map(bsc_party_ids_to_type_mapping) == True]
    recalculated_system_price_by_date_and_period = recalculated_system_price_df.set_index(
        ['settlement_date', 'settlement_period'])[recalculated_system_price_column_name].to_dict()
    recalculated_imbalance_cashflow_by_date_and_period = get_old_and_new_cashflows_by_bsc_party_type(
        mr1b_df_bsc_type_only, recalculated_system_price_by_date_and_period, npt_ids, zero_metered_volume_only)
    
    return recalculated_imbalance_cashflow_by_date_and_period

def get_old_and_new_cashflows_by_bsc_party_type(
    mr1b_data_by_party_type: pd.DataFrame, 
    recalculated_system_price_by_date_and_period: dict[tuple[str, int], pd.DataFrame],
    npt_ids: list[str],
    zero_metered_volume_only: bool
) -> pd.DataFrame:
    recalculated_imbalance_cashflow_by_date_and_period = []
    mr1b_data_copy = mr1b_data_by_party_type.copy()
    recalculated_mr1b_data = set_npt_imbalance_volume_to_zero(mr1b_data_copy, npt_ids, zero_metered_volume_only)
    for settlement_date, recalclated_mr1b_data_by_settlement_date in recalculated_mr1b_data.groupby('Settlement Date'):
        if type(settlement_date) is not str: settlement_date = settlement_date.strftime('%Y-%m-%d')
        for settlement_period, recalculated_mr1b_data_by_settlement_period in recalclated_mr1b_data_by_settlement_date.groupby('Settlement Period'):
            if (settlement_date, settlement_period) not in recalculated_system_price_by_date_and_period:
                continue
            recalculated_system_price = recalculated_system_price_by_date_and_period[(settlement_date, settlement_period)]
            original_imbalance_cashflow = -recalculated_mr1b_data_by_settlement_period['Imbalance Charge'].sum() # - sign to ensure that positive is profit for party
            recalculated_imbalance_cashflow = (recalculated_mr1b_data_by_settlement_period['Energy Imbalance Vol']*recalculated_system_price).sum()
            recalculated_imbalance_cashflow_by_date_and_period.append((settlement_date, settlement_period, original_imbalance_cashflow, recalculated_imbalance_cashflow))
    
    recalculated_imbalance_cashflow_by_date_and_period_df = pd.DataFrame(
        recalculated_imbalance_cashflow_by_date_and_period, 
        columns=['settlement_date', 'settlement_period', 'energy_imbalance_cashflow', 'recalculated_energy_imbalance_cashflow']
    )
    
    return recalculated_imbalance_cashflow_by_date_and_period_df

def calculate_net_npt_cashflow(
    bsc_party_id_to_npt_mapping: dict[str, bool],
    mr1b_data_df: pd.DataFrame
) -> pd.DataFrame:
    mr1b_df_npts_only = mr1b_data_df[mr1b_data_df['Party ID'].map(bsc_party_id_to_npt_mapping) == True]
    mr1b_data_npts_only_copy = mr1b_df_npts_only.copy()
    mr1b_data_npts_only_copy['Settlement Date'] = pd.to_datetime(mr1b_data_npts_only_copy['Settlement Date']).dt.date
    imbalance_cashflow = []
    for settlement_date, mr1b_data_npts_only_by_settlement_date in mr1b_data_npts_only_copy.groupby('Settlement Date'):
        for settlement_period, mr1b_data_npts_only_by_settlement_period in mr1b_data_npts_only_by_settlement_date.groupby('Settlement Period'):
            factual_imbalance_cashflow = -mr1b_data_npts_only_by_settlement_period['Imbalance Charge'].sum() # - sign to ensure that positive is profit for party
            imbalance_cashflow.append((settlement_date, settlement_period, factual_imbalance_cashflow))
    
    imbalance_cashflow_df = pd.DataFrame(imbalance_cashflow, columns=['settlement_date', 'settlement_period', 'npt_imbalance_cashflow'])

    return imbalance_cashflow_df

def calculate_cashflows_from_excel(
    bsc_roles_filepath: str,
    strict_npt: bool,
    strict_generator: bool,
    strict_supplier: bool,
    mr1b_file_directory: str,
    system_prices_filepath: str,
    output_file_directory: str,
    output_filepath: str,
) -> None:
    bsc_id_to_npt_mapping = recalculate_niv.get_bsc_id_to_npt_mapping(
        bsc_roles_filepath,
        strict_npt
    )
    bsc_id_to_generator_mapping = recalculate_niv.get_bsc_roles_to_generator_mapping(
        bsc_roles_filepath,
        strict_generator
    )
    bsc_id_to_supplier_mapping = recalculate_niv.get_bsc_roles_to_supplier_mapping(
        bsc_roles_filepath,
        strict_supplier
    )
    
    mr1b_data_filepaths = excel_interaction.get_excel_filepaths(mr1b_file_directory)
    system_prices_df = pd.read_excel(system_prices_filepath)
    system_prices_df['settlement_date'] = pd.to_datetime(system_prices_df['settlement_date']).dt.strftime('%Y-%m-%d')
    
    all_so_cashflows = []
    all_supplier_cashflows = []
    all_generator_cashflows = []
    all_npt_cashflows = []
    
    for i, filepath in enumerate(mr1b_data_filepaths):
        mr1b_data_df = pd.read_excel(filepath)
        mr1b_data_df = mr1b_data_df.map(lambda x: x.strip() if isinstance(x, str) else x)
        npt_ids = [k for k, v in bsc_id_to_npt_mapping.items() if v == True]
        so_cashflows_df = get_recalculated_imbalance_cashflows_SO(
            system_prices_df, 
            mr1b_data_df, 
            npt_ids
        )
        supplier_cashflows_df = recalculate_imbalance_cashflows_by_bsc_party_type(
            bsc_id_to_supplier_mapping, 
            system_prices_df, 
            mr1b_data_df, 
            npt_ids
        )
        generator_cashflows_df = recalculate_imbalance_cashflows_by_bsc_party_type(
            bsc_id_to_generator_mapping, 
            system_prices_df, 
            mr1b_data_df, 
            npt_ids
        )
        npt_cashflow_df = calculate_net_npt_cashflow(
            bsc_id_to_npt_mapping,
            mr1b_data_df
        )
        
        so_cashflows_df = so_cashflows_df.dropna()
        supplier_cashflows_df = supplier_cashflows_df.dropna()
        generator_cashflows_df = generator_cashflows_df.dropna()
        npt_cashflow_df = npt_cashflow_df.dropna()
        
        all_so_cashflows.append(so_cashflows_df)
        all_supplier_cashflows.append(supplier_cashflows_df)
        all_generator_cashflows.append(generator_cashflows_df)
        all_npt_cashflows.append(npt_cashflow_df)
        
        print(f"Processed file {i+1} of {len(mr1b_data_filepaths)}")
    
    all_so_cashflows_df = pd.concat(all_so_cashflows, ignore_index=True)
    all_supplier_cashflows_df = pd.concat(all_supplier_cashflows, ignore_index=True)
    all_generator_cashflows_df = pd.concat(all_generator_cashflows, ignore_index=True)
    all_npt_cashflows_df = pd.concat(all_npt_cashflows, ignore_index=True)
    
    ordered_so_cashflows_df = excel_interaction.order_by_settlement_date_and_period(all_so_cashflows_df)
    ordered_supplier_cashflows_df = excel_interaction.order_by_settlement_date_and_period(all_supplier_cashflows_df)
    ordered_generator_cashflows_df = excel_interaction.order_by_settlement_date_and_period(all_generator_cashflows_df)
    ordered_npt_cashflows_df = excel_interaction.order_by_settlement_date_and_period(all_npt_cashflows_df)

    excel_interaction.dataframes_to_excel(
        [
            ordered_so_cashflows_df,
            ordered_supplier_cashflows_df,
            ordered_generator_cashflows_df,
            ordered_npt_cashflows_df
        ],
        output_file_directory,
        output_filepath,
        sheet_names=[
            'SO Cashflows',
            'Supplier Cashflows',
            'Generator Cashflows',
            'NPT Cashflows'
        ]
    )
    
def recalculate_imbalance_cashflows_from_excel(
    bsc_roles_filepath: str,
    imbalance_price_filepath: str,
    imbalance_price_sheet_name: str,
    mr1b_file_directory: str,
    output_directory: str
) -> None:
    bsc_id_to_npt_mapping = recalculate_niv.get_bsc_id_to_npt_mapping(
        bsc_roles_filepath,
        strict_npt_mapping=True
    )
    
    bsc_id_to_generator_mapping = recalculate_niv.get_bsc_roles_to_generator_mapping(
        bsc_roles_filepath,
        strict_generator_mapping=True
    )
    
    bsc_id_to_supplier_mapping = recalculate_niv.get_bsc_roles_to_supplier_mapping(
        bsc_roles_filepath,
        strict_supplier_mapping=True
    )
    
    bsc_id_to_mixed_role_mapping = recalculate_niv.get_bsc_roles_to_mixed_role_mapping(
        bsc_roles_filepath
    )
    
    mr1b_data_filepaths = excel_interaction.get_excel_filepaths(mr1b_file_directory)
    system_prices_df = pd.read_excel(imbalance_price_filepath, sheet_name=imbalance_price_sheet_name)
    system_prices_df['settlement_date'] = pd.to_datetime(system_prices_df['settlement_date']).dt.strftime('%Y-%m-%d')
    all_so_cashflows = []
    all_supplier_cashflows = []
    all_generator_cashflows = []
    all_mixed_role_cashflows = []
    for i, filepath in enumerate(mr1b_data_filepaths):
        mr1b_data_df = pd.read_excel(filepath)
        mr1b_data_df = mr1b_data_df.map(lambda x: x.strip() if isinstance(x, str) else x)
        npt_ids = [k for k, v in bsc_id_to_npt_mapping.items() if v == True]
        so_cashflows_amv_df = get_recalculated_imbalance_cashflows_SO(
            system_prices_df[['settlement_date', 'settlement_period', 'AMV']], 
            mr1b_data_df, 
            npt_ids,
            zero_metered_volume_only=False,
            recalculated_system_price_column_name='AMV'
        )
        supplier_cashflows_amv_df = recalculate_imbalance_cashflows_by_bsc_party_type(
            bsc_id_to_supplier_mapping, 
            system_prices_df[['settlement_date', 'settlement_period', 'AMV']], 
            mr1b_data_df, 
            npt_ids,
            zero_metered_volume_only=False,
            recalculated_system_price_column_name='AMV'
        )
        generator_cashflows_amv_df = recalculate_imbalance_cashflows_by_bsc_party_type(
            bsc_id_to_generator_mapping, 
            system_prices_df[['settlement_date', 'settlement_period', 'AMV']], 
            mr1b_data_df,
            npt_ids,
            zero_metered_volume_only=False,
            recalculated_system_price_column_name='AMV'
        )
        mixed_cashflows_amv_df = recalculate_imbalance_cashflows_by_bsc_party_type(
            bsc_id_to_mixed_role_mapping,
            system_prices_df[['settlement_date', 'settlement_period', 'AMV']],
            mr1b_data_df,
            npt_ids,
            zero_metered_volume_only=False,
            recalculated_system_price_column_name='AMV'
        )
        
        so_cashflows_zmv_df = get_recalculated_imbalance_cashflows_SO(
            system_prices_df[['settlement_date', 'settlement_period', 'ZMV']], 
            mr1b_data_df, 
            npt_ids,
            zero_metered_volume_only=True,
            recalculated_system_price_column_name='ZMV'
        )
        supplier_cashflows_zmv_df = recalculate_imbalance_cashflows_by_bsc_party_type(
            bsc_id_to_supplier_mapping, 
            system_prices_df[['settlement_date', 'settlement_period', 'ZMV']], 
            mr1b_data_df, 
            npt_ids,
            zero_metered_volume_only=True,
            recalculated_system_price_column_name='ZMV'
        )
        generator_cashflows_zmv_df = recalculate_imbalance_cashflows_by_bsc_party_type(
            bsc_id_to_generator_mapping, 
            system_prices_df[['settlement_date', 'settlement_period', 'ZMV']], 
            mr1b_data_df,
            npt_ids,
            zero_metered_volume_only=True,
            recalculated_system_price_column_name='ZMV'
        )
        mixed_cashflows_zmv_df = recalculate_imbalance_cashflows_by_bsc_party_type(
            bsc_id_to_mixed_role_mapping,
            system_prices_df[['settlement_date', 'settlement_period', 'ZMV']],
            mr1b_data_df,
            npt_ids,
            zero_metered_volume_only=True,
            recalculated_system_price_column_name='ZMV'
        )
        
        so_cashflows_df = so_cashflows_amv_df.merge(
            so_cashflows_zmv_df,
            on=['settlement_date', 'settlement_period'],
            suffixes=('_amv', '_zmv')
        )
        
        supplier_cashflows_df = supplier_cashflows_amv_df.merge(
            supplier_cashflows_zmv_df,
            on=['settlement_date', 'settlement_period'],
            suffixes=('_amv', '_zmv')
        )
        
        generator_cashflows_df = generator_cashflows_amv_df.merge(
            generator_cashflows_zmv_df,
            on=['settlement_date', 'settlement_period'],
            suffixes=('_amv', '_zmv')
        )
        
        mixed_cashflows_df = mixed_cashflows_amv_df.merge(
            mixed_cashflows_zmv_df,
            on=['settlement_date', 'settlement_period'],
            suffixes=('_amv', '_zmv')
        )
        
        all_so_cashflows.append(so_cashflows_df)
        all_supplier_cashflows.append(supplier_cashflows_df)
        all_generator_cashflows.append(generator_cashflows_df)
        all_mixed_role_cashflows.append(mixed_cashflows_df)
        print(f"Processed file {i+1} of {len(mr1b_data_filepaths)}")
        
    all_so_cashflows_df = pd.concat(all_so_cashflows, ignore_index=True)
    all_supplier_cashflows_df = pd.concat(all_supplier_cashflows, ignore_index=True)
    all_generator_cashflows_df = pd.concat(all_generator_cashflows, ignore_index=True)
    all_mixed_role_cashflows_df = pd.concat(all_mixed_role_cashflows, ignore_index=True)
    
    ordered_so_cashflows_df = excel_interaction.order_by_settlement_date_and_period(all_so_cashflows_df)
    ordered_supplier_cashflows_df = excel_interaction.order_by_settlement_date_and_period(all_supplier_cashflows_df)
    ordered_generator_cashflows_df = excel_interaction.order_by_settlement_date_and_period(all_generator_cashflows_df)
    ordered_mixed_role_cashflows_df = excel_interaction.order_by_settlement_date_and_period(all_mixed_role_cashflows_df)

    excel_interaction.dataframes_to_excel(
        [
            ordered_so_cashflows_df,
            ordered_supplier_cashflows_df,
            ordered_generator_cashflows_df,
            ordered_mixed_role_cashflows_df
        ],
        output_directory,
        'Imbalance Cashflows',
        sheet_names=[
            'SO Cashflows',
            'Supplier Cashflows',
            'Generator Cashflows',
            'Mixed Role Cashflows'
        ]
    )
    
    
    