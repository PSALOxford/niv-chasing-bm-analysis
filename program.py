import asyncio
from pathlib import Path

from gb_analysis.engine import run

repository_directory = Path(__file__).resolve().parent
supporting_data_directory = repository_directory / 'Supporting Data'

years = [2021, 2022, 2023, 2024]  # Years to analyse
months = [i for i in range(1, 13)]  # January to December
output_directory = repository_directory / 'output'  # Location for output Excel files
mr1b_directory = ''  # Folder containing the monthly MR1B reports (MR1B_YYYY_MM.xlsx), available on request from Elexon
bsc_roles = supporting_data_directory / 'BSC ROLES - from Elexon.xlsx'  # Mapping from BSC ID to whether it holds each role (TN, TS and TG are True or False)
tlms = supporting_data_directory / 'Winter 2022 TLMs.xlsx'  # Mapping from BMU ID to TLM
bmu_id_to_ci_mapping = supporting_data_directory / 'BMU Carbon Intensity.xlsx'  # Mapping from BMU ID to carbon intensity, see REPLICATION.md section 3.4
# The following can be toggled between True and False
strict_npt = True
strict_supplier = True
strict_generator = True
zero_metered_volume_only = True


def check_inputs() -> None:
    required_inputs = {
        'MR1B folder': mr1b_directory,
        'BSC roles file': bsc_roles,
        'TLM file': tlms,
        'Carbon intensity file': bmu_id_to_ci_mapping
    }
    for name, path in required_inputs.items():
        if not path or not Path(path).exists():
            raise FileNotFoundError(f"{name} not found: '{path}'. Set it at the top of program.py, see REPLICATION.md section 3.")
    Path(output_directory).mkdir(parents=True, exist_ok=True)


async def main():
    check_inputs()
    await run(
        years,
        months,
        str(output_directory),
        str(mr1b_directory),
        str(bsc_roles),
        str(tlms),
        str(bmu_id_to_ci_mapping),
        strict_npt,
        strict_supplier,
        strict_generator,
        zero_metered_volume_only
    )


if __name__ == '__main__':
    asyncio.run(main())
