# Corpus

The specifications Concord is developed and tested against.

## The rule

**Every document here must be published openly by its owner.** If you cannot
point to a public URL where the owner makes it available, it does not belong
in Concord — not for testing, not "just locally", not temporarily.

Never use material from the owner's employer, material received under NDA, or
anything marked confidential, even if it is offered. This protects the owner
from trade-secret and IP-assignment claims, and it keeps the corpus usable as
a public library later.

## How it works

- `sources.yaml` is the manifest. Every document gets an entry *before* it is
  used: where it lives, who published it, and what terms the publisher states.
- Documents are fetched into `corpus/cache/`, which is git-ignored. The
  documents themselves are never committed — the manifest is.
- Test fixtures under `tests/fixtures/` are different: they are synthetic,
  written by us, and say so in a header comment.

## Entry format

```yaml
- id: acme-algo-guide-2026          # short, stable, kebab-case
  title: ACME Algorithmic Trading Guide
  publisher: ACME Securities
  url: https://example.com/acme-algo-guide.pdf
  kind: pdf                          # pdf | fixatdl | orchestra | html | other
  found: 2026-11-03                  # date catalogued
  terms: >-                          # what the publisher says about use, verbatim if short
    No stated terms; published openly on the firm's website.
  license: null                      # SPDX id if one applies (e.g. MIT for repo samples)
  notes: Covers VWAP, TWAP, IS. FIX 4.2. Custom tags 7600-7650.
```
