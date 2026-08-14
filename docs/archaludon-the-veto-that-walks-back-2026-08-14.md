# Their match point: the veto priced on a reply the body can step out of

[← Documentation index](README.md) · [the sibling rule, one rung up](marnie-the-reversible-bet-2026-08-14.md)

**Game**: episode 92848103, `records/registro_006_pasos_067_hasta_077.json`,
turn 6, against Archaludon ex. **Lost.**

Their Archaludon ex knocked our active Teal Mask Ogerpon ex out for 220 and the
menu of step 77 asked which body comes up.

## The board when we chose

| | |
| --- | --- |
| **Our active** | — (just knocked out) |
| **Our bench** | Meganium 160, **0/4** · **Teal Mask Ogerpon ex 210, 2/3** · Meowth ex 170, 0 · Dipplin 80, 0 · Tapu Bulu 140, **0/4, retreat 3** |
| **Our prizes** | **6** |
| **Their active** | Archaludon ex, **240**/400 (300 + Hero's Cape), 4 {M}, **resists {G} −30** |
| **Their prizes** | **2** |
| **Hand** | Teal Mask Ogerpon ex · **Lillie's Determination** |

The agent promoted the **Tapu Bulu**: 8514 against the Ogerpon's −30000.

## What the board was worth

### The knockout was one attachment away

Meganium's Wild Growth was on the bench, so each attachment is worth **two**,
and Myriad Leaf Shower is `30 + 30 × (our active's energy + their active's
energy)`:

| Grass on the Ogerpon | Base | Through their {G} resistance | KO on 240? |
| --- | --- | --- | --- |
| 2 (as it stood) | — (below the cost of 3) | — | no |
| **4 (one attachment)** | **270** | **240** | **yes, exactly** |

Their main attacker, two prizes, on **our** turn. And the hand held a Lillie's
Determination to go looking for the Grass — this is not a blind bet, it is
route (a) of the selector.

Note what this knockout does **not** need: Archaludon ex is weak to {R} and
*resists* {G}. The hit lands with the resistance subtracted, not with a
weakness doubling it.

### The Tapu Bulu could do nothing, and did nothing

Wood Hammer costs four and it carried zero; its retreat costs three and it
carried zero. It is a body that neither attacks nor steps aside — the same
shape as [the Marnie autopsy](marnie-the-reversible-bet-2026-08-14.md), on a
different board and against a different deck.

## Which rule chose it, and why

The selector got it **right**. `_promote_setup_ko_attacker` named that Ogerpon
at **+9500** — route (a), a draw Supporter in hand with nine Grass still
unseen. The choice was then overwritten one rung further down:

```text
_mp_price_ends_the_game(Ogerpon ex)   ->  score = PROMO_MATCH_POINT_VETO  (-30000)
```

and the arithmetic behind it is not wrong:

| | |
| --- | --- |
| their pile | **2** |
| what a Teal Mask Ogerpon ex pays | **2** |
| their projected blow | **220** ≥ its 210 HP |

A 2-prize ex their blow removes **is** their last two prizes. Every guard the
veto carries was satisfied, and both of its exemptions were shut: `_promo_kos_op`
measures TODAY's energy (2/3 — it cannot attack yet), and
`_promo_ko_wins_the_game` asks whether OUR knockout ends the game, which at six
prizes it does not.

## What changed: the veto is right about the arithmetic, wrong about the clock

The forced promotion **resolves at the end of THEIR turn**. Between the body
going up and their reply there is a whole turn of ours. So their blow only
collects those two prizes if the Ogerpon is still standing in front when it
arrives — and that is not a fact about the board, it is a choice we still hold:

- the Grass comes → we attack first, take the prize, and the reply the veto is
  priced on never happens;
- it does not come → the Ogerpon **retreats** — cost 1, and it carries two
  effective — and the cheap body takes the front **then**, before their reply.

Which is the sibling rule's sentence exactly, one rung further down: what pays
for the bet was never a guarantee of the energy, it is **the exit**.

```text
_promo_bet_walks_back = the finisher the selector already named
                        and it can pay its own retreat with the energy it carries
                        and not a deck that punishes retreating (Cubchoo)
```

The exemption reaches **one body** — the `_promote_setup_ko_attacker` — so the
other 2-prize ex on that bench (the Meowth ex) stays vetoed at −30000, as it
should: it has no upside to pay for the risk.

### Two guards that are deliberately absent

**"And somewhere to walk back into."** True, and it can never change a
decision: the only consumer of this flag is the veto itself, which already asks
`_mp_cheaper_candidate` of the whole menu before it fires at all. With nothing
cheaper on the bench the veto stays shut and the finisher keeps its +9500 with
the rule switched off as well. The mutation gate says the same thing — written
in, the term is a line no test can kill — and this is the same deletion route
(f) recorded for its own third guard.

**The plain veto one rung up** (`PROMO_MATCH_POINT_VETO` under
`_promo_survivors > 0`) reads true of the same sentence and was **left
untouched on purpose**. It asks for something the scaled one does not: a body
that ENDURES their blow. That is a different board — the alternative to the bet
is a tank that lives, not a mute wall that dies anyway — and no record in either
corpus produces it, so the trade has never been measured. The mutation gate
flagged it as a line nothing in the repository could kill, and it came back out.

## The second finding: the selector was reading half the type matchup

This board is also the one that shows `_promote_setup_ko_attacker` pricing its
candidates with

```python
if our energyType == their weakness:  damage *= 2
```

and nothing else — the **fifth inline copy** of an arithmetic whose canonical
model, `_our_effective_damage`, has carried weakness *and* resistance *and*
Full Metal Lab since the morning it was written, from a lost game against this
very archetype (episode 91627381, "every finisher kept over-reading by 30").

Archaludon ex is weak to {R} and **resists {G}**, so against the one meta
archetype that resists us the selector was promising knockouts 30 short. It did
not change *this* promotion — 270 resisted is exactly the 240 their Archaludon
had left, so the rule was right by one point of damage — which is why the test
that watches it takes one energy off their active: 30+30×(4+3) = 240 blind,
**210** resisted, on a 240 HP body.

The call now goes through `_our_effective_damage`. It can only ever LOWER a
candidate's damage, so it never invents a finisher; and it flips nothing in
either corpus, which is the honest report — the reading is a correctness fix
with a test, not a measured win.

## What it measures

| Instrument | Result |
| --- | --- |
| Golden corpus (`records/`) | **1 flip**: this step, Tapu Bulu → Teal Mask Ogerpon ex |
| Frozen corpus (3 580 decisions, 50 games) | **0 flips** |
| Mutation gate (`--changed HEAD`) | **0 survivors** on every new line |
| Firing census, 750 games / 5 matchups | 473 forced promotions, **8 changed** (0.011/game), in **4** of the 5 matchups |
| Self-play, 5 matchups, 2 000 games/arm | 92.60 % with the exemption vs 92.45 % without — **+0.15 pts** (z 0.18, p 0.86) |
| …and its `--control` at the same N | same code in both arms separates by **+0.75 pts**, with per-matchup swings to ±1.75. The delta above is *inside its own noise floor* |
| **Rules oracle, K=100 per batch, two independent runs** | **1 board, 1 in favour, 0 against, both times.** **+14 pp / +1.09 margin** (floor 1 pp / 0.05) and **+13 pp / +0.86** (floor 2 pp / 0.36) |

**The winrate cannot see this rule and says so honestly**: a decision that
changes once per ninety games is invisible to a scoreboard that saturates
against the bot — and the control proves it, because the same code played
against itself at the same N separated by five times as much as the rule did.
(Read the `alakazam +1.00, p=0.045` row of the rule's arm against the
`crustle +1.75` and `archaludon +1.50` of the control's: a row without its
`--control` at the same N is not a reading,
[[el-suelo-de-ruido-de-marnie-son-punto-cinco-puntos-y-parece-significativo]].)
What grades it is
`utils/oracle_the_veto_yields_to_the_body_that_walks_back.py`, which rolls the
two options forward under the engine's own rules — and on the board this was
written from, keeping the exit is worth thirteen to fourteen points of winrate
and about a full prize of margin. Two runs are quoted rather than one because
the search API is not seeded: the oracle is an estimator, and a single batch is
a sample of it.

Marked as **NEUTRAL in winrate, entered on the census and the oracle**, the same
standing the Cornerstone, Ultra Ball and reversible-bet rules carry.

## Pinned by

- `tests/test_the_match_point_veto_yields_to_the_body_that_walks_back.py` — the
  board, the arithmetic through the resistance, the decision, and three
  controls: empty the Ogerpon and the wall comes back; switch the flag off and
  the wall comes back; the other 2-prize ex stays vetoed either way.
- `utils/gate_the_veto_yields_to_the_body_that_walks_back.py` — the two-arm
  gate and the firing census.
