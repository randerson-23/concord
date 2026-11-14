# Decisions

Settled questions. Automated sessions do not reverse these; they propose
changes under *Needs owner* in `docs/STATUS.md`.

## D1 · 2026-11-01 · Wedge: broker algo specs first, pipeline built generically

*Owner decision.* Start with broker algo specifications — the acute,
two-sided problem where every OMS/EMS maps every broker's algo parameters by
hand, and FIXatdl already exists as the machine-readable target. Build the
pipeline generically (format-neutral IR) so it widens to full rules of
engagement and FIX Orchestra later.

## D2 · 2026-11-01 · Public sources only

*Owner decision.* All development and test material comes from documents
their owners publish openly. Nothing from the owner's employer, nothing under
NDA, nothing marked confidential. Protects the owner from trade-secret and
IP-assignment claims, and the public library doubles as the marketing asset.
Enforced by hard rule 1 in CLAUDE.md.

## D3 · 2026-11-01 · Daily automated runs, weekdays 05:37 US Central

*Owner decision.* A scheduled session runs each weekday morning, results ready
before the workday. To stop daily output outrunning the owner's review time,
runs drop to `[safe]` work once five unreviewed runs are waiting (CLAUDE.md,
review gate).

## D4 · 2026-11-01 · Branch model: `main` reviewed, `dev` automated, one rolling PR

Automated runs commit to `dev` and keep a single open PR `dev → main` with a
running summary. The owner reviews and merges in batches. Continuity between
runs is preserved because `dev` always carries yesterday's work, merged or not.

## D5 · 2026-11-01 · Stack: Python 3.11, uv, pydantic v2, lxml

Python has the strongest PDF, XML and LLM tooling. Pydantic gives the IR
validation and a JSON Schema for free. A TypeScript front end may come later
for the review UI and spec portal; the engine stays Python.

## D6 · 2026-11-01 · Everything goes through the IR

Every input format produces an `AlgoSpec`; every output consumes one. Readers
never talk to writers directly. Adding a format means writing one reader or
one writer, never N×M converters. The IR stores wire-level values as strings
so nothing is lost in transit.

## D7 · 2026-11-01 · Third-party schemas stay out of the repo until licensed

The FIXatdl 1.1 XSDs are © FIX Protocol Limited with use "subject to the
disclaimer" in the written specification, which has not been reviewed. Tests
that need them are opt-in via `CONCORD_FIXATDL_XSD_DIR`. FIX Orchestra
artifacts are Apache 2.0 and may be vendored with attribution.

## D8 · 2026-11-01 · No copyleft dependencies

Concord is proprietary software. GPL, AGPL and LGPL packages are excluded.
Notably PyMuPDF (AGPL) — use `pypdf` or `pdfplumber`.

## D9 · 2026-11-02 · Diff classification rules

Matching: strategies by `name`; parameters by `name`, with a removed+added pair
sharing a `fix_tag` treated as a cosmetic rename. Bounds (min/max value,
length, precision) compare numerically; a new bound is breaking, a removed
bound additive. A changed `default_value` is *additive* (the wire contract is
unchanged; the client may still send its own value). A new or changed rule
(StrategyEdit) is breaking; a removed one additive. Unlisted applicability is
unrestricted unless the spec lists included items of that kind. Any of these
may be proposed for change under *Needs owner* if they read wrong in practice.

**D9 addendum · 2026-11-06 · Strategy rename by wire value.** A removed+added
strategy pair sharing a non-empty `wire_value` is a cosmetic `strategy_renamed`;
the pair is diffed as usual and reported under the new name. Matching only
happens when exactly one removed and one added strategy carry that wire value;
otherwise they are reported as removed/added.

## D10 · 2026-11-03 · Citation verification is exact after folding

Quotes are compared case-sensitively against the cited page's text after NFKC,
typographic-character folding, whitespace collapse and line-break de-hyphenation.
No fuzzy scoring: a near-miss is a failure for human review, not a pass.
Uncheckable citations (no page/quote/source) fail rather than pass silently.

## D11 · 2026-11-04 · Extraction keeps only verified facts; SDK is an optional extra

A fact enters the extracted spec only with at least one citation that passes the
verifier (D10); failed citations are stripped, failed facts go to the review list.
The model backend is a protocol so CI uses recorded responses. The `anthropic`
SDK is an optional extra (`llm`), not a core dependency. First page's value wins
on a merge disagreement and the disagreement is reviewed.

## D12 · 2026-11-04 · PM + worker agents; runs auto-merge to `main`

*Owner decision.* Each run uses two subagents defined in `.claude/agents/`:
`product-manager` (Opus 5.5) researches and owns the roadmap in
`docs/BACKLOG.md`; `worker` (Sonnet 5.5) builds the top unblocked item. The
orchestrating session commits, pushes `dev`, and merges the `dev → main` PR
itself with a merge commit once checks are green — "for now", until the owner
revokes this. This amends D3 (the review gate is suspended) and D4 (runs, not
the owner, merge). Direct pushes to `main` and force-pushes remain forbidden.

## D13 · 2026-11-04 · Sessions start CI by hand before merging

Repo Actions are enabled and `ci.yml` passes (manual run 41898654875), but
pushes and merges made by Claude sessions never trigger it: no run exists for
any of their push or pull_request events. `ci.yml` therefore also accepts
`workflow_dispatch`, and each run triggers it on `dev` and waits for success
before merging (CLAUDE.md step 7). Pushes the owner makes trigger CI as usual.

## D14 · 2026-11-06 · PM and Worker run as two persistent sessions

*Owner request.* So both are visible and followable on mobile, the PM and the
Worker are separate long-lived sessions ("Concord PM", Opus 5.5, 05:07 CT;
"Concord Worker", Sonnet 5.5, 05:37 CT), each woken daily by its own
scheduled task, instead of subagents inside one fresh session per day. The
role definitions in `.claude/agents/` are unchanged in substance. The PM
commits and pushes its own planning changes to `dev`; only the Worker merges
(D12 unchanged). The old single "Concord daily build" task is disabled, not
deleted, so its run history is kept.

## D15 · 2026-11-07 · Public sample repos: fetched by pinned commit, opt-in tests

Public GitHub sample sets (corpus kind `fixatdl`) are read by `tests/test_public_samples.py`,
gated on `CONCORD_PUBLIC_SAMPLES=1` and skipped offline. Each repo is fetched with
`git init` + `git fetch --depth 1 <url> <sha>` + `git checkout FETCH_HEAD` into the
git-ignored `corpus/cache/<id>/`, reused when HEAD already equals the pinned sha (hard rule 2:
nothing committed). Item 9b (Orchestra XSD) should use the same approach. Round-trip equality
allows two documented writer normalisations: an `enumID` that is not a legal XML identifier
is regenerated, and an unlabeled enum value is written with its wire value as `uiRep`.

## D16 · 2026-11-11 · Wire-contract attributes on `<Strategies>` are in the IR

`tag957Support`, `changeStrategyOnCxlRpl` and `draftFlagIdentifierTag` are `AlgoSpec` fields
(`tag957_support`, `change_strategy_on_cxl_rpl`, `draft_flag_identifier_tag`, all optional,
no IR_VERSION bump). They are written only when set, so output stays byte-stable.
`imageLocation` is UI-only and is dropped on purpose. A parameter with no `fixTag` can only
travel in the 957 group, so the FIXatdl reader raises `FixatdlError` naming
`Strategy/Parameter` unless `tag957Support="true"`; none of the 29 public samples breaks this.
Diff (D9 style): losing `tag957_support` or `change_strategy_on_cxl_rpl` (true to not-true) is
breaking and gaining it is additive; unset and false are the same; a changed or removed
`draft_flag_identifier_tag` is breaking and a new one is additive. `parameter_transport(param)`
returns `tag` or `957-group` for the Orchestra writer. `848-pairs` has no FIXatdl form and
waits for PDF extraction.

## D17 · 2026-11-12 · Orchestra writer targets 1.0 (2020 namespace); fields and code sets first

`concord.orchestra.write_orchestra(spec)` writes Orchestra **1.0** (namespace
`http://fixprotocol.io/2020/orchestra/repository`, repo tag `v1.6`, commit `68ce876`), the
published standard that tools read. 1.1 is still a release candidate; the namespace is one
constant (`NS_REPOSITORY`) so moving is a one-line change. Revisit when 1.1 is final.
Rules: one field per distinct `fix_tag`; a tag defined differently by two strategies (name,
type or enum values) raises `OrchestraError` naming both, never a guess (item 20 may relax
this); field names are made legal (`[A-Za-z][A-Za-z0-9_]*`) and must stay unique; one code set
per enum parameter (`<Field>CodeSet`, id = tag) and one for the strategy identifier; code id =
tag * 1000 + position; tags under 5000 carry an annotation saying they are standard FIX fields;
no timestamps. The schema requires a repository `version` matching `major.minor`, so it is
`1.0`. The schema also requires at least one message, so 9a emits a `NewOrderSingle` whose
structure holds only the strategy identifier; item 9b fills it in. Parameters with no tag
(957 group) are not fields and are returned in `OrchestraResult.group_parameters`.
Schema validation is opt-in with `CONCORD_ORCHESTRA_XSD_DIR` (the D15 method: fetch the pinned
commit into git-ignored `corpus/cache`, point the variable at `repository/src/main/resources/xsd`).
The XSD imports `xml.xsd` from w3.org, so the test fixture redirects that one import to the
local copy. The XSDs stay out of the repo (Apache-2.0 would allow vendoring with a NOTICE).

## D18 · 2026-11-13 · Orchestra messages: one NewOrderSingle per strategy, as a scenario

Each strategy is written as `NewOrderSingle` (`msgType="D"`, id 14) with `scenario` set to the
strategy name made legal (`sanitize_name`; two strategies that collapse to one name raise
`OrchestraError`). Orchestra 1.0 (v1.6) has no `fixr:scenarios` element: the `scenario`
attribute alone declares it, and keys are unique on name + scenario. The strategy identifier is a
`fieldRef` with `presence="constant"` and `value` = wire value. Each tagged parameter is a
`fieldRef`: `required` when `required`, `constant` plus `value` for `const_value`, and
`minInclusive` / `maxInclusive` from the IR bounds (otherwise the default, optional).
957-group parameters go in one `group` (id 957, `StrategyParametersGrp`) with `numInGroup` 957
and fieldRefs 958 / 959 / 960; 958 has a code set of every parameter name used by any strategy;
a strategy gets a `groupRef` only when it has such parameters. A spec with no strategies gets one
base message holding the identifier, because the schema needs a message. `concord convert FILE
--to orchestra` writes the XML to stdout; `OrchestraError` exits 1. Supersedes the "minimal
message" note in D17. StrategyEdits as rules are item 9c.

## D19 · 2026-11-14 · StrategyEdits in Orchestra: presence rules only; the rest is annotation

A FIXatdl `StrategyEdit` is the condition under which an order is valid. Orchestra 1.0 field rules
only say when a field is required or forbidden, so `concord.score` maps two patterns and nothing
else: `F NX OR C` becomes a rule on F with `presence="forbidden"` and `when` = `!(C)`; `F EX OR C`
becomes `presence="required"` with the same `when`. The pattern must not have C read F itself (that
is a value check) and F must be a tagged parameter of the strategy, else it stays an annotation.
Every other edit is kept as a `documentation` note on the strategy's NewOrderSingle ("Not
enforceable in Orchestra 1.0: <message> Valid when: <Score>"), is returned in
`OrchestraResult.unenforced`, and is printed to stderr by `concord convert --to orchestra`, so
nothing is dropped silently. Score follows `Score.g4` at v1.6: `== != < <= > >= && || !`,
`exists F`, `^CodeName` for values of a field with a code set (the code name 9a assigned), quoted
strings, numbers; Score has no xor, so XOR is expanded; `FIX_X` is written as `X`. A parameter with
`mutable_on_cxl_rpl = False` gets a note on an `OrderCancelReplaceRequest` (msgType G, id 17)
scenario for that strategy: it must equal the value in the order being replaced (Orchestra 1.0 has
no "unchanged" rule).
