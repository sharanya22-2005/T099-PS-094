# PS-094: Construction-Linked Milestone Billing, Stamp Duty & Delay Compensation Engine

**Team ID:** T099  
**Members:** Shamantha O S (1AT24IS173), Sharanya P V (1AT24IS174)  
**Section:** ISE D  

## Overview
A command-file driven customer accounting engine in Python 3.10+ for residential real estate developers. It handles project and unit registration, customer bookings under Construction-Linked Plans (CLP) and Down-Payment Plans (DPP), sequential milestone certifications, demand note generation with GST rules, payment allocation with overdue simple interest, stamp duty & registration calculation, cancellations with forfeiture/refund rules, and RERA delay compensation.

## Project Structure
```text
T099-PS-094/
├── README.md
├── DESIGN_DOCUMENT.md
├── DECISION_LOG.md
├── main.py
├── src/
│   └── billing_engine/
│       ├── __init__.py
│       ├── models.py
│       ├── rules.py
│       ├── engine.py
│       └── reporter.py
├── sample_data/
│   └── commands.txt
└── tests/
    └── test_engine.py
```

## Quick Start
1. Ensure Python 3.10 or higher is installed (uses standard library only—zero third-party dependencies).
2. Run the sample command file:
   ```bash
   python3 main.py sample_data/commands.txt
   ```
3. Run the automated test suite (covers all business rules and mandatory edge cases):
   ```bash
   python3 -m unittest discover -s tests -v
   ```
