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
