# TODO for llm-tool-jina

* Option to read without the key when a key exists (for example
  `anonymous_read=true`). Why: a keyed read uses tokens of the Jina balance
  and links each URL to the account; an anonymous read is free and linked
  only to the IP address. Cost: the lowest rate limit.

* Search locale as constructor settings (`gl` country, `hl` language,
  `location` of s.jina.ai). Without them Jina selects the locale.

* Run actionlint and zizmor on `.github/workflows/` (not run yet).

* Untrusted-content hardening, second stage (same list as llm-tool-brave):
  homoglyph markers, detection and logging of suspicious phrases, captured
  response fixtures.

* Re-check the Jina API contract from time to time:
  `JINA_LIVE_TESTS=1 uv run pytest -m live -v`. Header names and limits are
  not documented as stable (README of github.com/jina-ai/reader,
  `src/dto/crawler-options.ts`).
