# Measuring the house: a plan for UA, the time constant and the steady temperature

*16 November 2026. Companion to `docs/hearth-auto-lab-report.md` (section XI has the same mathematics) and to `tools/hearth-house.py`, which does every calculation here.*

Paul, 16 November: "I have turned heating to the house off, so temperatures should be related to system wattage. Confirm that you have the data necessary to calculate heat loss, the UA value. Explain how leaving radbeeper running and with orrery, within a few days we have enough information to calculate values for steady state temp. ... show math. if its unknown show future calculation."

## 1. The answer first

| Question | Answer |
|---|---|
| Is the data needed for UA being recorded? | **Yes, all three parts**, and none of it needs the controller scheduled. The room every five seconds, the fleet's watts every five seconds, and SeaTac's air about hourly. |
| Can UA be calculated today? | **No. It can be bounded.** Six hours are recorded. The room is cooling with the fleet at 749 W and 18.0 °C over the outside, so UA is more than 42 W/°C. |
| What do a few days of leaving it running give? | The time constant, and how far over the outside the room settles **at the watts the fleet draws now**. That is the steady temperature for the present fleet. |
| What do they not give? | UA in watts a degree, and so the steady temperature at any *other* wattage. That needs the fleet's watts to change by a known amount and stay there about a day. It is one step, and it is Paul's to order. |

## 2. What is recorded, and by what

| Quantity | Symbol | Where it is kept | How often | Kept by |
|---|---|---|---|---|
| The room | T | `room.radXXXX.c` in `QUEUE/telemetry/saskatchewan/DAY.log`; also `temp-SERIAL-YYYY-MM.tsv` on saskatchewan | 5 s; 30 s | radbeeper asks each Geiger counter; the fleet's collector reports it; the keeper pulls it to the Mac |
| The fleet's watts | P | the same telemetry: each CPU's energy counter and each card's draw, made wall watts by `tools/plans/power.json` | 5 s | the collector on every machine |
| The outside | To | `QUEUE/hearth/outside-history.tsv` | about hourly | `hearth-house.py`, from the weather service's record for KSEA |

Three conditions keep the record whole:

1. **radbeeper's service stays running on saskatchewan**, and the two counters stay where they are. Moving a counter changes what its thermometer reads.
2. **The keeper stays running on the Mac.** If it stops, radbeeper's own file on saskatchewan still has the room; the watts for those hours are on each machine until the next pull.
3. **`hearth-house.py` runs at least once a week.** The weather service keeps about seven days of observations. Each run saves what is new.

`tools/hearth.py`'s own `record.tsv` has one line, because the controller's pass is not scheduled. It is not needed: `hearth-house.py` rebuilds the record from the telemetry.

## 3. The mathematics

One room, treated as one lump of heat:

    C dT/dt = P + P0 − UA (T − To)                                   (1)

| Symbol | Meaning | Unit | Known? |
|---|---|---|---|
| T | the room | °C | recorded |
| To | the outside | °C | recorded (the airport's) |
| P | the fleet's watts at the wall | W | recorded (a model, section 6) |
| P0 | every other watt the house gets: people, refrigerator, lights, sun | W | unknown |
| UA | watts lost for each degree the room is over the outside | W/°C | unknown, more than 42 |
| C | joules that warm the room one degree | J/°C | unknown |

**Steady state.** Set dT/dt = 0 in (1):

    T_ss = To + (P + P0) / UA                                        (2)

**Time constant.** With P, P0 and To held, (1) has the solution

    T(t) = T_ss + (T(0) − T_ss) e^(−t/τ),      τ = C / UA           (3)

**A bound from one reading.** If the room is cooling, the right side of (1) is negative:

    UA (T − To) > P + P0 ≥ P     so     UA > P / (T − To)            (4)

Tonight at 20:30: T = 26.0, To = 8.0, P = 749 W, the room falling 0.24 °C an hour. So UA > 749 / 18.0 = **42 W/°C**. It is a floor and nothing more: P0 is not zero, and the fall says the true figure is higher.

**The fit.** Divide (1) by C. It is a straight line in three recorded things:

    dT/dt = a P + b (T − To) + c,      a = 1/C,   b = −UA/C,   c = P0/C     (5)

Least squares over the hours gives a, b and c, and from them

    UA = −b/a,     C = 1/a,     P0 = c/a,     τ = C/UA = −1/b        (6)

**What each coefficient needs.**

- *b* needs (T − To) to change. The day and the night do that unasked.
- *a* needs **P to change**. While the fleet's watts are level, `a P` is a constant and cannot be told from `c`. Then (5) is

      dT/dt = k + b (T − To),      k = (P + P0)/C                    (7)

  and only two numbers come out: τ = −1/b, and the rise

      rise = −k/b = (P + P0) / UA                                    (8)

  which by (2) is how far over the outside the room settles at those watts.

**UA from a step.** Change the fleet's watts by a known ΔP and let the fit find the new rise. From (8), with P0 unchanged:

    UA = ΔP / Δrise                                                  (9)
    P0 = UA × rise − P                                               (10)
    C  = τ × UA                                                      (11)

**The controller's gains, once τ and UA are known.** The room answers a watt with 1/UA degrees after a lag of τ. For a loop about as fast as the room itself:

    Kp = UA   (W/°C),      Ki = UA / τ   (W/°C per hour, τ in hours)  (12)

and the feedforward term `UA × (target − outside)` comes into use with `hearth.py QUEUE set ua N`.

### A worked example, with invented numbers

These figures are made up to show the arithmetic. None is a measurement.

| Step | Calculation | Result |
|---|---|---|
| Two days at 750 W give, by (7) and (8) | | τ = 30 h, rise = 16.0 °C |
| The fleet is stepped down to 450 W and held; the fit gives | | rise = 12.5 °C |
| UA, by (9) | 300 / (16.0 − 12.5) | 86 W/°C |
| P0, by (10) | 86 × 16.0 − 750 | 626 W |
| C, by (11) | 30 × 3600 × 86 | 9.3 MJ/°C |
| The room at 5 °C outside with the fleet at 750 W, by (2) | 5 + (750 + 626)/86 | 21.0 °C |
| Watts to hold 21 °C at 0 °C outside | 86 × 21 − 626 | 1,180 W |
| Gains, by (12) | Kp = 86; Ki = 86/30 | 86 W/°C; 2.9 W/°C per hour |

## 4. Why a few days, and not tonight

| Reason | What it costs |
|---|---|
| The probes read in tenths of a degree, and the room moves about 0.25 °C an hour. | A slope is taken across four hours to stand clear of the tenths. The first fitted hour comes two hours after the record begins. |
| b needs the room's height over the outside to vary by 1.5 °C or more. | At least one night and one day; two of each to see it twice. |
| The house was warm from its own heating when that was switched off. Its walls and the other rooms give that heat back for a day or more. | The first day is mostly the house cooling toward its own level, not the fleet's. The fit should be read from the second day on (`--since`). |
| The sun and the people in the house add watts by day. | The fit is also made on 22:00 to 06:00 alone. Two nights are the least that gives it enough hours. |

`hearth-house.py` says a three-number fit is not to be believed until it has 48 fitted hours, the watts have stood 80 W apart, and (T − To) has stood 1.5 °C apart. Those thresholds are judgment, not derivation.

## 5. The plan

| When | What | Who | What comes out |
|---|---|---|---|
| **Mon 16 Nov, evening** | The house's heating is off. The fleet runs as it is. | done | The record begins: 15:05. |
| **Tue 17 and Wed 18 Nov** | Leave it. Run `python3 tools/hearth-house.py QUEUE --table` morning and evening. Note anything that adds or removes heat (section 7). | Paul or Claude | By Wednesday evening: τ and the rise at about 750 W, so T_ss for the present fleet by (2). |
| **Wed 18 Nov, evening** | **The step.** Change the fleet's watts by 300 W or more and hold. Down: pause the card lanes and CPU lanes of calber and whitewolf (about −330 W at tonight's prices). Or up: start bosporus and jaguaribe. | **Paul's word.** Nothing is paused or started without it. | |
| **Thu 19 Nov** | Hold the step. Run the fit morning and evening. | | The watts now stand apart; the three-number fit begins to close. |
| **Fri 20 Nov** | Read UA, C, P0 and τ, on all hours and on nights alone. If the two agree within about 15%, adopt: `hearth.py QUEUE set ua N`. Work out the gains by (12). | Paul adopts | UA in use; the feedforward on; T_ss for any watts and any outside. |
| **After** | Step back, which is a second, free measurement of the same UA. Then the first supervised hours in *act*, if Paul wants them. | Paul | |

**How big a step.** The rise is known to perhaps ±0.2 °C. For UA to 10%, Δrise must be 2 °C, so ΔP = 2 × UA: 170 W if UA is 86, 300 W if it is 150. A step of 300 to 400 W covers both. The fleet draws about 750 W, so that is roughly half of it.

**How long to hold.** The fit uses slopes, so the room need not finish settling. One τ is enough. τ is not known; plan a day and extend it if Wednesday's figure for τ is longer than a day.

## 6. What is wrong with the numbers, and what corrects each

| Weakness | Effect on UA | Correction |
|---|---|---|
| **The fleet's watts are a model, not a meter.** `power.json` adds an estimated rest-of-box figure and divides by an assumed supply efficiency. | UA is wrong by the same fraction the watts are. | A plug-in watt meter on each box for an hour, and its figure written into `power.json`. |
| **Machines not counted:** this Mac, the Mac mini, the switches, the monitors. bosporus and jaguaribe have reported nothing since 15 November; if they are on, their watts are missing too. | They fall into P0, harmlessly, as long as they are steady. | Confirm bosporus and jaguaribe are off. Give the rest fixed figures. |
| **P0 is not constant:** sun by day, cooking, people. | Scatter, and a bias by day. | The night-only fit. The utility meter read at 22:00 and 06:00 gives the whole house's electrical watts for the night: that is P + most of P0, measured. |
| **The probes are inside two counters' cases, on one machine.** | A constant offset cancels in every slope and in Δrise, so UA, τ and C are not moved by it. T_ss is high by the offset. | Stand a room thermometer beside them once and record the difference as each probe's offset. |
| **The outside is the airport's.** | A constant difference shifts the rise and not UA. A difference that varies with the weather adds scatter. | A probe outside the house, when one exists. |
| **One lump is not a house.** The room trades heat with the other rooms, which are cooling for the first day or two. | The first days' UA is too high; it falls as the house settles. | Fit from the second day. If the residuals show two time constants, add a second lump: the room and the house. |
| **Wind and rain** change the loss. | Scatter between days. | More days. Not corrected in this plan. |

## 7. Things to note while it runs

Write the time down for any of these, since each is a step in P0 the record cannot see: the house's heating on for any reason; another heater; a door between the fleet's room and the house left open or shut for hours where it was not before; a window opened; the oven or the dryer run for an hour; a machine switched on or off by hand.

## 8. The report and the film, reviewed

What the report of 16 November got wrong or left out, and what was done about it:

| # | Finding | State |
|---|---|---|
| 1 | The report never wrote the house's heat balance down, so "UA is unknown" had no path to "UA is known". | **Done:** section XI, with equations (1) to (12). |
| 2 | `fit-ua` waits for twelve hours in which the room holds within 0.3 °C. With the heating off and the outside swinging, a house does not do that. The rule could wait for ever. | **Done:** `tools/hearth-house.py` fits the moving room instead. `fit-ua` is left as it was. |
| 3 | The controller's record has one line because the pass is not scheduled. The report read that as "no data". | **Done:** the record is rebuilt from the telemetry; 6.2 hours on the first run. |
| 4 | The report gave no bound on UA although one reading gives one. | **Done:** more than 42 W/°C. |
| 5 | The gains were "a guess made slow" with no rule for replacing the guess. | **Done on paper:** equation (12). Not applied. |
| 6 | The film said the cold-room order "ends with waking a machine" and that the whole ladder takes "about three hours", against the corrected report. | **Done:** narration and captions changed; the film re-rendered. |
| 7 | The film had no mathematics. | **Done:** a scene after the law: the balance, tonight's four numbers, the bound, and what the days give. |
| 8 | The film leaves out section III.C, finding counters across the fleet. | Open. |
| 9 | The watts are a model and the report says so once, in passing. | **Done** in section XI; a meter is still wanted. |

## 9. To do

- [ ] Run `hearth-house.py` morning and evening through Friday 20 November. *(Paul or Claude)*
- [ ] Decide the step: down or up, and when. *(Paul)*
- [ ] Confirm bosporus and jaguaribe are off. *(Paul)*
- [ ] Read the utility meter at 22:00 and 06:00 one night. *(Paul)*
- [ ] Stand a room thermometer beside the counters once; record the offsets. *(Paul)*
- [ ] Put a watt meter on each box for an hour; correct `power.json`. *(Paul, then Claude)*
- [ ] Give the Mac, the Mac mini and the switches fixed watts in the model. *(Claude, on Paul's figures)*
- [ ] Adopt UA and the gains when the night fit and the all-hours fit agree. *(Paul)*
- [ ] Pull, build and restart radbeeper on saskatchewan for the minus-nought fix. Not urgent: `hearth-house.py` discards those readings. *(Paul)*
- [ ] The film's missing section on finding counters. *(Claude, if wanted)*
