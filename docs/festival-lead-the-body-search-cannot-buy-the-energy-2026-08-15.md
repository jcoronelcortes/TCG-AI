# The Supporter that buys bodies cannot unblock a turn with no energy (step 116)

[← Documentation index](README.md)

One board of a game we **won** (episode 93210930, vs Festival Lead). The turn
had one shortage — **energy** — and the agent spent its only Supporter on the
one card in hand whose printed text cannot produce any, and closed the turn
without attaching or attacking.

---

## The board

**Step 116, turn 9** — `records/registro_009_pasos_116_hasta_120.json`

```
US (3 prizes)                          THEM (3 prizes)
active  Hydrapple ex 190/330, 0 energy active  Thwackey 100/100, 0 energy
bench   Meganium 160/160, 0            bench   Dipplin (1 energy), Thwackey ×2,
        Teal Mask Ogerpon ex ×2, 0             Dipplin, Applin 40
hand    Bayleef, DAWN, ULTRA BALL      stadium Forest of Vitality (ours)
deck    29 cards: 8 Basic {G}, 3 Lillie's Determination, 2 Meowth ex, 3 Bug
        Catching Set, 2 Ultra Ball, Night Stretcher …
```

The menu offered exactly three things: play Dawn, play the Ultra Ball, end.

```
[0] DAWN         2680   <-- played
[2] END             0
[1] ULTRA BALL     -1   `_ub_cancel_no_surplus`
```

**Not one energy on the whole board and none in hand**, so no body of ours could
attack whatever the turn did: Hydrapple ex needs 2, Ogerpon ex 3, Meganium 4.
*Ripening Charge* and *Teal Dance* both take their Grass **from hand**, so an
empty hand closes every route at once.

Dawn is *"search your deck for a Basic, a Stage 1 and a Stage 2"*. It fetched a
Tapu Bulu and a second Hydrapple ex; the Tapu was benched and the turn ended.
**Zero energy attached, zero damage, three Pokémon cards in hand.**

---

## What the turn could have been

A turn plays **one** Supporter, so playing Dawn did not merely fail to help —
it **closed the only door**:

```
ULTRA BALL (discard Bayleef + Dawn) → MEOWTH EX → Last-Ditch Catch → LILLIE'S
DETERMINATION → shuffle the hand in, draw 6 of 27
```

Every link was verified with the agent's own decisions, not assumed: with the
cost veto lifted the Ultra Ball scores **12400** against Dawn's 2680, its fetch
picks the **Meowth ex** out of seven legal targets, the Meowth is **played**, and
Last-Ditch Catch picks **Lillie's Determination** out of six Supporters.

What the six cards are worth, with 8 Basic {G} left among 27:

| | |
| --- | --- |
| P(≥1 Grass) | **90.8 %** |
| P(≥2 Grass) | **59.4 %** |
| expectation | 1.78 Grass |

And what a Grass is worth on that board — *Wild Growth* is in play, so each Basic
{G} provides {G}{G}, and *Syrup Storm* is 30 + 30 per {G} on **all** our Pokémon:

| Grass attached | effective | Syrup Storm | their active (100 HP) |
| --- | --- | --- | --- |
| 1 (the manual attachment) | 2 | **90** | survives |
| 2 (+ *Ripening Charge*) | 4 | **150** | **knocked out, a prize** |

Both numbers come from `_attacker_base_damage` / `_our_effective_damage`, and
both are pinned in the test.

---

## The cause

The Ultra Ball was **already** the better card by the agent's own scoring. What
stood between them was one cost veto: `_ub_cancel_no_surplus`
([ptcg/decision/ultra_ball.py](../ptcg/decision/ultra_ball.py)), which cancels
the search when the cost of two cannot be paid out of surplus. Its count,
`_ub_real_fodder`, came out at **one** in a hand of three, because it protects a
lone refill Supporter:

```python
elif _ub_llid in (Lillie_Determination, Dawn):
    if (not state.supporterPlayed
            and hand[Lillie_Determination] + hand[Dawn] <= 1):
        _ub_ll_fodder = False        # "the last refill"
```

So the agent kept, as **tomorrow's refill**, the one card that could not answer
**today's** question — and paid for it with the whole turn.

That count exists to say *"what the DISCARD scorer would really let go"*, and on
this board the discard scorer did not agree with it: with Meganium **and**
Hydrapple ex both already in play, its Dawn ladder prices that same copy at
**75**, ordinary fodder, because there is nothing left for Dawn to buy. Two
layers of the agent were reading the same card and giving opposite answers.

---

## The rule

`THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN`
([ptcg/decision/ultra_ball.py](../ptcg/decision/ultra_ball.py)) — a Supporter of
`POKEMON_SEARCH_SUPPORTER_IDS` stops being protected fodder when all of this
holds at once:

1. the turn's Supporter slot is still free;
2. **the hand cannot unblock itself** — no Basic {G} in it, and no card of
   `GRASS_DIGGER_REACH` either (Bug Catching Set, Unfair Stamp, Lillie's, Night
   Stretcher, Lana's Aid);
3. **nothing attacks today** — `_a_body_can_attack_this_turn`, the same reading
   four other routes make, and permissive on purpose: a body it over-counts as
   an attacker leaves this rule silent;
4. **the route is walkable this turn**, step by step: an Ultra Ball to play, a
   Meowth ex left in the deck, a bench seat for it, its Last-Ditch unspent and
   unlocked (Watchtower cancels it), the Items not shut off (Budew), and a
   refill Supporter still in the deck — Lana's Aid only counting when there is a
   Basic {G} in the discard for it to bring back.

It is **deck-agnostic by construction**: three card *groups* and no opponent
name. `POKEMON_SEARCH_SUPPORTER_IDS` is "the Supporters that buy bodies",
`GRASS_DIGGER_REACH` is "the cards that can put a Basic Energy in hand". Swap
their contents and the sentence still reads *the slot cannot go to a card that
cannot buy what the turn is missing*.

The discard ladder says the same thing on the other side
([ptcg/turn/options/card.py](../ptcg/turn/options/card.py)): on the Ultra Ball's
**own** discard menu that Dawn drops to `DISCARD_SUPPORTER_DEAD_DROP`, so the
count and the ladder that pays the cost cannot disagree and burn the evolution
piece beside it instead.

---

## What it measures

**Golden corpus:** one flip — this step. **Frozen corpus: zero** of 3 580
decisions.

**Census** (`utils/census_the_body_search_cannot_buy_the_energy.py`, 500 games
per list, criterion **0.01 flips/game written before running**):

| list | our decisions | boards with no energy at all | flips/game | of which, this sentence |
| --- | --- | --- | --- | --- |
| festival_lead_1 | 120.4/game | 5.1/game | 0.016 | **0.008** (4 in 500) |
| marnie_grimmsnarl_1 | 121.2/game | 17.1/game | 0.000 | 0.000 |
| crustle_wall_1 | 132.1/game | 8.6/game | 0.000 | 0.000 |
| alakazam_1 | 136.2/game | 22.8/game | 0.002 | 0.000 |

⚠️ **Below its own criterion**, and stated rather than rounded up: roughly one
board in 125 games, all of them on the list the board came from. Every flip that
is not the sentence is a knock-on (four of them, same list). The rule is kept on
the argument of
[the policy for neutral changes](improving-the-agent.md): the valuation it
corrects is **wrong**, not merely infrequent — the fodder count contradicted the
discard scorer it exists to mirror.

**Winrate** (`utils/gate_the_body_search_cannot_buy_the_energy.py`, 1000 paired
seeds vs `festival_lead_1`, with its own `--control` row at the same N):

| | candidate | control (the noise floor at the same N) |
| --- | --- | --- |
| wins | 632/1000 = 63.20 % | 632/1000 = 63.20 % |
| delta | **+0.00 pp** (z 0.00, p 1.000) | +0.00 pp |
| prizes | **+0.002** | +0.000 |

**NEUTRAL, and expected to be.** At four boards in 500 games this axis cannot
resolve anything; the control row at exactly zero is the provenance proof that
the two arms differ in nothing but the flag.

**Rules oracle** (`utils/oracle_the_body_search_cannot_buy_the_energy.py`,
K=100, per-board floor from a second batch at different seeds) — the instrument
that *can* resolve a rare board, because it grades the board rather than the
season:

| board | with the rule | without | delta | its own floor |
| --- | --- | --- | --- | --- |
| `registro_009` step 116 | **82/100**, margin +0.74 | 74/100, +0.73 | **+8 pp** / +0.01 | 5 pp / 0.33 → **clears** |

**1 for, 0 against.** The winrate half clears the board's own floor; the prize
margin does not move, which is what a turn that buys a hand rather than a prize
should look like.

---

## The second board: it is not about an empty table (15 August, the same day)

The user brought a board of **another game and another archetype** — episode
**93224301**, turn 5 vs **Dragapult**, also won — with the same complaint. It is
the board that says what the rule actually means.

**Step 35** — `records/registro_005_pasos_035_hasta_044.json`

```
US (6 prizes)                            THEM (6 prizes)
active  Hydrapple ex 330/330, 0 energy   active  Fezandipiti ex 210
bench   Bayleef 110, 0                   bench   Drakloak, Dreepy x2, Munkidori
        Teal Mask Ogerpon ex, 1 {G}      stadium Forest of Vitality (OURS)
        Teal Mask Ogerpon ex, 1 {G}
hand    ULTRA BALL, Forest of Vitality (dead: ours is already in play), DAWN
```

**There are two energies on the table**, and the turn is blocked all the same:
Hydrapple ex is at 0 of the 2 it needs, each Ogerpon ex at 1 of 3, and there is
no Basic {G} in hand for the attachment — nor for *Teal Dance* or *Ripening
Charge*, which both take their Grass from hand. What decides is
`_a_body_can_attack_this_turn`, **not a count of energies**, and reading the
first board alone invites the wrong sentence ("the rule is for empty boards").

What the recorded Dawn did: fetched Applin + Bayleef + Meganium, evolved the
Meganium, benched the Applin, spent the Ultra Ball afterwards on a Tapu Bulu,
and **ended the turn with nothing attached, nothing attacked and two cards in
hand**. What the rule does instead — walked with the engine's own rules, not
argued:

```
ULTRA BALL (discard Forest + Dawn) → MEOWTH EX → Last-Ditch Catch → LILLIE'S
DETERMINATION → at SIX prizes it draws EIGHT → Bug Catching Set, a third
Ogerpon ex, Teal Dance, Meganium, the attachment, Ripening Charge → ATTACK
```

**Turn yield** (`utils/turn_yield_the_body_search_cannot_buy_the_energy.py`, 50
determinised worlds per arm, the agent finishing the turn in both, same seeds):

| | prizes | energy attached | hand at end | attacked |
| --- | --- | --- | --- | --- |
| with the reading (Ultra Ball) | **1.72** | **+3.06** | 6.88 | **94 %** |
| without it (the recorded Dawn) | 0.00 | +0.00 | 1.84 | 0 % |

**43 of 50 worlds take more prizes, 0 take fewer.**

The winrate oracle is **blind here and says so**: both arms win **100/100**
because the position is already won (margin +5.94 against +5.96, the board's own
floor 0.06 → *inside the floor*). That is an instrument at its ceiling, not a
tie, and it is why the turn-yield tool exists.

**Census vs the archetype the first table never ran** (500 games,
`dragapult_1`): 6 flips, **3 of them this sentence** (0.006/game); a first run
of the same size gave 1. Still below the 0.01 criterion, and now the sentence
has been seen on **two lists**, not one.

**And a column that was understating its own population.** The census reported
"boards with no energy at all", which is the shape of the *first* board, not the
rule's condition; this second board would not have been counted by it. The
honest population — slot free and nothing able to attack — is now printed beside
it and is several times larger:

| list | no energy at all | slot free and nothing attacks |
| --- | --- | --- |
| festival_lead_1 | 4.8/game | **34.1/game** |
| dragapult_1 | 15.6/game | **59.3/game** |

The `bought` column, the one the criterion is written on, is unchanged: it was
never gated by that population.

---

## Status

Carried by the **boards** — two of them now, on two archetypes — and by the
oracle on the first (+8 pp over a 5 pp floor) and the turn yield on the second
(1.72 prizes against 0.00, 43/50 worlds); the census is honestly **below its own
criterion** and the winrate is **neutral**, both stated above. What keeps it is
the contradiction it removes: a count whose whole job is to mirror the discard
scorer was protecting a card that same scorer prices as fodder.

The switch to flip is `THE_BODY_SEARCH_DOES_NOT_UNBLOCK_AN_ENERGYLESS_TURN` in
[ptcg/decision/ultra_ball.py](../ptcg/decision/ultra_ball.py); the board it comes
from is pinned in
[tests/test_the_body_search_cannot_buy_the_energy.py](../tests/test_the_body_search_cannot_buy_the_energy.py),
whose middle section is the half that must not move: with a Grass in hand, with
no Meowth ex left in the deck, with no refill left, with the Last-Ditch already
spent or with the Supporter already played, the rule stays silent and Dawn keeps
its slot.

The second board is pinned in
[tests/test_dragapult_the_body_search_cannot_buy_the_energy.py](../tests/test_dragapult_the_body_search_cannot_buy_the_energy.py),
and its first test is the one to read before touching any of this: **energy on
the table and the turn blocked anyway**.
