# PS-094: Construction-Linked Milestone Billing, Stamp Duty & Delay Compensation Engine

**Team ID:** T099  
**Team Members:** Shamantha O S (`1AT24IS173`), Sharanya P V (`1AT24IS174`)  
**Section:** ISE D  

## Overview
A command-file driven customer accounting engine built in Python 3.10+ for residential real estate developers. It processes project master data, unit bookings under Construction-Linked Plans (CLP) and Down-Payment Plans (DPP), sequential tower-wing milestone certifications, GST-compliant demand notes, payment allocations with daily simple interest, stamp duty/registration calculations, cancellations with forfeiture/refund rules, and RERA delay compensation.

## Folder Structure
```text
T099-PS-094/
├── main.py
├── realty_ledger/
│   ├── __init__.py
│   ├── domain.py
│   ├── calculations.py
│   ├── accounting.py
│   └── exporters.py
├── sample_data/
├── output/
├── tests/
│   └── test_billing.py
├── DESIGN_DOCUMENT.md
├── DECISION_LOG.md
└── README.md
```

## How to Run
```bash
# 1. Execute the command stream and generate all 4 evaluation CSV reports
python main.py --data-dir sample_data --out-dir output

# 2. Run the unit test suite
python -m unittest discover -s tests -v
```
