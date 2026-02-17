import datetime
import calendar

import pandas as pd
import ancillary_files.datetime_functions as datetime_functions
import ancillary_files.excel_interaction as excel_interaction
import data_collection.elexon_interaction as elexon_interaction
from  data_processing.price_data_processing import get_ancillary_price_data_for_sp_calculation
import gb_analysis.recalculate_niv as recalculate_niv
import gb_analysis.recalculate_settlement_stack as recalculate_settlement_stack
import gb_analysis.recalculate_balancing_cashflows as recalculate_balancing_cashflows
import gb_analysis.recalculate_imbalance_cashflows as recalculate_imbalance_cashflows
import gb_analysis.calculate_npt_profit as calculate_npt_profit
import gb_analysis.carbon_emissions as carbon_emissions
from gb_analysis.summary import create_summary_table
from gb_analysis.system_price_from_stack import get_new_system_prices_by_date_and_period 
from elexonpy.api_client import ApiClient

async def run(
    years: list,
    months: list, 
    output_directory: str,
    bsc_roles_filepath: str,
    tlms_filepath: str,
    bmu_to_carbon_intensity_filepath: str,
    strict_npt: bool,
    strict_supplier: bool,
    strict_generator: bool,
    zero_metered_volume_only: bool
) -> None:
    system_prices = []
    system_imbalances = []
    balancing_costs = []
    original_balancing_revenue = []
    new_balancing_revenue = []
    so_cashflows = []
    supplier_cashflows = []
    generator_cashflows = []
    intraday_cashflows = []
    npt_cashflows = []
    mefs = []
    all_missing_data = set()
    mr1b_filepaths = excel_interaction.get_excel_filepaths('/Users/josephcary/Library/CloudStorage/OneDrive-Nexus365/First Year/Data/Elexon/MR1B Excel Reports')
    filepath_dict = excel_interaction.create_filepath_dict(mr1b_filepaths)
    bsc_id_to_npt_mapping = recalculate_niv.get_bsc_id_to_npt_mapping(bsc_roles_filepath, strict_npt)
    bsc_id_to_supplier_mapping = recalculate_niv.get_bsc_roles_to_supplier_mapping(bsc_roles_filepath, strict_supplier)
    bsc_id_to_generator_mapping = recalculate_niv.get_bsc_roles_to_generator_mapping(bsc_roles_filepath, strict_generator)
    tlms_by_bmu = excel_interaction.create_dict_from_excel(tlms_filepath, 'BM Unit ID', 'TLM')
    bmu_id_to_ci_dict = excel_interaction.create_dict_from_excel(bmu_to_carbon_intensity_filepath, 'BMU_ID', 'Carbon Intensity')
    for year in years:
        for month in months:
            year_month = datetime.date(year, month, 1).strftime('%Y-%m')
            mr1b_filepath = filepath_dict[year_month.replace('-', '_')]
            await run_by_month(
                month, year, bsc_id_to_npt_mapping, bsc_id_to_supplier_mapping, bsc_id_to_generator_mapping, tlms_by_bmu, bmu_id_to_ci_dict, 
                mr1b_filepath, output_directory, system_prices, system_imbalances, balancing_costs, original_balancing_revenue, 
                new_balancing_revenue, so_cashflows, supplier_cashflows, generator_cashflows, intraday_cashflows, npt_cashflows, mefs, all_missing_data, zero_metered_volume_only)
    
    system_prices_df = pd.concat(system_prices)
    system_imbalances_df = pd.concat(system_imbalances)
    balancing_costs_df = pd.concat(balancing_costs)
    original_balancing_revenue_df = pd.concat(original_balancing_revenue)
    new_balancing_revenue_df = pd.concat(new_balancing_revenue)
    so_cashflows_df = pd.concat(so_cashflows)
    supplier_cashflows_df = pd.concat(supplier_cashflows)
    generator_cashflows_df = pd.concat(generator_cashflows)
    intraday_cashflows_df = pd.concat(intraday_cashflows)
    npt_cashflows_df = pd.concat(npt_cashflows)
    mefs_df = pd.concat(mefs)
    missing_data_df = pd.DataFrame(list(all_missing_data), columns=['settlement_date', 'settlement_period'])
    summary_df = create_summary_table(system_prices_df, system_imbalances_df, balancing_costs_df, so_cashflows_df, supplier_cashflows_df, generator_cashflows_df, intraday_cashflows_df, mefs_df)
    
    sheet_names_dict = {
        'Summary': summary_df,
        'Missing Data': missing_data_df,
        'System Prices': system_prices_df,
        'System Imbalances': system_imbalances_df,
        'Balancing Costs': balancing_costs_df,
        'Original Balancing Revenue': original_balancing_revenue_df,
        'New Balancing Revenue': new_balancing_revenue_df,
        'SO Cashflows': so_cashflows_df,
        'Supplier Cashflows': supplier_cashflows_df,
        'Generator Cashflows': generator_cashflows_df,
        'Intraday Cashflows': intraday_cashflows_df,
        'NPT Cashflows': npt_cashflows_df,
        'MEFs': mefs_df
    }
    file_name = f'{years[0]}-{months[0]}_to_{years[-1]}-{months[-1]}_results'
    excel_interaction.dataframes_to_excel(sheet_names_dict.values(), output_directory, file_name, sheet_names_dict.keys())
    print("Completed all months")
    print(f"Missing data points: {len(all_missing_data)}")
    
async def run_by_month(
    month: int, 
    year: int, 
    bsc_roles_to_npt_mapping : dict[str, bool],
    bsc_roles_to_supplier_mapping : dict[str, bool],
    bsc_roles_to_generator_mapping : dict[str, bool],
    tlms_by_bmu: dict[str, float],
    bmu_id_to_ci_mapping: dict[str, float],
    mr1b_filepath: str, 
    output_directory: str, 
    system_prices: list, 
    system_imbalances: list, 
    balancing_costs: list, 
    original_balancing_revenue: list, 
    new_balancing_revenue: list, 
    so_cashflows: list, 
    supplier_cashflows: list, 
    generator_cashflows: list,
    intraday_cashflows: list,
    npt_cashflows: list,
    mefs: list,
    all_missing_data: set[tuple[str, int]],
    zero_metered_volume_only: bool
) -> None:
    month_start_date = datetime.date(year, month, 1).strftime('%Y-%m-%d')
    _, last_day = calendar.monthrange(year, month)
    month_end_date = datetime.date(year, month, last_day).strftime('%Y-%m-%d')
    settlement_dates_with_periods_per_day = datetime_functions.get_settlement_dates_and_settlement_periods_per_day(month_start_date, month_end_date)
    api_client = ApiClient()
    missing_data_points = set()
    
    # Recalculate imbalance, stack, and system price
    mr1b_df = pd.read_excel(mr1b_filepath)
    mr1b_df = mr1b_df.map(lambda x: x.strip() if isinstance(x, str) else x)
    full_ascending_settlement_stack_by_date_and_period = await elexon_interaction.get_full_settlement_stacks_by_date_and_period(api_client, settlement_dates_with_periods_per_day, missing_data_points)
    if zero_metered_volume_only:
        system_imbalance_with_and_without_npts_df = await recalculate_niv.recalculate_niv_zero_metered_volume(settlement_dates_with_periods_per_day, mr1b_df, bsc_roles_to_npt_mapping, missing_data_points, api_client)
    else:
        system_imbalance_with_and_without_npts_df = await recalculate_niv.recalculate_niv(settlement_dates_with_periods_per_day, mr1b_df, bsc_roles_to_npt_mapping, missing_data_points)
    ancillary_price_data_for_sp_calculation = await get_ancillary_price_data_for_sp_calculation(api_client, settlement_dates_with_periods_per_day, missing_data_points)
    new_settlement_stacks_by_date_and_period = await recalculate_settlement_stack.recalculate_stacks(
        api_client, settlement_dates_with_periods_per_day, system_imbalance_with_and_without_npts_df, full_ascending_settlement_stack_by_date_and_period, missing_data_points)
    new_system_prices_by_date_and_period_df = get_new_system_prices_by_date_and_period(
        new_settlement_stacks_by_date_and_period, ancillary_price_data_for_sp_calculation, tlms_by_bmu, system_imbalance_with_and_without_npts_df)
    system_price_df = system_imbalance_with_and_without_npts_df[['settlement_date', 'settlement_period', 'system_sell_price']]
    recalculated_system_prices = system_price_df.merge(
        new_system_prices_by_date_and_period_df, on=['settlement_date', 'settlement_period'], 
        how='outer'
    )
    
    # Recalculate balancing cashflows
    balancing_costs_df = recalculate_balancing_cashflows.calculate_balancing_costs(full_ascending_settlement_stack_by_date_and_period, new_settlement_stacks_by_date_and_period)
    original_balancing_revenue_by_group_df, new_balancing_revenue_by_group_df = recalculate_balancing_cashflows.get_original_and_new_balancing_revenue_dfs(
        full_ascending_settlement_stack_by_date_and_period, new_settlement_stacks_by_date_and_period)
    
    # Recalculate imbalance cashflows
    npt_bsc_ids = [bsc_id for bsc_id, is_npt in bsc_roles_to_npt_mapping.items() if is_npt]
    so_cashflows_df = recalculate_imbalance_cashflows.get_recalculated_imbalance_cashflows_SO(new_system_prices_by_date_and_period_df, mr1b_df, npt_bsc_ids)
    supplier_cashflows_df = recalculate_imbalance_cashflows.recalculate_imbalance_cashflows_by_bsc_party_type(bsc_roles_to_supplier_mapping, new_system_prices_by_date_and_period_df, mr1b_df, npt_bsc_ids)
    generator_cashflows_df = recalculate_imbalance_cashflows.recalculate_imbalance_cashflows_by_bsc_party_type(bsc_roles_to_generator_mapping, new_system_prices_by_date_and_period_df, mr1b_df, npt_bsc_ids)
    npt_cashflows_df = recalculate_imbalance_cashflows.calculate_net_npt_cashflow(bsc_roles_to_npt_mapping, mr1b_df)
    marginal_emissions_df = carbon_emissions.calculate_marginal_emissions(full_ascending_settlement_stack_by_date_and_period, new_settlement_stacks_by_date_and_period, system_imbalance_with_and_without_npts_df, bmu_id_to_ci_mapping)
    
    npt_intraday_position = calculate_npt_profit.calculate_id_position(system_imbalance_with_and_without_npts_df, ancillary_price_data_for_sp_calculation)
    supplier_generator_id_positions = npt_intraday_position.copy()
    supplier_generator_id_positions['id_cashflow'] = -supplier_generator_id_positions['id_cashflow']
    npt_welfare = calculate_npt_profit.calculate_npt_welfare_midp(npt_cashflows_df, npt_intraday_position)
    #TODO - may want to change how all these results are presented 
    #Output Monthly Data
    system_prices_df = excel_interaction.process_df_for_output(recalculated_system_prices, missing_data_points)
    system_imbalances_df = excel_interaction.process_df_for_output(system_imbalance_with_and_without_npts_df, missing_data_points)
    balancing_costs_df = excel_interaction.process_df_for_output(balancing_costs_df, missing_data_points)
    original_balancing_revenue_df = excel_interaction.process_df_for_output(original_balancing_revenue_by_group_df, missing_data_points)
    new_balancing_revenue_df = excel_interaction.process_df_for_output(new_balancing_revenue_by_group_df, missing_data_points)
    intraday_cashflow_df = excel_interaction.process_df_for_output(supplier_generator_id_positions, missing_data_points)
    so_cashflows_df = excel_interaction.process_df_for_output(so_cashflows_df, missing_data_points)
    supplier_cashflows_df = excel_interaction.process_df_for_output(supplier_cashflows_df, missing_data_points)
    generator_cashflows_df = excel_interaction.process_df_for_output(generator_cashflows_df, missing_data_points)
    npt_welfare_df = excel_interaction.process_df_for_output(npt_welfare, missing_data_points)
    marginal_emissions_df = excel_interaction.process_df_for_output(marginal_emissions_df, missing_data_points)
    missing_data_df = pd.DataFrame(list(missing_data_points), columns=['settlement_date', 'settlement_period'])
    missing_data_df = excel_interaction.order_by_settlement_date_and_period(missing_data_df)
    summary_df = create_summary_table(
        system_prices_df, system_imbalances_df, balancing_costs_df, so_cashflows_df, supplier_cashflows_df, generator_cashflows_df,
        intraday_cashflow_df, marginal_emissions_df
    )
    
    sheet_names_dict = {
        'Summary': summary_df,
        'Missing Data': missing_data_df,
        'System Prices': system_prices_df,
        'System Imbalances': system_imbalances_df,
        'Balancing Costs': balancing_costs_df,
        'Original Balancing Revenue': original_balancing_revenue_df,
        'New Balancing Revenue': new_balancing_revenue_df,
        'SO Cashflows': so_cashflows_df,
        'Supplier Cashflows': supplier_cashflows_df,
        'Generator Cashflows': generator_cashflows_df,
        'Intraday Cashflows': intraday_cashflow_df,
        'NPT Welfare': npt_welfare_df,
        'Marginal Emissions Factors': marginal_emissions_df
    }
    
    excel_interaction.dataframes_to_excel(
        sheet_names_dict.values(), output_directory, f'{year}-{month}', sheet_names_dict.keys())
    print(f"Completed {year}-{month}")
    
    # Append to lists
    system_prices.append(recalculated_system_prices)
    system_imbalances.append(system_imbalance_with_and_without_npts_df)
    balancing_costs.append(balancing_costs_df)
    original_balancing_revenue.append(original_balancing_revenue_by_group_df)
    new_balancing_revenue.append(new_balancing_revenue_by_group_df)
    so_cashflows.append(so_cashflows_df)
    supplier_cashflows.append(supplier_cashflows_df)
    generator_cashflows.append(generator_cashflows_df)
    intraday_cashflows.append(intraday_cashflow_df)
    npt_cashflows.append(npt_welfare_df)
    mefs.append(marginal_emissions_df)
    all_missing_data.update(missing_data_points)
    
async def get_niv_results_zero_mv(
    years: list[int],
    months: list[int],
    bsc_roles_filepath: str,
    strict_npt: bool,
    output_directory: str
) -> None:
    all_missing_data = set()
    mr1b_filepaths = excel_interaction.get_excel_filepaths('/Users/josephcary/Library/CloudStorage/OneDrive-Nexus365/First Year/Data/Elexon/MR1B Excel Reports')
    filepath_dict = excel_interaction.create_filepath_dict(mr1b_filepaths)
    bsc_id_to_npt_mapping = recalculate_niv.get_bsc_id_to_npt_mapping(bsc_roles_filepath, strict_npt)
    api_client = ApiClient()
    zero_mv_nivs = []
    for year in years:
        for month in months:
            year_month = datetime.date(year, month, 1).strftime('%Y-%m')
            mr1b_filepath = filepath_dict[year_month.replace('-', '_')]
            month_start_date = datetime.date(year, month, 1).strftime('%Y-%m-%d')
            _, last_day = calendar.monthrange(year, month)
            month_end_date = datetime.date(year, month, last_day).strftime('%Y-%m-%d')
            settlement_dates_with_periods_per_day = datetime_functions.get_settlement_dates_and_settlement_periods_per_day(month_start_date, month_end_date)
            missing_data_points = set()
            mr1b_df = pd.read_excel(mr1b_filepath)
            mr1b_df = mr1b_df.map(lambda x: x.strip() if isinstance(x, str) else x)
            zero_mv_niv_one_month = await recalculate_niv.recalculate_niv_zero_metered_volume(
                settlement_dates_with_periods_per_day,
                mr1b_df,
                bsc_id_to_npt_mapping,
                missing_data_points,
                api_client
            )
            zero_mv_nivs.append(zero_mv_niv_one_month)
            all_missing_data.update(missing_data_points)
            print(f"Completed NIV recalculation with zero metered volume for {year}-{month}")
    
    zero_mv_nivs_df = pd.concat(zero_mv_nivs)
    file_name = f'{years[0]}-{months[0]}_to_{years[-1]}-{months[-1]}_results'
    excel_interaction.dataframes_to_excel([zero_mv_nivs_df], output_directory, file_name, ['Zero MV NIVs'])
    
def determine_supplier_net_position(
    years: list[int],
    months: list[int],
    bsc_roles_filepath: str,
    output_file_directory: str
) -> None:
    mr1b_filepaths = excel_interaction.get_excel_filepaths('/Users/josephcary/Library/CloudStorage/OneDrive-Nexus365/First Year/Data/Elexon/MR1B Excel Reports')
    filepath_dict = excel_interaction.create_filepath_dict(mr1b_filepaths)
    bsc_id_to_strict_supplier_mapping = recalculate_niv.get_bsc_roles_to_supplier_mapping(bsc_roles_filepath, True)
    bsc_id_to_loose_supplier_mapping = recalculate_niv.get_bsc_roles_to_supplier_mapping(bsc_roles_filepath, False)
    combined_results = []
    for year in years:
        for month in months:
            year_month = datetime.date(year, month, 1).strftime('%Y-%m')
            mr1b_filepath = filepath_dict[year_month.replace('-', '_')]
            mr1b_df = pd.read_excel(mr1b_filepath)
            mr1b_df = mr1b_df.map(lambda x: x.strip() if isinstance(x, str) else x)
            strict_supplier_mr1b_df = mr1b_df[mr1b_df['Party ID'].map(bsc_id_to_strict_supplier_mapping) == True]
            loose_supplier_mr1b_df = mr1b_df[mr1b_df['Party ID'].map(bsc_id_to_loose_supplier_mapping) == True]
            strict_supplier_grouped = strict_supplier_mr1b_df.groupby(['Settlement Date', 'Settlement Period'])['Energy Imbalance Vol'].sum().reset_index()
            strict_supplier_grouped.columns = ['settlement_date', 'settlement_period', 'strict_supplier_total_imbalance']
            loose_supplier_grouped = loose_supplier_mr1b_df.groupby(['Settlement Date', 'Settlement Period'])['Energy Imbalance Vol'].sum().reset_index()
            loose_supplier_grouped.columns = ['settlement_date', 'settlement_period', 'loose_supplier_total_imbalance']
            combined_df = strict_supplier_grouped.merge(loose_supplier_grouped, on=['settlement_date', 'settlement_period'], how='outer')
            combined_results.append(combined_df)
            print(f"Determined supplier net positions for {year}-{month}")
    
    combined_results_df = pd.concat(combined_results)
    file_name = f'supplier_net_positions_{years[0]}-{months[0]}_to_{years[-1]}-{months[-1]}'
    excel_interaction.dataframes_to_excel([combined_results_df], output_file_directory, file_name, ['Supplier Net Positions'])