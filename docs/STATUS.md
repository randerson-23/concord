# Status

**Phase:** A — building the engine · **Wedge:** broker algo specs → FIXatdl
**Build:** green (see CI; schema-validated against FIXatdl 1.1)
**Repo:** <https://github.com/randerson-23/concord>

## Last run

**2026-11-07 (extra run) — public FIXatdl samples.** Worker read 29 public sample
files (atdl4j + FixPortal, MIT, pinned) with the opt-in `CONCORD_PUBLIC_SAMPLES=1` test.
25 round-trip equal, 1 deliberate negative errors cleanly, 3 are strict xfails: the IR
rejects shared strategy wire values (2 atdl4j files) and a repeated fixTag (`tz-clock.xml`);
backlog item 20 decides the rule. Reader errors from IR validation now name the strategy.
Checks pass; the PR is left for the owner to merge unless told otherwise.

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
   `prerak-proof.github.io`, `docs.cdp.coinbase.com`, `quod-financial.github.io`,
   `developers.lseg.com`, `ember.deltixlab.com`, `wex-help.atlassian.net`,
   `www.commanderfx.com`, `www.integralsupport.com`, plus `archive.fixtrading.org`,
   `cdnws.fixtrading.org` and `www.globaltrading.net` for research (confirmed blocked
   2026-11-05; `ember.deltixlab.com` and `wex-help.atlassian.net` again 2026-11-06).
   *Blocks:* backlog item 13 (corpus terms review), and with it any real-spec
   extraction test.
4. **Add `ANTHROPIC_API_KEY` as an environment secret** when you're ready to
   spend on live extraction (budget roughly $10–25 per spec converted).
   *Blocks:* backlog item 5 live runs only — everything else proceeds.
5. ~~Public FIXatdl samples need repo access.~~ *Resolved 2026-11-07, no action
   needed.* Sessions can `git clone` public GitHub repos, so backlog item 2 is
   unblocked.
6. **FIXatdl XSD license.** The official XSDs say use is "subject to the
   disclaimer" in the written spec. *Recommended:* keep them out of the repo
   (current approach — tests fetch them on demand) until you or a lawyer has
   read that disclaimer. *Blocks:* nothing today.
