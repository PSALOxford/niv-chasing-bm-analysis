import asyncio

from gb_analysis.engine import run

years = [2021]
months = [i for i in range(10, 13)]  # January to December
output_directory = '' #Location for output excel files
bsc_roles = '' #Filepath to mapping form BSC ID to their status in each type (e.g. TN, TG, TS is assigned True or Fals) 
tlms = '' #Filepath from BMU ID to TLM
bmu_id_to_ci_mapping = '' #Filepath from BMU ID to Carbon Intensity mapping
#The following can be toggled between True and False
strict_npt = True
strict_supplier = True
strict_generator = True
zero_metered_volume_only = True

async def main():
    await run(
        years,
        months,
        output_directory,
        bsc_roles,
        tlms,
        bmu_id_to_ci_mapping,
        strict_npt,
        strict_supplier,
        strict_generator,
        zero_metered_volume_only
    )
    
asyncio.run(main())