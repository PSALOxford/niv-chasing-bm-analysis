# niv-chasing-bm-analysis

Code supporting the analysis of the effects of NIV chasing by non-physical traders in the GB market. This repository contains code for analysing Great Britain (GB) electricity Balancing Mechanism (BM) data, imbalance pricing, settlement cashflows, and related system metrics. It supports recalculation of system prices, Net Imbalance Volume (NIV), balancing and imbalance cashflows, stack-based pricing, and carbon emissions analysis.

The codebase was developed to support the analysis in:

> **Speculative Imbalance Positions by Non-Physical Traders: Impacts on Electricity System Balancing in Great Britain**
> *Joseph Cary; Thomas Morstyn*
> *Submitted to Energy Economics, 2026*
> DOI: [10.2139/ssrn.7641018](https://doi.org/10.2139/ssrn.7641018) (SSRN preprint)

Instructions for replicating the results, including data availability, are in **[REPLICATION.md](REPLICATION.md)**.

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

`program.py` is the entry point. It sets the inputs and calls `gb_analysis/engine.py`.

`gb_analysis/` – counterfactual simulation and analysis:

* `engine.py` – Main execution logic
* `recalculate_niv.py` – Net Imbalance Volume recalculation
* `recalculate_settlement_stack.py` – Settlement stack reconstruction
* `system_price_from_stack.py` – System price derivation from stack
* `recalculate_balancing_cashflows.py` – Balancing cashflow recalculation
* `recalculate_imbalance_cashflows.py` – Imbalance cashflow recalculation
* `calculate_npt_profit.py` – NPT intraday position and profit calculation
* `carbon_emissions.py` – Marginal emissions factor estimation
* `bm_analysis.py` – Descriptive analyses of BM data
* `summary.py` – Summary statistics

`data_collection/` – data access:

* `elexon_interaction.py` – Interface to the Elexon Insights API

`data_processing/` – data handling:

* `price_data_processing.py` – Processing of price inputs
* `stack_data_handler.py` – Settlement stack construction and manipulation
* `bm_physical_data_handler.py` – Handling of BM physical notifications
* `bm_unit.py` – BM unit abstraction
* `boa.py` – Bid/Offer Acceptance logic

`ancillary_files/` – helper functions:

* `datetime_functions.py` – Convert between settlement periods and time
* `excel_interaction.py` – Read inputs from and write outputs to Excel

`Supporting Data/` – input files that can be shared (BSC party roles, TLMs, BM Unit reference data).

---

## Installation

Python 3.12 was used for the paper. Install the pinned dependencies with:

```bash
pip install -r requirements.txt
```

---

## Data Requirements

This repository does **not** include raw BM, MR1B, or settlement data.

* All BM data (DISEBSP, ISPSTACK, BOD, PN/MELS/MILS, MID, NETBSAD) are downloaded at run time from the Elexon Insights API. No API key is needed.
* Party-level imbalance data (MR1B) are available only on request from Elexon and are not redistributed here.
* The BSC party roles, TLMs and BM Unit reference data used in the paper are in `Supporting Data/`.

See **[REPLICATION.md](REPLICATION.md)** for the full data availability table, input file formats, and how to obtain each dataset. Data must be used in compliance with Elexon licensing terms.

---

## Reproducing Results

Set `mr1b_directory` (and, if needed, the other inputs) at the top of `program.py`, then run:

```bash
python program.py
```

For step-by-step instructions, a description of the outputs, auxiliary analyses and the mapping from outputs to the paper's tables and figures, see **[REPLICATION.md](REPLICATION.md)**.

---

## Methodological Notes

* Settlement stack reconstruction follows the methodology described in the associated publication.
* System price derivation is performed directly from the recalculated stack.
* NIV recalculation is based on reconstructed accepted volumes.
* Cashflow calculations follow standard GB settlement rules unless otherwise stated.
* Carbon emissions are estimated using unit-level marginal emissions factors where available.

Users should review the associated paper for full methodological detail.

---

## Limitations

* No warranty is provided regarding completeness or correctness of external data.
* Results depend on data quality and completeness.
* Regulatory rule changes over time may affect reproducibility for other periods.
* This code is research-oriented and not production-hardened.

---

## Citation

If you use this code, please cite the paper (see also `CITATION.cff`):

```bibtex
@misc{cary2026speculative,
  title={Speculative Imbalance Positions by Non-Physical Traders: Impacts on Electricity System Balancing in Great Britain},
  author={Cary, Joseph and Morstyn, Thomas},
  year={2026},
  doi={10.2139/ssrn.7641018},
  note={SSRN preprint. Submitted to Energy Economics}
}
```

---

## License

The code in this repository is licensed under the MIT License (see [LICENSE](LICENSE)). Data obtained from Elexon is subject to Elexon's licence terms.

---

## Contact

For questions related to the methodology or publication:

* Name: Joseph Cary
* Email: joseph.cary@wolfson.ox.ac.uk
* Institution: Power Systems Architecture Lab, Department of Engineering Science, University of Oxford

---
