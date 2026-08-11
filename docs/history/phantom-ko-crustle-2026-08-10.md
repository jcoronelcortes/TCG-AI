# The Crustle PHANTOM_KO — 234 boards, and what can already be ruled out

> ## ⚠ CORRECTION, 10 August: 89% of this was the detector
>
> **`judge()` was comparing one body's prediction with another body's outcome.**
> The plan carries `target` — 0 is their active, 1 and up their bench — and
> nothing read it: `remain_hp` was attributed to whichever body had lost hit
> points that step.
>
> Of the **611 dumped `PHANTOM_KO`, 545 (89.2%)** had the plan pointing at a body
> on **their bench** while the attack landed on the active. Three taken at random
> predicted leaving a 70 HP body at −70 and were scored against one of 150 or 300
> that had just taken 100. **The agent was right**: *if I gust that, it falls*.
> Then it did not gust, it attacked the wall in front, and the wall survived.
>
> And it explains why Crustle topped every table: against a wall the best prize
> route is almost always a gust to their bench, so that is where the plan points
> and that is where the misattribution lives. **The concentration belonged to the
> detector, not the agent.**
>
> Re-measured on `crustle_wall_9` at n=1 000 with the target checked:
>
> | | before | now |
> |---|---:|---:|
> | `PHANTOM_KO` | 124 | **17** |
> | `DAMAGE_DRIFT` | 76 | 42 |
> | rate for the list | 4.92% | **1.58%** |
> | discarded for being a different body | — | 209 |
>
> Fixed in `utils/differential_oracle.py` (`planned_serial`), pinned in
> `tests/test_the_oracle_judges_the_body_the_plan_was_about.py` and validated in
> both directions: a phantom **on the plan's own body** is still reported.
>
> **What survives of this document:** sections 2 and 3 — the engine resolves the
> base damage, and it is not the stadium, not a tool, not the double attack —
> remain correct measurements over the boards that *were* correctly attributed.
> What does **not** survive is the magnitude, and with it the urgency. §5 already
> warned that the residue did not explain the matchup (r = +0.09); now we know
> why.

**Status: measured, and the culprit was the instrument. Not one line of the agent
has been touched.**

It comes out of census B1a of the night of 9–10 August
(`docs/night-plan-2026-08-10-c.md`), the first against the 87 real lists of the
meta harvested on the 9th.

---

## 1. Where it is

The oracle's residue by family, over 128 338 attacks judged:

| family | lists | mean rate | median drift | % optimistic |
|---|---:|---:|---:|---:|
| **`crustle_wall`** | 16 | **4.58%** | **+40** | **90%** |
| `great_tusk_crustle` | 1 | 4.06% | −10 | 40% |
| `festival_lead` | 11 | 3.98% | −30 | 44% |
| `marnie_grimmsnarl` | 9 | 0.11% | +25 | 50% |

It is not one deck breaking away: it is the whole family, sixteen lists, six of
which had never been measured.

**And the category separates better than the rate does.** At n=1 000 games per
list:

| list | PHANTOM_KO | MISSED_KO | DAMAGE_DRIFT |
|---|---:|---:|---:|
| `crustle_wall_9` | **124** | 5 | 76 |
| `crustle_wall_6` | **110** | 2 | 55 |
| `festival_lead_10` | 2 | **112** | 616 |
| `festival_lead_8` | 6 | **91** | 442 |

`festival_lead` leads the rate and **wins 97% of its matchups** because its
residue is `MISSED_KO`: it predicted hit points would be left and the body fell
— a good surprise. Crustle is `PHANTOM_KO` at twenty times that rate: **it
predicted the body would fall and it did not**. That one costs the turn.

---

## 2. What the 234 dumped boards say

`log/noche_2026-08-10-c/violaciones_oraculo/crustle_wall_{6,9}/phantom_ko_*.json`,
each with the whole observation.

**The engine resolves exactly the base damage. Every time.**

| pairing | n | damage the engine resolved |
|---|---:|---|
| Dipplin → Crustle | 77 | **100** with a bench of 5, **80** with 4 |
| Tapu Bulu → Mega Kangaskhan ex | 31 | **220**, without a single exception |
| Meganium → Crustle | 30 | **140** in 22 of 30 |

`Do the Wave` is 20 × our bench: 5 → 100, 4 → 80. Exact. Tapu Bulu's 220 and
Meganium's 140 are their printed damage. Exact.

**Crustle is not reducing anything.** The natural hypothesis — "the wall absorbs
it" — is ruled out by the numbers themselves: the engine applied the full
damage. The excess is entirely our projection's.

What the agent predicted, by contrast, is all over the place: Dipplin 180 (×29)
and 200 (×19); Tapu Bulu 370 (×20); Meganium 220 (×11) and 240 (×6).

Excess (predicted − actual) over the 234:

```text
+80  x43     +230 x33     +100 x31     +150 x28
+60  x13     +330 x12     +50  x11     +110 x8
```

---

## 3. What can already be ruled out

Three cheap hypotheses, all three dead on the data already in hand:

1. **It is not the stadium.** The distribution of the excess is the same with
   `Forest of Vitality` (148 cases), with `Battle Cage` (77) and with no stadium
   (9). If a stadium inflated the projection, the split would move with it.
2. **It is not a tool.** Our attacker carries no tool in **234 of 234**.
3. **It is not Festival Grounds' double attack.** That stadium is not on the
   board in any of the 234.

---

## 4. What is left, and why it was not done that night

The most repeated excesses — **+80** and **+100** — appear across different
pairings (Dipplin 100→180, Meganium 140→220), which points at an addend on our
side rather than a multiplier. Confirming it requires **reading
`_our_effective_damage` and the plan's projector**, not aggregating more boards.

That is agent code, and the rule of the night is that **a rule landing halfway
through means the blocks before and after measured two different agents**. So it
stops here.

It is the second time this class has appeared: the first was Full Metal Lab,
where "the agent's own damage projection was 30 too generous", and this same
oracle found it. That one moved 2 decisions in 50 955. **This one is 110–124
boards per 1 000 games**, so the frequency still has to be measured before
touching anything — but the order of magnitude is no longer the same.

---

## 5. And yet it does NOT explain the matchup — B2, n=1 000 per list

This has to be read before fixing anything, because it is what prevents the
false conclusion.

The whole family against the control group:

| | range | mean |
|---|---|---:|
| `crustle_wall` (16 lists) | 71.4% – 85.4% | ~77.5% |
| `mega_lucario` (4, control) | 87.7% – 91.3% | ~89.3% |

**The intervals do not even touch** (Crustle's ceiling is 85.4%, the control's
floor 87.7%), so Crustle genuinely is ~12 points harder. And **no deck breaks
away**: it is a band, not an outlier. The previous night's 54.5% has no heir.

But within the family, crossing the two measurements from that same night:

```text
correlation oracle-rate vs winrate, n=16 lists:  r = +0.09
```

`crustle_wall_12` has a 5.25% residue and wins **85.4%**; `crustle_wall_5` has
1.87% and wins **73.0%**. **The oracle's rate does not predict the winrate
within the family.**

These are two separate facts and they should not be merged:

1. **The projection is wrong.** 110–124 boards per 1 000 games, with the
   observation dumped. It is a correctness defect and it gets fixed for that
   reason.
2. **Crustle is a hard matchup.** Twelve points below the control, and the
   residue does **not** explain it.

Fixing (1) expecting to move (2) is exactly the error this project already has a
name for: **measure the frequency before the winrate**. The frequency justifies
the fix; the winrate will not necessarily thank you for it.

### The anomaly that IS new: `crustle_wall_6`'s prizes

| list | winrate | prizes |
|---|---:|---:|
| `crustle_wall_6` | 71.4% | **−0.22** |
| `crustle_wall_4` | 71.8% | +1.56 |
| rest of the family | 72–85% | +1.50 to +2.56 |

The same winrate as its neighbour and the prize differential collapses by more
than a point and a half. We win 71% of the games **while losing the prize race**,
which points at those wins coming through another route — the deck as a clock.
It is the only list in the corpus with negative prizes and **nobody had ever
measured it**: it is one of the six `crustle_wall` lists the bridge marked NEW.

---

## 6. The retired deck, measured before it stopped mattering — B2b

The previous night asked which of three things `crustle_wall` was: a defect of
the agent, a defect of the bot, or just a hard matchup. The bridge answered
"none, the deck left the meta". **B2b answers the one that was left: it was
real.**

```text
crustle_wall_6 RETIRED, from the 7 Aug backup, n=1000:
    58.8%  [55.7-61.8]   prizes -0.27
    (at n=200 it read 54.5% [47.6-61.3]; the intervals overlap)

its two neighbours from the same retired corpus:
    crustle_wall_2   73.5%   prizes +1.83
    crustle_wall_1   85.8%   prizes +2.31
```

**It was not the ±7 of a short sample.** Twenty-five points below its own
family, with a narrow interval. That deck genuinely beat us, and it left on its
own.

### What survived the rotation is not the deck, it is the signature

| | winrate | prizes |
|---|---:|---:|
| `crustle_wall_6` **retired** (7 Aug) | 58.8% | **−0.27** |
| `crustle_wall_6` **new** (32 cards from the previous one) | 71.4% | **−0.22** |
| any other list in either corpus | 71.8–91.3% | +1.50 to +3.27 |

They are **two different decks** sharing a name by accident of rank, and they
share two more things: being the weakest in their corpus, and being the **only
ones with the prize race in the negative**. We win those games without winning
the prizes.

The phenomenon survived the meta's rotation even though the deck did not; what
it lost is twelve points of severity. And **the marker is not the winrate, it is
the prize differential**: that is what separates these two from the other
thirty-seven lists measured that night.

That also says how to look for it the next time the meta rotates: not by name
and not by archetype, but by sweeping the corpus for **negative prizes**.

---

## 7. Where to start tomorrow

1. The 234 JSON files are ready-made fixtures. **Detecting is not executing**:
   reproducing the board is another job.
2. `B8.log` adds `crustle_wall_11`, `crustle_wall_12` and
   `great_tusk_crustle_1` — the positive-drift lists B1b did not reach, because
   it chose by rate and three of its five slots went to the harmless family.
3. Start with **Dipplin → Crustle**, which is 77 of the 234 and the only pairing
   where the real damage is a known, verifiable function of the board
   (20 × bench).
