# Status

**Phase:** A — building the engine · **Wedge:** broker algo specs → FIXatdl
**Build:** green (see CI; schema-validated against FIXatdl 1.1)
**Repo:** <https://github.com/randerson-23/concord>

## Last run

**2026-11-05 — static spec site.** PM refreshed the backlog and research notes
(`docs/research/`), catalogued 6 more public sources (16 of 25). Worker built
`concord site SPEC OUT_DIR` (`concord.site`): escaped, deterministic static HTML
with citation links and `uncited` markers (backlog item 6). 85 tests pass.

## Needs owner

Each item: the question, the recommended answer, what it blocks. Reply in the
PR or edit this file.

2. **Check your employment agreement before Concord goes public.** Look for
   an IP-assignment clause (especially one covering work "related to the
   business" or done "using company knowledge"), a moonlighting or
   outside-business clause, and non-compete terms. *Recommended:* read it this
   month; if anything is ambiguous, an hour with an employment lawyer is cheap
   insurance. *Blocks:* public launch, first customer conversations.
3. **Widen the environment's network access** so runs can fetch public spec
   PDFs. Today it allows GitHub, package registries and search only.
   *Recommended:* add specific domains as the corpus catalogue finds them,
   rather than opening everything. *Recommended one-word answer:* **Yes**. That
   means allowlisting these publisher domains from `corpus/sources.yaml`:
   `nyse.com`, `www.nyse.com`, `www.cqg.com`, `help.cqg.com`, `www.sc.com`,
   `www.developer.saxo`, `www.home.saxo`, `developer.gs.com`, `business.bofa.com`,
   `nasdaq.com`, `www.nasdaq.com`, `cdn.cboe.com`, `library.tradingtechnologies.com`,
   `prerak-proof.github.io`, plus `archive.fixtrading.org`, `cdnws.fixtrading.org`
   and `www.globaltrading.net` for research (confirmed blocked 2026-11-05).
   *Blocks:* backlog item 13 (corpus terms review), and with it any real-spec
   extraction test.
4. **Add `ANTHROPIC_API_KEY` as an environment secret** when you're ready to
   spend on live extraction (budget roughly $10–25 per spec converted).
   *Blocks:* backlog item 5 live runs only — everything else proceeds.
5. **Public FIXatdl samples need repo access.** Sessions are scoped to
   `randerson-23/concord`. *Recommended:* either paste raw URLs + licenses of the
   atdl4j / fixportal sample files into `corpus/sources.yaml` yourself, or allow
   read access to those public repos. *Blocks:* backlog item 2.
6. **FIXatdl XSD license.** The official XSDs say use is "subject to the
   disclaimer" in the written spec. *Recommended:* keep them out of the repo
   (current approach — tests fetch them on demand) until you or a lawyer has
   read that disclaimer. *Blocks:* nothing today.
