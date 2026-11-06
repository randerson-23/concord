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
2. `blocked: session GitHub scope covers only randerson-23/concord, so other repos (atdl4j etc.) can't be read` **Public FIXatdl samples.** Find FIXatdl files published on GitHub
   under permissive licenses (start with `atdl4j/atdl4j` examples and
   `FixPortal/fixportal-fixatdl`). Record each in `corpus/sources.yaml`
   with URL and license. Add a test that fetches them into `corpus/cache/`
   (skipped when offline) and reads every one without error. Fix reader gaps
   they expose. Do not commit the files themselves.
3. `done 2026-11-02` **PDF text layer.** `concord.pdf`: page-aware text and table
   extraction that keeps page numbers, for citations. Use `pypdf` or
   `pdfplumber` (permissive). Not PyMuPDF (AGPL). Test against a synthetic PDF
   generated in the test itself.
   Done: `concord.pdf` (`read_pdf`, `extract_tables`, `normalize`); tables are a
   layout-gap heuristic. Follow-up: ruled-table detection via pdfplumber if the
   heuristic proves weak on real specs.
4. `done 2026-11-03` **Citation verifier.** Given an `AlgoSpec` and its source PDF,
   confirm every citation's `quote` actually appears on its cited `page`
   (whitespace- and hyphenation-tolerant). Report failures. This is the
   deterministic guard against an LLM inventing a rule — it is the core of
   the accuracy story, so make it strict.
   Done: `concord.verify` + `concord verify spec.json --source ID=PDF` (exit 2 on
   any failure). Follow-ups: check `Citation.locator`; flag quotes that match
   on several pages when none is cited.
5. `done 2026-11-04` **LLM extraction scaffold.** `concord.extract`: chunk a PDF by page,
   ask Claude for IR fragments with mandatory page+quote citations via
   structured output, merge fragments into one `AlgoSpec`, run the citation
   verifier, route anything unverified to a review list. Use the latest Claude
   model. Tests run against recorded responses so no API key is needed in CI.
   Live runs `blocked: ANTHROPIC_API_KEY` until the owner adds it.
   Done: `concord.extract` (`extract_spec`, `Backend` protocol, `ReplayBackend`,
   `AnthropicBackend`) and `concord extract PDF --id --title --out [--replay DIR]`
   (exit 2 if the review list is non-empty). Facts without a verified citation
   never enter the spec. Follow-ups: tune prompt on a real spec once a key exists
   (item 5b); per-page calls miss cross-page context (consider a second pass that
   resolves "see table 3"); cost/token accounting.
6. `done 2026-11-05` **Static spec site, core: `concord site SPEC OUT_DIR` renders one
   `AlgoSpec` as deterministic static HTML with every fact linked to its source
   page.** This starts the free public library, the funnel in business plan §5/§8.
   Nobody else offers a public spec browser
   (`docs/research/competitors.md`). It needs no owner input.
   Acceptance:
   - New `src/concord/site.py` using the stdlib only (`html.escape`, no template
     engine, no new dependency). All IR text is escaped. Inline CSS, no JS, no
     external assets, so the output works from `file://`.
   - `SPEC` accepts IR JSON or FIXatdl (reuse `cli._load`). Output is `index.html`
     (provider, description, identifier tag, a table of strategies with
     name / label / wire value / parameter count) plus
     `strategies/<slug>.html` for each strategy. Each strategy page shows a
     parameter table (name, FIX tag, type, required, default, min/max, enum
     values as `wire — label`, mutable on cancel/replace), rules (StrategyEdits as
     readable expressions such as `Side == 1 AND OrderQty > 0`) and applicability.
     Slugs are unique even when two names slug the same.
   - Citations: each cited fact shows `[source-id p.N]`. It links to
     `SourceDocument.url#page=N` when the source has a URL, and the quote goes in a
     `title` attribute. Facts with no citation get a visible `uncited` marker.
     Concord does not hide guesses.
   - Deterministic: render the same spec twice and get byte-identical trees (no
     timestamps, IR order kept).
   - `tests/test_site.py` uses the existing `tests/fixtures/fixatdl/example_broker.xml`
     plus one synthetic IR with citations. It covers escaping (a `<script>` in a
     description comes out inert), citation links and `uncited` markers,
     determinism, slug collisions, and `concord site` exiting 0 and writing the
     expected files.
   Done: `concord.site` (`render_site`, `write_site`) and `concord site SPEC OUT_DIR`;
   `tests/test_site.py`. Only http(s) source URLs become links. Follow-ups: item 8
   (cxl/rpl badge), item 12 (library index); add a nav link between strategies.
7. `done 2026-11-06` **Diff: match strategies by wire value when names change.** A
   removed+added strategy pair with the same `wire_value` is reported as a rename.
   The rename is cosmetic. Changes inside it are diffed as usual. This follows the
   D9 parameter rule, so it extends D9 and does not reverse it. Record it as a
   D9 addendum in DECISIONS. Why first: diff is the paid feature, and public specs
   show wire values are the stable identity while names and labels drift
   (`docs/research/customer-signal.md`, 2026-11-06).
   Acceptance:
   - Tests in `tests/test_diff.py`: rename alone (cosmetic only, text report reads
     `renamed 'Old' -> 'New' (wire value 1001)`); rename plus a removed parameter
     (breaking, reported under the new name); two removed strategies sharing a
     wire value (no match, reported as removed/added); JSON output carries the
     old and new names.
   - CLI test: `concord diff old.json new.json --fail-on-breaking` exits 0 for a
     rename alone and 2 for rename plus removed parameter.
8. `todo` **Site: mark parameters that are not mutable on cancel/replace.** Show a
   badge wherever `mutable_on_cxl_rpl is False`, and add a "cannot amend" summary
   on each strategy page. Customer signal says custom tags breaking cxl/rpl is a
   recurring OMS failure (`docs/research/customer-signal.md`). Also add prev/next
   and index navigation links between strategy pages (item 6 follow-up).
   Acceptance: a site test with one immutable parameter checks the badge and the
   summary line; a test checks each strategy page links back to `index.html`;
   determinism test still passes.
10. `todo` **IR: parameter encoding.** Add a `wire_encoding` field to the strategy
    or spec, with values `tag` / `848-pairs` / `957-group`. Public specs use all
    three (TT uses 957–960, the FIX 4.4 extension uses 848, most use flat custom
    tags; see `docs/research/customer-signal.md`). This adds a field without
    changing any meaning, so no IR_VERSION bump. The FIXatdl reader sets `tag`.
    Moved ahead of item 9 because the Orchestra writer must know the encoding.
    Acceptance: round-trip test, diff classifies an encoding change as breaking,
    site shows the encoding, and `concord schema` shows the field.
9a. `todo` **FIX Orchestra writer, fields and codeSets.** `concord.orchestra`
    writes an Orchestra repository with one field per algo parameter (custom
    tags as user-defined fields) and one codeSet per enum, plus the strategy
    identifier field with a codeSet of strategy wire values. Follow the draft
    *Recommended Practices: Onboarding with FIX Orchestra*
    (<https://forum.fixtrading.org/t/public-comment-period-fix-recommended-practices-onboarding-with-fix-orchestra/17170>).
    Acceptance: deterministic (byte-identical test); lxml XPath tests on the
    `example_broker.xml` fixture output for field ids, types and codes. No CLI yet.
9b. `todo` **FIX Orchestra writer, NewOrderSingle and CLI.** Add a NewOrderSingle
    message referencing the fields from 9a (encoding-aware per item 10), and
    `concord convert spec.json out.xml --to orchestra`. Schema validation is opt-in
    through `CONCORD_ORCHESTRA_XSD_DIR` (skipped when unset), matching the FIXatdl
    pattern. Fetching the XSD from `FIXTradingCommunity/fix-orchestra` may hit the
    same scope block as item 2. If it does, ship with the opt-in test and do not
    vendor the XSD. D7 allows vendoring, but only once the XSD can be fetched.
    Acceptance: CLI test writes the file and exits 0; XPath test for the message
    members; determinism test.
11. `todo` **Verifier follow-ups.** Flag quotes that match on several pages, and
    check `Citation.locator` when present.
    Acceptance: tests in `tests/test_verify.py` for each, with D10 strictness kept.
12. `todo` **Site: library index.** `concord site` accepts several specs and writes a
    top-level index of providers and strategies across specs. It also takes
    `--diff OLD` to add a rendered change report page. This builds on item 6.
    Acceptance: multi-spec test plus determinism test.
19. `todo` **Diff: citation (provenance) drift.** Report a fact whose citation
    page or quote changed while its value did not, as *cosmetic* with a
    `provenance` note, so reviewers see when a re-extraction moved evidence
    (item 1 follow-up). Acceptance: tests for a moved page and a changed quote;
    text and JSON output both show it.

## Phase A — research `[safe]`

13. `blocked: network policy blocks every publisher domain, so terms cannot be read (STATUS Needs owner 3)` `[safe]` **Corpus terms review.** For each
    `corpus/sources.yaml` entry, fetch the document into `corpus/cache/`, record
    the publisher's stated terms and check whether it carries FIX wire tags.
    Acceptance: every entry has `terms` filled in, with no "Not reviewed" left.
14. `todo` `[safe]` **Public algo spec catalogue** (18 of 25 catalogued: 10 on
    2026-11-04, 6 on 2026-11-05, 2 on 2026-11-06). Find more openly published broker/venue algo
    specs and record each in `corpus/sources.yaml`. Prefer documents that carry
    FIX wire tags; prose-only factsheets are weak test material.
    Acceptance: 25 entries and the YAML still parses.
15. `done 2026-11-05` `[safe]` **Competitive watch.** No PDF→FIXatdl/Orchestra
    converter found; see `docs/research/competitors.md`. Next check due 2026-12-05.

## Phase B — product surface (after Phase A)

16. `todo` Review UI: side-by-side PDF page and extracted rules, accept/fix.
17. `todo` MCP server: FIX repository lookups plus the public spec library.
18. `todo` Hosted spec portal with change-watch alerts.

## Owner items

Tracked under *Needs owner* in `docs/STATUS.md`.
