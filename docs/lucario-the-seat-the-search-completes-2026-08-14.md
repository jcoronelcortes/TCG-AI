# The promotion is a seat for tomorrow's body, and a search is a route to it

[← Documentation index](README.md) · [the sibling rule, one rung up](archaludon-the-veto-that-walks-back-2026-08-14.md)

**Game**: episode 92943959, `records/registro_004_pasos_047_hasta_059.json`,
turn 4, against Mega Lucario ex. **Lost.**

Their Mega Lucario ex knocked our active Bayleef out and the menu of step 59
asked which body comes up.

## The board when we chose

| | |
| --- | --- |
| **Our active** | — (just knocked out) |
| **Our bench** | **Dipplin 80, 0** · Teal Mask Ogerpon ex 210, **3 {G}** · Teal Mask Ogerpon ex 210, 0 · Applin 40, 0 |
| **Our prizes** | **6** |
| **Their active** | Mega Lucario ex, **440**/440, 1 energy + tool — its blow projects **270** |
| **Their prizes** | 5 |
| **Hand** | **Dawn** · Basic Grass ×2 · Bayleef |

The agent promoted the **charged Teal Mask Ogerpon ex**.

## What each choice was worth

### The Ogerpon ex loses on both halves at once

| | Ogerpon ex (3 {G}) | Dipplin → Hydrapple ex |
| --- | --- | --- |
| Reaches the 440 in front? | Myriad at 3 + 1 energy = **150** — no | Syrup Storm — no |
| Survives their 270? | 210 HP — **no** | **330 HP — yes** |
| Prizes handed over | **2** | 1 (and it is not handed over) |
| Energy lost with the body | **3 Grass** | 0 — the charged Ogerpon stays benched |

It does not close and it does not survive: it is a two-prize body plus three
Grass, paid for nothing.

### The Dipplin was the seat

The promotion resolves at the **end of their turn**, so our whole turn happens
before their next attack:

1. **Dawn** — search the deck for a Basic, a Stage 1 and a Stage 2:
   Fezandipiti ex, Dipplin, Hydrapple ex (2 copies of the Hydrapple ex still in
   the deck, the tracker agrees);
2. **Hydrapple ex** goes on the promoted Dipplin, **Dipplin** on the benched
   Applin;
3. one Grass by hand plus one by **Ripening Charge** pays Syrup Storm's cost;
4. **Fezandipiti ex** on the bench: our Pokémon was knocked out last turn, so
   Flip the Script draws three.

What the opponent finds in front of them is 330 HP their 270 falls short of,
with the charged Ogerpon still safe on the bench.

## Which rule chose it, and why

The chain worked exactly as written, all the way down:

```text
candidate loop      key (can_ko, prudence, hp, dmg) -> nobody knocks out a 440,
                    so it falls through to MOST HP -> Ogerpon ex 210
_rt_* tank          wants a Hydrapple ex already ON THE BENCH -> none
_ev_* survivor      nothing survives 270 as it is, so the block DOES open...
                    ...and looks for the evolution IN HAND -> none
_evk_* knocker      same hand-only reading, and no knockout exists anyway
```

`_ev_*` is the block whose whole sentence is *"if no benched body survives the
projected hit as it is, but a pre-evolution can evolve next turn into a body
that survives, promote that pre-evolution."* Its premise held. It asked "can
this body evolve next turn?" and answered it by **looking only in the hand** —
and the answer was wrong, because the Hydrapple ex was in the deck and what the
hand held was the tutor that reaches it.

## The fix

`main.py`, `_ev_*`, behind the named switch `PROMOTE_SEAT_THE_SEARCH_COMPLETES`:
the evolutions a benched body can wear next turn are the ones in **hand** plus
the ones a Pokémon-search Supporter in hand can still buy out of the **deck**.

Four things keep it narrow, and they are the reason the event is rare:

* the **deck** is the only zone a search reaches — a copy in the discard is not
  a route, the same sentence `_evo_top_unlocked_by_the_search` already says;
* the pre-evolution must have been down a turn (`appearThisTurn`);
* the evolution must **survive** the projected blow with the damage the
  pre-evolution already carries;
* under **Festival Lead** the opponent attacks again the moment we promote, so
  the turn that would spend the Supporter never happens: the guard is on the new
  route only, and the route in hand keeps whatever behaviour it had.

A card in hand is a certainty and a search is a belief, so the route in hand
wins every tie — the search only ever **adds** candidates.

Deck-agnostic: the stages come from `_direct_evolution_ids` (the reverse index
of `evolvesFrom`) and the tutors from `POKEMON_SEARCH_SUPPORTER_IDS`. Swap the
list and the sentence still holds.

## Measured

| Instrument | Result |
| --- | --- |
| Unit suite | 2 731 pass · the one red is pre-existing at HEAD (`test_the_prize_is_cashed_by_the_body_that_outlasts`) |
| Firing census (both corpora) | **1 of 3 685 decisions** — 0 of 3 580 on the frozen fifty, 1 of 105 on the live records: this board |
| Golden corpus | **1 flip**, this one |
| Mutation gate (`--changed HEAD`) | **0 survivors** against the whole suite |
| Rules oracle, K=500 | **+1 pp / +0.17 margin** against a per-board floor of **0.07** → clears it, 1 board in favour, 0 against |
| Self-play vs the two Mega Lucario lists, 3 000 games/arm | 91.97 % vs 91.87 % — **+0.10 pts** |
| …and its own `--control` at the same n (same code in both arms) | **−0.93 pts**: that is the run's noise floor, and the +0.10 is nowhere near it. Self-play cannot resolve a 1-in-3 685 event, exactly as the census warned |

Kept as a **corrected reading**, not as a preference: the block was answering
"can this body evolve next turn" with half the zones. Neutral-but-correct is
kept; the oracle is the evidence that it is also not a loss.

## What was tried and is NOT here

**"When nobody survives, promote the cheapest body."** `_ko_prefer_basic_general`
already says exactly that, and it is gated on `_best_promote_card is None` — so
on this board, where the loop had named the Ogerpon, it never ran even though
its own premise (their blow one-shots even our biggest tank) was fully
satisfied. Lifting that gate was probed: it flips two corpus decisions and both
go to a bare **Applin**, including this one, because in `card.py` it scores
8500+ and outbids the `+4000` the seat gets.

That is the finding, and it is worth keeping: **the cheapest body is not the
answer — the cheapest body that is a seat is.** An Applin hands over one prize
and develops nothing; the Dipplin hands over one prize *and* is the body the
search turns into the wall. Anyone who lifts that gate later has to make it
yield to the seat first.

---

Next: [Improving the agent](improving-the-agent.md) · [The instruments](instruments.md)
