"""The company being evaluated. To evaluate a different company, change this file, not the rules.

Northstar Builders is a fictional demo company. Its figures are illustrative, loosely modeled
on a large Midwest general contractor.
"""

from app.schemas import Company

COMPANY = Company(
    name="Northstar Builders (demo)",
    eligible_set_asides=[],  # a large firm: not a small business, so it qualifies for no set-asides
    bonding_capacity_usd=750_000_000,
    states=["MN", "WI", "IA", "ND", "SD", "IL", "CO", "AZ", "TX", "FL"],
)