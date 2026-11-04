# Status

**Phase:** A — building the engine · **Wedge:** broker algo specs → FIXatdl
**Build:** green (see CI; schema-validated against FIXatdl 1.1)
**Repo:** <https://github.com/randerson-23/concord>

## Last run

**2026-11-04 (hold mode) — corpus catalogue, part 1.** Five unreviewed runs are
waiting, so only `[safe]` work. Catalogued 10 public candidates in
`corpus/sources.yaml` (NYSE Pillar algo specs, Proof, CQG, Standard Chartered,
Saxo, Goldman, etc.). Nothing fetched; publisher terms unreviewed, so entries
are marked not-yet-usable. Backlog item 8 stays open (10 of 25). Please review
and merge the batch to reopen feature work.

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
