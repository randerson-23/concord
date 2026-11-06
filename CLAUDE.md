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

Two long-lived sessions do the work, each woken by its own scheduled task and
each visible as its own session in the Claude app (D14):

| Session | Model | Fires (US Central) | Role |
|---|---|---|---|
| **Concord PM** | Opus 5.5 | daily 05:07 | Research and roadmap — `.claude/agents/product-manager.md` |
| **Concord Worker** | Sonnet 5.5 | daily 05:37 | Build, verify, ship — `.claude/agents/worker.md` |

The PM runs first, so the Worker builds from a fresh plan. The two never edit
the same files on the same morning: the PM owns `docs/BACKLOG.md` ordering,
`docs/research/` and `corpus/sources.yaml`; the Worker owns code, tests and
the `done` markings. Both may add to *Needs owner* in `docs/STATUS.md`.

These sessions persist between firings, but their containers may be rebuilt
at any time. Never rely on local state surviving: push everything before a
firing ends, and re-sync at the start of every firing.

### Every firing, both sessions

1. **Sync.**

   ```sh
   git fetch origin
   git checkout -B dev origin/dev 2>/dev/null || git checkout -B dev origin/main
   git merge --no-edit origin/main          # pick up anything merged since
   uv sync
   ```

2. **Orient.** Read `docs/STATUS.md`, `docs/BACKLOG.md` and
   `docs/DECISIONS.md`. If the owner left answers under *Needs owner*, act on
   them first and move decisions to the decision log.
3. **Do your role** — below.
4. **Push.** Commit with a subject starting `pm: ` or `run: ` plus the date,
   e.g. `run: 2026-11-07 add Orchestra writer`. Run the full check (rule 4),
   then push `dev`. If the push is rejected as non-fast-forward (the other
   session pushed meanwhile), `git pull --rebase origin dev`, re-run the
   checks, and push again. Never force-push.
5. **Report.** End with three lines at most: what you did, whether checks
   passed, and whether anything now needs the owner. If something needs the
   owner, say so in the first line — it becomes the push notification.

### Concord PM

Follow `.claude/agents/product-manager.md`: research, then rewrite
`docs/BACKLOG.md` so the top `todo` item is the single most valuable thing the
Worker can finish in one firing. You write no product code. Commit and push
your changes to `dev` (step 4); you do not merge — the Worker does.

### Concord Worker

Follow `.claude/agents/worker.md`: take the highest unblocked `todo` item and
finish it with tests. Split anything too big and do the first part. A firing
that leaves the build red, or a half-built feature with no tests, is worse
than one that did less.

Then record and ship:

- `docs/BACKLOG.md`: mark the item `done YYYY-MM-DD` with follow-ups.
- `docs/STATUS.md`: replace *Last run* with today's summary; update *Needs
  owner* (each entry: the question, your recommended answer, what it blocks).
- `docs/DECISIONS.md`: add an entry for any technical decision a future
  session would otherwise re-litigate.
- Push `dev` (step 4). Make sure exactly one open pull request from `dev` into
  `main` exists — create it if not — and describe the run(s) it carries.
- Per D12, merge it with a **merge commit** once local checks and CI are
  green. Pushes and merges made by sessions do not trigger GitHub Actions
  (D13), so trigger `ci.yml` with `workflow_dispatch` on ref `dev` (GitHub MCP
  `actions_run_trigger`, method `run_workflow`), wait for that run to finish on
  your pushed HEAD, and merge only if it succeeded. Confirm the PR's head SHA
  equals your local `dev` HEAD and pass it as the expected SHA. If CI is red,
  do not merge: fix it on `dev` or record it under *Needs owner*.

If GitHub API tools are unavailable, `git push` still works and an open PR
picks up the commits on its own. Skip the PR and CI steps, and add *"Merge
`dev` into `main`"* under *Needs owner* in STATUS.

### Verifying schema output

If schema tests matter for a change, fetch the FIXatdl XSDs into a scratch
directory and run with `CONCORD_FIXATDL_XSD_DIR` set — see `tests/conftest.py`.

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
