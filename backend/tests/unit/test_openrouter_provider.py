"""Tests for the OpenRouter LLM, embedding and translation providers."""

from __future__ import annotations

import json

import httpx
import pytest
from tenacity import wait_none

from app.core.providers.embeddings.openrouter import OpenRouterEmbedder
from app.core.providers.llm.openrouter import OpenRouterLLM, extract_json, parse_model_list
from app.core.providers.translation.openrouter_translator import OpenRouterTranslator


def _attach(provider, handler) -> list[dict]:
    """Route the provider's HTTP calls to `handler`; return the captured request bodies."""
    seen: list[dict] = []

    def capture(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content) if request.content else {})
        return handler(request)

    client = provider._client if hasattr(provider, "_client") else provider._llm._client
    client._http = httpx.AsyncClient(
        base_url="https://openrouter.test/api/v1", transport=httpx.MockTransport(capture)
    )
    return seen


def _chat(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@pytest.fixture(autouse=True)
def _no_retry_wait():
    for fn in (OpenRouterLLM.generate, OpenRouterLLM.generate_structured, OpenRouterEmbedder.embed_batch):
        fn.retry.wait = wait_none()


def test_parse_model_list_ignores_blanks():
    assert parse_model_list(" a:free , ,b ") == ["a:free", "b"]


def test_missing_key_raises_value_error(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.openrouter_api_key", "")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        OpenRouterLLM()


async def test_generate_sends_fallback_models_and_data_policy():
    llm = OpenRouterLLM(api_key="k", model="m1:free,m2:free")
    seen = _attach(llm, lambda r: _chat("hello"))

    assert await llm.generate("hi", system="be brief", use_context_cache=True) == "hello"
    body = seen[0]
    assert body["model"] == "m1:free"
    assert body["models"] == ["m1:free", "m2:free"]
    assert body["provider"] == {"data_collection": "allow"}
    assert body["messages"][0] == {"role": "system", "content": "be brief"}


async def test_generate_retries_rate_limit_then_succeeds():
    llm = OpenRouterLLM(api_key="k", model="m:free")
    replies = iter([httpx.Response(429, json={"error": {"message": "slow down"}}), _chat("ok")])
    _attach(llm, lambda r: next(replies))

    assert await llm.generate("hi") == "ok"


async def test_error_in_200_body_is_retried():
    llm = OpenRouterLLM(api_key="k", model="m:free")
    replies = iter([httpx.Response(200, json={"error": {"code": 502, "message": "upstream"}}), _chat("ok")])
    _attach(llm, lambda r: next(replies))

    assert await llm.generate("hi") == "ok"


async def test_generate_structured_parses_fenced_json_and_sends_schema():
    llm = OpenRouterLLM(api_key="k", model="m:free")
    schema = {"type": "object", "properties": {"intent": {"type": "string"}}}
    seen = _attach(llm, lambda r: _chat('Sure:\n```json\n{"intent": "bail"}\n```'))

    assert await llm.generate_structured("q", output_schema=schema) == {"intent": "bail"}
    assert seen[0]["response_format"]["json_schema"]["schema"] == schema
    assert json.dumps(schema) in seen[0]["messages"][0]["content"]


def test_extract_json_returns_empty_dict_on_garbage():
    assert extract_json("no json here") == {}
    assert extract_json("[1, 2]") == {}


async def test_stream_yields_deltas_and_skips_keepalives():
    llm = OpenRouterLLM(api_key="k", model="m:free")
    sse = "\n".join(
        [
            ": OPENROUTER PROCESSING",
            'data: {"choices":[{"delta":{"content":"Hel"}}]}',
            'data: {"choices":[{"delta":{}}]}',
            'data: {"choices":[{"delta":{"content":"lo"}}]}',
            "data: [DONE]",
        ]
    )
    seen = _attach(llm, lambda r: httpx.Response(200, text=sse))

    chunks = [c async for c in llm.stream("hi", max_tokens=50)]
    assert "".join(chunks) == "Hello"
    assert seen[0]["stream"] is True
    assert seen[0]["max_tokens"] == 50


async def test_embed_batch_orders_by_index_and_sets_input_type(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.gemini_embedding_dimension", 3)
    emb = OpenRouterEmbedder(api_key="k")
    data = {"data": [{"index": 1, "embedding": [0, 0, 1]}, {"index": 0, "embedding": [1, 0, 0]}]}
    seen = _attach(emb, lambda r: httpx.Response(200, json=data))

    assert await emb.embed_batch(["a", "b"]) == [[1, 0, 0], [0, 0, 1]]
    assert seen[0]["input_type"] == "document"
    assert seen[0]["dimensions"] == 3

    await emb.embed_text("q")
    assert seen[1]["input_type"] == "query"


async def test_embed_batch_rejects_wrong_dimension(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.gemini_embedding_dimension", 1536)
    emb = OpenRouterEmbedder(api_key="k")
    _attach(emb, lambda r: httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1] * 1024}]}))

    with pytest.raises(ValueError, match="1024-dim"):
        await emb.embed_text("q")


async def test_translator_reuses_gemini_prompts(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.openrouter_api_key", "k")
    translator = OpenRouterTranslator()
    seen = _attach(translator, lambda r: _chat("  नमस्ते  "))

    assert await translator.translate("hello", source="en", target="hi") == "नमस्ते"
    assert "from English to Hindi" in seen[0]["messages"][-1]["content"]


def test_dependencies_select_openrouter(monkeypatch):
    from app.core import dependencies

    monkeypatch.setattr("app.core.config.settings.llm_provider", "openrouter")
    monkeypatch.setattr("app.core.config.settings.openrouter_api_key", "k")
    for factory in (dependencies.get_llm, dependencies.get_flash_llm, dependencies.get_embedder, dependencies.get_translator):
        factory.cache_clear()
    try:
        assert isinstance(dependencies.get_llm(), OpenRouterLLM)
        assert isinstance(dependencies.get_flash_llm(), OpenRouterLLM)
        assert isinstance(dependencies.get_embedder(), OpenRouterEmbedder)
        assert isinstance(dependencies.get_translator(), OpenRouterTranslator)
    finally:
        for factory in (dependencies.get_llm, dependencies.get_flash_llm, dependencies.get_embedder, dependencies.get_translator):
            factory.cache_clear()


async def test_daily_limit_fails_fast_without_retrying():
    import time

    llm = OpenRouterLLM(api_key="k", model="m:free")
    reset_ms = str(int((time.time() + 5 * 3600) * 1000))
    seen = _attach(llm, lambda r: httpx.Response(429, headers={"x-ratelimit-reset": reset_ms},
                                                 json={"error": {"message": "free-models-per-day"}}))

    with pytest.raises(httpx.HTTPStatusError):
        await llm.generate("hi")
    assert len(seen) == 1


async def test_slow_query_understanding_falls_back_to_passthrough(monkeypatch):
    import asyncio

    from app.core.search.query import understand_query

    monkeypatch.setattr("app.core.config.settings.search_understanding_timeout", 0.05)

    class SlowLLM:
        async def generate_structured(self, **_):
            await asyncio.sleep(1)
            return {"intent": "never"}

    qu = await understand_query("bail in NDPS cases", SlowLLM())
    assert qu.expanded_query == "bail in NDPS cases"
    assert qu.intent != "never"
