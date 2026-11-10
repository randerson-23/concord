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

## 2026-11-06

- **TargetStrategy(847) values are not portable.** Coinbase Prime uses letter codes
  (`T` = TWAP, `V` = VWAP), Saxo uses its own numbers (`1014` = TWAP) and Proof uses
  `1001`/`1002`, although FIX 4.4 defines 847 as an integer with 1000+ left to users.
  <https://docs.cdp.coinbase.com/prime/fix-api/order-entry-messages> ·
  <https://www.developer.saxo/fix/message-definitions/algo-order-fix-tags> ·
  <https://forum.fixtrading.org/t/targetstrategy-field-in-4-4/1633>
  *Product:* storing wire values as strings (D6) is right. Strategy wire value is the
  stable identity across versions, which supports diff matching by wire value (item 7).

## 2026-11-06 (second PM firing)

- **Brokers identify the strategy in at least four ways.** TargetStrategy(847) with
  integers (LSEG FXall `1001` = TWAP) or letters (Coinbase), a custom tag carrying a
  string (NYSE Pillar Gateway, up to 20 characters), the routing destination
  ExDestination(100) (WEX `WEX-VWAP`), and BrokerID(76) together with OrdType `X` (Deltix Ember).
  <https://developers.lseg.com/content/dam/devportal/api-families/fx-venues/cash-rfq-fix/refinitiv_fxall_fx_trading_fix_api.pdf> ·
  <https://www.nyse.com/publicdocs/nyse/NYSE_Pillar_Gateway_FIX_Protocol_Specification.pdf> ·
  <https://wex-help.atlassian.net/wiki/spaces/WFS/pages/7602239/WEX+Dynamic+Algorithms> ·
  <https://ember.deltixlab.com/docs/algos/vwap/>
  *Product:* `strategy_identifier_tag` (an int) with string wire values covers all four.
  Algos also often require a fixed value on a standard field (FXall: OrdType=E; Deltix:
  OrdType=X). These must be extracted as rules (StrategyEdits). If they are missed, the
  orders are rejected.
- **Participation-rate tags vary.** The tag is 849, NYSE 20049/20050, or TT 9103.
  <https://library.tradingtechnologies.com/tt-fix/tt-fix-general/fix-message-structure/component-targetstrategy-tt-premium-order-types/>
  *Product:* this is the kind of cross-broker mapping an OMS team does by hand. A
  later "same concept, different tag" view in the library would sell it.

## 2026-11-10

- **No real version pairs exist yet for testing the diff engine.** The public FIXatdl
  sample repos (atdl4j, FixPortal) have one commit per sample file, so their history
  holds no earlier versions. The Nasdaq Nordic v2.02.2/v2.02.3 PDF pair is still
  unreachable from here. The first real diff will come from either (a) the owner
  downloading that pair by hand, or (b) extracting two editions of a public spec once
  the API key is in.
  *Product:* the diff engine is tested only on synthetic edits. Say so when demoing it.
