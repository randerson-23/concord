# Concord — Business Plan

**Machine-readable rules of engagement for FIX.**
Original analysis 2026-11-01 · revised the same day after owner decisions.
Reviewable page: <https://claude.ai/code/artifact/6ffeb4f2-257b-4ff1-abd7-c758eea2b3b0>

---

## Revisions — 2026-11-01

The plan below is the original analysis. Four owner decisions since then change
how it plays out. Where they conflict with the text below, these win.

**1. The wedge narrows to broker algo specs.** The original plan targeted
rules-of-engagement documents in general. The sharper opening is the algo
subset: every broker publishes a long algo spec, every OMS/EMS maps its
parameters by hand, and FIXatdl already exists as the machine-readable target.
Narrower, more acute, and two-sided — brokers want their algos exposed
correctly in every OMS; OMS vendors need every broker's parameters. The
pipeline is still built generically so it widens to full RoE and Orchestra
(DECISIONS D1, D6).

**2. Validation compresses and runs in parallel.** The plan assumed 25+
interviews to learn whether the pain is real. With 18 years of daily FIX work
and a shipped FIX analyzer, the pain is known first-hand. What is *not* known
is willingness to pay — especially for the publisher tier. Validation shrinks
to 10–15 targeted conversations about budget and buyer, run alongside the build
rather than before it.

**3. Public sources only.** No employer material, nothing under NDA. Every
development and test document is publicly published and catalogued in
`corpus/sources.yaml` (DECISIONS D2).

**4. The build runs daily, unattended.** Automated sessions advance the backlog
every weekday morning; the founder reviews in batches. The review gate in
CLAUDE.md stops output outrunning review (DECISIONS D3).

### New top risk: employment and IP

The founder is employed full-time in FIX and recently built a FIX analyzer for
their employer. Employment agreements commonly assign IP for work "related to
the employer's business" and restrict outside businesses. This now outranks
every risk in section 11, because it can end the business before it starts.

**Mitigation:** read the agreement this month; get a lawyer's read if anything
is ambiguous; keep Concord strictly on personal time, personal equipment and
public material; reuse nothing from the employer's analyzer.

---

## 1. Executive summary

Every firm that trades electronically publishes a "Rules of Engagement" (RoE)
document: a PDF that says which FIX messages it accepts, which tags are
mandatory, which enum values it supports, and how it deviates from the base
standard. There are thousands. Almost all are unstructured prose. Every
counterparty that connects reads one by hand, translates it into engine config,
code and test cases, then spends days or weeks in certification discovering the
parts the PDF got wrong.

The FIX Trading Community already defined the fix — **FIX Orchestra**, a
machine-readable format for rules of engagement — and released the underlying
FIX Repository under Apache 2.0. What's missing is the expensive middle step:
converting existing PDF specs into that format accurately, keeping them
current, and making them useful. That conversion is a document-understanding
problem, the task LLMs recently got good at, in a niche where nobody has
industrialized it.

**Concord** is a spec-intelligence platform for FIX connectivity:

1. **Convert** an RoE or algo spec into a verified machine-readable spec, with
   every extracted rule citing its source page.
2. **Diff** two specs — versions, or yours against a counterparty's — and show
   exactly what breaks.
3. **Generate** downstream artifacts: engine dictionaries, typed client code,
   validation rules, certification tests, and a hosted browsable spec portal.

Sold three ways: a free developer tier for reach, a team tier for firms that
*consume* specs, and a publisher subscription for venues and brokers that
*publish* them.

It suits a solo founder with AI because it is parsers, schemas, code generation
and a documentation site — the work AI assistance multiplies best — and because
it touches specification documents, never live order flow: no production
access, no market-data licensing, no security-review gauntlet before the first
sale.

## 2. Landscape

**Reference and specification.** FIXimate (official, base standard only);
orchimate.org (community alternative — proves appetite for better reference
UX); the FIX Repository (machine-readable XML); FIX Orchestra (Apache 2.0,
actively maintained); Esprow's free tools (lead-gen); fix2dict and fixations
(hobby-scale, no commercial layer).

**Testing, certification, log analysis.** Esprow ETP (enterprise testing and
certification); B2BITS/EPAM FIXEye (log analysis, enterprise licensing); OnixS
FIX Analyser and engines (subscriptions in the tens of thousands per year);
FIXSIM (cloud simulator — the key comparable); ValidFIX and aprics (free
parsers); Fixnox (onboarding as a service).

**Engines.** QuickFIX in C++, Java, .NET and Go — liberal licenses, production
use at major institutions. Solved and commoditized. **Do not build an engine.**

**The pricing anchor.** FIXSIM sells month-to-month: Starter $500/mo
(individual developers), Pro $1,500+/mo (QA teams, OMS/EMS vendors), Enterprise
custom. A small vendor can sell FIX developer tooling at four-figure monthly
prices with no enterprise sales team.

## 3. The gap

1. **Onboarding takes weeks, and everyone says so.** The most-complained-about
   workflow in FIX; Fixnox sells services against exactly this.
2. **The RoE corpus is unstructured and enormous.** Virtu, Pictet, Match-Trader
   and thousands more publish PDFs describing their extensions. Nobody has
   normalized them.
3. **The standards body built the target format and gave it away.** Orchestra
   is Apache 2.0, and the community is modernizing around it (Orchestra DSL,
   protobuf translators, SBE utilities, `PlayList`, `fix-log-to-orchestra`).
4. **Orchestra tooling is thin.** `fix-log-to-orchestra` has two stars and no
   release. No hosted, supported, commercial layer exists.
5. **AI made the hard part tractable.** Converting a 180-page prose spec to
   structured form was a specialist human-week. That economics just inverted.

## 4. Ideas considered

Scored 1–5: pain, willingness to pay, AI leverage, low friction, moat, solo
feasibility.

| Idea | Total |
|---|---|
| **A · Spec intelligence (RoE → machine-readable → code, tests, docs)** | **25** |
| F · Productized FIX consultancy | 21 |
| E · Developer DX layer (browser, MCP server, libraries) | 20 |
| C · Hosted certification and simulator | 19 |
| B · AI log-triage copilot | 18 |
| D · Crypto FIX gateway kit | 16 |

B has the sharpest pain but needs customers' production logs — a security
review that outlasts a solo founder's runway. C is where FIXSIM and Esprow
already are. D means running production connectivity. E is the best funnel and
worst business. F is the surest revenue and doesn't scale.

## 5. The recommendation

**Build A. Give away E for reach. Sell F for cash and corpus.** The moat is the
corpus: every converted-and-verified spec improves the next conversion and
grows a library a competitor cannot prompt into existence.

## 6. Product

- **Convert** — ingest PDF/Word/Excel or existing dictionaries; emit verified
  machine-readable specs; every rule cites page and quote; uncertain output
  goes to review, never silently into the file; replay sample logs to find
  what the spec fails to explain. *Accuracy is the product.*
- **Diff** — compare versions or counterparties; classify breaking / additive /
  cosmetic; watch published specs and alert on change.
- **Generate** — engine dictionaries, typed clients, validation rules,
  certification tests, hosted portal.
- **Free tier** — better spec browser, parser, MCP server, open libraries.

## 7. Business model

| Tier | Price | Buyer |
|---|---|---|
| Free | $0 | Any developer |
| Pro | $149/user/mo | Consultants, individual engineers |
| Team | $1,200–2,500/mo | Buy-side, vendors, OMS/EMS |
| **Publisher** | $18k–50k/yr | Venues, brokers, LPs, crypto exchanges |
| Services | $8k–40k/engagement | Anyone with a spec backlog |

Publisher is the tier that matters: it sells to a firm whose onboarding
backlog costs it revenue, priced against the sales-engineering headcount it
displaces, from a different budget line than developer tools.

## 8. Go to market

Publish, then converse, then sell. Free tools and a public spec library for
durable search traffic; presence in FIX Trading Community working groups and
the Orchestra repos; first publishers where cycles are short (crypto venues,
FX LPs, prime-of-prime, MTFs); every services engagement ends with a hosted
portal upsell. No ads, no expensive conferences in year one, no tier-1 banks
before SOC 2.

## 9. Financial model

Estimates, not forecasts.

**Year 1 — ~$134k revenue, ~$130k exit ARR.** Services ~$72k, Pro ~$28k, Team
~$24k, Publisher ~$10k recognized. Costs ~$35k. *Revised:* with the founder
employed full-time, services revenue in year 1 depends on available hours and
on the employment agreement permitting outside paid work — treat it as
uncertain until risk item 1 is resolved.

**Year 2 — ~$850k recognized, ~$1.0M exit ARR.** Publisher ~$300k, Team ~$420k,
Pro ~$215k, Services ~$80k. Costs ~$275k.

**Sensitivity:** publisher count carries the model. Three instead of ten turns
$1.0M into ~$600k. **Variable cost:** $8–25 of inference per spec conversion.

## 10. Roadmap

*Revised for the algo-first wedge and compressed validation.*

1. **Engine (now – month 3).** IR, FIXatdl reader/writer, diff, PDF text layer,
   citation verifier, LLM extraction, static spec site. Runs daily, unattended.
   10–15 buyer conversations in parallel, focused on willingness to pay.
2. **Corpus (months 2–5).** Convert 30–50 public broker algo specs; publish the
   library free. Proof, marketing asset and accuracy corpus at once.
3. **Diff and generate (months 4–8).** Change-watch, engine dictionaries, typed
   clients. Launch Pro and Team.
4. **Publisher (months 8–14).** Hosted branded portal, onboarding packs. First
   two publisher deals. *Gate:* two signed by month 14, or Team becomes the
   primary business.
5. **Certification and Orchestra (months 14–24).** Test generation from verified
   specs; widen from algo specs to full rules of engagement via Orchestra.

## 11. Risks

| Risk | Severity |
|---|---|
| **Employment / IP claim** (see Revisions) | **Critical** |
| Conversion accuracy fails in production | Critical |
| FIX Trading Community ships a free equivalent | High |
| Nobody pays for the publisher tier | High |
| Incumbents add the feature | Medium |
| Market too small | Medium |
| Spec and schema licensing | Medium |
| Solo-founder concentration | Medium |

## Sources

FIX Orchestra (github.com/FIXTradingCommunity/fix-orchestra) · FIX Repository
(fixtrading.org/standards/fix-repository) · FIXimate user guide · FIXSIM and
FIXSIM pricing (fixsim.com) · Esprow FIX testing and tools · B2BITS log
analyzers and licensing · OnixS FIX Analyser and licensing · Fixnox onboarding ·
QuickFIX and QuickFIX/J · 2025 FINRA Industry Snapshot · Traders Magazine on AI
in FIX connectivity · Global Trading on FIX Orchestra · public RoE examples from
Virtu, Pictet and Match-Trader. Full links in the published plan.
