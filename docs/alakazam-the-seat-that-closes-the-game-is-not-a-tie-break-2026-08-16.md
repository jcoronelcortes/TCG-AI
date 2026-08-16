# The seat that closes the game is not a tie-break (Alakazam, step 174)

*`records/registro_013_pasos_156_hasta_174.json`, last menu of the record —
episode 93579160 vs Alakazam, **lost**. Their Alakazam at 140/140: one prize,
and our pile was **one**. That body **is** the rest of the count. On the bench, a
Meganium holding one physical Grass — two symbols under its own *Wild Growth*,
**one card away** from Solar Beam's four — and in hand the Lana's Aid that pulls
that Grass out of a nine-card discard.*

## First: age the log before accusing the agent

**The episode's own defect was already fixed**, and that has to be said before
anything else. The episode was played by an **old submission**. Bisected over
the record itself: `718e407` returns the Fezandipiti ex, `91a9d28` onward
returns the Meganium; `9e0b8ac` — [the front spot goes to the body that can
attack](archaludon-the-front-spot-goes-to-the-body-that-can-attack-2026-08-16.md)
— is what fixed it.

## What was still broken is **what that choice depended on**

```text
Meganium        9500 (_promote_setup_ko_attacker) + 350 tie-break = 9850
Fezandipiti ex  9450 (PROMO_LAST_STAND)           + 100           = 9550
```

Three hundred points — out of a tie-break bounded to **0..450** that orders *how
many charges away are you / how many prizes do you cost*, an ornament whose own
comment says it stays *"far below any decisive rule"*.

`PROMO_KO_BONUS` already has written down why that is not good enough, for the
body that knocks out **today**: it goes **+20000** *"so that it is a GUARANTEE
and does not depend on the knocker scoring higher base than the tank"*. The
finisher one charge away, at **our** match point, is that same play one turn
earlier — and it had no guarantee at all.

And it is not only the margin. The three discounts that come afterwards can sink
it, and all three are arguments about **surviving a reply that never arrives** —
the promotion resolves at the end of *their* turn, and ours goes first:

```text
 −500   PROMO_TERA_COVER_PRICE   a Teal Mask Ogerpon ex finisher falls to 9000,
                                 BELOW the last stand
−6000   the match-point doomed   its exemption asks `_promo_kos_op`, TODAY's
                                 energy — exactly what this body does not have yet
−1200   PROMO_KO_FRONT
```

## The rule

`PROMO_CLOSER_SEAT` (**15000**) + `THE_SEAT_THAT_CLOSES_THE_GAME_IS_A_GUARANTEE`,
read in `card.py` as
`_promo_closer_seat = _promo_ko_wins_the_game and card is _promote_setup_ko_attacker`,
which also **exempts it from all three discounts**.

15000 is bounded on both sides: above `9450 + 450`, and below `PROMO_KO_BONUS` —
if `_promo_ko_wins_the_game` is true, **any** knockout by the active is worth the
whole pile, so the body that knocks out *today* keeps the last word.

## Neutral, and marked as such

| instrument | number |
| --- | --- |
| Census, local | 1 of 7 forced promotions is this board, margin 300 |
| Census, self-play 500 games vs `alakazam_1` | 584 promotions, **18** at our match point, 7 already had a knocker, **0** with a named finisher |
| Golden corpus | 0 flips |
| Frozen corpus | **0 of 3 580**; flag on/off diff over the frozen corpus: 0 |
| Seeded paired gate | 600 games, two trees: **0 divergent**, 581/600 both arms |

Both arms are the same agent against the bot, so **no winrate can say anything
here**: what is adopted is the guarantee, not a win percentage.

The test carries its control: with the flag removed the choice is the **same**,
and the margin fits entirely inside the ornament's 450.

## The instrument that could not read the turn either

The same board exposed a defect in `utils/turn_explorer.py` — the tool that
answers *"was there a better line?"* — which said **no** about this exact turn.
The answer was the **tool's**, not the board's. Two things were missing:

1. **Wild Growth in the simulated charge.** The observation lists *effective*
   energy — a body with one physical Grass under a Meganium shows **two** entries
   in `energies` — but `_attach` added a single entry per card. Every projected
   line came up one symbol short per charge, exactly on the boards where the
   doubler **is** the plan.
2. **Lana's Aid.** The only recovery modelled was Night Stretcher. Here the
   discard held ten Grass, the hand none, and Lana's Aid was the only route to
   the missing charge. It is a Supporter, so it shares the slot with Boss's
   Orders, and that now branches.

With both in place, the same turn from both seats:

```text
Meganium        LANA->3 GRASS -> ATTACH->Meganium -> ATTACK   wins, 1 prize
Fezandipiti ex  LANA->3 GRASS -> ATTACH -> RETREAT -> ATTACK  80, does not win
```

And the **agent** plays all three links, not just the explorer: in the real menu
it picks Lana's Aid; with the three Grass in hand — the record's real hand — it
attaches to the **active**; at 4/4 it attacks with Solar Beam.

## Files

* `ptcg/cards/scoring.py`, `ptcg/turn/options/card.py` — the rung and its
  exemptions.
* `tests/test_the_seat_that_closes_the_game_is_not_a_tie_break.py` ·
  `tests/fixtures/alakazam_our_match_point_the_seat_that_closes_the_game_step174.json`
* `utils/census_the_seat_that_closes_the_game.py`
* `utils/turn_explorer.py` ·
  `tests/test_the_explorer_can_read_this_decks_last_turn.py` — the tool fix, with
  its two controls (no Meganium on the board → the charge is worth one; from the
  seat the episode chose → there is no winning line). The test does **not** hang
  off `records/`, which is transient data.
