# Cost data (SYNTHETIC)

These tables are **synthetic, illustrative values** shaped like commercial cost databases
(e.g. RSMeans square-foot models). They are good enough to demonstrate the method, not to price
real work. A firm using BidSmith would replace these files with its own licensed cost data,
keeping the same columns.

- `building_costs.csv`: national-average $/SF by building type and quality, base year 2025, plus the archetype used for the CSI split and a typical size for the size adjustment.
- `csi_splits.csv`: share of hard cost by CSI MasterFormat division, per archetype (each sums to 100).
- `location_index.csv`: state-level location factor (national average = 1.00).
- `escalation.csv`: assumed annual construction cost escalation by year.
- `premiums.csv`: percentage adders for special requirements the analyst agent can select.
