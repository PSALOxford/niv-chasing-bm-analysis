import pytz
from datetime import datetime, timedelta

gb_timezone = pytz.timezone('Europe/London')

def get_settlement_dates_and_settlement_periods_per_day(
    start_date: str, 
    end_date_str: str
) -> dict[str, int]:
    full_date_list = generate_settlement_dates(start_date, end_date_str)
    dates_with_settlement_periods_per_day = get_settlement_periods_for_each_day_in_date_range(full_date_list)
    dates_with_settlement_periods_per_day = {key.strftime('%Y-%m-%d'): value 
                                                 for key, value in dates_with_settlement_periods_per_day.items()}
    return dates_with_settlement_periods_per_day

def generate_settlement_dates(
    start_date: str, 
    end_date: str,
    date_as_string: bool = False
) -> list[datetime]:
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError as e:
        raise ValueError("Incorrect date format, should be YYYY-MM-DD") from e

    date_list = [(start_date + timedelta(days=i)) for i in range((end_date - start_date).days + 1)]

    if date_as_string:
        date_list = [date.strftime('%Y-%m-%d') for date in date_list]

    return date_list

def get_settlement_periods_for_each_day_in_date_range(
    settlement_dates_inclusive: list[datetime]
) -> dict[datetime, int]:
    settlement_periods_per_day = {}
    settlement_dates_for_calculation = settlement_dates_inclusive + [
        settlement_dates_inclusive[-1] + timedelta(days = 1)]

    for i in range(len(settlement_dates_for_calculation) - 1):
        current_date = settlement_dates_for_calculation[i]
        next_date = settlement_dates_for_calculation[i+1]
        offset_now = gb_timezone.utcoffset(current_date)
        offset_next = gb_timezone.utcoffset(next_date)
        settlement_periods_in_day = 48

        if offset_now != offset_next:
            settlement_periods_in_day = (46 if offset_next > offset_now else 50)
            
        settlement_periods_per_day[current_date] = settlement_periods_in_day
    
    return settlement_periods_per_day

def get_settlement_date_period_to_utc_start_time_mapping(
    years: list[int]
) -> dict[tuple[str, int], datetime]:
    mapping = {}
    
    for year in years:
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        year_dates = generate_settlement_dates(start_date, end_date)
        settlement_periods_per_day = get_settlement_periods_for_each_day_in_date_range(year_dates)
        
        for settlement_date, num_periods in settlement_periods_per_day.items():
            settlement_date_str = settlement_date.strftime('%Y-%m-%d')
            
            london_midnight = gb_timezone.localize(settlement_date.replace(hour=0, minute=0, second=0, microsecond=0))
            
            for period in range(1, num_periods + 1):
                london_start_time = london_midnight + timedelta(minutes=30 * (period - 1)) 
                utc_start_time = london_start_time.astimezone(pytz.UTC)
                mapping[(settlement_date_str, period)] = utc_start_time
    
    return mapping