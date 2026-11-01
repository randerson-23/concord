# Concord

Machine-readable rules of engagement for FIX.

Brokers publish their algo specifications as long PDFs. Every OMS and EMS that
connects reads them by hand and re-keys every parameter. Concord turns those
specifications into verified, machine-readable form — FIXatdl today, FIX
Orchestra next — with every extracted rule citing the page it came from.

> **Status:** early development. Not yet a product. See
> [docs/STATUS.md](docs/STATUS.md) for where things stand and
> [docs/business-plan.md](docs/business-plan.md) for why.

## What works today

- A format-neutral **intermediate representation** (IR) for algo specs —
  strategies, parameters, enums, defaults, validation rules, applicability and
  source citations. [`src/concord/ir.py`](src/concord/ir.py)
- A **FIXatdl 1.1 reader** that handles real-world namespace sloppiness, pulls
  enum labels and defaults out of the layout section, resolves `EditRef`s, and
  refuses external entities. [`src/concord/fixatdl/read.py`](src/concord/fixatdl/read.py)
- A **FIXatdl 1.1 writer** that emits schema-valid output with a generated
  layout. [`src/concord/fixatdl/write.py`](src/concord/fixatdl/write.py)

## Quick start

```sh
uv sync
uv run concord inspect tests/fixtures/fixatdl/example_broker.xml
uv run concord convert tests/fixtures/fixatdl/example_broker.xml --to json
uv run pytest
```

Schema-validation tests run only when the official FIXatdl 1.1 XSDs are
available locally (they are not committed until their license is confirmed):

```sh
CONCORD_FIXATDL_XSD_DIR=/path/to/xsds uv run pytest
```

## Layout

| Path | What |
|---|---|
| `src/concord/ir.py` | The IR: the contract every input and output shares |
| `src/concord/fixatdl/` | FIXatdl 1.1 reader, writer, schema facts |
| `corpus/` | Manifest of **public** specs used for testing — see its README |
| `docs/` | Status, backlog, decisions, business plan |
| `CLAUDE.md` | Operating manual for automated development sessions |
