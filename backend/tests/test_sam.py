import json

import httpx
import pytest

from bidsmith.ingest import sam
from bidsmith.settings import Settings

ITEM = {
    "noticeId": "abc123",
    "title": "Construct Clinic",
    "solicitationNumber": "36C-1",
    "fullParentPathName": "VETERANS AFFAIRS",
    "type": "Solicitation",
    "postedDate": "2026-10-01",
    "responseDeadLine": "2026-11-20T14:00:00-06:00",
    "naicsCode": "236220",
    "typeOfSetAsideDescription": None,
    "placeOfPerformance": {"city": {"name": "St. Cloud"}, "state": {"code": "MN"}},
    "description": "https://api-alpha.sam.gov/prod/opportunities/v1/noticedesc?noticeid=abc123",
    "uiLink": "https://alpha.sam.gov/opp/abc123/view",
}


@pytest.fixture
def settings(tmp_path, monkeypatch):
    s = Settings(sam_api_key="test-key", sam_env="alpha", sam_max_requests=8, data_dir=tmp_path)
    monkeypatch.setattr(sam, "get_settings", lambda: s)
    from bidsmith import rfp_input

    monkeypatch.setattr(rfp_input, "get_settings", lambda: s)
    return s


def mock_client(calls: list, search_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/opportunities/v2/search"):
            if search_status == 404:
                return httpx.Response(404)  # what both hosts return for an unknown key
            if search_status != 200:
                return httpx.Response(search_status, text="nope")
            return httpx.Response(200, json={"totalRecords": 1, "opportunitiesData": [ITEM]})
        if request.url.params.get("noticeid") != "abc123" or request.url.params.get("api_key") != "test-key":
            return httpx.Response(404)
        return httpx.Response(200, json={"description": "<p>Build a 45,000 SF clinic.</p>"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_alpha_env_uses_alpha_host(settings):
    calls = []
    summary = sam.fetch_opportunities(naics=["236220"], client=mock_client(calls))
    assert calls[0].url.host == "api-alpha.sam.gov"
    assert calls[0].url.params["api_key"] == "test-key"
    assert summary == {**summary, "env": "alpha", "new": 1, "descriptions_fetched": 1, "requests_used": 2}
    saved = json.loads(settings.sam_live_file.read_text())
    assert saved[0]["description"] == "Build a 45,000 SF clinic."
    assert saved[0]["place_state"] == "MN"


def test_rerun_reuses_saved_descriptions(settings):
    sam.fetch_opportunities(naics=["236220"], client=mock_client([]))
    calls = []
    summary = sam.fetch_opportunities(naics=["236220"], client=mock_client(calls))
    assert len(calls) == 1  # search only; description already saved
    assert summary["updated"] == 1 and summary["new"] == 0


def test_budget_caps_requests(settings):
    calls = []
    summary = sam.fetch_opportunities(naics=["236220"], max_requests=1, client=mock_client(calls))
    assert len(calls) == 1
    assert summary["missing_descriptions"] == 1


def test_bad_key_and_rate_limit_messages(settings):
    with pytest.raises(sam.SamApiError, match="alpha.sam.gov"):
        sam.fetch_opportunities(client=mock_client([], search_status=401))
    with pytest.raises(sam.SamApiError, match="did not accept the API key"):
        sam.fetch_opportunities(client=mock_client([], search_status=404))
    with pytest.raises(sam.SamApiError, match="limit"):
        sam.fetch_opportunities(client=mock_client([], search_status=429))


def test_missing_key_points_to_right_site(settings):
    settings.sam_api_key = None
    with pytest.raises(sam.SamApiError, match="alpha.sam.gov"):
        sam.fetch_opportunities()


def test_unknown_env_rejected():
    with pytest.raises(ValueError):
        sam.search_url("staging")


def test_live_results_listed_before_samples(settings, tmp_path):
    (tmp_path / "fixtures").mkdir(exist_ok=True)
    settings.sam_fixture.write_text(json.dumps([{"notice_id": "SAMPLE-1", "title": "s"}]))
    sam.fetch_opportunities(naics=["236220"], client=mock_client([]))
    ids = [o.notice_id for o in sam.load_opportunities()]
    assert ids == ["abc123", "SAMPLE-1"]


# --- catalog: newest-first browsing, older batches on demand, lazy descriptions ---------------

def test_older_batch_then_recent_pages(settings):
    calls = []
    items = [{**ITEM, "noticeId": f"{i:032x}", "postedDate": f"2026-10-{10 + i:02d}"} for i in range(8)]

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"totalRecords": 8, "opportunitiesData": items})

    summary = sam.fetch_older_batch(batch=8, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert summary["added"] == 8 and summary["next_offset"] == 8
    assert calls[0].url.params["offset"] == "0"

    page = sam.recent_page(0, 5)
    assert [o.posted_date.day for o in page["items"]] == [17, 16, 15, 14, 13]  # newest first
    assert page["has_more_cached"] and not page["can_fetch_older"]  # all 8 remote records saved
    assert all(o.description == "" and o.description_url for o in page["items"])


def test_description_fetched_once_on_demand(settings):
    sam.fetch_opportunities(naics=["236220"], with_descriptions=False, client=mock_client([]))
    calls = []
    first = sam.ensure_description("abc123", client=mock_client(calls))
    again = sam.ensure_description("abc123", client=mock_client(calls))
    assert first.description == "Build a 45,000 SF clinic." == again.description
    assert len(calls) == 1


def test_resolve_inputs(settings, monkeypatch):
    from bidsmith import rfp_input

    assert rfp_input.classify("https://sam.gov/opp/" + "a" * 32 + "/view") == ("sam_link", "a" * 32)
    assert rfp_input.classify("https://sam.gov/workspace/contract/opp/" + "B" * 32 + "/view")[0] == "sam_link"
    assert rfp_input.classify("A" * 32) == ("notice_id", "a" * 32)
    assert rfp_input.classify("sample-004") == ("sample", "SAMPLE-004")
    assert rfp_input.classify("Some pasted RFP text")[0] == "text"

    text = "Design-build of a 20,000 SF clinic in Fargo, ND.\n" + "Requirements apply. " * 20
    opp = rfp_input.resolve(text)
    assert opp.notice_id.startswith("PASTE-") and opp.source == "pasted"
    assert opp.title.startswith("Design-build of a 20,000 SF clinic")
    assert sam.get_opportunity(opp.notice_id).description == text.strip()  # findable for runs

    with pytest.raises(rfp_input.InputError, match="too short"):
        rfp_input.resolve("tiny")
