# A stadium ability nobody scored is not a free play (Academy at Night, step 101)

[← Documentation index](README.md)

*`records/registro_007_pasos_098_hasta_105.json` step 101, turn 7 vs a Slowking
deck — **lost**. Their stadium was **Academy at Night** (1248): "Once during
**each player's** turn, that player may put a card from their hand on top of
their deck." Our hand was down to two cards, one of them the Lillie's
Determination that refills it, and the turn's Supporter was still unplayed.*

```text
US (seat 0)                                FIELD
active Hydrapple ex 250/330, 2 {G}         stadium  ACADEMY AT NIGHT (theirs)
bench  Ogerpon ex 3G, Meowth ex,
       Chikorita, Ogerpon ex, Applin       RIVAL
hand   LILLIE'S DETERMINATION, Meganium    active   Slowpoke 80/80

    [0] PLAY Lillie's Determination
    [1] ABILITY of the stadium (area 7)   <-- fired
    [2] ATTACK Syrup Storm
    [3] END
```

The agent fired the stadium ability, and its sub-selection then handed it the
**Lillie's**. The one card that refills the hand and fixes the bench was buried
in our own deck, by us, for nothing.

## Nothing ever decided to use it — and that is the whole point

Stadiums are **shared**. The simulator offers *us* the ability of whatever
stadium is on the field, including theirs, so the option was legal and on the
menu. What priced it is the fallback at the bottom of the ABILITY scorer, which
dispatches by card id and gives everything it does not name a generic:

```python
score = 29000
```

**29000 is the band of a real play**, and it sits above the Supporter in hand.
Academy at Night was never modelled, so it inherited the price of a good play —
and the only effect it has is to *remove a card from our hand*. The turn's one
real play was spent deleting itself.

## The fix is by AREA, not by card

The one stadium ability this deck wants is **Grand Tree**, and it is decided
further up by id with a plan behind it (`_gt_plan`). Everything else offered on
the stadium slot — theirs today, a card printed next set tomorrow — is an effect
nobody scored, and **an unscored effect must not be paid for with a card from
hand**. So the veto reads the area:

```python
elif o.area == AreaType.STADIUM:
    score = SCORE_VETO          # -1
```

By card id it would have fixed exactly one card and left the fallback loaded for
the next one. `Academy_at_Night` is added to `ptcg/cards/ids.py` so the case has
a **name in the tests**, and no rule reads it.

**The control lives in the same file.** The same board, the same hand, the same
bench — with **Grand Tree** on the field instead — still fires the ability. A
veto wide enough to switch off the stadium engine that *is* modelled would have
cost more than the bug.

## The corpus was hiding it under the wrong name

`tests/golden_corpus.py` labelled an ABILITY over **area 7** by falling through
to `me['bench'][index]`, so it came out named after whatever body happened to sit
in that bench seat. Eleven decisions to fire the **opponent's** Academy at
Night — every one of them *"put a card from our hand on top of our deck"* — had
been sitting in the snapshot for weeks reading:

```text
ABILITY Hydrapple ex
ABILITY Meowth ex
ABILITY Latias ex
```

A corpus is a **diagnostic**. A wrong name there does not flip a decision — it
hides one, which is worse, because every review of that snapshot read past it.
Area 7 is now read off the stadium.

It is also why the single frozen-corpus flip looks like it does: the accepted
decision moves from `ABILITY Teal Mask Ogerpon ex(96)` to `END`, and it was never
the Ogerpon's ability at all.

## The same 29000 had already been written down once

`tests/test_the_last_resort_grass_does_not_eat_the_ultra_ball.py` is where that
number was first recorded, and the note now lives there too. There the stadium
was their **Spikemuth Gym** — *"search your deck for a Marnie's Pokémon"* — and
this deck plays none, so firing it shuffles our deck and does nothing else. It
scored 29000 for exactly the same reason. That file's own argument is unchanged:
the **order** was burying an Ultra Ball at 11900, and it still is.

## Measurement

| instrument | number |
| --- | --- |
| Suite | **3 247 green** (27 skipped), +3 from the new file |
| `lint_architecture` | clean |
| Frozen corpus | **1 decision of 3 580** — and it is the mislabelled one above |

## Files

* `ptcg/turn/options/ability.py` — the veto by area in the ABILITY fallback.
* `ptcg/cards/ids.py` — `Academy_at_Night`, so the case has a name.
* `tests/test_their_academy_at_night_does_not_eat_our_supporter.py` — the bug,
  the play made in its place, and the Grand Tree control.
* `tests/golden_corpus.py` — area 7 is the stadium, not a bench seat.
* `tests/state_builder.py` — `with_stadium_ability`, the menu the simulator
  offers to **either** player.

---

Related: [The top in play does not close the
line](ultra-ball-the-top-in-play-does-not-close-the-line-2026-08-16.md) is the
other page about a band that buries the play already taking the turn — there the
inversion is what stopped a fix from paying, here it is the defect itself.
