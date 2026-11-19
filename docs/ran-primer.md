# RAN Domain Primer for the Agent

> **⚠️ DRAFT — written 2026-11-20 from public sources, BEFORE the 27/11 data drop.**
> Nothing here is verified against the challenge's task docs, tool API, or
> answer schema — those do not exist publicly yet. Every claim marked
> **VERIFY 27/11** must be checked against the real task files before it is
> used to make a scored decision. Thresholds quoted as "field guidance" are
> vendor rules of thumb, NOT 3GPP requirements: 3GPP defines what the
> quantities measure, not what counts as "good".
>
> Purpose: give the agent (and its prompts) the 3GPP concepts the six task
> types assume, so hypotheses are formed in the right vocabulary. This is
> background knowledge, not a scoring rulebook.

Sources: 3GPP TS 38.215 (physical-layer measurements), TS 38.211 (physical
channels/signals), TS 38.300 (NR overall description), TS 38.331 (RRC,
measurement events), TS 38.104 (base-station radio requirements),
TR 38.901 (channel model); ITU-R M.2135 (UMa scenario, used by Giulia's
example config). Secondary explainers cited inline.

## 1. The three measurements: RSRP / RSRQ / SINR (TS 38.215)

All three are measured by the UE on the SSB (synchronisation signal block)
— SS-RSRP, SS-RSRQ, SS-SINR — or on CSI-RS where configured. They answer
three different questions, and confusing them is the most common diagnostic
error.

| Quantity | Definition (TS 38.215 §5.1) | Unit | What it tells you |
|---|---|---|---|
| **SS-RSRP** | Linear average of the power of the resource elements carrying the SSS (secondary synchronisation signal) | dBm | Absolute received strength of a beam/cell. Says nothing about interference — a cell at −80 dBm in a hostile interference environment is not a good cell. |
| **SS-RSSI** | Linear average of *total* received power in the measurement symbols, from all sources including noise | dBm | Not reported on its own. It is the denominator of RSRQ. |
| **SS-RSRQ** | N × SS-RSRP / SS-RSSI, N = number of RBs in the measurement bandwidth | dB | How much of the received power is *this cell*. Falls when neighbours load up, even though RSRP is unchanged. |
| **SS-SINR** | SSS power / (noise + interference power over the same resource elements) | dB | Closest thing to "will this link work". Most directly tracks achievable modulation (MCS) and throughput. |

Key relationships (use these when forming fault hypotheses):

- **RSRP moves with distance and blockage** (path loss, shadowing). It does
  not move with load.
- **RSRQ moves with load** — both the serving cell's own load (a busier cell
  radiates more total power into RSSI) and neighbour load.
- **SINR moves with both, plus noise.** A cell can be strong but noisy.
- All three are reported as integers 0..127 (`RSRP-Range` etc.); the mapping
  to physical values differs per quantity.

### Field bands (vendor guidance, NOT 3GPP)

3GPP does not grade these values. The bands below are Teltonika Networks'
published field guidance for its routers (other vendors publish their own;
prefer the task docs' bands if the 27/11 drop defines any — **VERIFY 27/11**):

| Metric | Excellent | Good | Fair–poor | Poor |
|---|---|---|---|---|
| RSRP | ≥ −80 dBm | −80 to −90 | −90 to −100 | < −100 dBm |
| RSRQ | ≥ −10 dB | −10 to −15 | −15 to −20 | ≤ −20 dB |
| SINR | ≥ 20 dB | 13 to 20 | 0 to 13 | ≤ 0 dB |

The baseline agent (`ran_agent/baseline.py`) uses −100 dBm RSRP and 0 dB
SINR as its weak/unusable thresholds — consistent with the "poor" column
above, and deliberately coarse until real thresholds arrive.

### Diagnostic signatures (hypothesis formation)

| Observation | Most likely story | Check next |
|---|---|---|
| RSRP good, SINR collapsed, neighbours normal | **Interference** — something radiates into this cell (neighbour, external source, PCI/mod conflict) | Neighbour load/RSRQ; PCI plan; SINR of neighbours |
| RSRP very low everywhere in the cell | **Propagation** — distance, shadowing, obstruction, or power/tilt mis-set | Power, tilt, azimuth; terrain/shadowing maps |
| RSRP low AND SINR low, one cell only | **Misconfiguration** or hardware (antenna, feeder, PA) | Compare against the same cell's history; config audit |
| RSRQ falling while RSRP steady | **Load** — the cell or its neighbours got busy | Load %, PRB utilisation, throughput |
| All neighbours degrading together | Shared fault (backhaul, power, interference source), NOT independent cell faults | Common-cause check before blaming one cell |

## 2. Handover and mobility (TS 38.300, TS 38.331 §5.5)

A connected UE moves between cells by handover; the network decides from
the UE's measurement reports. The pieces that matter for the tasks:

- **Measurement configuration (RRC):** measurement objects (which
  frequencies/cells), report configurations (which event, thresholds,
  offsets, time-to-trigger), measurement identities linking the two.
- **Event A3 (the classic intra-frequency trigger):** a neighbour becomes
  *offset better* than the serving cell — entering condition roughly
  `Mn + Ocn > Ms + Off + Hys`, where `Mn`/`Ms` are neighbour/serving
  measurements, `Ocn` is the cell-individual offset for that neighbour,
  `Off` the A3 offset, `Hys` hysteresis. The condition must hold for the
  **time-to-trigger** before the UE reports. Typical values: 3 dB offset,
  320 ms TTT — these are configuration choices, not constants.
- **Event A5 (coverage handover):** serving falls below threshold 1 AND
  neighbour rises above threshold 2. Used when the serving cell is dying,
  not merely worse.
- **Other events:** A1/A2 (serving crosses a threshold), A4 (neighbour
  crosses a threshold), A6 (neighbour better than secondary cell),
  B1/B2 (inter-RAT). A3 and A5 cover most handover reasoning.
- **Handover types:** Xn handover (direct gNB-to-gNB link), N2 handover
  (via the core network), plus conditional handover (CHO) and dual active
  protocol stack (DAPS) in later releases.
- **Why it matters for the agent:** handover failures show up as SINR/RSRP
  patterns at cell edges; the *offsets* (A3 offset, CIO — see §6) are the
  knobs that move handover boundaries without touching antennas. Ping-pong
  (rapid back-and-forth handover) means offsets/hysteresis are too small.

## 3. PCI: collision, confusion, and the mod rules (TS 38.211 §7.4.2.1)

The physical cell identity is how a UE names a cell at the physical layer:

- **NR:** PCI = 3 × N_ID(1) + N_ID(2); N_ID(1) is the SSS group (0–335),
  N_ID(2) is the PSS index (0–2) → **1008 PCIs, 0–1007**.
- **LTE:** same formula with N_ID(1) 0–167 → **504 PCIs, 0–503**.
- The pool is small, so reuse is inevitable in any real deployment — the
  plan must make reuse *safe*, not avoid it.

Two hard failures (both break handover):

- **Collision:** two cells heard in the same place on the same SSB
  frequency share a PCI. The UE sees them as one cell; measurements and
  handovers go to the wrong cell.
- **Confusion:** one cell has *two neighbours* with the same PCI (even far
  apart). When a UE reports that PCI, the serving cell cannot tell which
  target is meant, so the handover cannot be prepared.

Softer rules (structured interference — meet them where the neighbour
graph allows):

- **mod 3:** PCI mod 3 = N_ID(2) = the PSS. Neighbours sharing mod 3
  collide on PSS sequences.
- **mod 6 / mod 30:** affect other reference-signal patterns (uplink
  reference signals, PCFICH in LTE). PCI-mod-3 planning is the one most
  often enforced; mod-6 matters in mixed MIMO/SISO, mod-30 in uplink
  decoding.

**Agent implication:** if a fault task shows handover failures or SINR
collapse localised to a cell pair, check the PCI plan (collision/confusion/
mod-3) *before* proposing power or tilt changes — no amount of power fixes
two cells that the UE cannot distinguish. **VERIFY 27/11** whether the task
scenarios even expose PCI (the challenge may or may not model it — Giulia
supports per-cell radio customisation, so it plausibly does).

## 4. Antenna: tilt and azimuth

Tilt is the angle of the main beam below the horizontal plane; azimuth is
the horizontal pointing direction (degrees from north). Together they set
the cell's footprint and its interference into neighbours.

- **Mechanical tilt:** physically angles the antenna housing. Range
  typically 0–15°, set at installation (tower crew). Tilts the whole
  pattern, including sidelobes and back lobe.
- **Electrical tilt:** phase-shifts the signals fed to the array elements
  to steer the beam down without moving the housing. Range typically
  0–10°. Adjusted remotely (**RET** — remote electrical tilt, AISG
  standard) in seconds, which is why it is the day-to-day optimisation
  knob. Total downtilt ≈ mechanical + electrical.
- **Rule of thumb:** geometric downtilt θ = arctan(antenna height /
  distance to target); aim the beam centre at ~60–70% of the desired cell
  radius, not at the cell edge. A 1° change can move the cell-edge boundary
  by hundreds of metres and change the interference footprint at neighbours
  by 6–10 dB.
- **Downtilt more** → smaller footprint, less interference to neighbours,
  but a dead zone can open near the tower and far users lose service.
- **Downtilt less (uptilt)** → larger footprint, more interference,
  overshoot into neighbouring cells.
- **Azimuth** rotates the footprint horizontally. Misaligned azimuth shows
  up as a coverage gap on one side and overshoot on the other; it is the
  first suspect when a *sector* of a site is weak while its siblings are
  fine.
- 3GPP does not specify tilt values; the framework is TS 38.104 (base
  station radio requirements) and the antenna pattern models in
  TR 38.901 §7.3 / ITU-R F.1336.

**Agent implication:** power/tilt/azimuth are the three coverage knobs, in
that order of cost: power is cheapest to test in simulation, tilt next,
azimuth/site moves most expensive. The baseline agent tests power first
for exactly this reason. Note the mock's tilt model (RSRP −0.3 dB/deg) is
a placeholder — real tilt effects are geometry-dependent and must come
from Giulia, not from this primer.

## 5. Power

- Transmit power (dBm per cell, typically ~43 dBm macro baseline in the
  mock) sets the cell's reach. +3 dB roughly doubles radiated power.
- Raising power raises the serving cell's RSRP and SINR — but also raises
  interference *into* neighbours, so network-wide SINR can fall even as
  the target cell improves. Any power change must be judged on all cells,
  not just the one changed (the baseline's radio-config loop does this).
- Power is also the energy lever: the power amplifier dominates a base
  station's consumption, so cutting power (or shutting a carrier/cell) is
  where energy savings come from — see §7.
- Power control on the uplink is a separate mechanism (UE transmit power);
  the tasks' "power" knob is the downlink cell power unless the task says
  otherwise — **VERIFY 27/11**.

## 6. Load balancing (MLB)

Mobility load balancing shifts users between cells by moving handover
boundaries, not by moving antennas:

- **Cell individual offset (CIO / Ocn):** a per-neighbour offset added to
  the neighbour's measurement in the A3 entering condition. Raising the
  CIO of an underloaded neighbour (or lowering it for an overloaded
  serving cell) makes UEs hand over earlier, offloading the busy cell.
  This is the standard MLB knob.
- **Tilt-based balancing:** changing tilt reshapes the best-server
  boundary itself — slower, coarser, and it changes coverage as well as
  load. Useful for persistent imbalance, not for fast traffic swings.
- **What to look for:** one cell at >90% load with a neighbour at <30% is
  a load-balancing opportunity; one cell at >90% with *all* neighbours
  also loaded is a capacity problem (needs a new site/carrier, not
  balancing). Offloading onto a neighbour only helps if that neighbour
  has spare PRBs *and* acceptable SINR at the handover boundary.
- **Failure mode:** aggressive offload creates ping-pong handovers and
  drops at the boundary; the offset must be large enough to matter and
  small enough to stay stable.

## 7. Energy saving: carrier shutdown and cell switch-off

Base stations burn most of their energy in the power amplifier and
always-on signalling, even at low traffic — so the saving comes from
turning things off when traffic is low, not from running them slightly
cooler.

- **Three levels** (coarse → fine): carrier shutdown (a whole carrier/cell
  off for hours, e.g. night-time), symbol shutdown (OFDM-symbol level,
  microseconds, opportunistic), channel shutdown / deep sleep (hardware
  blocks off).
- **The 3GPP rule that matters:** only *capacity* cells may be switched
  off. A capacity-boost cell (pico/small cell overlaid on a macro) can be
  shut down when its traffic stays below a threshold for a set period; the
  *coverage* cell that provides basic service must stay on — otherwise
  there is a hole, not a saving. (TS 36.300 energy-saving procedure;
  same principle in NR.)
- **Procedure sketch (LTE/NR):** the capacity cell's UEs are handed over
  to the coverage cell (handover cause "energy saving"), the cell signals
  deactivation to its neighbours (X2AP ENB Configuration Update /
  Deactivation Indication), and it is woken by a Cell Activation message
  when the coverage cell's load overfills.
- **What to verify before claiming a saving:** coverage still holds
  (no new hole), throughput still meets targets, the neighbours that
  absorb the traffic are not themselves overloaded, and the saving is
  net of the wake-up cost. The baseline agent enforces the first two
  with guardrails (≤3 pts coverage, ≤10% throughput) and reports the
  saving as 0% when they fail — an energy saving that breaks service is
  a failure, not a saving.
- **Time dimension:** shutdowns are normally scheduled (night hours) or
  load-triggered with hysteresis — a cell that flaps on/off every few
  minutes saves nothing and drops users. If the task files include a
  traffic-over-time pattern, use it; a single snapshot cannot justify a
  schedule — **VERIFY 27/11**.

## 8. How this maps to the six task types

| Task type | Concepts that usually decide it |
|---|---|
| Fault diagnosis | §1 signatures (RSRP vs RSRQ vs SINR), §3 PCI, hardware vs config |
| Outage impact | §1 (what the lost cell served), §2 (where its users hand over to), §6 (neighbour overload) |
| Coverage | §4 tilt/azimuth, §5 power, §1 RSRP; cheapest fix first |
| Radio config | §4 + §5 knobs, §6 CIO; verify *all* conditions after each change |
| Site placement | §1 gap location, §3 PCI for the new cell, §4 footprint geometry |
| Energy | §7 shutdown rules, §6 absorption capacity, §1 guardrail KPIs |

## 9. Verify against the 27/11 task docs (checklist)

- [ ] Do the task scenarios expose PCI? (If not, §3 is background only.)
- [ ] Are there RSRP/RSRQ/SINR thresholds in the task files? (Replace the
      field-guidance bands in §1 and the baseline's −100 dBm / 0 dB.)
- [ ] What are the per-task simulation budgets? (Retune the baseline's
      experiment counts — it currently spends ≤2 sims on most types.)
- [ ] Does Giulia's task config model tilt/azimuth/power as the agent's
      knobs, or different ones? (Retune the mock's directional model.)
- [ ] Is there a traffic-over-time pattern for the energy tasks?
      (A single snapshot cannot justify a shutdown schedule.)
- [ ] Do the answer schemas use GeoJSON or WKT polygons? Lat/lon or
      local coordinates? (The baseline's synthetic grid coordinates are
      placeholders.)
- [ ] Which 3GPP release / frequency range (FR1/FR2) do the scenarios use?
      (FR2 beam-based measurements change the §1 picture.)

## Sources

- 3GPP TS 38.215 — NR physical layer measurements (SS-RSRP/RSRQ/SINR
  definitions, §5.1). https://www.3gpp.org/ (specification number TS 38.215)
- 3GPP TS 38.211 §7.4.2.1 — PCI construction (1008 identities, 0–1007).
- 3GPP TS 38.331 §5.5 — measurement events A1–A6, B1–B2.
- 3GPP TS 38.300 — NR/NG-RAN overall description (handover, energy saving).
- 3GPP TS 36.300 — energy-saving procedure (capacity vs coverage cells,
  X2AP activation/deactivation).
- Measurement definitions and field bands, explained:
  https://www.rfwireless-world.com/articles/5g-nr-rsrp-rsrq-sinr-measurements
  and https://www.industrialwirelessio.com/network-paths/cellular-signal-quality-rsrp-rsrq-sinr-checklist-for-remote-telemetry/
- PCI collision/confusion/mod rules:
  https://www.cafetele.com/5g-tools/5g-pci-planner/
- Handover events and optimisation:
  https://www.telecomhunt.com/post/5g-mobility-handover-a3-xn-n2-optimization
- Tilt (mechanical vs electrical/RET, geometry):
  https://www.5g6gacademy.com/learn/antenna-tilt-optimization
- Energy saving (carrier shutdown, capacity vs coverage):
  https://patents.google.com/patent/WO2023010305A1/en
  (background; the 3GPP procedure is TS 36.300 / TS 38.300).
