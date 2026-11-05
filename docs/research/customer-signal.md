# Customer signal

What OMS/EMS teams, buy-side desks and brokers say about algo onboarding.
Each note carries its source. Most public commentary is old: no 2025–26 trade
press on multi-month algo onboarding turned up (search on 2026-11-05).

## 2026-11-05

- **Turnaround is slow and varies.** A buy-side contributor reports broker
  turnaround "from a few weeks to over a year, depending on the broker, algo type
  and level of customization", and says their system never takes a broker's
  FIXatdl "as-is".
  <https://www.globaltrading.net/getting-the-right-fit-buy-side-sell-side-and-vendor-on-non-standard-atdl-implementation/2>
  *Product:* the diff and review step matter more than a one-shot conversion.
- **Tooling has not kept up with the standard.** One article says the focus on
  evolving the standard has not been matched by "sufficient coding tools to
  facilitate adoption".
  <https://globaltrading.net/?p=3077>
- **Brokers resist, and the working group shifted to OMS-side consumption.** Forum
  posts say FIXatdl production "has to be broker led" and "there is little appetite".
  The working group moved its emphasis to OMSs that consume many brokers' files.
  <https://forum.fixtrading.org/t/broker-dealers-actively-supporting-fixatdl/1477>
  *Product:* this supports selling to the consumer side first (Team tier), because
  brokers will not produce the files themselves.
- **Brokers keep their parameters private.** That is why the generic
  StrategyParameters group exists.
  <https://forum.fixtrading.org/t/strategyparameters-repeating-group-documentation/13921>
  *Product:* the public corpus will be thinner than hoped. Track how many public
  specs actually carry wire tags.
- **Custom tags break cancel/replace.** OMSs ignore custom algo tags in their
  cancel/replace logic, so an algo change on a VWAP order is rejected.
  <https://forum.fixtrading.org/t/changes-to-custom-tags-in-cancelreplace/1445>
  *Product:* `mutable_on_cxl_rpl` is a high-value fact to extract, show on the
  site and flag in diffs.
- **Wire encodings vary.** Brokers use 847 or a custom identifier tag (Goldman 8031,
  NYSE 20046, CQG 6401), and send parameters as flat tags, 848 tag:value pairs or the
  957–960 group.
  <https://forum.fixtrading.org/t/tag-848-or-957-repeating-groups/1524> ·
  <https://developer.gs.com/docs/services/ria-custody/fix-specs> ·
  <https://help.cqg.com/apihelp/Documents/algorithmicstrategiessupport.htm>
  *Product:* the IR's `strategy_identifier_tag` is right. A parameter-encoding field
  (flat / 848 / group) is probably needed.
- **Firms pay people to do this work today.** BestEx Research and FlexTrade are
  hiring FIX onboarding analysts.
  <https://apply.workable.com/bestex-research/jobs/view/3E161F6EC4.md> ·
  <https://careers.flextrade.com/o/fix-analyst-client-onboarding-2?lang=en>
  These are good first conversations for the Team tier.
