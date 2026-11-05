"""The shapes of the data that moves through BidSmith Lite.

RfpFacts  - what Claude must pull out of an RFP (this is also Claude's output format)
Company   - what the rules need to know about the company that might bid
Decision  - the answer we send back: bid or no_bid, and why
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class RfpFacts(BaseModel):
    summary: str = Field(description="One sentence: what the government wants built or leased, and where.")
    building_type: Literal["office", "warehouse", "healthcare", "laboratory", "housing", "other"]
    city: str | None = Field(description="City where the work happens, or null if not stated.")
    state: str | None = Field(description="Two-letter US state code, or null if not stated.")
    set_aside: Literal["none", "small_business", "8a", "hubzone", "sdvosb", "wosb", "other"] = Field(
        description="Which businesses may bid. 'none' means full and open competition or not stated."
    )
    value_low_usd: float | None = Field(description="Low end of the stated project value in US dollars, or null.")
    value_high_usd: float | None = Field(description="High end of the stated project value in US dollars, or null.")
    response_deadline: date | None = Field(description="Date proposals are due, or null if not stated.")


class Company(BaseModel):
    name: str
    eligible_set_asides: list[str]
    bonding_capacity_usd: float
    states: list[str]


class Decision(BaseModel):
    verdict: Literal["bid", "no_bid"]
    reasons: list[str]