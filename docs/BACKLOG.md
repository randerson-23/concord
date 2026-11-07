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
    Note (research 2026-11-06): strategy identifiers also arrive as ExDestination(100)
    or BrokerID(76). `strategy_identifier_tag` already covers these, so this item adds
    nothing for them. Keep the fixture's identifier on 847.
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
    pattern. The XSDs can be fetched (checked 2026-11-07): `repository.xsd`,
    `repositorytypes.xsd` and the `dc*` / `xml.xsd` imports are under
    `repository/src/main/resources/xsd/` in `FIXTradingCommunity/fix-orchestra`,
    which is Apache-2.0 (corpus id `fix-orchestra-repository-xsd`, pinned).
    D7 allows vendoring them with attribution (a NOTICE entry). Fetching on
    demand like the FIXatdl XSD is also fine. The worker picks one and records it.
    `repository/src/test/resources/examples/mit_2016.xml` is a reference
    Orchestra file to check the writer's structure against.
    Acceptance: CLI test writes the file and exits 0; XPath test for the message
    members; determinism test.
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
    top-level index of providers and strategies across specs. It also takes
    `--diff OLD` to add a rendered change report page. This builds on item 6.
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
