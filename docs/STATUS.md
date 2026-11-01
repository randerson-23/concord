# Status

**Phase:** A — building the engine · **Wedge:** broker algo specs → FIXatdl
**Build:** green (39 tests, schema-validated against FIXatdl 1.1)
**Repo:** <https://github.com/randerson-23/concord>

## Last run

**2026-11-01 — bootstrap (interactive session).** Set up the project:
IR v0.1, FIXatdl 1.1 reader and writer, CLI, CI, synthetic test fixture,
operating manual, backlog, decision log, corpus policy. Writer output and the
fixture both validate against the official FIXatdl 1.1 XSDs. Pushed to `main`
and `dev`. Daily runs start 2026-11-02, weekdays 05:37 US Central.

## Needs owner

Each item: the question, the recommended answer, what it blocks. Reply in the
PR or edit this file.

1. **Open a pull request from `dev` into `main`** once `dev` has commits.
   Daily runs can push but cannot create pull requests (their sessions have no
   GitHub API tools). After the PR exists, every run's push adds to it
   automatically. *Blocks:* nothing — just makes review one click.
2. **Check your employment agreement before Concord goes public.** Look for
   an IP-assignment clause (especially one covering work "related to the
   business" or done "using company knowledge"), a moonlighting or
   outside-business clause, and non-compete terms. *Recommended:* read it this
   month; if anything is ambiguous, an hour with an employment lawyer is cheap
   insurance. *Blocks:* public launch, first customer conversations.
3. **Widen the environment's network access** so runs can fetch public spec
   PDFs. Today it allows GitHub, package registries and search only.
   *Recommended:* add specific domains as the corpus catalogue finds them,
   rather than opening everything. *Blocks:* backlog item 8 beyond cataloguing.
4. **Add `ANTHROPIC_API_KEY` as an environment secret** when you're ready to
   spend on live extraction (budget roughly $10–25 per spec converted).
   *Blocks:* backlog item 5 live runs only — everything else proceeds.
5. **FIXatdl XSD license.** The official XSDs say use is "subject to the
   disclaimer" in the written spec. *Recommended:* keep them out of the repo
   (current approach — tests fetch them on demand) until you or a lawyer has
   read that disclaimer. *Blocks:* nothing today.
