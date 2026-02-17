import pandas as pd

def create_summary_table(
    system_prices_df: pd.DataFrame,
    system_imbalances_df: pd.DataFrame,
    balancing_costs_df: pd.DataFrame,
    so_cashflows_df: pd.DataFrame,
    supplier_cashflows_df: pd.DataFrame,
    generator_cashflows_df: pd.DataFrame,
    intraday_cashflows_df: pd.DataFrame,
    marginal_emissions_df: pd.DataFrame
) -> pd.DataFrame:
    # Calculate statistics for factual scenario
    factual_stats = {
        'Average system price': system_prices_df['system_sell_price'].mean(),
        'System price volatility (standard deviation)': system_prices_df['system_sell_price'].std(),
        'Average system imbalance': system_imbalances_df['net_imbalance_volume'].mean(),
        'Average absolute system imbalance': system_imbalances_df['net_imbalance_volume'].abs().mean(),
        'System imbalance standard deviation': system_imbalances_df['net_imbalance_volume'].std(),
        'Total absolute system imbalance': system_imbalances_df['net_imbalance_volume'].abs().sum(),
        'Total balancing costs': balancing_costs_df['balancing_costs'].sum(),
        'Total SO cashflows': so_cashflows_df['energy_imbalance_cashflow'].sum(),
        'Total supplier cashflows': supplier_cashflows_df['energy_imbalance_cashflow'].sum(),
        'Total generator cashflows': generator_cashflows_df['energy_imbalance_cashflow'].sum(),
        'Total intraday cashflows': intraday_cashflows_df['id_cashflow'].sum(),
        'Average MEF': marginal_emissions_df['factual_mef'].mean()
    }

    counterfactual_stats = {
        'Average system price': system_prices_df['recalculated_system_price'].mean(),
        'System price volatility (standard deviation)': system_prices_df['recalculated_system_price'].std(),
        'Average system imbalance': system_imbalances_df['counterfactual_niv'].mean(),
        'Average absolute system imbalance': system_imbalances_df['counterfactual_niv'].abs().mean(),
        'System imbalance standard deviation': system_imbalances_df['counterfactual_niv'].std(),
        'Total absolute system imbalance': system_imbalances_df['counterfactual_niv'].abs().sum(),
        'Total balancing costs': balancing_costs_df['recalculated_balancing_costs'].sum(),
        'Total SO cashflows': so_cashflows_df['recalculated_energy_imbalance_cashflow'].sum(),
        'Total supplier cashflows': supplier_cashflows_df['recalculated_energy_imbalance_cashflow'].sum(),
        'Total generator cashflows': generator_cashflows_df['recalculated_energy_imbalance_cashflow'].sum(),
        'Total intraday cashflows': 0,
        'Average MEF': marginal_emissions_df['counterfactual_mef'].mean()
    }

    summary_df = pd.DataFrame({
        'Factual': factual_stats,
        'Counterfactual': counterfactual_stats
    })
    
    summary_df['Difference'] = summary_df['Counterfactual'] - summary_df['Factual']
    summary_df = summary_df.reset_index()
    summary_df.rename(columns={'index': 'Statistic Name'}, inplace=True)

    return summary_df