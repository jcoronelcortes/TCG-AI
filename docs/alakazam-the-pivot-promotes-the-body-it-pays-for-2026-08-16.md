# The front seat vs Alakazam: first whether it is sold, then to whom (step 113)

*Episode 93519870 step 113 (`registro_008`) — **won**. Our Hydrapple ex at
330/330 with four Grass, its attack on the menu and already knocking out their
80 HP Kadabra, **retreated**. It paid two Grass — down to the bench at **zero**
energy — gave up the turn's attack, and left a 210 HP Teal Mask Ogerpon ex in
front: two prizes exposed all the same, and 120 HP less to hold them.*

## The board

```text
US (seat 0)                                RIVAL
active  HYDRAPPLE ex 330/330, 4 {G}        active  Kadabra 80/80
bench   Teal Mask Ogerpon ex 210           bench   Abra, ...
        ...                                hand    2 cards
```

Two defects, **one per menu**, and each carries its own switch.

## The retreat

`_alakazam_pivot_1prize` (**6000**, against the attack's 1100) is a
prize-accounting sentence — *"retreat the ex and promote a one-prize body; if
they knock it out we hand over 1 instead of 2"* — and it **presupposes the
knockout**. With their hand at two, their projected *Powerful Hand* is **80
against 330**: the corpse the pivot avoids was not on offer.

`THE_PIVOT_NEEDS_A_CORPSE_THEY_CAN_TAKE` vetoes it when the body in front
already knocks out **and** `_powerful_hand_projected` does not reach it.

### The reading is *not* their bench

The first version asked about the **immediate** reply (`_promoted_reply_damage`)
and switched off `registro_005` step 56, a finding this project has already
measured: there the immediate reply is **10** and retreating is still correct,
because what it fears is the *Powerful Hand* the Abra → Kadabra → Alakazam line
assembles **afterwards**. The canonical projection separates the five boards of
the family on its own: 330 with a hand of 2 → 80; 200 with a hand of 9 → 220.

## The seat

The retreat and the promotion are **different menus**, and only the first one
knew the sentence. On that turn both candidates landed in the same band
(`+PROMO_KO_BONUS`) and the ex won on trimmings — **20557 against 20525, thirty-two
points**.

`THE_PIVOT_PROMOTES_THE_BODY_IT_PAYS_FOR` hands that menu the **same list** that
justified the retreat (`_alk_koers`, one single copy of the arithmetic) with
`PROMO_PIVOT_PAYS_FOR_THE_SEAT` (**2200**) — the size of a tie-break.

With the same limit: if their projection kills the one-prize body but **not** the
two-prize seat it replaces, the discount is a prize given away. Without that
limit it took the seat away from a 330 HP Hydrapple ex in `registro_010` turn 10,
where the retreat had been paid for by a different rule.

### A trap in the shared helper

`grass_scale=0` came in from the one-prize loop, which is unaffected by it, and
read a **charged Hydrapple ex as 30**. It now travels with `total_grass`.

## Measurement

| instrument | number |
| --- | --- |
| Census (`census_the_pivot_promotes_the_body_it_pays_for.py`) | **7 decisions of 2 416** across 32 Alakazam games; 1 of them the second half (`--only`) |
| Leakage | **0 of 3 940** outside the matchup (`--outside`; *not* `--all-matchups`, which includes the matchup itself) |
| Local corpus | 0 flips |
| Frozen corpus | **1 flip of 3 580**, reviewed: `registro_008_alakazam_8` turn 16, a 330/330 Hydrapple ex in front of a 140 Alakazam that stops retreating |
| Suite | 3 133 green, with 11 new tests and their controls over three real boards |

## Files

* `main.py`, `ptcg/cards/scoring.py`, `ptcg/turn/ctx_scoring.py`,
  `ptcg/turn/options/card.py` — the two switches and `_alk_koers`.
* `tests/test_the_front_seat_is_not_sold_for_a_prize_they_cannot_take.py`
* `tests/fixtures/the_front_seat_vs_alakazam_ep93519870_step113.json` ·
  `the_front_seat_vs_alakazam_step068.json` ·
  `the_seat_the_alakazam_pivot_paid_for.json`
* `utils/census_the_pivot_promotes_the_body_it_pays_for.py` ·
  `utils/gate_the_front_seat_vs_alakazam.py`

---

Related: [A wall that falls to the same hit is not a
wall](alakazam-the-pivot-wall-must-survive-the-reply-2026-08-15.md) — the same
Hydrapple ex pivot, vetoed for the opposite reason. Two menus, one sentence, is
the recurring shape: see also [The seat that hands the game over yields to the
body that survives the
reply](froslass-the-seat-that-loses-the-game-yields-to-the-wall-2026-08-16.md).
