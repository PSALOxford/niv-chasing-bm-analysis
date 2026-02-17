# niv-chasing-bm-analysis
Code supporting the analysis of the effects of NIV chasing by non-physical traders in the GB market. This repository contains code for analysing Great Britain (GB) electricity Balancing Mechanism (BM) data, imbalance pricing, settlement cashflows, and related system metrics. It supports recalculation of system prices, Net Imbalance Volume (NIV), balancing and imbalance cashflows, stack-based pricing, and carbon emissions analysis.

The codebase was developed to support the analysis in:

> **[Speculative Imbalance Positions by Non-Physical Traders: Impacts on Electricity System Balancing in Great Britain]**
> *Joseph Cary; Thomas Morstyn*
> *Submitted to Energy Economics, 2026*
> DOI: 

---

## Overview

The repository provides:

* Processing of BM physical and price data
* Interaction with Elexon data sources
* Recalculation of:

  * Net Imbalance Volume (NIV)
  * System prices
  * Settlement stack
  * Balancing cashflows
  * Imbalance cashflows
* Profit calculation for non-physical trades (NPT)
* Carbon emissions estimation
* Summary statistics and analysis utilities

The code is modular and designed to allow replication of published results and experimentation with alternative pricing or settlement methodologies.

---

## Repository Structure

Core modules:

* `engine.py` – Main execution logic
* `price_data_processing.py` – Processing of price inputs
* `stack_data_handler.py` – Settlement stack construction and manipulation
* `bm_physical_data_handler.py` – Handling of BM physical notifications
* `bm_unit.py` – BM unit abstraction
* `boa.py` – Bid/Offer Acceptance logic
* `elexon_interaction.py` – Interface to Elexon data
* `recalculate_niv.py` – Net Imbalance Volume recalculation
* `system_price_from_stack.py` – System price derivation from stack
* `recalculate_settlement_stack.py` – Settlement stack reconstruction
* `recalculate_balancing_cashflows.py` – Balancing cashflow recalculation
* `recalculate_imbalance_cashflows.py` – Imbalance cashflow recalculation
* `calculate_npt_profit.py` – NPT profit calculation
* `bm_analysis.py` – Analytical utilities
* `summary.py` – Summary statistics
* `carbon_emissions.py` – Carbon emissions estimation
* `datetime_functions.py` - Ancilarry functions to convert between settlement periods and time
* `excel_interaction` - Inputs and outputs from excel

---

## Installation

### Requirements

* Python 3.9+ (recommended)
* Standard scientific Python stack:

  * `pandas`
  * `numpy`
  * `matplotlib` (if using plotting functionality)
  * Any additional dependencies required by `elexon_interaction.py`
  * asyncio

---

## Data Requirements

This repository does **not** include raw BM, MR1B, or settlement data.

You will need:

* Elexon Balancing Mechanism Reports Service (BMRS) data and/or API access
* Relevant settlement, bid/offer, and physical notification datasets
* Any additional reference datasets used in the paper

Data sources must be obtained in compliance with Elexon licensing terms.

Directory structure for data (example):

```
data/
  raw/
  processed/
  outputs/
```

Adjust paths in the scripts as required.

---

## Reproducing Results

To reproduce the main results from the paper:

1. Obtain the required BM and settlement datasets.
2. Configure data paths in the relevant modules.
3. Run the workflow in the following logical order:

   * Process raw data
   * Recalculate settlement stack
   * Recalculate NIV
   * Derive system price
   * Recalculate balancing and imbalance cashflows
   * Generate summary outputs

Depending on your setup, execution may begin via:

```bash
python engine.py
```

or by running individual recalculation modules.

For reproducibility, it is recommended to:

* Use fixed data snapshots
* Tag the repository version corresponding to the publication (e.g., `v1.0-paper`)
* Archive the release with a DOI (e.g., Zenodo)

---

## Methodological Notes

* Settlement stack reconstruction follows the methodology described in the associated publication.
* System price derivation is performed directly from the recalculated stack.
* NIV recalculation is based on reconstructed accepted volumes.
* Cashflow calculations follow standard GB settlement rules unless otherwise stated.
* Carbon emissions are estimated using technology-level or unit-level emissions factors where available.

Users should review the associated paper for full methodological detail.

---

## Limitations

* No warranty is provided regarding completeness or correctness of external data.
* Results depend on data quality and completeness.
* Regulatory rule changes over time may affect reproducibility for other periods.
* This code is research-oriented and not production-hardened.

---

## Citation

If you use this code, please cite:

```bibtex
@article{citation,
  title={Paper Title},
  author={Cary, Joseph and Morstyn, Thomas},
  journal={Journal Name},
  year={Year},
  doi={DOI}
}
```

You may also cite the software directly once a DOI is minted.

---

## License

This repository is licensed under the [MIT License](LICENSE)

---

## Contact

For questions related to the methodology or publication:

* Name: [Joseph Cary]
* Email: [joseph.cary@wolfson.ox.ac.uk]
* Institution: [Power Systems Architecture Lab, Department of Engineering Science, University of Oxford]

---

