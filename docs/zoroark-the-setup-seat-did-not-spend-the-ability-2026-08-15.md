# The seat the setup gave did not spend the ability (Ultra Ball, turn 1)

[← Documentation index](README.md)

Our opening turn had no attacker and nothing to develop: two Stage 1s in hand with
nothing to sit on. The agent played the Ultra Ball **at the right price** — 31450,
the price of the *UB → Meowth ex → Last-Ditch Catch → Lillie's* engine — and then
the fetch menu of that same Ultra Ball bought a **Chikorita**. `ub->meowth` had
scored **10**, through `last_ditch_produces_nothing`.

The reason is one line: our starting active *was* a Meowth ex, and everything the
**setup** deals carries `appearThisTurn` on turn 1. `_meowth_ld_free` read that as
"a Meowth appeared this turn, so the turn's only Last-Ditch is already spent" —
about a body that never used it. **The setup plays nothing.**

---

## The board

`records/registro_001_pasos_005_hasta_010.json`, steps 5–10, turn 1, episode
93488655 vs **Zoroark ex** — **LOST**. Six prizes each, we go first.

```
US (6 prizes)                          THEM (6 prizes)
active Meowth ex 170/170, 0 en.        active N's Zekrom 70/70
bench  --                              bench  --
hand   Xerosic's Machinations          stadium --
       Forest of Vitality ×2
       ULTRA BALL                      turn 1, WE GO FIRST
       Basic {G} Energy                (no Supporter may be played)
       Bayleef, Dipplin

    [1] PLAY Forest of Vitality
    [2] PLAY Ultra Ball      score 31450   <-- played
    [3] PLAY Forest of Vitality
    [4] ATTACH Basic {G}
    [5] END
```

Neither Stage 1 in hand has a body to evolve, no Basic can be benched, and the
first player may not play a Supporter on turn 1 — the engine's own menu proves it,
the Xerosic in hand is not among the options. So the whole turn is the Ultra Ball,
and the whole Ultra Ball is **what it fetches**.

What it fetched, and the rest of the turn: Chikorita → benched → the turn's energy
onto it. Turn ends with a lone 70 HP Basic and four cards in hand that cannot be
played.

---

## What the two menus of one card said

| menu | consumer | answer |
|---|---|---|
| **play** (step 5) | `_ub_engine_refresh_pivot` | **31450** — the UB is bought FOR the Meowth engine, and scoring it arms `_ub_engine_pivot_turn` so the fetch completes the chain |
| **fetch** (step 7) | `_RULES_UB_MEOWTH` | **10** — `last_ditch_produces_nothing` |
| | `_RULES_UB_CHIKORITA` | 1050 — `t1_going_first_needs_a_basic` ← chosen |

That contradiction is the exact failure `ptcg/decision/ultra_ball.py` warns about
in its own header (*"the decision to play the Ultra Ball and the later decision of
what it fetches happen at DIFFERENT MENUS … both must reach the same
conclusion"*). The engine flag `_ub_engine_pivot_turn` was armed the whole time
and never got asked: `last_ditch_produces_nothing` sits **above** `engine_pivot_turn`
in the ladder, and rightly so — a rule that says the ability cannot produce
anything must outrank every engine. It was simply answering the wrong question.

Below it, four more rungs would have bought the Meowth on this board —
`develop_the_only_pokemon` (1250, *the only Pokémon in play, no playable Basic, no
Lillie's in hand*), `no_attacker_prefers_meowth`, `engine_pivot_turn`,
`lillie_in_deck_refresh`. Every one of them was unreachable behind the same false
reading.

---

## What the log actually says

The engine distinguishes the two events, and never puts both on one serial:

| event | log |
|---|---|
| the SETUP seats the starting active | `MOVE_CARD` · `fromArea` HAND → `toArea` ACTIVE |
| we PLAY a body from hand | `PLAY` |
| an effect puts a body down from the deck | `MOVE_CARD` · DECK → BENCH |
| a promotion or a retreat | `MOVE_CARD` · BENCH ↔ ACTIVE |

On the record, serial 20 (the Meowth ex) has **one** MOVE_CARD hand→active and
**no** PLAY. Its Last-Ditch Catch never fired — no Supporter was searched at
setup, which is also visible in the step-5 hand.

---

## The change

Two lines of reading and one field of state, none of them naming a card:

* `AGENT_STATE._in_play_without_a_play` ([ptcg/state/agent_state.py](../ptcg/state/agent_state.py))
  — the serials of OUR bodies that reached play **without being played**. Filled
  in [main.py](../main.py) from the log batch: a `MOVE_CARD` into ACTIVE/BENCH
  whose `fromArea` is *not* an in-play area adds the serial; a `PLAY` removes it.
  It scans the **whole batch** and not the per-turn slice, because the setup lines
  are logged before the first `TURN_START` — and it is a fact of the GAME, so
  nothing resets it.
* `_meowth_ld_free` now asks for `appearThisTurn` **and** a seat that was played
  for.

`fromArea` is what decides, and that is the load-bearing half: a promotion after a
knockout and a retreat are MOVE_CARD entries into the active spot too. Counting
those would hand the turn's ability back to a Meowth we played and then promoted
— two prizes given away for an ability that does not run, which is the expensive
direction of the same mistake.

**Deck-agnostic by construction**: the rule is written about the LOG, not about
Meowth ex. Any come-into-play ability, in any list, gets the same answer from the
same set — and so does any future card that puts a body into play from the deck.

---

## The numbers

**Corpus**, two arms walked side by side with the memory switched off in one:

| corpus | our decisions | flips |
|---|---|---|
| `records/` — the harvested games on disk | 18 (9 records) | **1** |
| `tests/corpus/` — the frozen fifty | 3 580 (50 records) | **0** |

The single flip is `registro_001` step 7, `[0] Chikorita → [1] Meowth ex` — **the
board the user reported, and nothing else.**

**Firing census** (`utils/gate_the_setup_seat_did_not_spend_the_ability.py --census`,
60 seeded games × 3 lists, the candidate driving with the neutralised arm
shadowing every frame):

| list | decisions read differently | games touched | decisions CHANGED |
|---|---|---|---|
| `dragapult` | 34 | 5/60 (8.3 %) | 0 |
| `alakazam` | 34 | 5/60 (8.3 %) | 0 |
| `crustle_kangaskhan` | 30 | 5/60 (8.3 %) | **2** (one game) |

**0.54 decisions per game are read differently and 0.01 change** (2 of 9 663).
That is the honest shape of it: our starting active is the ability's own body in
about **one game in twelve**, and only on the openings that have no other
development does the reading move a card. The census prints its own warning, and
it means it — at that exposure a winrate cannot resolve this.

**The rules oracle on the accused board**
(`utils/oracle_the_setup_seat_did_not_spend_the_ability.py`, K=100 × 3 batches per
option, rival list identified as `otro_ns_zoroark_ex_1`, 100 % of their visible
board):

| their seat plays | Meowth ex | Chikorita | delta | board floor |
|---|---|---|---|---|
| **our agent** | 99.3 % · margin **+5.02** | 98.7 % · margin +3.13 | **+0.7 pp / +1.89** | 1.0 pp / 0.67 → **clears** |
| random | 99.7 % · margin +4.35 | 99.7 % · margin +4.85 | +0.0 pp / −0.50 | 1.0 pp / 0.29 → clears |

**The sign flips with the opponent's policy, and that is the reading, not a
defect.** Against a random seat the refill buys nothing — nobody punishes a dead
hand — so all that is left of the play is its cost, the two-prize body we put on
our own bench, worth half a prize of margin. Against a seat that plays our own
agent the refill is worth **nearly two prizes of margin**. The winrate is
saturated in both (≈99 %) and grades nothing here.

**Winrate** (`utils/gate_the_setup_seat_did_not_spend_the_ability.py --games 300`,
three lists, 900 games per arm), with its `--control` run at the SAME N — a row
without one is not a reading:

| row | dragapult | alakazam | crustle_kangaskhan | aggregate |
|---|---|---|---|---|
| candidate | +0.67 pp | +0.67 pp | +3.33 pp | **+1.56 pp** (z 1.25, p 0.21) |
| **control** (same code both arms) | −1.67 pp | +0.00 pp | **+3.67 pp** | +0.67 pp |

**Inside its own noise floor and reported as such.** The control's crustle row
(+3.67 with identical code) is larger than the candidate's (+3.33): at 0.01
decisions changed per game there is nothing here for a winrate to find, and more
games would not change that. What the run is really watched for is forfeits and
crashes — **0/0 everywhere**.

**Live, seeded**: seed 4 of `utils/selfplay.py` (starting active = Meowth ex) now
plays the whole chain on turn 1 — `PLAY Ultra Ball → FETCH Meowth ex → PLAY Meowth
ex → Last-Ditch Catch → FETCH Lillie's Determination`. The Lillie's is not played
that turn and cannot be: the first player has no Supporter on turn 1. It is bought
for the next turn, which with six prizes still up draws **eight** cards.

---

## Status

Suite green (3 016 passed, 25 skipped), corpus snapshot accepted with the single
intended flip. Pinned by
[tests/test_the_setup_seat_did_not_spend_the_ability.py](../tests/test_the_setup_seat_did_not_spend_the_ability.py)
— the record's own logs, the three entries into play that are not plays
(promotion, retreat, a PLAY on the same serial), the fetch, and the control that
says the reading is the cause: the same board with a **PLAY** log on that serial
goes back to buying the Chikorita.

**Left standing, on purpose**: the play-side `_eval_ub_best_target` still returns
early on turn 1 going first and offers Meowth ex only against Budew — and that
early return also asks `field_counts.get(Meowth_ex, 0) == 0`, the same proxy for
"the ability is spent" that this finding is about. On the record it did not bite
(the Ultra Ball was bought by the pivot engine at 31450, above that block), so it
is written down rather than changed: a second reading, with its own board and its
own measurement.

---

Related: [The promotion is the seat the search
completes](lucario-the-seat-the-search-completes-2026-08-14.md) · [A full bench is
not a second attacker](a-full-bench-is-not-a-second-attacker-2026-08-15.md) · [The
body search cannot buy the
energy](festival-lead-the-body-search-cannot-buy-the-energy-2026-08-15.md)
