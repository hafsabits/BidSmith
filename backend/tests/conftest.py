import pytest

from bidsmith import retrieval
from bidsmith.graph import runner
from bidsmith.llm import set_llm
from fakes import hit


@pytest.fixture(autouse=True)
def fake_retrieval(monkeypatch):
    monkeypatch.setattr(retrieval, "search_past_performance", lambda cid, q, k=8: [hit("own-1", cid)])
    monkeypatch.setattr(retrieval, "search_market_comps", lambda cid, q, k=10: [hit("peer-1", "other")])
    monkeypatch.setattr(retrieval, "company_stats", lambda cid: {"by_building_type": {"medical_office": 1}})
    monkeypatch.setattr(retrieval, "owner_counts", lambda: {})
    runner.get_graph.cache_clear()
    yield
    set_llm(None)
