# Competitive watch

Updated monthly by the PM agent. Question each time: has anyone shipped
PDF → FIXatdl or PDF → Orchestra conversion, or a hosted algo-spec portal?

## 2026-11-05

**No one is shipping PDF-to-FIXatdl or PDF-to-Orchestra conversion that we can find.**
Web searches for AI or PDF-based FIXatdl/Orchestra generation came back empty.
Here is what does exist:

- **Hand authoring of FIXatdl.** Rapid Addition's Algo Editor is a WYSIWYG tool for
  broker-dealers to publish algo parameters as FIXatdl. It takes no PDF input and has
  no AI. <https://www.finextra.com/pressarticle/25621/rapid-addition-upgrades-algorithm-editor>
  Rapid Addition also once announced a FIXatdl portal, and Ullink built a FIXatdl
  publishing system. These are old announcements and the closest precedent for our
  portal idea. <https://www.waterstechnology.com/node/1636456> ·
  <https://waterstechnology.com/node/1636414>
- **FIXatdl consumers.** FIXSIM's Algo Tickets feature (guide updated 2026-08-13) turns
  an uploaded broker FIXatdl file into a live ticket. It reads FIXatdl and does not
  produce it, so it is a channel or partner for us rather than a competitor.
  <https://www.fixsim.com/userguide/algotickets>
  Trading Technologies asks algo providers for a hand-written definition file.
  <https://library.tradingtechnologies.com/tt-core-sdk/cs-creating-an-algo-definition.html>
- **Orchestra Server** (FIX Trading Community, a member benefit, built on Esprow ETP
  S-Box, launched February 2023). It is a browser editor that imports QuickFIX
  dictionaries and exports Orchestra XML plus a PDF RoE. It is the reverse direction
  (structured → PDF), it takes no PDF input and it has no AI. The risk to watch is
  "FIX Trading Community ships a free equivalent". We found no 2025–26 update.
  <https://archive.fixtrading.org/?p=101574> ·
  <https://cdnws.fixtrading.org/wp-content/uploads/2024/11/France-Conference-2024-RoE-with-Orchestra.pdf>
- **Community Orchestra tooling.** Log2Orchestra (logs → Orchestra) and Playlist
  (subset/export) are still the only converters. The 2025 Nordic deck promotes RoE
  with Orchestra using FIXimate and Playlist v1.2.
  <https://cdnws.fixtrading.org/wp-content/uploads/2025/06/Nordic-2025-RoE-with-Orchestra.pdf>
- **Standards activity to track.** There is a public-comment draft of *FIX Recommended
  Practices: Onboarding with FIX Orchestra*. Our Orchestra writer should follow it.
  <https://forum.fixtrading.org/t/public-comment-period-fix-recommended-practices-onboarding-with-fix-orchestra/17170>

**Implication:** the conversion gap is still open. The nearest threat is a
member-only, manual tool aimed at publishers. Our free public spec browser
(backlog item 6) has no direct equivalent.

## 2026-11-07 (interim note)

- **FixPortal FIXatdl library (.NET, MIT) is actively developed again.** Its last
  commit was 2026-11-03, and it has conformance and "RealWorld" fixtures plus AI
  review tooling. It parses and renders FIXatdl. It does not turn PDFs into
  FIXatdl, so it consumes our output and is a possible partner. Watch it for
  any authoring or conversion features.
  <https://github.com/FixPortal/fixportal-fixatdl>
