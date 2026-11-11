"""Real requests to Jina: they verify the API contract that the plugin uses.

Run with: JINA_LIVE_TESTS=1 uv run pytest -m live -v
read runs without a key (free, lowest rate limit). search needs JINA_API_KEY
and uses at least 10000 tokens of the Jina balance.
"""

import os

import pytest

from llm_tool_jina import Jina, JinaError

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("JINA_LIVE_TESTS") != "1", reason="set JINA_LIVE_TESTS=1 to run"
    ),
]

KEY = os.environ.get("JINA_API_KEY")


@pytest.fixture
def anonymous(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_USER_PATH", str(tmp_path))
    monkeypatch.delenv("JINA_API_KEY", raising=False)


def test_read_small_page(anonymous):
    result = Jina().read("https://example.com/")
    assert result["title"] == "Example Domain"
    assert result["url"] == "https://example.com/"
    assert "documentation examples" in result["content"]
    assert result["truncated"] is False
    assert isinstance(result["total_tokens"], int)


def test_read_in_parts_with_page_limit(anonymous):
    toolbox = Jina(max_tokens=500, max_page_tokens=1500)
    url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
    first = toolbox.read(url)
    assert first["truncated"] is True
    # X-Max-Tokens works: Jina cut the page at max_page_tokens.
    assert first["total_tokens"] == 1500
    assert "max_page_tokens=1500" in first["warning"]
    second = toolbox.read(url, offset=first["next_offset"])
    assert second["content"] != first["content"]


def test_read_unresolvable_host(anonymous):
    with pytest.raises(JinaError) as info:
        Jina().read("https://nonexistent-host-zz9.invalid/")
    assert info.value.status_code == 422


def test_read_target_404_is_reported(anonymous):
    result = Jina().read("https://example.com/this-page-does-not-exist-zz9")
    assert result.get("http_status") == 404 or "warning" in result


def test_search_without_key_is_refused_by_plugin(anonymous):
    with pytest.raises(JinaError, match="needs an API key"):
        Jina("search").search("python pathlib")


@pytest.mark.skipif(not KEY, reason="JINA_API_KEY is not set")
def test_search_with_key():
    result = Jina("search").search("python pathlib documentation", count=3)
    assert 1 <= len(result["results"]) <= 3
    for item in result["results"]:
        assert item["url"].startswith("http")
        assert set(item) <= {"title", "url", "description", "date"}


@pytest.mark.skipif(not KEY, reason="JINA_API_KEY is not set")
def test_search_with_allowed_domains():
    result = Jina("search", allowed_domains="python.org").search("pathlib", count=3)
    assert result["results"]
    assert all("python.org" in item["url"] for item in result["results"])
