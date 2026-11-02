# Status

**Phase:** A — building the engine · **Wedge:** broker algo specs → FIXatdl
**Build:** green (see CI; schema-validated against FIXatdl 1.1)
**Repo:** <https://github.com/randerson-23/concord>

## Last run

**2026-11-02 (second run) — PDF text layer.** Added `concord.pdf`: page-numbered
text, layout text, heuristic table rows, quote normalisation (pypdf, BSD-3).
5 tests on a synthetic PDF. Item 2 (public FIXatdl samples) is blocked: the
session's GitHub scope is this repo only. Pull request could not be created
(see Needs owner 1).

## Needs owner

Each item: the question, the recommended answer, what it blocks. Reply in the
PR or edit this file.

1. **Open a pull request from `dev` into `main`** once `dev` has commits.
   Check whether one exists; runs may lack the ability to create it. After the PR exists, every run's push adds to it
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
5. **Public FIXatdl samples need repo access.** Sessions are scoped to
   `randerson-23/concord`. *Recommended:* either paste raw URLs + licenses of the
   atdl4j / fixportal sample files into `corpus/sources.yaml` yourself, or allow
   read access to those public repos. *Blocks:* backlog item 2.
6. **FIXatdl XSD license.** The official XSDs say use is "subject to the
   disclaimer" in the written spec. *Recommended:* keep them out of the repo
   (current approach — tests fetch them on demand) until you or a lawyer has
   read that disclaimer. *Blocks:* nothing today.
