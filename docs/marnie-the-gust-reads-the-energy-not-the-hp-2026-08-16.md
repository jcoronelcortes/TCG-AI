# The gust reads the energy, not the HP — and it reads it in **both** chains (Marnie, step 173)

*Episode 93680377 step 173, turn 14 vs Marnie — **won in spite of this**.
Boss's Orders already played; this is the target select.*

```text
US (seat 1, 2 prizes)                RIVAL (4 prizes)
active Hydrapple ex 280/330, 2G      active Munkidori 90/110, 1D
bench  Ogerpon ex 4G, Hydrapple ex,  bench  [0] Munkidori 100/110, 0e
       Ogerpon ex 2G, Ogerpon ex 1G,        [1] Munkidori 100/110, 1D
       Fezandipiti ex                       [2] Marnie's Morgrem 1D
                                            [3] Froslass 90/90
                                            [4] Marnie's Morgrem 1D
```

The agent brought up index 0 — the **bare** Munkidori.

## The HP was not the cause

Both benched Munkidori were at **exactly** 100/110; the one at 90 was their
active, which is not on the menu. The real trace:

```text
idx 0  Munkidori bare      3450 -> 15600   <- chosen, BY POSITION
idx 1  Munkidori charged   6450 -> 15600
idx 3  Froslass            9600 -> 15400
```

[`marnie_the_engine_before_the_line`](marnie-the-engine-goes-before-its-line-2026-08-16.md)
did `max(s, 15000 + rank[card_id])` with **one single number per species**: the
two tied, and the argmax kept the first one on the bench. Note the `tier_ko` the
`max` throws away — **6000 against 3000**: the chains already knew which body was
the more developed one. **The floor is what flattened them.**

## The ladder

`_marnie_engine_rung`, in `ptcg/decision/boss_orders.py`:

```text
Munkidori WITH energy (1600) > Froslass (1200) > Munkidori WITHOUT energy (800)
                             > Snorunt (400)
```

and inside a rung, the **lowest current HP**. One ladder answers both of the
user's sentences because the Froslass sits **between the two halves of the
species**: *"Munkidori outranks Froslass when at least one Munkidori has
energy"*, and *"with only bare Munkidori on the board, the Froslass first"*.

*Adrena-Brain* costs no energy and a bare Munkidori fires it too, so the cut is
**not** about the ability. It is about which of the two copies already has its
turn assembled: the charged one also **attacks from the seat we are selling it**,
while the bare one is a body they still have to pay for.

### The HP does not choose a rung

The tie-break is worth at most **39** (`MARNIE_ENGINE_HP_TIEBREAK_MAX`), far
below the 400 that separate two rungs, so no amount of damage lifts a bare
Munkidori over a Froslass or a Froslass over a charged Munkidori. It only
separates bodies that already tied on everything the chains read — which is
exactly the pair this record put on the table. The candidate ctx gains an `hp`
field with that single use and a default of 999: **what cannot be measured goes
to the end of its rung, not the front**.

Switch: `MARNIE_ENGINE_READS_THE_ENERGY` (False = the previous flat ladder).

## Second half: the jam chain was carrying half the matchup

`ptcg/turn/options/card.py` routes the menu **by our own active**: if it cannot
attack, the same menu is resolved by `_ADJUST_GUST_NUISANCE`, where the engine
rung **did not exist**. The matchup does not change with our active, and that
chain was reading the board **backwards**, and worse than the offensive one ever
did:

```text
Marnie's Morgrem   9050   `opponent_line_higher_evolution` (Stage 1 + 1e)
Froslass           9000   the same step: Froslass is ALSO a Stage 1
Munkidori bare    ~2100   `net_stuck` 600 + 1500 for being harmless
Munkidori charged  -200   pays its own retreat: the defect
```

That is the line rule this sentence exists to override, **plus** the engine order
inverted on top, **plus** the record's own body **last of the five**. A rule that
only holds while our active happens to be usable is not a matchup reading — it is
an accident of which chain ran.

**One single `_Adjustment` object in both lists**, defined above them and with
its identity pinned by test (`is`). Two copies of this rule is exactly how the
matchup came to depend on our active in the first place.

### The invariant that nearly broke, caught by the suite itself

`test_with_the_seat_unlocked_the_rule_is_silent`: **the jam chain has no
`tier_ko`.** The ladder's band always ended with *"…and BELOW a two-prize
knockout: if the Grimmsnarl ex is on their bench and we can finish it, two prizes
beat cutting the engine"*. In the offensive chain `tier_ko` guarantees that for
free (a charged two-prize ex is 24000 against the engine's 16639 ceiling). Here a
knockout is priced by `opponent_line_higher_evolution`, which reads the **stage**
and is blind to what it pays: the Marnie's Grimmsnarl ex of `registro_008` p72 —
310/320, five energies, **two prizes**, and our benched Ogerpon does **540** to it
— comes out at `6000 + 2×3000 + 250 = 12250`, **below the engine floor**.

New bracket `the_bigger_prize_outranks_the_engine`: `15000 + 3000 + 1000 per
prize` = 20000 with two and 21000 with three. Above the engine ceiling and below
`_v_gust_relay_seat` (20000 + 2000 per prize, from 22000), which still rules,
because when their knockout is the only key to our own seat that trade beats the
matchup. It is gated on `marnie_engine_first` **on purpose**: it is the half this
ladder's own bracket was missing, **not** a general repair of that chain's
prize-blindness — that is a different change with a different measurement.

With the p72 board unlocked (three Grass on the Tapu Bulu: it cannot attack, but
it can retreat, which is the only state in which the engine has anything to say
there):

```text
with their Grimmsnarl ex benched   Grimmsnarl ex 20000  <- chosen
swapping it for a Morgrem          Munkidori charged 16630 > Froslass 16231
                                   > Munkidori bare 15832 > Morgrem 9250
```

## Measurement

| instrument | number |
| --- | --- |
| Full suite | 3 228 pass (25 in the new file, 9 of them jam-chain) |
| Golden corpus | **0 flips** |
| Replay of the records | **1 flip in 377 decisions** (3 complete games of `records/marnie/` plus this episode) — and it is the user's |
| Own census, n = 300 | **2 flips = 0.007/game**, both "bare Munkidori → Froslass". Leakage **0** vs `crustle_wall_1` |
| Parent census, n = 300 | from 7 flips (0.02/game) to **11** (0.04), and the exact sentence from 6/7 to 10/11. Leakage **0** |

The own census lands **below its written criterion** (0.01/game), and what is
missing is the interesting half: **not one flip of the record's own sentence**
(bare → charged) in 300 games. The bot does not build that board — it attacks
with the Munkidori it just attached to and rarely leaves the spare copy bare on
the bench — so the shape of *two copies tied on HP*, which the real opponent of
93680377 did put down, does not occur here. It is the same limit the parent gate
already documents from the other side: **the matchup the harness simulates is not
the matchup the rule was written for.** Against the records the answer is sharp,
and the golden corpus does not move.

Both new halves of the jam chain hang off `marnie_engine_first` and therefore off
`MARNIE_ENGINE_BEFORE_THE_LINE`, so the parent census measures them and that
switch remains the complete revert. The two censuses are not the same seeds with
one rung moved, so the doubling reads as an **order of magnitude and not a
delta**; what it does establish is that the jam chain was not a rare corner of
this matchup.

## The ambiguous case, pinned

In its own test so that changing it is a decision and not an accident: a charged
Munkidori that is **not gustable** — their **active**, which is exactly this
record's case — does **not** lift the bare ones. *"At least one Munkidori with
energy"* is about the body being **chosen**, not about a copy the Boss's cannot
buy.

## Files

* `ptcg/decision/boss_orders.py` — `_marnie_engine_rung`, the shared
  `_Adjustment`, the `the_bigger_prize_outranks_the_engine` bracket.
* `ptcg/cards/ids.py` — `MARNIE_ENGINE_READS_THE_ENERGY`,
  `MARNIE_ENGINE_GUST_RANK`, `MARNIE_ENGINE_HP_TIEBREAK_*`.
* `tests/test_marnie_the_gust_reads_the_energy_not_the_hp.py` ·
  `tests/fixtures/marnie_step174_el_gusteo_elige_el_munkidori_cargado.json`
* `utils/census_the_gust_reads_the_energy_not_the_hp.py` ·
  `utils/census_marnie_the_engine_before_the_line.py`
