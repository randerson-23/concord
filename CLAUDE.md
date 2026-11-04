# Concord — operating manual

You are building Concord, a business that turns FIX rules-of-engagement
documents (starting with **broker algo specs**) into verified machine-readable
specs: FIXatdl first, FIX Orchestra next. Read `docs/business-plan.md` once for
the why. This file is the how.

The owner has 18 years of daily FIX experience and a full-time job. Their time
is the scarcest resource in this project. Spend yours, not theirs: decide
everything you reasonably can, and when you must ask, ask in a way they can
answer with one word.

## Hard rules

These are never broken, by any session, for any reason. If a task seems to
require breaking one, stop that task and record it under *Needs owner* in
`docs/STATUS.md`.

1. **Public sources only.** Every spec, FIXatdl file or other document used
   for development or testing must be publicly published by its owner, and
   must be listed in `corpus/sources.yaml` with its public URL. Never use,
   request or accept material from the owner's employer, material received
   under NDA, or anything marked confidential — even if offered. See
   `corpus/README.md`.
2. **Never commit third-party documents or schemas.** Fetched documents live in
   `corpus/cache/` (git-ignored). Third-party schemas (e.g. the FIXatdl XSDs)
   stay out of the repo until their license is confirmed in
   `docs/DECISIONS.md`. Test fixtures are synthetic and written by us.
3. **Never push directly to `main`.** Work goes to `dev` and reaches `main`
   only through the `dev → main` pull request. Until the owner revokes D12,
   each run merges that PR itself once checks are green (merge commit, never
   squash or rebase, never force-push).
4. **Green before push.** `uv run ruff check .`, `uv run ruff format --check .`
   and `uv run pytest` must all pass before every push.
5. **No copyleft dependencies.** Concord is proprietary. No GPL/AGPL/LGPL
   packages — note that PyMuPDF is AGPL; use `pypdf` or `pdfplumber`. Check the
   license of every new dependency and record it in the commit message.
6. **No secrets in the repo.** API keys come from environment variables.
7. **Decisions are the owner's.** Do not reverse anything in
   `docs/DECISIONS.md`. Propose a change under *Needs owner* instead.

## Daily run procedure

Automated sessions fire on weekday mornings. Each one follows these steps.

### 1. Sync

```sh
git fetch origin
git checkout dev 2>/dev/null || git checkout -b dev origin/main
git merge --no-edit origin/main          # pick up anything the owner merged
uv sync
```

If `origin/dev` exists and is ahead of your local `dev`, pull it first.

### 2. Orient

Read `docs/STATUS.md`, `docs/BACKLOG.md` and `docs/DECISIONS.md`. Check
whether the owner left answers under *Needs owner* in STATUS — act on them
first and move them to the decision log if they are decisions.

### 3. Plan — `product-manager` agent (Opus 5.5)

Spawn the `product-manager` subagent (`.claude/agents/product-manager.md`).
It researches (competitors, public corpus, customer signal) and rewrites
`docs/BACKLOG.md` so the top `todo` item is the most valuable thing to finish
today. Skip this step only if the PM already ran today.

The review gate (hold mode after 5 unreviewed runs) is suspended while D12
auto-merge is in force, because nothing waits for review.

### 4. Build — `worker` agent (Sonnet 5.5)

Spawn the `worker` subagent (`.claude/agents/worker.md`) to take the highest
unblocked `todo` item. It splits items that are too big and finishes what it
starts: a run that leaves the build red, or a half-built feature with no
tests, is worse than a run that did less. Check its work (diff and checks)
before committing — the orchestrating session owns the commit.

### 5. Verify

Run the full check (rule 4). If schema tests matter for your change, fetch the
FIXatdl XSDs into a scratch directory and run with `CONCORD_FIXATDL_XSD_DIR`
set — see `tests/conftest.py`.

### 6. Record

- `docs/BACKLOG.md`: mark the item `done` with the date; add follow-ups you
  discovered, in priority order.
- `docs/STATUS.md`: replace *Last run* with today's summary; update *Needs
  owner* (each entry: the question, your recommended answer, what it blocks).
- `docs/DECISIONS.md`: add an entry for any technical decision a future session
  would otherwise re-litigate.

### 7. Commit and push

Make your final commit's subject start with `run: ` and the date, e.g.
`run: 2026-11-03 add spec diff engine`. Push `dev`. Make sure exactly one open
pull request from `dev` into `main` exists — create it if not — and write its
description as a summary of the run(s) it carries. Then, per D12, merge it
with a **merge commit** once local checks and CI are green. If CI is red, do
not merge: fix it on `dev` or record it under *Needs owner*.

Pushes and merges made by these sessions do **not** trigger GitHub Actions
(D13). Start CI yourself: trigger `ci.yml` with `workflow_dispatch` on ref
`dev` (GitHub MCP `actions_run_trigger`, method `run_workflow`), wait for that
run to complete on your pushed `dev` HEAD, and merge only if it succeeded.
Pass the PR's head SHA as the expected SHA when merging, and confirm it
equals your local `dev` HEAD first.

If GitHub API tools are not available in your session, `git push` still
works, and an existing PR picks up the new commits on its own. Skip the PR
step, and if no PR exists yet, add *"Open a PR from `dev` into `main`"* under
*Needs owner* in STATUS. The pushed commits are what matter; the PR
description is a convenience.

### 8. Report

End with three lines at most: what you did, whether checks passed, and
whether anything now needs the owner. This becomes the push notification.

## Architecture

```
  inputs                      IR                        outputs
  ──────                      ──                        ───────
  FIXatdl ──── read ──┐                          ┌── write ──── FIXatdl
  PDF spec ── extract ┼──►  AlgoSpec (ir.py)  ───┼── write ──── Orchestra   (planned)
  Orchestra ── read ──┘    + citations           ├── render ─── spec site   (planned)
                                                 └── diff ───── change report (planned)
```

Everything goes through the IR in `src/concord/ir.py`. Readers never talk to
writers directly.

## Conventions

- Python 3.11, managed with `uv`. Lint and format with `ruff`. Test with
  `pytest`. Type hints throughout.
- IR changes: add fields freely; renaming or removing a field, or changing its
  meaning, bumps `IR_VERSION` and needs a DECISIONS entry.
- Readers ingest untrusted documents: no XML entity resolution, no network
  access during parsing, bounded recursion.
- Writers are deterministic. Same IR in, same bytes out — diffs depend on it.
- Errors name the location (`Strategy[@name='X']/Parameter[@name='Y']`) and
  say what was expected.
- Every extracted fact should carry a `Citation`. Extraction without a citation
  is a guess, and Concord does not ship guesses.
- Tests sit beside the behaviour they pin. Prefer one fixture exercised many
  ways over many fixtures.
