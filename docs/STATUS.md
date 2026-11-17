# Status

**Phase:** A — building the engine · **Wedge:** broker algo specs → FIXatdl
**Build:** green (see CI; schema-validated against FIXatdl 1.1)
**Repo:** <https://github.com/randerson-23/concord>

## Last run

**2026-11-17 (daily firing) — corpus fetch and plan.** Worker added `concord corpus fetch` and
`concord corpus plan` (D22). `fetch` takes only `use: ok` PDF and HTML sources, checks each response
(a bot-challenge page or non-PDF is `blocked`, never retried) and records a sha256. Real run: all 14
eligible sources are cached (7 PDF, 7 HTML, 311 PDF pages) and `plan` estimates about 285,000 input
tokens for them (characters / 4); cost needs `--price-per-mtok`. New dependency: PyYAML 6.0.3 (MIT).
Before that: `concord lint` (24), identity by name (20), Orchestra rules (9c).

## Needs owner

Each item: the question, the recommended answer, what it blocks. Reply in the
PR or edit this file.

2. **Check your employment agreement before Concord goes public.** Look for
   an IP-assignment clause (especially one covering work "related to the
   business" or done "using company knowledge"), a moonlighting or
   outside-business clause, and non-compete terms. *Recommended:* read it this
   month; if anything is ambiguous, an hour with an employment lawyer is cheap
   insurance. *Blocks:* public launch, first customer conversations.
4. ~~Add `ANTHROPIC_API_KEY`.~~ *Resolved 2026-11-17:* the owner said **Go** and added it as an
   environment variable on Default (confirmed by name; sessions never see the value). The first live
   run is backlog item 26, capped at 150k input tokens.
6. **FIXatdl XSD license.** The official XSDs say use is "subject to the
   disclaimer" in the written spec. *Recommended:* keep them out of the repo
   (current approach — tests fetch them on demand) until you or a lawyer has
   read that disclaimer. *Blocks:* nothing today.
7. **FIX dictionary files license (new 2026-11-16).** `FIXTradingCommunity/orchestrations` is
   Apache-2.0, but `OrchestraFIXLatest.xml` itself says "Copyright (c) FIX Protocol Ltd. All Rights
   Reserved." *Recommended:* **Fetch**, meaning we keep fetching it on demand and never commit or
   ship it until a hosted product needs it, and decide then. *Blocks:* nothing today (backlog item 24
   fetches on demand).
