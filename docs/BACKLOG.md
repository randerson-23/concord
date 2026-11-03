# Backlog

Ordered by priority. Automated runs take the highest `todo` item that is not
blocked. `[safe]` items may run in hold mode (see CLAUDE.md, review gate).

States: `todo` · `doing` · `done YYYY-MM-DD` · `blocked: <reason>`

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
5. `todo` **LLM extraction scaffold.** `concord.extract`: chunk a PDF by page,
   ask Claude for IR fragments with mandatory page+quote citations via
   structured output, merge fragments into one `AlgoSpec`, run the citation
   verifier, route anything unverified to a review list. Use the latest Claude
   model. Tests run against recorded responses so no API key is needed in CI.
   Live runs `blocked: ANTHROPIC_API_KEY` until the owner adds it.
6. `todo` **Static spec site.** `concord site spec.json out/`: render an
   `AlgoSpec` as a browsable static HTML reference — strategies, parameter
   tables, enums, rules, with citations linked to source pages. The seed of
   the free spec browser (the funnel).
7. `todo` **FIX Orchestra writer.** IR → Orchestra repository XML for the
   order-entry slice (NewOrderSingle + algo parameters). Validate against the
   Orchestra schema from `FIXTradingCommunity/fix-orchestra` (Apache 2.0, so
   it may be vendored with attribution).

## Phase A — research `[safe]`

8. `todo` `[safe]` **Public algo spec catalogue.** Use web search to find
   broker and venue algo specifications published openly as PDFs (algo guides,
   FIX rules of engagement with algo sections). Record each in
   `corpus/sources.yaml`: URL, publisher, title, document type, what terms the
   publisher states. Aim for 25. Do not download beyond what the network
   policy allows; cataloguing URLs is enough.
9. `todo` `[safe]` **Competitive watch.** Check whether anyone has shipped
   PDF-to-FIXatdl or PDF-to-Orchestra conversion since 2026-11-01. One
   paragraph in `docs/research/competitors.md`, updated monthly.

## Phase B — product surface (after Phase A)

10. `todo` Review UI: side-by-side PDF page and extracted rules, accept/fix.
11. `todo` MCP server: FIX repository lookups plus the public spec library.
12. `todo` Hosted spec portal with change-watch alerts.

## Owner items

Tracked under *Needs owner* in `docs/STATUS.md`.
