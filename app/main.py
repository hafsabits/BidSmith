"""The web server. It connects the pieces and contains no logic of its own.

GET  /             -> the web page
POST /api/analyze  -> RFP text in, extracted facts + bid decision out
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.company import COMPANY
from app.extract import ExtractionError, extract_facts
from app.rules import decide
from app.schemas import Decision, RfpFacts

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="BidSmith Lite")


class AnalyzeRequest(BaseModel):
    rfp_text: str = Field(max_length=100_000)


class AnalyzeResponse(BaseModel):
    company: str
    facts: RfpFacts
    decision: Decision


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    if not request.rfp_text.strip():
        raise HTTPException(status_code=400, detail="Paste the RFP text first.")
    try:
        facts = extract_facts(request.rfp_text)
    except ExtractionError as error:
        raise HTTPException(status_code=502, detail=str(error))
    except anthropic.APIError:
        raise HTTPException(status_code=502, detail="Couldn't reach Claude. Try again in a minute.")
    decision = decide(facts, COMPANY)
    return AnalyzeResponse(company=COMPANY.name, facts=facts, decision=decision)