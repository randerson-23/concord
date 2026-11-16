# Status

**Phase:** A — building the engine · **Wedge:** broker algo specs → FIXatdl
**Build:** green (see CI; schema-validated against FIXatdl 1.1)
**Repo:** <https://github.com/randerson-23/concord>

## Last run

**2026-11-15 (daily firing) — shared identity.** Worker made strategies and parameters identified by
name (D20): the IR accepts a shared strategy wire value and a shared tag in one strategy, which the
public samples use. All 28 public sample files now pass (the three xfails are gone; earlier "29"
was a miscount). Diff, Orchestra and the site handle the shared values. No new dependency. Before
that: Orchestra rules (9c), messages (9b), fields and code sets (9a).

## Needs owner

Each item: the question, the recommended answer, what it blocks. Reply in the
PR or edit this file.

2. **Check your employment agreement before Concord goes public.** Look for
   an IP-assignment clause (especially one covering work "related to the
   business" or done "using company knowledge"), a moonlighting or
   outside-business clause, and non-compete terms. *Recommended:* read it this
   month; if anything is ambiguous, an hour with an employment lawyer is cheap
   insurance. *Blocks:* public launch, first customer conversations.
4. **Add `ANTHROPIC_API_KEY` as an environment secret** when you're ready to
   spend on live extraction (budget roughly $10–25 per spec converted).
   *Blocks:* backlog item 5 live runs only — everything else proceeds.
   *How (agreed 2026-11-07, deferred by owner for now):* when the owner says **Go**,
   a session opens the secure network-secret form for `api.anthropic.com` (header
   `x-api-key`, no prefix). The key is stored on the Default environment and never
   in the repo or chat. The session also sets the non-secret placeholder
   `ANTHROPIC_API_KEY=proxy-injected`, because `extract.py` refuses to start without
   it. Make a dedicated Concord key with a monthly spend limit in the Anthropic
   Console first. Default is shared by all the owner's cloud sessions.
7. **FIX dictionary files license (new 2026-11-16).** `FIXTradingCommunity/orchestrations` is
   Apache-2.0, but `OrchestraFIXLatest.xml` itself says "Copyright (c) FIX Protocol Ltd. All Rights
   Reserved." *Recommended:* **Fetch**, meaning we keep fetching it on demand and never commit or
   ship it until a hosted product needs it, and decide then. *Blocks:* nothing today (backlog item 24
   fetches on demand).
6. **FIXatdl XSD license.** The official XSDs say use is "subject to the
   disclaimer" in the written spec. *Recommended:* keep them out of the repo
   (current approach — tests fetch them on demand) until you or a lawyer has
   read that disclaimer. *Blocks:* nothing today.
