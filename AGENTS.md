# Repository guidance

## Scope and layout

- `llm_tool_jina.py` is the full plugin: toolbox `Jina`, tools `read` and
  `search`, URL and domain policy, untrusted-content handling, HTTP.
- `tests/test_llm_tool_jina.py` is the offline test suite (network replaced).
- `tests/test_live.py` sends real requests; it runs only with
  `JINA_LIVE_TESTS=1`.
- `README.md` is the user-facing source of truth (behavior, settings,
  security, privacy, release procedure). Update it with each user-facing change.

## Development

- Use `uv`. Run `uv run pytest` after each code change; not
  `.venv/bin/python -m pytest` (it skips the sync with `pyproject.toml`).
- In a sandbox, the default uv cache is read-only. Prefix each uv command:
  `UV_CACHE_DIR="$TMPDIR/uv-cache" UV_LINK_MODE=copy uv run pytest`.
- Add or update tests for behavior changes, also for error paths.
- Tests must never use the real key: the autouse fixture removes
  `JINA_API_KEY` and points `LLM_USER_PATH` to a temporary directory.
- Before code that changes request headers or parses responses, verify the
  Jina behavior with a live request (`tests/test_live.py` or curl). The Reader
  source of truth for headers is `src/dto/crawler-options.ts` in
  github.com/jina-ai/reader.

## Invariants

- Tool methods take only per-query parameters (`url`, `offset`, `query`,
  `count`). Every other setting is a constructor argument.
- Tool names are `Jina_<method>`; the class name contains no `_` (llm 0.32+
  finds the toolbox with `tool_name.split("_")[0]`).
- Never keep `api_key` in `self._config` (llm writes it to the logs database).
- Send the API key only to `https://*.jina.ai`.
- Errors are `JinaError` exceptions, never error dicts.
- Check the domain policy before any request, and check the final URL
  (after redirects) before content goes to the model.
- Send the URL in the normalized form that the policy checked.
- Page `content` goes between `JINA_UNTRUSTED_CONTENT` markers with a random
  id; all text from Jina goes through `_sanitize`.
- Offsets refer to the sanitized page text in the page cache.
- No cookies, no redirects of the API endpoint (private opener).
- Search sends `X-Respond-With: no-content`.
- `no_store` (default true) sends `DNT: 1`; `no_cache` sends `X-No-Cache`.
- `read` sends `X-Timeout` (`page_timeout`, default 15; from 20 Reader
  waits for full network idle). The HTTP timeout stays at least
  `page_timeout + 30`.

## Releasing

- Commit `bump: vX.Y.Z` (only `version` in `pyproject.toml`, no body).
  Annotated tag `vX.Y.Z`: subject `release: vX.Y.Z`, blank line, release
  notes in Markdown. The GitHub release shows the tag notes unchanged.
  `tag-check` in `publish.yml` refuses any other form.
- On a bump request: `uv lock --upgrade` and `uv run pytest`; read
  `git log` and `git diff` since the previous tag; write the notes to
  `$TMPDIR/release-notes-vX.Y.Z.md` (sections, empty ones omitted: Breaking
  changes, Features, Fixes, Other, Commits as `- subject (hash)`, then the
  compare link `.../compare/vPREV...vX.Y.Z`); show them to the user and wait
  for approval; then commit and
  `git tag -a vX.Y.Z --cleanup=verbatim -F <notes>` (without verbatim, git
  removes the `#` headings).
- The user pushes (`git push --follow-tags`, YubiKey touch): never push
  without an explicit request.
- Failure before the PyPI upload: save the notes, delete the tag (remote and
  local), fix, tag again. After the upload: re-run only the `release` job.
- Do not run `gh release create`; do not rename `publish.yml` (the PyPI
  trusted publisher is bound to it). README has the details.
