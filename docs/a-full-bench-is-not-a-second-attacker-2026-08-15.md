# A full bench is not a second attacker (Last-Ditch Catch, turn 9)

[← Documentation index](README.md)

A Meowth ex went down — two prizes handed to the opponent — and its Last-Ditch
Catch bought a **Boss's Orders** on a board where nothing behind our dying
attacker could attack. The card that board was asking for was the refill.

---

## The board

Reported by the user (15 August 2026, turn 9 against a Marnie's / Froslass
list). It is reproduced **synthetically** in
[tests/test_a_full_bench_is_not_a_second_attacker.py](../tests/test_a_full_bench_is_not_a_second_attacker.py),
because what decided it is a *count* and not a card list.

```
US                                        THEM
active  Teal Mask Ogerpon ex 140/210,     active  a charged attacker that
        CHARGED — it attacks today                knocks our active out next
bench   Bayleef   (waiting for Meganium)          turn
        Applin    (waiting for Dipplin)   bench   two Froslass, dripping 10 a
        Teal Mask Ogerpon ex, ONE {G}             turn onto every body of ours
        of the three its attack costs             that has an ability
        Meowth ex, just benched
```

Four bodies behind the front and **not one of them can attack**. Our attacker
was one hit from being knocked out and there was nothing to take over — which is
the board the refill exists for.

---

## The cause, and it is a head count

The refill's band in `_RULES_MEOWTH_FETCH` is `lillie_development` (1250), fed by
`_meowth_devel_lillie` in [main.py](../main.py):

```python
_mdl_max_in_play = 4 if _mdl_hand_size <= 2 else 3
if _mdl_in_play <= _mdl_max_in_play:
    _meowth_devel_lillie = True
```

It measures **how full the bench is**. On this board it counted four bodies,
answered *"already developed"*, and the refill lost its band. The chain then fell
through to the tail — `supporter_value` — where the raw scale prices

```
Boss's Orders 850   >   Lillie's Determination 650
```

and the gust won a comparison the board never asked for. Reproduced exactly: on
the board above the trace reads `supporter_value=850` for the Boss's; move two
bodies off the bench and the same board answers `lillie_development=1250`.

Every one of those four bodies was a **card, not an attack**. This is the same
blindness `boss_beats_the_untouchable_active` was written for (a `strong_attacker`
that is a species reading, true on a board of bodies at zero energy) and the same
one `_a_body_can_attack_this_turn` exists to replace: **listo is not utilizable**.

---

## The rule

`the_gust_without_a_reason_yields_to_the_second_wave`, in
[ptcg/decision/meowth.py](../ptcg/decision/meowth.py), just under
`lillie_development`:

```python
_FixedRule("the_gust_without_a_reason_yields_to_the_second_wave",
           lambda c: (c.lone_ready_attacker      # _ready_attacker_count <= 1
                      and c.active_doomed        # _active_doomed_real
                      and not c.first_turn
                      and c.card_id == Boss_Orders),
           lambda c: min(c.sv, 40)),
```

**Two premises, and the play half of this same engine already reads both.** The
engine decides twice — [play.py](../ptcg/turn/options/play.py) decides whether to
spend two prizes benching the Meowth ex for a refill, this chain decides what the
Last-Ditch then brings — and that first half fires on
`_active_doomed_real and _ready_attacker_count <= 1`. The fetch now answers the
same board with the same reading, so the two halves cannot contradict each other.

**It prices the gust; it does not crown the refill.** The first version of this
rule lifted the refill to the development band instead, and an existing control
caught it: `test_with_the_slot_free_the_dawn_wins_again` (registro_005 step 52).
With a Forest of Vitality on the field the **Dawn** assembles a line and evolves
it the same turn — it buys the second attacker more directly than eight cards do,
and `_v_meowth_fetch_value` already prices that rush by whether the Forest is
really in play. The claim here is about the gust, so only the gust is priced.

**It never talks over a gust that has a reason.** Every reason a Boss's can have
returns *above* this rung — `winning_boss` 1300, the two-prize gust,
`boss_deny_evo` 1280, `boss_beats_the_untouchable_active` 1270 — so reaching it
means the ladder itself found none. **40** and not a veto, the same
"the prompt still forces a card" band as `copy_already_in_hand`: a deck holding
no other Supporter still brings it.

Deck-agnostic: two readings of **our** board plus the one Supporter that rewrites
**theirs**. The Froslass drip is why the board mattered, not why the rule fires.

---

## What it measures

**Frozen corpus:** **0 flips** of 3 580 decisions.

**Firing census** (`utils/rule_census.py --corpus`, the same workload):

| | evaluated | fired | for comparison |
| --- | --- | --- | --- |
| `the_gust_without_a_reason_yields_to_the_second_wave` | 8 181 | **204** | `lillie_development` 197 · `winning_boss` 52 · `boss_deny_evo` 0 |

**What it changes**, measured directly (the fetch resolved on 3 533 boards of the
frozen corpus, argmax of the chain with the rule and without it):

| | boards | outcome |
| --- | --- | --- |
| the card the Last-Ditch brings changes | **3 of 3 533** | Boss's Orders → Lillie's Determination, all three in one game (`registro_034_dragapult_2`) |

**Winrate** (`utils/matchup_matrix.py --games 600 --seeds 600`, **paired seeds**,
87 opponent lists, 52 200 games per arm; the control arm is the same tree with
this rule switched off):

| | candidate | control | delta |
| --- | --- | --- | --- |
| winrate | 93.60 % | 93.61 % | **−0.00 pp** |
| prizes | +3.898 | +3.899 | −0.000 |
| lists that move at all | — | — | **1 of 87** (`crustle_wall_16`, −0.2 pp = one game in 600) |

**NEUTRAL, and expected to be.** The population is three boards in fifty recorded
games; the generic OpponentBot rarely builds the board this rule is about (an
undeveloped bench behind a doomed attacker, with a Meowth ex still to bench and a
Boss's left in the deck). It is kept on the **board** — the fetch that spent two
prizes of Meowth ex on a gust with no reason while nothing could take over — and
on the two halves of one engine now reading the same pair of flags, per
[the policy for neutral changes](improving-the-agent.md).

---

## Status

In the working tree, suite green (2 974 passed). Pinned by
[tests/test_a_full_bench_is_not_a_second_attacker.py](../tests/test_a_full_bench_is_not_a_second_attacker.py),
whose controls are the half that must not move: the same four bodies with the
benched Ogerpon ex **charged**, the same undeveloped bench with a **healthy**
active, the four gusts that have a reason, either premise alone, and the
first-turn ladder.

**Open:** the record itself. The board above was reported from a game whose log
is not in `records/` — the JSON attached to the report is
`registro_009_pasos_085_hasta_092.json`, a different game (vs Alakazam) with no
Last-Ditch fetch in it. When the real record appears, the synthetic board here
should be replaced by a fixture of the actual prompt.

---

Related: [The gust that cuts the line beats the refill](../tests/test_the_gust_that_cuts_the_line_beats_the_refill.py)
· [The Supporter that buys bodies cannot unblock a turn with no energy](festival-lead-the-body-search-cannot-buy-the-energy-2026-08-15.md)
· [The refill buys the wave the evolution would delete](festival-the-refill-buys-the-wave-2026-08-15.md)
