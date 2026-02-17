import pandas as pd

def get_physical_volume(
    original_data: pd.DataFrame
) -> float:
    physical_data = original_data.copy()
    physical_data.loc[:, 'time_from'] = pd.to_datetime(physical_data['time_from'])
    physical_data.loc[:, 'time_to'] = pd.to_datetime(physical_data['time_to'])
    physical_data.loc[:, 'duration_hours'] = (physical_data['time_to'] - physical_data['time_from']).dt.total_seconds() / 3600
    physical_data.loc[:, 'energy_MWh'] = ((physical_data['level_from'] + physical_data['level_to']) / 2) * physical_data['duration_hours']
    total_energy_MWh = physical_data['energy_MWh'].sum()
    
    return total_energy_MWh