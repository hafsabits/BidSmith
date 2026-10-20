from pathlib import Path

from bidsmith.ingest.adapters.csv_adapter import CSVAdapter
from bidsmith.ingest.adapters.usaspending import row_to_project
from bidsmith.ingest.classify import classify_building_type, clean_description
from bidsmith.retrieval import market_comps_query, past_performance_query

REPO = Path(__file__).resolve().parents[2]

# Shape recorded from the live spending_by_award endpoint.
USASPENDING_ROW = {
    "internal_id": 281041909,
    "Award ID": "47PG0218C0003",
    "Recipient Name": "RYAN COMPANIES US INC",
    "Award Amount": 126837558.95,
    "Description": "IA0089ZZ NEW DES MOINES FEDERAL COURTHOUSE CMC SITE: TBD, DES MOINES, IA",
    "Start Date": "2018-06-21",
    "End Date": "2023-09-05",
    "Awarding Agency": "General Services Administration",
    "Place of Performance State Code": "IA",
    "NAICS": {"code": "236220", "description": "COMMERCIAL AND INSTITUTIONAL BUILDING CONSTRUCTION"},
    "PSC": {"code": "Y1AA", "description": "CONSTRUCTION OF OFFICE BUILDINGS"},
    "generated_internal_id": "CONT_AWD_47PG0218C0003_4740_-NONE-_-NONE-",
}


def test_usaspending_row_mapping():
    p = row_to_project(USASPENDING_ROW, "ryan")
    assert p.owner_company_id == "ryan"
    assert p.id.startswith("usa:CONT_AWD_")
    assert p.building_type == "office"
    assert p.state == "IA" and p.naics == "236220"
    assert p.award_value == 126837558.95


def test_classifier_prefers_specific_types():
    assert classify_building_type("Community Based Outpatient Clinic") == "medical_office"
    assert classify_building_type("VA Medical Center bed tower") == "hospital"
    assert classify_building_type("Barracks renovation") == "multifamily"
    assert classify_building_type("Something unrelated") == "other"


def test_clean_description_strips_codes():
    assert clean_description("IGF::OT::IGF RENOVATE  CHAMBERS") == "RENOVATE CHAMBERS"


def test_csv_adapter_reads_sample():
    projects = list(CSVAdapter("acme", REPO / "data/samples/acme_projects.csv").iter_projects())
    assert len(projects) == 12
    assert all(p.owner_company_id == "acme" for p in projects)


def test_retrieval_enforces_ownership():
    vector = [0.0] * 384
    own = str(past_performance_query("ryan", vector, 5).compile(compile_kwargs={"literal_binds": False}))
    comps = str(market_comps_query("ryan", vector, 5).compile())
    assert "projects.owner_company_id = " in own
    assert "projects.owner_company_id != " in comps
