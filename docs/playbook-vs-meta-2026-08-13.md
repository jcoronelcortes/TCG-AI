# Playbook against the meta — 13 August 2026

[← Documentation index](README.md) · [the plan that produced it](night-plan-2026-08-13-b.md)

> ### ⚠️ Superseded in three places by [the night of 14 August](history/night-2026-08-14.md)
>
> **Every number below was measured on the list of 13 August**, before
> `deck.csv` went to one Tapu Bulu, one Night Stretcher, two Poké Pad and
> fourteen Grass. Re-measured on the new sixty, the headline is **95.4 % ±0.17,
> prizes +4.172** (against 94.50 % / +4.063 here): the four cards are worth
> **+0.59 pp [+0.34, +0.84]** and the day's thirteen rule commits a further
> **+0.36 pp [+0.10, +0.63]**. The per-archetype rows below move with them;
> Ogerpon Verde by +1.54 pp, and **Mega Lopunny / Mega Froslass the wrong way,
> −0.90 pp at 7.2 % of the meta**.
>
> * **§6's "someone in the top-500 plays our exact list" is false.** The 60/60
>   mirror is now 58/60. The mirror CLASS is unchanged — 7 Festival Lead lists,
>   2.8 % of the meta — and `festival_lead_1` moved *toward* us, 56 → 58.
> * **§7's P5 is closed, with no rule.** The negative Festival Lead seat gap is
>   the mirror class and not the archetype: the mirrors alone are −1.78 pp
>   ±1.64, and Festival Lead without them is indistinguishable from zero.
> * **Going first is worth half of what it says here** under the new list:
>   +1.04 pp ±0.37 against +2.08 pp ±0.37, two intervals that do not overlap.

**What this is.** The measured answer to *how do we pilot our list against the
500 decks at the top of the leaderboard*. Every number here comes from
`log/noche-2026-08-13-b/`, at HEAD **`8192c22`**, against **133 real lists**
carrying their meta weight, with the seeded engine (control noise floor zero) and
the game budget spread by meta share.

⚠️ **Read this bound first.** `8192c22` reversed the seat policy: our agent now
answers YES to `IS_FIRST`. Since the reference bot also answers YES and `torneo`
alternates seats, every figure below is an **exact 50/50 seat mix**, not the
going-second half that every earlier figure in this repository describes. The two
are not comparable, and on HEAD the going-second half can no longer be measured in
isolation. Where a seat number appears it comes from `cand_primero` /
`cand_segundo`, disjoint game sets, half the games each.

---

## 1. The headline, under both metas

| Weighting | Ladder winrate | Prize differential | Lists carrying weight |
|---|---|---|---|
| **The field** (all 500) | **94.50 %** ±0.19 | +4.063 | 133 |
| **The top-100** | **95.81 %** ±0.25 | +4.179 | **38** |

**We do better at the top of the ladder than in the field**, and that is not a
paradox — it is the whole finding of this night. The field is weighted toward the
decks we struggle against; the top-100 is weighted toward decks we beat almost
freely. Climbing and holding are different problems, and the field average was
quietly answering the second one.

**Zero forfeits in 53 181 games.** This matters more than it looks: `8192c22`
made every `we_go_first == True` branch execute for the first time — roughly
26 590 games' worth of code that no self-play had ever run — and none of it made
an illegal play. §7 of the plan had a rule ready for a forfeit spike. There was
none.

### The metric that actually discriminates

The winrate is **saturated** against the reference bot: 18 of 22 archetypes sit
above 92 %, and eleven above 97 %. The **prize differential** is what has
resolution, and it separates the field cleanly — +4.0 to +4.8 where we are
comfortable, +2.1 to +2.3 where we are not. **Rank matchups by prizes, not by
winrate.**

---

## 2. Where the ladder points actually go

The ranking **reorders completely** between the two metas, and one archetype
leaves the table entirely:

| Weighting | 1st | 2nd | 3rd | 4th |
|---|---|---|---|---|
| **Field** | **crustle_wall 1.64** | marnie 1.18 | ogerpon_verde 0.91 | alakazam 0.74 |
| **Top-100** | **ogerpon_verde 0.81** | marnie 0.71 | alakazam 0.61 | mega_lucario 0.48 |

(points = meta weight × loss rate)

**Crustle Wall is the field's biggest leak and nearly absent from the top-100**
(8.23 % → 2.02 %). **Ogerpon Verde does not shrink** (6.22 % → 6.06 %) and becomes
the top-100's biggest leak. If the goal is climbing, Ogerpon Verde is the first
matchup to fix; if it is holding a field position, Crustle Wall is.

### ⚠️ What the 500 decks bought, and what they did not (M3)

The same code measured against the **old 87-list corpus** (built from the
top-300) and against the new 133-list one:

| Corpus | Ladder winrate | Prize differential |
|---|---|---|
| 87 lists (top-300) | 94.6 % ±0.23 | **+4.063** |
| 133 lists (top-500) | 94.50 % ±0.19 | **+4.063** |

**The headline number did not move, and the prize differential is identical to
three decimals.** So the honest verdict is split, and both halves matter:

* **For "how good are we", the 500 bought nothing** but a slightly tighter
  interval. The 87-list corpus was already the right corpus for that question,
  and no past verdict resting on it needs relabelling on corpus grounds.
* **For "what should we work on", the 500 changed the answer.** The old corpus's
  loss ranking named `crustle_wall_2` third at 0.34 pts — one list. Aggregated
  across the 21 Crustle Wall lists the 500 contains, the archetype is **8.23 % of
  the field and the single biggest leak at 1.64 pts.** The old corpus did not
  under-measure the matchup; it **fragmented the archetype** across too few lists
  to see its total weight.

This is the plan's §9 falsification test coming back **half true**, which was one
of the two outcomes it named in advance. The corpus rebuild was not what paid;
the second weighting and the archetype-level aggregation were.

---

## 3. The two hard matchups — and they are hard the same way

Only two archetypes sit below 92 %, and everything about them agrees:

| | Winrate | Prizes | Going first | Going second | **Seat gap** |
|---|---|---|---|---|---|
| **crustle_wall** (8.23 % field) | 80.0 % | **+2.32** | 83.2 % | 76.8 % | **+6.4 pp** |
| **ogerpon_verde** (6.22 % field) | 85.4 % | **+2.14** | 88.1 % | 82.8 % | **+5.3 pp** |
| *everything else* | 92–99 % | +2.7…+5.3 | — | — | ≈ +1 pp |

**These are the same two matchups on all three axes**: lowest winrate, lowest
prize differential, largest seat dependence. The worst individual lists are
`crustle_wall_10` at **71.7 %** and `ogerpon_verde_1` at **80.9 %** (n=901, so
that one is not a small-sample artefact).

The coherent reading: these are the matchups where the game is decided by tempo,
and tempo is exactly what the seat buys. Everywhere the winrate is saturated the
seat is worth ~1 pp; where the game is actually contested it is worth 5–6.

### ⭐ Why we lose them — and the negative result that redirects the work

Four archetypes autopsied at 400 games each with a **control group** (the same
traits counted over won turns, which is the only thing that explains anything):

| | Record | Loss modes |
|---|---|---|
| crustle_wall_1 | 306–94 | prizes 63, **deckout 26 (28 %)**, bench-out 5 |
| ogerpon_verde_1 | 349–51 | prizes 44, bench-out 7, **no deckout** |
| alakazam_1 | 379–21 | **bench-out 11 (52 %)**, prizes 9, deckout 1 |
| marnie_grimmsnarl_1 | 387–13 | prizes 11, deckout 1, bench-out 1 |

The trait table, as loss % − win % (the full tables are in
`log/noche-2026-08-13-b/A1-*.log`):

| Trait | crustle | ogerpon | alakazam | marnie |
|---|---|---|---|---|
| turn closed with END, no attack | **+22.0** | +18.1 | **+44.7** | **+41.9** |
| no attacker ready anywhere | +13.0 | +18.1 | **+40.9** | +20.0 |
| active STUCK (neither attacks nor retreats) | +8.4 | +15.3 | +31.2 | +21.9 |
| stuck with **NO** escape | +8.6 | +10.4 | +29.2 | +24.1 |
| **stuck WITH an escape and did not take it** | **−0.2** | **+4.9** | **+2.0** | **−2.3** |

⚠️ **The last row is the result.** "Stuck with an escape available and it was not
taken" is the trait that would indicate a **scoring defect** — and it does not
separate losses from wins in any of the four matchups (−2.3 to +4.9). The trait
that separates strongly, everywhere, is "stuck with **no** escape" (+8.6 to
+29.2).

**So these losses are not misplays. They are board and resource starvation.** The
agent is not leaving an available escape on the table; it has no escape to take.
The immediate consequence is uncomfortable and worth stating plainly: **more
scoring rules will not fix Crustle Wall or Ogerpon Verde.** §7's P2 named the
right targets and the wrong instrument.

This is [[no-poder-atacar-no-es-un-tablero-raro]] measured across the meta rather
than on one board: not being able to attack is not a weird board, it is the
ordinary texture of a losing game.

### The three failure classes that are NOT shared

The consistency above is about *how* the turns fail. The *game* fails differently
per archetype, and this is where the piloting advice actually lives:

1. **Crustle Wall: 28 % of losses are DECKOUT** — unique to it, plus "no Grass in
   hand" (+11.6) and the longest stuck streaks in the corpus (max 11 consecutive
   turns in losses against max 7 in wins). The wall holds, we spin, the deck runs
   out. Against Crustle the clock is **our deck**, not the prize race
   ([[el-mazo-es-el-reloj-de-la-carrera-de-premios]]).
2. **Alakazam: 52 % of losses are BENCH-OUT** — a completely different failure
   from everything else, and Alakazam is **17.87 % of the field**. We do not lose
   the prize race; we run out of bodies. Supporters also go **unspent** in its
   losses (+30.4), which is the opposite of Ogerpon Verde below.
3. **Ogerpon Verde: we spend MORE and still cannot attack.** Supporters unspent
   −7.0 and attachments unspent −7.9 — resources are being used in the losses, and
   "no attacker ready anywhere" still stands at **77.3 %** of losing turns. It is
   also the only matchup whose "escape not taken" is positive (+4.9), so if a
   decision defect exists anywhere in these four, it is here.

---

## 4. The seat — the half that had never run

| Weighting | Going first | Going second | Difference |
|---|---|---|---|
| Field | 95.45 % | 93.54 % | **+1.92 pp** |
| Top-100 | 96.43 % | 95.20 % | +1.23 pp |

**Going first is worth +1.92 pp across the meta, and +6.4 pp against our worst
matchup** — measured with opening rules that were tuned for the *other* seat and
with every `we_go_first` branch running for the first time. That is what the seat
is worth *unpolished*, and it is the strongest evidence available that
`8192c22` was the right call.

**Four archetypes where going first is WORSE**, and they are a real class rather
than noise:

| Archetype | Seat gap | Note |
|---|---|---|
| team_rocket_mewtwo | **−3.3 pp** | smallest sample here (n=180) |
| otro_empoleon_ex | −2.2 pp | n=180 |
| **festival_lead** | **−1.1 pp** | ⚠️ **5.02 % of the field, 11.11 % of the top-100** |
| otro_cornerstone_mask_ogerpon_ex | −1.1 pp | n=180 |

`festival_lead` is the one that matters: it is 11 % of the top-100, and it is also
**the near-mirror class** (§6). Against it, opening appears to cost us a point.

---

## 5. Per-archetype table

Field weight, top-100 weight, winrate, prize differential, seat split, and the
weakest individual list. Full data in `log/noche-2026-08-13-b/A0-perfil_arquetipos.txt`.

| Archetype | Field | Top-100 | Win | Prizes | 1st | 2nd | Gap | Weakest list |
|---|---|---|---|---|---|---|---|---|
| marnie_grimmsnarl | 37.55 % | 21.21 % | 96.9 % | +4.78 | 97.8 % | 95.9 % | +1.9 | marnie_grimmsnarl_8 93.3 % |
| alakazam | 17.87 % | 15.15 % | 95.9 % | +3.67 | 96.1 % | 95.5 % | +0.6 | alakazam_5 94.2 % |
| **crustle_wall** | 8.23 % | 2.02 % | **80.0 %** | **+2.32** | 83.2 % | 76.8 % | **+6.4** | crustle_wall_10 **71.7 %** |
| mega_lopunny_mega_froslass | 7.23 % | **16.16 %** | 97.6 % | +4.29 | 97.8 % | 97.4 % | +0.3 | …_2 94.4 % |
| dragapult | 6.43 % | 14.14 % | 98.2 % | +4.64 | 99.4 % | 97.1 % | +2.3 | dragapult_11 95.0 % |
| **ogerpon_verde** | 6.22 % | 6.06 % | **85.4 %** | **+2.14** | 88.1 % | 82.8 % | **+5.3** | ogerpon_verde_1 **80.9 %** |
| festival_lead | 5.02 % | 11.11 % | 97.3 % | +4.49 | 96.8 % | 97.9 % | **−1.1** | festival_lead_6 92.8 % |
| mega_lucario | 3.82 % | 7.07 % | 92.4 % | +3.34 | 93.5 % | 91.3 % | +2.3 | mega_lucario_3 88.9 % |
| cynthia_garchomp | 1.81 % | 0.00 % | 98.6 % | +4.55 | 99.2 % | 98.1 % | +1.0 | …_3 97.8 % |
| mega_kangaskhan | 1.41 % | 4.04 % | 95.0 % | +4.49 | 95.4 % | 94.6 % | +0.8 | …_6 93.4 % |
| mega_starmie | 0.60 % | 0.00 % | 85.9 % | +3.09 | 87.0 % | 84.8 % | +2.2 | mega_starmie_1 78.3 % |
| team_rocket_mewtwo | 0.60 % | 1.01 % | 95.0 % | +4.20 | 93.3 % | 96.7 % | **−3.3** | …_2 94.4 % |

**`mega_starmie` deserves a line despite its 0.6 %**: at 85.9 % it is the third
weakest archetype in the corpus, and `mega_starmie_1` at 78.3 % would sit inside
the worst ten lists. It is rare enough that it cannot pay for a rule, but a human
piloting into it should know it is a real matchup and not a free win.

---

## 6. Two facts about the corpus that change how to read all of the above

**Someone in the top-500 plays our exact list.** `festival_lead_5` overlaps
**60/60** with `deck.csv`, and six more Festival Lead lists overlap 50–58/60 —
**2.8 % of the meta**. Against those the reference bot pilots *our own engine*,
badly, so those matchups read as high winrates that are **not matchups**. They are
kept (people do play them) and flagged in `pesos.csv`. Any Festival Lead number
above, including its negative seat gap, carries this caveat.

**The top-100 rests on 38 lists, not 133.** Ninety-five admitted lists have zero
decks in the top 100. The top-100 interval (±0.25) is therefore wider than the
field's despite covering the same games, and its weights are the noisier half —
99 decks is a small denominator for a meta model.

---

## 7. Recommendations

Split as the plan requires: **piloting** (about play, testable as agent rules) and
**list** (about the 60 cards, proposed only — the list is frozen).

### Piloting

| # | Recommendation | Evidence | Status |
|---|---|---|---|
| P1 | **Take the first turn.** Keep `8192c22`. | +1.92 pp field, +6.4 pp vs Crustle, +5.3 vs Ogerpon Verde, zero forfeits in 26 590 first-seat games | **Confirmed by measurement.** Already shipped |
| P2 | **Aim the next work at Crustle Wall and Ogerpon Verde — but NOT with scoring rules.** | The only two archetypes under 92 % and under +2.4 prizes, together 14.45 % of the field. Track A: "stuck WITH an escape not taken" is flat (−0.2, +4.9) while "stuck with NO escape" is +8.6/+10.4 — the losses are starvation, not misplay | **Target confirmed, instrument refuted.** A scoring rule has a low prior here |
| P2a | **Against Crustle Wall, the clock is OUR DECK.** 28 % of those losses are deck-out. Pilot the matchup as a resource race, not a prize race: stop spinning the engine when the wall is up. | deckout 26/94, unique to Crustle; "no Grass in hand" +11.6; stuck streaks max 11 in losses vs 7 in wins | Ranked #1 for the field |
| P2b | **Against Alakazam, the failure is BENCH-OUT, not the prize race** — 52 % of its losses, at 17.87 % of the field. Keep bodies in reserve; supporters also go unspent (+30.4) in exactly those games. | bench_out 11/21 | Ranked #1 by weight × specificity |
| P2c | **Ogerpon Verde is the only place a decision defect plausibly lives** (+4.9 on "escape not taken", the only positive among the four). Read its losses by hand before writing anything. | 77.3 % of losing turns with no attacker ready, while supporters/attachments are spent MORE than in wins | Ranked #1 for climbing |
| P3 | **Prioritise by prizes, not winrate.** | 18 of 22 archetypes above 92 % — the winrate cannot rank them; prizes separate +2.1 from +4.8 | Method, adopt directly |
| P4 | **Decide the goal before optimising.** Climbing → Ogerpon Verde first. Holding field position → Crustle Wall first. | The loss ranking reorders completely between the two metas, and Crustle leaves the top-100 table | Decision for the deck owner |
| P5 | **Investigate why opening costs us against Festival Lead** (−1.1 pp at 11 % of the top-100). | Negative seat gap in a large-weight archetype, confounded by the mirror class of §6 | Open — measure with the mirror lists excluded |

### List (proposed only, never merged)

Nothing here is measured yet. The card-level census (track A3.3 — which of our 60
never gets played in a given matchup) is the block that would produce these, and
it had not completed when this document was written. **No list change is proposed
on the strength of winrates alone.**

---

## 8. What is measured here, and what is not

| Block | State |
|---|---|
| C1 corpus (500 → 135 → 133 admitted) | ✅ weights sum 0.9960, dominant list admitted |
| C2 band report | ✅ `log/noche-2026-08-13-b/C2-bandas.md` |
| C3 top-100 weights | ✅ `deck/real_opponents_500/pesos_top100.csv` |
| M1 baseline, 53 181 seeded games | ✅ |
| M2 both weightings | ✅ |
| M4 seat split, all 133 matchups | ✅ free, from counters that already existed |
| M3 continuity vs the 87-list corpus | ✅ headline unchanged, prizes identical |
| A1–A2 loss harvest + census with control group, 4 archetypes × 400 games | ✅ |
| A3–A4 failure classes and ranking | ✅ §3, and they refuted P2's instrument |
| A3.3 card-level census (which of our 60 never gets played) | ❌ **not run** — no tool exists for it; it needs instrumenting. This is why §7's list column is empty |
| A5 holdout (370 unlabelled extras) | ❌ **not run** — cut per §7's order (it is the most droppable block) |
| H1 measured piloting hypotheses | ❌ **not run**, and now deliberately: track A's negative result gives a scoring rule a low prior. Writing one tonight would have measured a hypothesis its own census argues against |
| H2 list hypotheses | ❌ **not run** — depended on A3.3 |

**What is missing and why it matters.** The list recommendations (§7's second
table) are empty, and that is a real gap rather than a tidy conclusion: the
card-level census that would fill them does not exist as a tool. Track A says the
two hard matchups fail through **starvation**, which is exactly the kind of
problem a list change addresses and a scoring rule does not — so the one block
that could have acted on tonight's main finding is the block that was never
built. **That is the top item for the next session.**

---

Next: [the plan](night-plan-2026-08-13-b.md) · [Matchups](matchups.md) · [Strategy](strategy.md) · [Instruments](instruments.md)
