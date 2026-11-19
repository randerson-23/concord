# Status

**Phase:** A — building the engine · **Wedge:** broker algo specs → FIXatdl
**Build:** green (see CI; schema-validated against FIXatdl 1.1)
**Repo:** <https://github.com/randerson-23/concord>

## Last run

**2026-11-19 (daily firing) — HTML text layer (backlog 25b, D24).** Worker built
`concord.html.read_html`: HTML specs become one page per `h1`/`h2` section with the heading as
locator, tables kept as layout text, stdlib only. `concord verify` and `concord extract` accept
`.html` files. The cached Saxo page reads as 22 sections and 20 tables, and tag 847 is found in a
table. Item 26b is still blocked: `ANTHROPIC_API_KEY` is not set in this session (Needs owner 8).
No new dependency.

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
8. **`ANTHROPIC_API_KEY` is not visible in the Worker session (2026-11-18).** The Default
   environment variable reaches a session only when it starts or resumes, and this long-lived Worker
   session predates it, so the first live extraction (backlog 26b) cannot run. *Recommended
   one-word answer:* **Restart**: resume or restart the "Concord Worker" session (a fresh container
   picks the variable up), and the next firing runs 26b. Nothing else is blocked. If you would
   rather not restart, say **Skip** and the Worker moves on to items 25b and 25c.
   *PM 2026-11-19:* the scheduled wake-up does not count as a resume. The PM session also woke
   today without the variable, so only a **fresh session** (a new container) gets it. Options:
   (a) in the Claude app, start a new "Concord Worker" session and point the Worker scheduled task
   at it (D14 stays intact); or (b) let the PM do the one live run from a fresh one-off session
   it creates, with your OK. *Recommended:* **(a)**. The Worker works on 25b (HTML text layer) and 25c
   until then, so nothing is idle.
6. **FIXatdl XSD license.** The official XSDs say use is "subject to the
   disclaimer" in the written spec. *Recommended:* keep them out of the repo
   (current approach — tests fetch them on demand) until you or a lawyer has
   read that disclaimer. *Blocks:* nothing today.
7. **FIX dictionary files license (new 2026-11-16).** `FIXTradingCommunity/orchestrations` is
   Apache-2.0, but `OrchestraFIXLatest.xml` itself says "Copyright (c) FIX Protocol Ltd. All Rights
   Reserved." *Recommended:* **Fetch**, meaning we keep fetching it on demand and never commit or
   ship it until a hosted product needs it, and decide then. *Blocks:* nothing today (backlog item 24
   fetches on demand).
