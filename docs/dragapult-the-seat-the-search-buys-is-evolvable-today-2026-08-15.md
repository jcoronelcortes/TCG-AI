# The seat a search buys is evolvable today (Budew/Dragapult, step 22)

*User question, 15 August 2026, on `records/registro_003_pasos_019_hasta_029.json`
(episode 93495939 vs Budew/Dragapult — **won**): "the Forest of Vitality is in
play and we hold a Poké Pad, a Dipplin and a Hydrapple ex. Why did it not search
for an Applin to evolve into Dipplin and then into Hydrapple ex using the
stadium?"*

## The board

```text
US (6 prizes)                          RIVAL (6 prizes)
active  Teal Mask Ogerpon ex, 1 {G}    active  Budew 30/30
bench   Teal Mask Ogerpon ex x2        bench   Dreepy x4
hand    Unfair Stamp, Lillie's
        Determination, Xerosic's,      stadium OUR Forest of Vitality
        DIPPLIN, HYDRAPPLE ex,                 (played this turn, step 20)
        POKE PAD

    [0] PLAY Lillie's Determination   <-- played
    [1] PLAY Xerosic's Machinations
    [2] END
```

`Forest of Vitality`: *each player's {G} Pokémon can evolve into {G} Pokémon
during the turn they play those Pokémon, except during their first turn.*
`Poké Pad`: *search your deck for a Pokémon that doesn't have a Rule Box, reveal
it, and put it into your hand.*

So the line the question describes is real and it is a **Stage 2 in one turn**:
Pad → Applin → bench it → Dipplin → Hydrapple ex, with two Applin still in the
deck and two free bench seats. The Pad is also the *only* card in that hand that
can buy the bottom of the line, because the Ultra Ball and the Hydrapple ex are
Rule Box cards and the Pad is the one that reaches a non-Rule-Box Basic.

## First answer: at step 22 the agent declined nothing

Their Budew's *Itchy Pollen* had the Item lock on, and the record's own menu is
the proof — the two Items in hand are simply not among the options:

| hand index | card | in the menu? |
| ---: | --- | --- |
| 0 | Unfair Stamp (Item) | no |
| 1 | Lillie's Determination | **yes** |
| 2 | Xerosic's Machinations | **yes** |
| 3 | Dipplin | no (nothing to evolve) |
| 4 | Hydrapple ex | no (nothing to evolve) |
| 5 | **Poké Pad (Item)** | **no** |

The same holds for step 23, one action later: the refilled hand carries the Pad
again and the menu still offers only the two Pokémon it can bench. The Pad was
unplayable for the whole turn, so no search was passed over. (This is the same
lock, on the same Budew, that
[a veto that defers to a locked Item](dragapult-the-locked-item-is-not-the-better-play-2026-08-15.md)
was written from.)

Which leaves the Lillie's Determination the agent *did* play — it shuffled the
Dipplin, the Hydrapple ex and the Pad back into the deck and drew eight, and
that was the right call on a turn where all three were cardboard.

## Second answer, and the real one: the reading behind the question was missing

The board still exposes a rule the agent did not have. **Every "rush" rung in
the package asks for the pre-evolution to be already ON THE BOARD** —
`c.field.get(Applin, 0) >= 1` — and none of them asks the same question of a
seat the search itself is about to buy out of the deck. Four of the five
searchers paper over it with a rung of their own:

| searcher | rung | says |
| --- | --- | --- |
| Ultra Ball | `_v_ub_applin_arrancar` | **980** with Forest + Dipplin + Hydrapple ex in hand |
| Bug Catching Set | `_RULES_BCS_APPLIN.line_from_scratch_rush` | 850 |
| Dawn | `_RULES_DAWN_APPLIN.rush_with_dipplin` | 830 |
| Night Stretcher | `_ESC_NS_RECUPERACION.applin_combo_completo` | 980 |
| **Poké Pad** | — | **nothing** |

And on the Pad the absence is not a missing bonus, it is an **inversion**. Its
fetch ladder fell through to the last rung it has:

```text
Forest in play | hand: Dipplin + Hydrapple ex | nothing of either line on the board

  Applin       650   ['fb_applin=650']        <-- becomes a Stage 2 this turn
  Chikorita    800   ['fb_chikorita=800']     <-- becomes nothing this turn   -- WINS
```

Its play scorer told the same story from the other side: `_pp_evo_value` returned
0, so `evolution_this_turn` never fired and the Pad was priced in the
development band (`secure_chikorita` 12800) instead of the assembly band
(23000).

## The correction

Two helpers in `ptcg/cards/lines.py`, both deck-agnostic by construction —
neither reads `EVO_LINES` or knows what our sixty cards are:

* `_line_climb_from_hand(card_id, hand_counts) -> (steps, top_id)` — how far up
  its own chain the HAND alone would carry a body the moment it lands. The
  **mirror image of `_evo_body_in_play`**: that one asks what a card in hand can
  be worn by, this one asks what a body can be dressed in. Links come from
  `_direct_evolution_ids`, the reverse index of `evolvesFrom` over the whole
  card database.
* `_line_in_play_from(card_id, field_counts)` — is any body of that chain, from
  the candidate up, already standing? The guard the other rungs spell out per
  deck (`field.get(Applin) + field.get(Dipplin) + ... == 0`), written once and
  matched by NAME. With a body already up, the pieces in hand have a seat
  *without* the search and buying a second Basic is development, not the turn.

And two call sites in `ptcg/decision/poke_pad.py`, one sentence between them:

* `_pp_seat_the_hand_completes` feeds `_pp_evo_value`, so a two-step climb
  prices with the 1100 band (`evolution_this_turn`, 23000) and a one-step climb
  with 950.
* `rush_seat_the_hand_completes` in `_RULES_PP_FETCH`, `790 + 70·steps`, placed
  at the end of the direct-evolution block: **930 / 860**, under
  `evo_bayleef_rush` (950) and `evo_meganium` (1000) — which reach the same
  Stage 2 without spending a bench seat and three plays — and over every `fb_*`
  fallback, which reach nothing today.

The stadium question is asked once, by `_pp_forest_this_turn`, in the reading
`_v_ub_applin_arrancar` already uses: on the field **or still in hand**. Both
halves call it, because two halves of one rule that read the board separately is
[the trap `_ld_supp_comprometido` documents](mega-lucario-the-cost-keeps-the-supporter-the-turn-plays-2026-08-15.md).

### The tie-break is stated, not inherited from the menu

Two complete lines in one hand is not a rare board. The frozen corpus holds one
— `registro_001_alakazam_10_asiento1`, turn 8: Dipplin **and** Hydrapple ex
**and** Bayleef **and** Meganium in hand, one bench seat, Applin and Chikorita
both offered by the search — and the first version of the rung scored both at
930, so the winner was whichever the simulator listed first. That produced the
one corpus flip the change had, and a flip decided by menu order is not a
decision.

The line that ends in the **Grass doubler** goes first (+12,
`GRASS_DOUBLER_LINE_IDS`, derived rather than written out). It is the order
`chikorita_combo_completo` (990) already states over `applin_combo_completo`
(980) one ladder over: Wild Growth pays for every other body on the board, and
the other Stage 2 does not. With the order stated the corpus flip disappears —
the change becomes purely **additive**, firing only where nothing fired before.

## The numbers

| measurement | result |
| --- | --- |
| suite | 3 017 passed, 25 skipped |
| frozen corpus (`--census`, two arms) | **0 of 3 580 decisions** |
| golden corpus (`records/`) | 0 flips |
| `lint_architecture` / `purity` | clean |
| live exposure (`rule_census.py`, 150 games each) | dragapult **0.033**, alakazam **0.040**, crustle_kangaskhan **0.027** fetches/game; comfey 0.000 (the Pad's fetch chain never ran at all there) |

The census warning applies and is worth repeating: at ~0.03/game the winrate
gate cannot resolve this, and the honest report is the exposure plus a clean
corpus. The gate rows below are recorded for the same reason every other entry
records them — a row without its `--control` at the same N is not a reading.

```text
REAL      (n=15 000 por brazo, 5 000 x 3 listas)
  dragapult            97.66%  vs  97.96%   -0.30 pts  z=-1.02  p=0.305   premios 4.17 vs 4.14
  alakazam             99.42%  vs  99.44%   -0.02 pts  z=-0.13  p=0.894   premios 3.46 vs 3.49
  crustle_kangaskhan   78.20%  vs  78.58%   -0.38 pts  z=-0.46  p=0.644   premios 4.28 vs 4.31
  AGREGADO             91.76%  vs  91.99%   DELTA -0.23 pts  z=-0.74  p=0.460

CONTROL   (--control: MISMO codigo en los dos brazos = suelo de ruido de esta corrida)
  dragapult            97.56%  vs  97.38%   +0.18 pts  z=+0.57  p=0.567
  alakazam             99.62%  vs  99.54%   +0.08 pts  z=+0.62  p=0.536
  crustle_kangaskhan   78.42%  vs  78.12%   +0.30 pts  z=+0.36  p=0.716
  AGREGADO             91.87%  vs  91.68%   DELTA +0.19 pts  z=+0.59  p=0.556
```

**The gate is blind to this and its own control says so.** The candidate's
aggregate is **−0.23 pts**; the noise floor measured on the same run, with the
same code in both arms, is **+0.19 pts**, and every per-deck row of the real arm
(−0.30 / −0.02 / −0.38) sits inside the spread the control produces from nothing
(+0.18 / +0.08 / +0.30). The sign is not informative: at ~0.03 fetches/game,
15 000 games per arm buy an SE far larger than the effect could be, and 45 000
games would only halve it. Zero forfeits in all four arms.

So this entered **NEUTRAL by winrate**, and what it is kept on is the board:
`fb_chikorita` 800 taking the fetch from `fb_applin` 650 is wrong on its face —
the card that scored 150 lower becomes a Stage 2 before the turn ends and the
one that won becomes nothing — and four of the five searchers already say so in
their own words. It is a consistency fix, not a source of new plays, which is
also why the corpus is untouched.

## What this is not

* **Not a defect at step 22.** Nothing was declined there; the Item lock had the
  Pad out of the menu, and the test asserts that first so nobody re-opens the
  file thinking the agent passed on a search.
* **Not measurable from `records/` any more, and that is the point of the
  fixture.** A harvest on the same afternoon replaced episode 93495939 in
  `log_analisys/` and renumbered every file under `records/`, so a test keyed on
  `registro_003_pasos_019_hasta_029.json` began *skipping* rather than failing —
  the exact shape of "a test that pins the NAME of a transient record breaks
  when you harvest". The observation lives in
  `tests/fixtures/the_seat_the_search_buys_step22.json` instead.
* **Not the cause of the local golden-corpus flip** seen the same afternoon
  (`registro_001 paso 7`, Chikorita → Meowth ex). That flip reproduces with this
  change stashed out, and the two-arm replay over the whole current `records/`
  set reports **0 of 40** decisions changed by the rule. It belongs to the
  harvest, not here.
* **Not a change to the other four searchers.** The Ultra Ball, the Set, Dawn
  and the Night Stretcher already carry the sentence; what they carry is
  hard-coded per line, and the two new helpers are what a later pass would use
  to fold them into one reading. That pass is not this change and is not
  measured here.
