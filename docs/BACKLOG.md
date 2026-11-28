# Backlog

Ordered by priority. Automated runs take the highest `todo` item that is not
blocked. `[safe]` = changes no product behaviour.

States: `todo` · `doing` · `done YYYY-MM-DD` · `blocked: <reason>`

Every item must leave `uv run ruff check .`, `uv run ruff format --check .` and
`uv run pytest` green; that is implied in each acceptance list below.

## Foundation

- `done 2026-11-01` IR v0.1: strategies, parameters, enums, defaults, edits,
  applicability, citations.
- `done 2026-11-01` FIXatdl 1.1 reader (namespace-tolerant, XXE-safe, layout
  merging, EditRef resolution) and schema-valid writer.
- `done 2026-11-01` CLI: `inspect`, `convert`, `schema`. CI workflow.

## Phase A — the engine (no owner input needed)

1. `done 2026-11-02` **Spec diff engine.** `concord diff old new` comparing two
   `AlgoSpec`s. Classify every change as *breaking* (tag removed, enum value
   removed, parameter became required, range narrowed, type changed, strategy
   wire value changed), *additive* (new optional parameter, new enum value,
   range widened) or *cosmetic* (labels, descriptions). Output human-readable
   text and JSON. This is the first feature people will pay for — make the
   report read the way a FIX support engineer would want it.
   Follow-ups: diff Citation changes (provenance drift) and reorder-only
   changes; match strategies by wire value when names change; diff against
   real public FIXatdl samples once item 2 lands.
2. `done 2026-11-07` **Public FIXatdl samples: read every public sample without error.**
   Done: `tests/test_public_samples.py` (opt-in `CONCORD_PUBLIC_SAMPLES=1`, fetch
   approach in D15). 29 files: 25 read, write back and re-read equal; `invalid-schema.xml`
   raises a clean `FixatdlError`; 3 strict xfails (item 20). `malformed.atdl.xml` is not a
   negative: it parses (its own header says so). The reader now wraps IR validation errors
   as `FixatdlError` naming the strategy. Follow-up: diff real samples (item 1 follow-up).
21. `done 2026-11-07` **PDF tables: read real field tables with wrapped cells.**
    Done: `concord.pdf.extract_tables` now infers columns from a block's first row, merges
    last-column continuation lines (blank-line gaps allowed) into the row above, appends
    first-column notes such as `(repeating group)` to the first cell, and sets `Table.depths`
    (0, or 1 for an indented group member). pypdf only; no new dependency. Commander FIX page 28
    went from `[2, 2, 2]` fragments to one 17-row table. Tests: synthetic wrapped table with
    group, prose termination, and an opt-in real-spec test (`CONCORD_PUBLIC_SAMPLES=1`, fetched
    by URL into `corpus/cache`, skipped if the server returns non-PDF). Limits: a description
    line printed above its row (vertically centred cells) attaches to the previous row; a
    page-top fragment of a row split across pages is a partial row.
22. `done 2026-11-08` **PDF tables: repair split glyphs in cells from the plain text.**
    Done: `concord.pdf.repair_split_glyphs`, applied to every table in `read_pdf`. A run of 2-3
    adjacent cell tokens is joined only when the joined word is in the page's plain text and the
    split form is not. Commander FIX page 28 now yields `TrdRegPublicationType` and
    `TrdRegPublicationReason`. The extraction system prompt now says to quote from the page-text
    section, not the layout text. D10 untouched. Tests: split, three-way split, genuine two-word
    cell kept, unrelated cell untouched, and the opt-in real-page check. Limit: a cell broken
    by a page boundary (`ansactionId`) is a fragment, not a repairable split.
8. `done 2026-11-10` **Site: mark parameters that are not mutable on cancel/replace.**
   Done: parameters with `mutable_on_cxl_rpl is False` get a red "cannot amend" badge (colour
   plus text) in the name cell. Each strategy page has a "Cannot amend on cancel/replace:" line
   above the parameter table, listing those parameters or saying "none stated". Strategy pages
   also link to the previous and next strategy and, as before, back to the index. Tests: badge
   and summary with escaping and ordering, the none-stated case, index and neighbour links.
   Follow-up: item 12 (library index). Note: the repo targets Python 3.11, so f-string
   expressions must not contain backslashes (ruff catches it; local Python is 3.13).
23. `done 2026-11-09` **Site: rendered change report (`concord site NEW OUT_DIR --diff OLD`).**
    Done: `render_site(spec, old=None)` / `write_site(..., old)` and `--diff OLD` write
    `changes.html` (summary line, then Breaking, Additive, Cosmetic sections; each change shows
    `Strategy › Parameter`, message, old → new, and the raw path in small type) and link it from
    `index.html` with the counts. Severity is shown by colour and a text label. The inline CSS
    moved to one shared `style.css` with light and dark colours; every page links it. Without
    `--diff` no `changes.html` is written. Tests: one change per severity under the right
    heading, escaping, index link and counts, byte-identical output, CLI. Follow-ups: item 12
    (multi-spec library index); a strategy-level view of the report; item 8 still todo.
10. `done 2026-11-11` **IR + FIXatdl: keep the wire-contract attributes on `<Strategies>`.**
    Done (decision D16): `tag957_support`, `change_strategy_on_cxl_rpl`,
    `draft_flag_identifier_tag` read, written only when set, diffed (breaking / additive per
    D16), shown on the site index, listed by `concord schema`. `parameter_transport(param)` gives
    `tag` or `957-group`; the reader rejects a tagless parameter without `tag957Support="true"`.
    `example_broker.xml` now declares all three. Public samples (29 files): 0 set
    `tag957Support`, 2 set `changeStrategyOnCxlRpl` (`regions-enums.xml`, `tz-clock.xml`),
    0 set `draftFlagIdentifierTag`; the strictness breaks none. Follow-up: the Orchestra writer
    (9a) should use `parameter_transport`; `848-pairs` waits for PDF extraction.
9a. `done 2026-11-12` **FIX Orchestra writer, fields and codeSets.** Done (decision D17):
    `concord.orchestra.write_orchestra(spec) -> OrchestraResult` (`.xml` bytes,
    `.group_parameters`). Orchestra 1.0 / 2020 namespace in one constant. Fields per distinct tag,
    code sets for enum parameters and the strategy identifier, legal names, standard-tag
    annotation, conflicting definitions raise `OrchestraError`. The output validates against the
    real v1.6 XSD (checked locally with `CONCORD_ORCHESTRA_XSD_DIR`). The schema forces a
    message, so a minimal `NewOrderSingle` (strategy identifier only) is emitted for 9b to fill.
    No CLI yet. Follow-ups: 9b (message members, encoding, CLI); revisit at Orchestra 1.1 final.
9b. `done 2026-11-13` **FIX Orchestra writer: NewOrderSingle per strategy, 957 group, CLI.**
    Done (decision D18): one `NewOrderSingle` per strategy as a scenario, identifier constant,
    `required` / `constant` / bounds on parameter `fieldRef`s, a 957 group with a 958 code set of
    parameter names, and `concord convert FILE --to orchestra` (stdout). Note: v1.6 has no
    `fixr:scenarios` element, so the "declare scenarios" step was dropped. Both the fixture output
    and a 957-group case validate against the real v1.6 XSD when `CONCORD_ORCHESTRA_XSD_DIR` is
    set (checked locally). Follow-ups: 9c (rules); a stderr summary of skipped items.
9c. `done 2026-11-14` **FIX Orchestra writer: StrategyEdits as field rules where they fit.**
    Done (decision D19): new `concord.score` renders edits in Score (one test per operator) and
    recognises `F NX|EX OR C`; the writer turns those into `fixr:rule` presence rules and keeps all
    other edits as message annotations, returned in `OrchestraResult.unenforced` and printed on
    stderr by `concord convert --to orchestra`. Non-amendable parameters get an
    `OrderCancelReplaceRequest` scenario note. All four fixture edits read their own field, so they
    are annotations; a synthetic `StartTime NX OR Urgency == H` becomes a forbidden rule with
    `!(Urgency == ^High)`. Validates against the v1.6 XSD (opt-in, checked locally). Follow-ups:
    a CLI `--strict` that fails when anything is unenforced; revisit when Orchestra 1.1 is final.
20. `done 2026-11-15` **IR: allow a shared strategy wire value and a shared tag inside one strategy.**
    Done (decision D20): the IR drops both uniqueness checks (names stay unique); diff renames only
    on an unshared wire value or tag; the Orchestra identifier code set has one code per distinct
    wire value and a same-tag/different-type pair is an error naming both parameters; the site marks
    shared wire values and lists shared-tag parameters. The three strict xfails are gone: all 28
    public sample files pass (`CONCORD_PUBLIC_SAMPLES=1`). Tests: IR, FIXatdl round trip, two diff
    guards, Orchestra (one code; error text), site. Follow-up: represent two types on one tag in
    Orchestra (for example a String field with an annotation).
24. `done 2026-11-16` **Standard-tag check against the FIX dictionary (`concord lint`).** Done
    (decision D21): `concord.fixdict` (streaming reader, FIX Latest loads in 0.2 s) and
    `concord.lint`; `concord lint SPEC [--fix-version] [--dict-dir] [--format]` exits 2 on errors.
    Unit tests use a synthetic dictionary written in the test (no download): each error and warning
    kind and every `unionDataType` rule. An opt-in test (`CONCORD_PUBLIC_SAMPLES=1`) loads the real
    Latest and 4.2 files, lints the fixture (clean) and the 27 readable public samples: 4 errors,
    11 warnings. The four errors are real, all in FixPortal `regions-enums.xml`: `TimeInForce` (59),
    `Side` (54) and `OrdType` (40) declared Int where FIX says char. Follow-ups: run lint inside
    `concord extract` so findings reach the review list; let the Orchestra writer take names and types
    for standard fields from the dictionary instead of re-declaring them; a lint finding for a
    parameter that reuses a standard tag with a non-standard meaning.
25a. `done 2026-11-17` **Corpus pipeline, part 1: `concord corpus fetch` and `concord corpus plan`.**
    Done (decision D22). `fetch` takes only `use: ok` pdf/html entries, checks each response
    (`%PDF`, bot-challenge titles, HTTP status), writes `meta.json`, reuses the cache, and never
    retries. `plan` sizes the cache and estimates tokens; cost only with `--price-per-mtok`. Tests
    replace the network (`concord.corpus.http_get`): PDF ok, a PDF that is really a challenge
    page, HTML ok, challenge and 403, restricted/unreachable/unset-use and non-pdf/html entries
    skipped with no request, cache reuse, `meta.json`, plan on a synthetic PDF and HTML, the CLI.
    Real run 2026-11-17: all 14 eligible sources are in the cache (7 PDF, 7 HTML); a fresh fetch
    of three of them into a scratch directory succeeded (NYSE's PDF came back as a real PDF today),
    and `plan` estimated about 285,000 input tokens for the 14 (1.14 M characters, 311 PDF pages).
    New dependency: PyYAML (MIT). Follow-ups: 25b and 25c below.
26a. `done 2026-11-18` **Usage accounting and the input-token cap (first half of item 26).** Done
    (decision D23): `Usage` capture in `AnthropicBackend`, `ReplayBackend` (`page-N.usage.json`) and
    an estimate fallback; `--max-input-tokens` (default 150000) stopping before the call that would
    exceed it, keeping extracted facts and adding a `token_cap` review item; per-page and total
    tokens on stderr and in `<out>.usage.json`; `--record DIR` for raw responses. Tests (replay, no
    key): usage capture, estimate fallback, `usage_from_response`, the cap stopping early (and
    before page 1), no cap, recording round trip, the CLI.
26b. `blocked: ANTHROPIC_API_KEY is not visible in the Worker session (STATUS Needs owner 8)` **First
    live extraction on one real spec** (second half of item 26, unchanged). The Worker session's
    container predates the key, and a Default-environment variable only reaches a session that starts
    or resumes. Run it on `nyse-pillar-to-algo-fix` (`concord corpus fetch nyse-pillar-to-algo-fix`
    first, then `concord extract ... --record corpus/cache/<id>/run-<date>/responses --out
    corpus/cache/<id>/run-<date>/spec.json`, then `concord lint`), never commit the outputs
    (hard rule 2), and report pages, tokens, estimated cost (current price via the `claude-api`
    skill), verified facts, the review list's top 3 reasons, the lint findings and where extraction
    went wrong.
25b. `done 2026-11-19` **HTML text layer for HTML sources.** `concord.html.read_html(path) ->
    list[Page]` turns an HTML spec into pages, one per `h1`/`h2` section, with the
    section heading as the page's `locator` (the `Citation.locator` field already
    exists). It keeps tables as layout text, so `extract_tables` (item 21) works
    on them. It is stdlib `html.parser` only, with no scripts, no network and
    bounded depth (the untrusted-input rule). The verifier and extractor must
    accept these pages. A citation's `page` is the section index and its
    `locator` the heading. Acceptance: tests on a synthetic HTML page with two
    sections and a field table: section count, table rows, and a verify pass
    and fail on a quote. The opt-in test reads the cached Saxo page
    (`saxo-algo-order-fix-tags`) and finds tag 847 in a table.
    Done (decision D24): `concord.html.read_html` (stdlib parser, depth 200, 20 MB cap) and a
    `locator` field on `pdf.Page`; `build_prompt` names the section; `concord verify` and
    `concord extract` pick the reader by `.html`/`.htm` suffix. Tests: `tests/test_html.py` (sections,
    table rows, verify pass/fail, prompt, determinism, depth, malformed, CLI). The opt-in test reads
    the cached Saxo page: 22 sections, 20 tables, tag 847 found. Follow-up: item 11 (check
    `Citation.locator` against `Page.locator`); 25c should use `read_html` for `kind: html` sources.
25c. `done 2026-11-20` **Corpus pipeline, part 2: `concord corpus convert ID`.** One command
    runs extract (PDF or HTML, `--replay DIR` or live), then verify, then lint
    (item 24). The review list gets lint errors as well as unverified facts. It
    writes `corpus/out/<id>/` with `spec.json`, `strategies.xml`
    (FIXatdl), `orchestra.xml`, `site/` and `review.json`. Exit 2 if the review
    list is not empty. Acceptance: a replay test end to end on a synthetic PDF
    with recorded responses writes all five outputs, a lint error lands in
    `review.json`, and the output is byte-identical across two runs. Add a
    second replay case on a synthetic HTML page, since 25b is done; its citations
    carry the section `locator`. Thread `--max-input-tokens` through from 26a,
    and copy `usage.json` into the output folder. Live use is blocked only until
    the key reaches a session (STATUS 8). Add `corpus/out/` to `.gitignore`, which does not
    cover it today (hard rule 2: the output is derived from third-party documents).
    Done (decision D25): `concord.pipeline.convert_source` and `concord corpus convert ID` (`--replay`,
    `--record`, `--max-input-tokens`, `--fix-version`, `--dict-dir`, `--out-dir`). Writes `spec.json`,
    `strategies.xml`, `orchestra.xml`, `site/`, `review.json`, `usage.json`; exit 2 if the review list is
    not empty (extraction items, failed citations, lint errors). Dictionaries load before any model call.
    `corpus/out/` is git-ignored. Tests: `tests/test_pipeline.py` (PDF and HTML replay, locators, lint
    error and unverified fact in `review.json`, byte-identical reruns, token cap, bad requests, CLI).
    Follow-up: 26b is the first live use (needs the key, STATUS 8).
27. `blocked: the Worker routine prompt forbids merging without the owner's direct word (STATUS Needs owner 9)` `[safe]` **Ship the unmerged runs (D12).** PM check 2026-11-21: PR #22 (`dev` → `main`)
    has been open since 2026-11-19, and `main` is still at `d43b351` (2026-11-18). CI passed on
    `dev` head `8c56a3e` (run 44729408067). The 25b and 25c runs pushed but did not merge, and
    STATUS gives no reason. At the start of the firing, confirm the PR head SHA equals local
    `dev` and merge with a merge commit, per CLAUDE.md. If the merge is refused, record the exact
    refusal under *Needs owner* in STATUS, as CLAUDE.md asks, instead of leaving it silent.
    Then take the next item.
11. `done 2026-11-21` **Verifier follow-ups.** Flag quotes that match on several pages, and
    check `Citation.locator` when present.
    Moved up 2026-11-21: it tightens the D10 guard before the first live run (26b). HTML
    pages (25b) rely on `locator`, so check it against the section heading too.
    Acceptance: tests in `tests/test_verify.py` for each, with D10 strictness kept.
    Done (decision D26): a citation whose `locator` differs from the heading of the cited page (pages
    from `read_html`) fails as `locator_mismatch`; a PDF page or a heading-less page cannot check a
    free-form locator and ignores it. A quote that also appears on other pages still verifies but is
    listed as ambiguous (text and JSON `ambiguous`, `CitationResult.also_on`), never a failure (D10
    kept). Tests in `tests/test_verify.py`; the HTML test now cites real headings.
12. `done 2026-11-22` **Site: library index (`concord library OUT_DIR SPEC...`).** Made concrete 2026-11-22.
    This is the public library page for the Corpus phase (business plan §10.2), and the
    one the converted specs (25c → `corpus/out/<id>/spec.json`) will feed. It needs no
    API key.
    Do this:
    - `concord library OUT_DIR SPEC [SPEC ...]` takes FIXatdl or IR JSON files, and
      `--from-corpus corpus/out` takes every `*/spec.json` there. It writes
      `OUT_DIR/index.html` and calls the existing `render_site` for each spec into
      `OUT_DIR/<provider-slug>/`, reusing item 6's slugging. Two specs from the same
      provider get distinct slugs.
    - The index has one table: provider, strategies (count), strategy identifier tag,
      parameter count, *cited* facts as a share of all facts (the accuracy story,
      shown as e.g. `42 / 45 cited`), and the lint error and warning counts when a
      `review.json` sits next to the spec. Then comes a strategy finder: one row per
      strategy across all specs (provider, strategy, wire value, link), sorted by
      provider and then strategy name.
    - Use the existing shared `style.css` (item 23): stdlib only, no JS, works from
      `file://`, all text escaped.
    Acceptance: a test with two specs (the fixture, plus a second synthetic IR with
    citations built in the test) checks both rows, the cited counts, links that
    resolve to written files, and escaping. Output is byte-identical across two
    runs and independent of argument order. A `--from-corpus` test uses a temporary
    directory with two `spec.json` files and one `review.json`.
    Done (decision D27): `concord library OUT_DIR [SPEC ...] [--from-corpus DIR]` and
    `concord.library` (`render_library`, `write_library`, `entry_for`). `index.html` has a provider table
    (strategies, identifier tag, parameters, `N / M cited`, lint errors, lint warnings, review items; `-`
    when the sidecar file is absent) and a strategy finder sorted by provider then name; each spec's own
    site sits under `<provider-slug>/`. `concord corpus convert` now also writes `lint.json` (all
    findings) because `review.json` holds only lint errors. Tests: `tests/test_library.py` (counts,
    escaping, links resolve, sidecars, slug clash, order independence, CLI incl. `--from-corpus`).
17a. `done 2026-11-23` **MCP server, part 1: `concord mcp` (stdio) over what Concord already does.** Added
    2026-11-23. Phase A's key-free work is done except item 19, and live extraction waits on the
    owner (STATUS 8). The business plan's free tier (§6) is "better spec browser, parser, MCP
    server", and §8 says "publish, then converse". An MCP server lets an OMS engineer ask Claude
    "what is tag 849 in FIX 4.2?" or "what breaks if I move from v1 to v2 of this broker spec?"
    and get Concord's deterministic answers. It needs no API key on our side.
    Do this:
    - Dependency: the official Python MCP SDK, PyPI `mcp` (MIT; 2.3.0, released 2026-10-02, is
      old enough). Make it an **optional extra** `mcp`, the way `llm` is (D11), so the core has
      no new dependency. Rule 5: check the license of every transitive dependency it pulls in
      (httpx2, starlette, sse-starlette, pyjwt, opentelemetry-api, python-multipart and so on)
      and list them in the commit message. Stop and record under *Needs owner* if any is
      GPL/AGPL/LGPL.
    - `concord mcp` runs a stdio server with four read-only tools. Each returns JSON plus a short
      text summary:
      - `fix_field(tag, fix_version="latest")`: name, type, code set values and
        `unionDataType` from `concord.fixdict` (item 24). The dictionaries are fetched on demand
        as today; if they are absent, return a clear error that says how to fetch them.
      - `lint_spec(path, fix_version)`: `concord lint` findings.
      - `diff_specs(old_path, new_path)`: `concord diff` JSON (D9).
      - `describe_spec(path)`: strategies, parameters, tags and citations, as `concord inspect` but
        structured.
    - Untrusted input: paths are files the caller names. Read them with the existing readers
      (XXE-safe). Never write files, never fetch the network except the existing dictionary
      fetch, and return errors with locations, not stack traces.
    - README section: how to add it to Claude Code (`claude mcp add concord -- uv run concord mcp`)
      and to Claude Desktop config.
    Acceptance: unit tests call each tool's handler function directly, with no MCP transport, on
    the fixture and a synthetic v2 built in the test: field lookup through a tiny synthetic
    dictionary (as item 24's tests do), a lint finding, a breaking diff, and the
    `describe_spec` shape. One smoke test starts `concord mcp` over stdio with the SDK client
    and lists the four tools, skipped when the `mcp` extra is not installed. Plain `uv run pytest`
    passes without the extra.
    Done (decision D28): `concord mcp` (stdio) with `fix_field`, `lint_spec`, `diff_specs`,
    `describe_spec`; handlers in `concord.mcp_tools` (no SDK), server in `concord.mcp_server`. Optional
    extra `mcp` (`mcp>=1.2`, locked at 2.3.0). Tests: `tests/test_mcp.py` (each handler, error cases, an
    SDK stdio smoke test skipped without the extra); `uv run pytest` passes with and without it. README
    section added. Follow-up: 17b (public spec library lookups once `corpus convert` has real output).
19. `done 2026-11-24` **Diff: citation (provenance) drift.** Report a fact whose citation
    page or quote changed while its value did not, as *cosmetic* with a
    `provenance` note, so reviewers see when a re-extraction moved evidence
    (item 1 follow-up). Sharpened 2026-11-24:
    - Kind `provenance_changed`, severity *cosmetic*, with old and new `source:page`
      and quote. Compare only citations whose `source_id` matches on both sides. Between
      two different editions every page moves, so a changed source is not drift and is
      not reported.
    - **Opt-in** with `--provenance` (on `concord diff` and `diff_specs(...,
      provenance=False)`), because between broker versions the noise would bury the
      real changes. The use case is re-extracting the *same* PDF, e.g. after prompt
      tuning (26b onwards), to see where evidence moved.
    - Leave D9 classification unchanged. Without the flag the output is byte-identical
      to today's.
    Acceptance: tests for a moved page, a changed quote, a changed `source_id` (not
    reported), and flag off (no change from current output). Text and JSON both show
    it when on.
    Done (decision D29): `diff_specs(old, new, provenance=False)` and `concord diff --provenance`. A
    cosmetic `provenance_changed` change names the fact and shows old and new `source:page "quote"`,
    for citations to a source present on both sides; flag off leaves output byte-identical. Facts
    covered: strategies (including wire-value renames), parameters and enum values matched by name or
    wire value. Not covered: edits and renamed parameters. Tests in `tests/test_diff.py`.

## Phase A — research `[safe]`

13. `done 2026-11-07` `[safe]` **Corpus terms review.** Fetched the 25 non-repo sources into
    `corpus/cache/` and read their terms. 14 `ok`, 4 `restricted` (BofA: marked confidential;
    Cboe, LSEG, Proof: no copying) and their cached copies deleted, 7 `unreachable` (CQG
    technical parameters and Goldman: HTTP 403; FIXsim: proxy refusal; FIX Trading archive: 502;
    both Nasdaq Nordic PDFs and Integral: server errors). Follow-up: retry the unreachable ones
    in a later run; do not work around 403s. Wire tags (from keyword/number scan, not a read):
    carried by the three NYSE specs, `commanderfx-rules-of-engagement`, `saxo-algo-order-fix-tags`,
    both TT pages and `cqg-algo-engine-support`; prose-only: `saxotraderpro-algoguide`, WEX,
    Standard Chartered, Deltix. `proof-fix-spec` is now excluded, so the extraction item should
    start from `nyse-pillar-to-algo-fix`.
14. `done 2026-11-06` `[safe]` **Public algo spec catalogue** (25 of 25 catalogued: 10 on
    2026-11-04, 6 on 2026-11-05, 9 on 2026-11-06). Find more openly published broker/venue algo
    specs and record each in `corpus/sources.yaml`. Prefer documents that carry
    FIX wire tags; prose-only factsheets are weak test material.
    Acceptance: 25 entries and the YAML still parses.
    Done: 25 entries, all unique ids, all catalogued from search only (fetching is
    blocked, item 13). Follow-up: add sources only when they carry wire tags or form
    a version pair for diff tests.
15. `done 2026-11-05` `[safe]` **Competitive watch.** No PDF→FIXatdl/Orchestra
    converter found; see `docs/research/competitors.md`. Next check due 2026-12-05.

## Phase B — product surface (after Phase A)

16a. `done 2026-11-25` **Review screen, part 1: `concord review OUT_DIR` writes a read-only review page.** Added
    2026-11-25. Phase A's key-free work is done (item 19 was the last). Live extraction waits on the
    owner (STATUS 8), and every converted spec will then put items on a review list. The business
    plan says "uncertain output goes to review, never silently into the file", and accuracy is the
    product (§6). The review screen is how a human clears that list, so build it before the first
    live run produces one. It is also the most demoable thing left (the owner asked for a demo on
    2026-11-08).
    Do this:
    - Input: a `corpus convert` output folder, `corpus/out/<id>/` (25c), holding `spec.json`,
      `review.json` (the `ReviewItem` dicts plus lint entries) and `lint.json`, plus the
      source document. Add a `source_path` field to `review.json` or `spec.json` if it is not
      already recorded.
    - Output: `OUT_DIR/review/index.html`, a static page with no JS that works from `file://`
      and uses the shared `style.css` (item 23).
      - At the top: counts by kind (`unverified`, `conflict`, lint `error` / `warning`).
      - One card per item, side by side, stacking on narrow screens. On the left, the cited
        page's text (page N or the HTML section `locator`), read with the same
        `read_pdf`/`read_html` the verifier uses, with the quote highlighted (`<mark>`) where
        D10 folding finds it. If it is not found, say "quote not found on page N" and show
        the page. On the right, the fact (location `Strategy › Parameter`, the extracted
        value), the kind, and the reason message.
      - Escape every piece of document text, since it is untrusted.
    - It is read-only here. Accept and fix come in 16b. Each card gets a stable `id` (a hash of
      location, kind and page), so 16b can record decisions against it.
    Acceptance: an end-to-end test on the synthetic replay folder the 25c tests produce, with one
    unverified fact, one conflict and one lint error. Check the counts, one card each, the
    `<mark>` around a found quote, the "not found" text for a fabricated quote, the escaping of a
    `<script>` in page text, byte-identical output over two runs, and stable card ids.
    Done (decision D30): `concord review OUT_DIR [--source PATH]` and `concord.review`
    (`build_review`, `render_review`, `card_ids`) write `OUT_DIR/review/index.html` and `style.css`:
    counts by kind, one card per item (cited page left with `<mark>` on the quote, fact and reason
    right), lint warnings from `lint.json` as extra cards, stable card ids. `ReviewItem` gained
    `quotes` (the model's page and quote, written to `review.json` only when present) and `corpus
    convert` writes `source.json` (id, kind, path). Tests: `tests/test_review.py` (counts, `<mark>`,
    not-found text, `<script>` escaping, byte-identical reruns, stable ids, CLI and `--source`).
    Follow-up: 16b needs the card ids; quotes found only after hyphenation or typography folding are
    reported but not marked.
16b. `done 2026-11-26` (first half; server is 16c) **Review screen, part 2: accept / fix, recorded.** `concord review OUT_DIR --serve` runs a
    local stdlib `http.server` on 127.0.0.1 only. Each card gets **Accept** (keep the fact, recorded
    as human-verified, with reviewer and time) and **Reject** (drop it), with an optional corrected
    value. Decisions go to `OUT_DIR/decisions.json`, keyed by card id. `corpus convert --apply-
    decisions` rebuilds `spec.json`, FIXatdl, Orchestra and the site with them. A human-verified fact
    carries a `Citation`-like record of the reviewer's decision, so it is never "uncited". Record the
    model of human verification as a D-entry, which needs an IR field (additive, no version bump).
    Sharpened 2026-11-26:
    - IR: add a `review: Review | None` field to facts, with fields `decision` (accepted/
      rejected/corrected), `reviewer`, `at` (ISO date), `note` and `card_id`. A fact with
      an accepted review counts as cited on the site and in the library, with a visible
      "human-verified" label and no "uncited" marker.
    - Server safety: bind to 127.0.0.1 only. Create a random token at start-up, print it
      in the URL, and require it on every POST. Allow no path outside `OUT_DIR`. Decision
      writes are atomic (write a temp file, then rename). Stop with Ctrl-C.
    - The HTML is still no-JS-required: plain `<form method=post>` per card, so it also
      works in a phone browser over an SSH tunnel.
    Acceptance: the handler is tested directly (no sockets) for accept, reject and correct.
    Test that a bad token returns 403 and a path-traversal attempt returns 404, that
    `--apply-decisions` changes `spec.json` and drops a rejected fact, and that output is
    byte-identical over two applies. One smoke test runs the real server on an ephemeral
    port and makes one POST.
    Done (decision D31): IR `Review` on every fact (`decision`, `reviewer`, `at`, `note`, `card_id`;
    additive, no version bump); `concord.decisions` and `concord review OUT_DIR --apply-decisions`
    (exit 2 while cards are open or unapplied) apply `decisions.json` (accept, reject, correct with
    `corrections`) from `spec.extracted.json`, so reapplying is idempotent, and rewrite `spec.json`,
    `strategies.xml`, `orchestra.xml`, `site/` and `applied.json`. A reviewed fact shows
    "human-verified" on the site and counts as cited in the library. It is `review --apply-decisions`,
    not `corpus convert --apply-decisions` as first written: applying must not re-run extraction (a
    live model call that could change card ids). Tests: `tests/test_decisions.py`.
16c. `done 2026-11-27` **Review screen, part 3: Accept restores a dropped fact.** (Split 2026-11-27: restore
    first, because without it Accept on an `unverified` card does nothing, and that is the commonest
    card a live run will produce. The server is now 16d.)
    - `extract._filter_fragment` drops the fact in `reject()` and keeps only its quotes. Add an
      optional `fact` field to `ReviewItem` holding the dropped fact's IR JSON (the Strategy,
      Parameter or EnumPair dict as `ir` serialises it), written to `review.json` only when present
      so older files keep their shape (same pattern as `quotes`).
    - In `concord.decisions`, Accept or Correct on a card whose fact is absent restores it from
      `fact`: insert at its location (Parameter under its Strategy, EnumPair under its Parameter;
      a whole Strategy appended), record the `Review`, and keep the order deterministic (append at
      the end of the parent's list). If the parent is itself absent, leave the card unapplied with
      a reason naming the missing parent. Reject keeps the fact dropped. Cards with no `fact`
      (older review files) stay unapplied with today's message.
    - The restored fact's failed citations stay stripped; it counts as cited only through its
      `Review` (D31), so the site shows "human-verified", not a quote it could not find.
    Acceptance: synthetic fixture with one dropped Parameter and one dropped EnumPair. Accept
    restores each at the right place in `spec.json`, `strategies.xml` and `orchestra.xml`; Reject
    leaves them out; Correct restores with the corrected value; a dropped Parameter whose Strategy is
    also dropped stays unapplied with a clear reason; two applies give byte-identical output; an old
    `review.json` without `fact` still loads. No new dependency.
    Done (decision D32): `ReviewItem.fact` holds a dropped Strategy, Parameter, EnumValue or
    StrategyEdit as IR JSON with every `citations` list removed (written to `review.json` only when
    present). In `concord.decisions`, Accept or Correct on a card whose fact is absent restores it at
    the end of its parent's list and records the `Review`; Reject keeps it dropped; a missing parent
    is named in the unapplied reason; an older `review.json` without `fact` keeps the old message.
    Decisions apply parents before children (stable by review order). Tests in
    `tests/test_decisions.py`: extraction stores the fact, Accept and Correct restore in place, Reject,
    missing parent, an invalid correction, and restored facts in `spec.json`, `strategies.xml`,
    `orchestra.xml` and the site, byte-identical over two applies.
16d. `todo` **Review screen, part 4: the local server.** (Sharpened 2026-11-28.) The last piece
    of the review screen: today a reviewer must hand-edit `decisions.json`. After this, `concord
    review OUT_DIR --serve` opens the side-by-side page with buttons, and one click rebuilds the
    outputs. It is the first thing a design partner can use without a terminal editor.
    Do this:
    - Put the logic in a pure function, e.g. `review_server.handle(method, path, headers, body,
      *, root, token) -> (status, headers, body)`, and keep the `http.server` subclass a thin
      wrapper around it. Stdlib only, no new dependency.
    - Routes: `GET /?t=TOKEN` renders the page through `review.render_review` with a form per card
      (Accept, Reject, Correct with a value box, a reviewer field, and an optional note).
      `POST /decide` records one decision. `POST /apply` runs `decisions.apply_to_folder`. Both
      POSTs answer 303 to `/?t=TOKEN`, so a reload never re-submits. `GET /site/...` serves the
      rebuilt site read-only. Anything else is 404.
    - Writes reuse `decisions._atomic_write`. Stamp `at` in UTC ISO-8601 and keep the existing
      keys of `decisions.json` untouched, apart from the card being decided. The page shows the
      exit state of the last apply: how many applied, and which cards are still open.
    - Safety:
      - Bind 127.0.0.1 only, with port 0 by default, and print the URL with the token.
      - The token comes from `secrets.token_urlsafe(16)` and is compared with
        `hmac.compare_digest`. It must be on every request, the GETs included.
      - Return 400 unless the Host header is `127.0.0.1:PORT` or `localhost:PORT` (this guards
        against DNS rebinding).
      - Cap request bodies at 64 KiB (413 above that).
      - Resolve every served path and refuse it unless it sits inside `OUT_DIR` (404).
      - Return 400 for an unknown card id or decision, naming the field.
      - Ctrl-C stops the server cleanly.
    - The page needs no JavaScript: plain `<form method=post>`. Escape every value taken from the
      spec or the PDF.
    Acceptance:
    - `handle` is tested directly, with no sockets: accept, reject and correct each write the
      expected `decisions.json`; a missing or wrong token gives 403; a bad Host gives 400; a
      `../` path or a symlink out of `OUT_DIR` gives 404; an oversize body gives 413; an unknown
      card gives 400.
    - `POST /apply` changes `spec.json`, and a second apply is byte-identical.
    - One smoke test starts the real server on an ephemeral port in a thread, makes one GET and
      one POST with `urllib`, then shuts it down.
17. `todo` MCP server: FIX repository lookups plus the public spec library.
18. `todo` Hosted spec portal with change-watch alerts.

## Owner items

Tracked under *Needs owner* in `docs/STATUS.md`.
