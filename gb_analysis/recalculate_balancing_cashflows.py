import pandas as pd

def calculate_balancing_costs(
    original_settlement_stacks_by_date_and_period: dict[tuple[str, int], pd.DataFrame], 
    new_settlement_stacks_by_date_and_period : dict[tuple[str, int], pd.DataFrame]
) -> pd.DataFrame:
    balancing_costs = []
    for (settlement_date, settlement_period), settlement_stack in original_settlement_stacks_by_date_and_period.items():
        if settlement_stack.empty:
            balancing_cost = 0
        else:
            balancing_cost = (settlement_stack['original_price']*settlement_stack['volume']).sum()
        new_settlement_stack = new_settlement_stacks_by_date_and_period[(settlement_date, settlement_period)]
        if new_settlement_stack.empty:
            new_balancing_cost = 0
        else:
            new_balancing_cost = (new_settlement_stack['original_price']*new_settlement_stack['volume']).sum()
        balancing_costs.append((settlement_date, settlement_period, balancing_cost, new_balancing_cost))
    
    balancing_costs_df = pd.DataFrame(balancing_costs, columns=[
        'settlement_date',
        'settlement_period', 
        'balancing_costs', 
        'recalculated_balancing_costs'])
    
    return balancing_costs_df

def get_original_and_new_balancing_revenue_dfs(
    original_settlement_stacks_by_date_and_period: dict[tuple[str, int], pd.DataFrame],
    new_settlement_stacks_by_date_and_period: dict[tuple[str, int], pd.DataFrame]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    original_balancing_revenue_df = get_balancing_revenue_df(original_settlement_stacks_by_date_and_period)
    new_balancing_revenue_df = get_balancing_revenue_df(new_settlement_stacks_by_date_and_period)
    
    return original_balancing_revenue_df, new_balancing_revenue_df

def get_balancing_revenue_df(
    settlement_stacks_by_date_and_period: dict[tuple[str, int], pd.DataFrame]
) -> pd.DataFrame:
    df_list = []
    for (settlement_date, settlement_period), df in settlement_stacks_by_date_and_period.items():
        if df.empty:
            df_list.append(pd.DataFrame([[settlement_date, settlement_period, '', 0]], columns=['settlement_date', 'settlement_period', 'bmu_group', 'revenue']))
        else:
            df_copy = df.copy()
            df_copy['bmu_group'] = df_copy['id'].str[0]
            df_copy['revenue'] = df_copy['original_price'] * df_copy['volume']
            df_copy['settlement_date'] = settlement_date
            df_copy['settlement_period'] = settlement_period
            df_list.append(df_copy[['settlement_date', 'settlement_period', 'bmu_group', 'revenue']])
    
    combined_df = pd.concat(df_list, ignore_index=True)
    
    pivot_df = combined_df.pivot_table(
        index=['settlement_date', 'settlement_period'], 
        columns='bmu_group', 
        values='revenue', 
        aggfunc='sum', 
        fill_value=0
    ).reset_index()
    
    return pivot_df
