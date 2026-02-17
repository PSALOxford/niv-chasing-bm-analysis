import pandas as pd
import ancillary_files.excel_interaction as excel_interaction

def calculate_marginal_emissions(
    full_ascending_settlement_stack_by_date_and_period: dict[tuple[str, int], pd.DataFrame],
    new_settlement_stacks_by_date_and_period: dict[tuple[str, int], pd.DataFrame],
    system_imbalance_with_and_without_npts_by_date_and_period: pd.DataFrame,
    bmu_id_to_ci_mapping: dict[str, float]
) -> pd.DataFrame:
    mefs = []
    for (settlement_date, settlement_period), settlement_stack in full_ascending_settlement_stack_by_date_and_period.items():
        if (settlement_date, settlement_period) not in new_settlement_stacks_by_date_and_period:
            mefs.append(settlement_date, settlement_period, None, None)
            continue
        
        new_stack = new_settlement_stacks_by_date_and_period[(settlement_date, settlement_period)]
        row = system_imbalance_with_and_without_npts_by_date_and_period.loc[
            (system_imbalance_with_and_without_npts_by_date_and_period['settlement_date'] == settlement_date) &
            (system_imbalance_with_and_without_npts_by_date_and_period['settlement_period'] == settlement_period)
        ]
        if row.empty:
            mefs.append((settlement_date, settlement_period, None, None))
            continue
        system_imbalance = row['net_imbalance_volume'].values[0]
        counterfactual_imbalance = row['counterfactual_niv'].values[0]
        
        if system_imbalance is None or settlement_stack.empty:
            mefs.append((settlement_date, settlement_period, None, None))
            continue
        factual_mef, factual_bmu_id = get_mef_and_bmu_id(system_imbalance, settlement_stack, bmu_id_to_ci_mapping)
        if counterfactual_imbalance is None or new_stack.empty:
            mefs.append((settlement_date, settlement_period, factual_mef, factual_bmu_id, None, None))
            continue
        counterfactual_mef, counterfactual_bmu_id = get_mef_and_bmu_id(counterfactual_imbalance, new_stack, bmu_id_to_ci_mapping)
        
        mefs.append((settlement_date, settlement_period, factual_mef, factual_bmu_id, counterfactual_mef, counterfactual_bmu_id))
    
    mef_df = pd.DataFrame(mefs, columns=['settlement_date', 'settlement_period', 'factual_mef', 'factual_marginal_unit', 'counterfactual_mef', 'counterfactual_marginal_unit'])
    
    return mef_df
        
def get_mef_and_bmu_id(
    system_imbalance: float,
    settlement_stack: pd.DataFrame,
    bmu_id_to_ci_mapping: dict[str, float]
) -> float | None:
    if settlement_stack.empty:
        return None
    unflagged_settlement_stack = settlement_stack[settlement_stack['so_flag'] == False]
    if unflagged_settlement_stack.empty:
        return None, None
    if system_imbalance > 0:
        marginal_action = unflagged_settlement_stack.iloc[0]
    else:
        marginal_action = unflagged_settlement_stack.iloc[-1]
    
    marginal_action_bmu_id = marginal_action['id']
    
    if marginal_action_bmu_id in bmu_id_to_ci_mapping:
        mef = bmu_id_to_ci_mapping[marginal_action_bmu_id]
    else:
        mef = None
    
    return mef, marginal_action_bmu_id

def create_emissions_dataset(
    bm_units_json_filepath: str,
    carbon_intensity_by_fuel_type_filepath: str,
    output_filename: str,
    output_directory: str
) -> None:
    bm_units_df = pd.read_json(bm_units_json_filepath)
    carbon_intensity_by_fuel_type_df = pd.read_excel(carbon_intensity_by_fuel_type_filepath)
    carbon_intensity_by_fuel_type = carbon_intensity_by_fuel_type_df.set_index('FUEL')['kgCO2/MWh'].to_dict()
    for index, bm_unit in bm_units_df.iterrows():
        bm_fuel_type = bm_unit['fuelType']
        if bm_fuel_type in carbon_intensity_by_fuel_type:
            bm_units_df.loc[index, 'carbon_intensity'] = carbon_intensity_by_fuel_type[bm_fuel_type]
        else:
            bm_units_df.loc[index, 'carbon_intensity'] = None
    
    ci_data = bm_units_df[['elexonBmUnit', 'carbon_intensity']]
    ci_data = ci_data.dropna()
    
    excel_interaction.dataframes_to_excel(
        [ci_data],
        output_directory,
        output_filename
    )