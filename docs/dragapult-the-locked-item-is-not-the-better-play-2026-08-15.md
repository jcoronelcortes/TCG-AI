# A veto that defers to a locked Item defers to nothing (Budew, turn 14)

[← Documentation index](README.md)

Episode 93229766 vs a **Budew / Dragapult** list, **LOST**. Our first attack of
the whole game landed on **turn 18**: eight of our own turns — 2, 4, 6, 8, 10,
12, 14, 16 — ended without one. The user pointed at step 39 (turn 8). The defect
is on **turn 14**, and turn 8 is the board that says why the two are not the
same.

---

## The turn that was thrown away

**Turn 14** — `records/registro_014_pasos_051_hasta_051.json`

```
US (6 prizes)                          THEM (6 prizes)
active  Chikorita 20/70, 0 energy      active  BUDEW 30/30
bench   Applin 30/40, 0                bench   Fezandipiti ex 210
        Applin 40/40, 0                        Munkidori 110, Munkidori 110
        Teal Mask Ogerpon ex, 3 {G}            Dreepy 70
        Teal Mask Ogerpon ex, 1 {G}    stadium Forest of Vitality (OURS)
hand    Poké Pad, Chikorita, Night Stretcher, Xerosic's Machinations,
        Poké Pad, BUG CATCHING SET, MEOWTH EX, Fezandipiti ex
deck    35 cards, Lillie's Determination still among them
```

The menu, and what the agent scored:

```
[3] END              0   <-- played
[0] PLAY Chikorita  -1   the Meganium line cap (one already on the board)
[1] PLAY Meowth ex  -1   <-- the defect
[2] PLAY Fez ex     -1
```

**The turn was frozen on three axes at once**, and only one of them was ours:

* their Budew declared *Itchy Pollen* last turn, so **no Item can be played**:
  both Poké Pad, the Night Stretcher and the Bug Catching Set are dead cards;
* their hand was **empty**, so Xerosic's Machinations had no legal target and
  the engine did not even offer it;
* our own Chikorita stood in front with **no energy and a retreat cost of one**,
  so it could neither attack nor step aside — and the Teal Mask Ogerpon ex
  holding **three** Grass was stranded on the bench behind it.

One card in hand still did something. *Last-Ditch Catch* searches the deck for a
Supporter when the Meowth ex is played onto the bench; the deck still held a
Lillie's Determination, and at six prizes that Supporter draws **eight** cards.

---

## What vetoed it

`ptcg/turn/options/play.py`, the Meowth branch:

```python
elif _bcs_playable_in_hand and bench_count >= 1:      # "play the Set first"
    score = SCORE_VETO
```

The rule is sound — a Bug Catching Set digs cheaper than a two-prize body does.
It just was not true here: the Set could not be played at all.

Four branches further down sits the rule written for exactly this board:

```python
elif (_active_cant_attack_this_turn and not state.supporterPlayed
      and hand_counts[Lillie_Determination] == 0
      and Lillie_Determination in the deck):
    score = 21800
```

**The ladder never reached it.** The turn ended with END, eight cards in hand,
none of them playable, and the Chikorita died two turns later.

---

## The cause, in one word

`_bcs_playable_in_hand` ([main.py](../main.py)) asked two questions — is there a
Set in hand, is there anything left in the deck for it to find — and never the
third: **can an Item be played this turn at all**.

The agent already knows the answer. `itchy_pollen_active` collects all three
sources of the lock (Budew's Itchy Pollen, Galvantula ex's Fulgurite, and an
opposing active of `OP_ITEM_LOCK_ACTIVE_IDS`), and the **other two consumers of
the pair already ask it by hand**:

| where | reads the lock |
| --- | --- |
| [ptcg/turn/options/attach.py](../ptcg/turn/options/attach.py) `:291` | `if _bcs_playable_in_hand and not itchy_pollen_active and …` |
| [ptcg/decision/bug_catching_set.py](../ptcg/decision/bug_catching_set.py) `cap_if_pokepad_playable` | `w.pp_playable_in_hand and not w.itchy_pollen_active` |
| the Meowth branch of `play.py` | — |

The one that forgot is the one that cost the game. So the lock moves into the
**flag**, where every reader inherits it — the general rule before its special
case ([[la-regla-general-va-antes-que-su-caso-especial]]) — rather than being
restated a third time at the call site.

`AN_ITEM_UNDER_A_LOCK_IS_NOT_A_PLAYABLE_CARD` ([main.py](../main.py)) is the
named switch, for the same reason as the five flags above it: it is the only
difference the census, the gate and the rules oracle put between two arms.

It is **deck-agnostic by construction**. There is no archetype and no card name
in the correction: it is one word of the word *playable*, and it holds for any
list that runs Items against any list that locks them.

---

## Turn 8 is not the same board, and the engine says so

Step 39 — the board the report started from — looks identical: same frozen
active, same locked hand, same Meowth ex, and the agent ends the turn. It was
**right** there, and the difference is one card:

```
stadium  Team Rocket's Watchtower (THEIRS)
         "{C} Pokémon in play (both yours and your opponent's) have no Abilities."
```

Meowth ex is a {C} Pokémon (`card_table[1071].energyType == COLORLESS`), so
*Last-Ditch Catch* does not exist while that stadium is up. Benching it there
would have handed over a two-prize body for nothing.

**Measured against the engine, not argued.** Forced through `search_begin` from
that exact observation, playing the Meowth ex produces a bare `PLAY` log and a
menu of one option — END — with no ability prompt. Across roughly two hundred
Meowth ex plays in `records/` and `log/` **without** that stadium, the prompt
after the play is always the `YES/NO` of the ability (`select.context == 43`),
and the Watchtower appears at none of them.

Our own Forest of Vitality replaced that stadium on **turn 12**. The correction
therefore leaves turn 8 alone and changes turn 14 — the guard for that is a test
of its own — and the agent's own veto chain gets the Watchtower right two
branches above the one that was wrong.

The search-oracle reading of turn 8, for the record (random policy, K = 2 000,
per-batch floor ≈ 2–3 pp): bench the second Chikorita **19.9 %**, END **18.4 %**,
bench the Meowth ex **18.1 %** — the Meowth is the worst of the three, which is
what a muted ability plus two extra prizes should look like. Under the agent
policy the oracle is **blind** (100/100 on all three arms) and says so.

---

## What was checked and did NOT hold

The obvious upstream suspect was **turn 10**, the one turn of the eight that had
energy to spend. Teal Dance put the hand's Grass on a benched Ogerpon ex and
drew a second one; the manual attachment then went to the **same** benched body,
taking it to three, while the option to attach to the frozen active — the key to
its retreat — was scored and lost:

```
[5] attach → bench Ogerpon ex (2 → 3)   9000   <-- played
[7] Teal Dance on the other Ogerpon     7500
[2] attach → ACTIVE Chikorita           7000
```

It reads like `LISTO ≠ UTILIZABLE`: a body charged behind an active that cannot
step aside is not an attacker. **The measurement disagrees.** Search oracle,
random policy, K = 1 500 per arm, two independent seed bases:

| | seed 1000 | seed 7000 |
| --- | --- | --- |
| third Grass on the bench body (played) | **25.9 %** | **25.8 %** |
| one Grass on the active (the retreat key) | 24.1 % | 22.7 % |

The retreat **discards** the energy that pays it, so that line spends a Grass to
arrive at an Ogerpon holding two instead of three; letting the 70 HP Chikorita
die as a shield and promoting for free — which is what happened on turn 17 — is
the better half of the trade. No change was made and the reason is written here.

---

## The measurements

**Corpus.** 1 flip in the local records — turn 14, `END` → `PLAY Meowth ex`, the
decision this was written for — and **0 of the 3 580** frozen decisions. Full
suite green (2 935 passed).

**Census** (`utils/census_an_item_under_a_lock_is_not_playable.py`, 300 games vs
`dragapult_1`, both seats):

| | per game |
| --- | --- |
| decisions of ours | 134.99 |
| Items locked this turn | 0.737 |
| **…and the old flag claimed the Set as playable** | **0.063** |
| decisions the correction flips | 0.000 |

The criterion was written before the run and not moved: `claimed ≥ 0.05 per
game`. It **passes** at 0.063 — roughly one board every sixteen games.

**Gate** (`utils/gate_an_item_under_a_lock_is_not_playable.py`, 400 games,
shared seeds): `delta +0.00 pp, z +0.00, p 1.000`. Predicted, and worth stating
plainly: with `flip = 0.000` in self-play the two arms play the same games, so
the winrate cannot resolve this and never could.

**So it is NEUTRAL, and it is kept anyway.** The policy that governs that is
`politica-neutro-se-revierte-salvo-valor-ilegal`: a neutral rule is reverted
unless the value it corrects was **wrong**, not merely worse. This one was — the
flag reported a card as playable that the engine would refuse — and the board it
was found on is a real game we lost with eight cards in hand.

The gap between `claimed` 0.063 and `flip` 0.000 is the honest shape of the
finding: the reading is wrong on one board every sixteen games, and it only
changes a decision when a Meowth ex is in hand on a turn that cannot attack.
Self-play against the reference bot did not produce that conjunction in 300
games. A real opponent produced it in one.

---

## Files

| | |
| --- | --- |
| the flag | [main.py](../main.py) — `AN_ITEM_UNDER_A_LOCK_IS_NOT_A_PLAYABLE_CARD`, `_bcs_playable_in_hand` |
| the test | [tests/test_the_locked_item_is_not_the_better_play.py](../tests/test_the_locked_item_is_not_the_better_play.py) |
| the fixture | `tests/fixtures/locked_item_is_not_the_better_play_turn14.json` |
| the census | [utils/census_an_item_under_a_lock_is_not_playable.py](../utils/census_an_item_under_a_lock_is_not_playable.py) |
| the gate | [utils/gate_an_item_under_a_lock_is_not_playable.py](../utils/gate_an_item_under_a_lock_is_not_playable.py) |
