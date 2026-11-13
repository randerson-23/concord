# Status

**Phase:** A — building the engine · **Wedge:** broker algo specs → FIXatdl
**Build:** green (see CI; schema-validated against FIXatdl 1.1)
**Repo:** <https://github.com/randerson-23/concord>

## Last run

**2026-11-13 (daily firing) — Orchestra messages and CLI.** Worker finished the Orchestra writer's
message side (D18): one `NewOrderSingle` per strategy as a scenario, constants, required, bounds,
the 957 group with a code set of parameter names, and `concord convert FILE --to orchestra`.
Both example outputs validate against the real v1.6 XSD locally. No new dependency. Before that:
Orchestra fields and code sets (9a), wire-contract attributes (10), amendability (8).

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
6. **FIXatdl XSD license.** The official XSDs say use is "subject to the
   disclaimer" in the written spec. *Recommended:* keep them out of the repo
   (current approach — tests fetch them on demand) until you or a lawyer has
   read that disclaimer. *Blocks:* nothing today.
