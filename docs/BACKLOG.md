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
20. `todo` **IR: strategies that share a wire value or a fixTag.** Three public files
    are rejected by IR uniqueness checks: atdl4j `Example Strategy Filtering.xml` and
    `Example StrategyPanel Tests2.xml` (many strategies, same `wireValue`, distinguished by
    region/`fixMsgType` filters) and FixPortal `tz-clock.xml` (two parameters on tag 7157, one
    active per state rule). Decide the identity rule (wire value plus applicability? tag per
    state?) and write it as a D-entry before relaxing the validators; that changes diff
    matching (D9). Remove the strict xfails in `test_public_samples.py` when fixed.
    Acceptance: all 29 samples pass with no xfail; diff tests still pass.
11. `todo` **Verifier follow-ups.** Flag quotes that match on several pages, and
    check `Citation.locator` when present.
    Acceptance: tests in `tests/test_verify.py` for each, with D10 strictness kept.
12. `todo` **Site: library index.** `concord site` accepts several specs and writes a
    top-level index of providers and strategies across specs. This builds on
    item 6. The `--diff` part moved to item 23.
    Acceptance: multi-spec test plus determinism test.
19. `todo` **Diff: citation (provenance) drift.** Report a fact whose citation
    page or quote changed while its value did not, as *cosmetic* with a
    `provenance` note, so reviewers see when a re-extraction moved evidence
    (item 1 follow-up). Acceptance: tests for a moved page and a changed quote;
    text and JSON output both show it.

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

16. `todo` Review UI: side-by-side PDF page and extracted rules, accept/fix.
17. `todo` MCP server: FIX repository lookups plus the public spec library.
18. `todo` Hosted spec portal with change-watch alerts.

## Owner items

Tracked under *Needs owner* in `docs/STATUS.md`.
