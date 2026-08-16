# The gust that ends the game is not a jam (Dragapult, step 131)

*User question, 16 August 2026, on `records/registro_010_pasos_129_hasta_137.json`
(episode 93517174 vs Dragapult — **won**): "we had a Meganium active ready to
retreat, an Ogerpon on the bench charged for 270, and a Boss's Orders in hand.
The game gusted a Drakloak. That is fine when we cannot win this turn, but we
could: it had to pick the Fezandipiti ex, which gives two prizes, retreat the
Meganium, promote the Ogerpon and win, because we only had two prizes left. Why
did it not see that play when it computed the attack of its benched Pokémon, the
opponent's possible targets and our prize count to choose the best candidate?"*

## The board

```text
US (2 prizes)                          RIVAL (5 prizes)
active  Meganium 160/160, 2 of 4 {G}   active  Drakloak 90/90
bench   Teal Mask Ogerpon ex   8 {G}   bench   Drakloak 90/90, 1 {G}
        Teal Mask Ogerpon ex   4 {G}           FEZANDIPITI ex 210/210, 0 {G}
        Teal Mask Ogerpon ex   2 {G}           Dreepy 70/70
        Fezandipiti ex, Munkidori
hand    BOSS'S ORDERS, ...             stadium their Artazon

    [0] their bench #0  Drakloak        <-- gusted
    [1] their bench #1  Fezandipiti ex
    [2] their bench #2  Dreepy
```

Our Meganium sat at two of the four energies *Petal Dance* costs, so it could
not attack — but its retreat cost is **two**, and it could pay it. Behind it, a
Teal Mask Ogerpon ex at **eight effective energies** (four Grass cards, doubled
by the Meganium's *Wild Growth*).

*Myriad Leaf Shower* counts the energy on **both** Actives, so against a bare
Fezandipiti ex it reads `30 + 30 × 8 = 270` on a **210 HP** body worth **two
prizes** — our last two. Retreat, promote, attack, game.

The agent gusted the Drakloak, hit it for 300 (their one energy adds the extra
30), took **one** prize, and played on. It won the game later anyway; the
question is about the turn.

## The answer: the reading was never missing

The first thing to rule out is the one the question asks about. Every number the
play needs was computed, correctly, on that very turn. Spying on
`_ctx_gust_target` as the recorded turn resolves:

| candidate | `can_ko` | `prizes` | `wins_now` | `tier_ko` |
| --- | :-: | :-: | :-: | :-: |
| Drakloak | ✅ | 1 | ❌ | 4 |
| **Fezandipiti ex** | ✅ | **2** | **✅** | 7 |
| Dreepy | ✅ | 1 | ❌ | 1 |

`can_ko` found the retreat-and-promote route, `prize_count_op` priced the ex at
two, and `wins_now` compared that with our two prizes and came out **True**. The
agent knew, on that turn, that gusting the Fezandipiti ex ended the game.

The **play** half knew it too, and independently: the Supporter was priced at
`win_via_bench` (990 → 5600). That flag comes from a detector added for
`registro_012` p241 which walks their bench with the same
`_bench_attacker_can_ko`, finds the body whose knockout wins… and `break`s
**without recording which body it was**.

So the card justified itself with one reading and then aimed itself with
another — the exact failure `ptcg/decision/boss_orders.py` warns about in its own
header, happening one function further along.

## Where it was thrown away: the ladder that ran

`ptcg/turn/options/card.py` picks the target ladder off **our own active**:

```python
if _active_cant_attack_this_turn or _sel_active_cant_attack:
    score = _resolve_with_trace("boss->objetivo/estorbo", _RULES_GUST_NUISANCE, ...)
else:
    score = _resolve_with_trace("boss->objetivo", [], _ADJUST_GUST_OFFENSIVE, ...)
```

That is a sound proxy for *"no knockout is on offer"* only while the knockout has
to come from the **front**. It does not: `can_ko` has always had a second route
— retreat, promote, attack — and that route is at its **strongest** precisely
when the active is stuck, because a stuck active is what makes retreating free
of opportunity cost.

Our Meganium could not attack, so all three candidates went to the JAM ladder,
which prices bodies by what escaping them would cost the opponent. That ladder is
**prize-blind by construction**: its only knockout-aware rung,
`opponent_line_higher_evolution`, is gated on `line_rank >= 1` — Stage 1 or
Stage 2 — so a two-prize **Basic** can never reach it, however lethal it is.

The recorded trace, verbatim:

```text
[reglas boss->objetivo/estorbo] defecto=-200 | opponent_line_higher_evolution:-200->9050
[reglas boss->objetivo/estorbo] net_stuck=600
[reglas boss->objetivo/estorbo] net_stuck=550
```

`9050` for the Drakloak — 6000 + 3000 for being the Stage 1 of their line, + 50
for its one energy. `600` for the game: 500 + 100 of net retreat cost, the
default nuisance price of any body that cannot pay its own way out. **One prize
outranked the game by 8450 points.**

Note also what the third line says. The Dreepy scored 550, so even the ordering
*inside* the jam reading was doing its job — nothing here is a threshold that
drifted. The ladder answered the question it was asked. It was asked the wrong
one.

## The correction

`gust_wins_the_game`, in `_ADJUST_GUST_NUISANCE`:

```python
_Adjustment("gust_wins_the_game",
        lambda c, s: c.wins_now,
        lambda c, s: max(s, 100000 + c.tier_ko * 3000 + c.prizes * 100)),
```

It is the sentence the offensive chain already carries, written in the other
ladder. Three things about its shape:

* **`max()` and not `+`.** The rules above hand out `SCORE_FORBID` for a free
  retreat, for Latias freeing the basics and for the Iron Thorns lock — and every
  one of those is an argument about the board we get to **keep** after the gust.
  There is no such board. (The Iron Thorns rung's own docstring already says so:
  *"in OFFENSIVE mode it does not apply: gusting it to knock it out takes 2
  prizes and removes it from the board."*)
* **Last in the list**, so nothing below can undercut it.
* **`wins_now` already carries the guarantee.** It is
  `can_ko and prizes >= my_prize and not _ko_not_guaranteed(card)`, so a coin-flip
  survivor (Tenacious Body, Survival Brace) does not get to promise a game.

The prize term only orders **winners against each other**, which is the only
thing left to choose by once every candidate ends the game.

### What was deliberately *not* done

Deciding the ladder **per candidate** — routing any `can_ko` target to the
offensive chain — is the obvious wider fix, and the file records that it was
tried in the July 2026 cycle and **measured at −1.4 points vs Crustle with
n = 4000/branch, then reverted as a block**. That evidence stands. This change
does not re-open it: it moves nothing except the turn on which the game ends.

### Deck-agnostic by construction

The rung reads our bench's damage, their body's HP, `prize_count_op` and our own
prize count. No card id, no matchup, no evolution line — a test asserts that its
source contains none. Any deck whose active is stuck with a charged finisher
behind it gets the same answer, and the test suite shows it on a board where
their bench is Munkidori / Fezandipiti ex / Munkidori, a shape the rule was never
written against.

## Measurement

| instrument | number |
| --- | --- |
| Golden corpus (`records/`, 50 games) | **1 flip**, and it is exactly the reported decision: `registro_010` turn 10 action 3, `Drakloak → Fezandipiti ex` |
| Frozen corpus (`tests/corpus/`) | **0 of 3 580** decisions |
| Full test suite | 3 114 passed, 27 skipped |
| Live census, 4 lists × 300 games | **5 firings / 0.004 per game**, against a denominator of **461 candidates / 0.38 per game** actually priced by the jam ladder |
| Two-arm winrate gate | **not run as a claim** — see below |

The live census is the honest part of this page, and it is reported with its
**denominator** so that a small number can be read at all:

```text
dragapult             1 firing  /  108 candidates priced by the jam ladder / 300 games
dragapult_1 (real)    4 firings /  207 candidates                          / 300 games
alakazam              0         /   22                                     / 300 games
crustle_kangaskhan    0         /  124                                     / 300 games
```

Three things that number says. The jam ladder **does** run — 0.38 candidates a
game — so a zero would have meant "never at match point", not "never measured".
All five firings are against **Dragapult**, the archetype the record came from,
and the **real harvested list fires it four times as often as the synthetic
one**, which is the direction that argues the board is a property of real
opponents rather than of the reference bot. And 5 in 1 200 is the ceiling of any
winrate effect: a gate at that exposure would resolve nothing but its own noise
floor, so the tool prints the census rather than a delta.

The situation needs a turn that is simultaneously **at match point**, played with
a **stuck active**, and holding a **Boss's Orders**. Against a bot we beat from
the front, that is rare by construction.

What the rule buys is not frequency. It is that every firing is a game that ends
a turn earlier — and the board it was written from is a real ladder game, not a
simulated one, which is where the exposure that matters lives.

## Files

* `ptcg/decision/boss_orders.py` — the rung, with the record in its comment.
* `tests/test_the_gust_that_ends_the_game_is_not_a_jam.py` — 13 tests: the
  record, the control that reproduces the mistake with the rung removed, the
  reading that was already right, the scope (3 prizes, a short finisher, an
  active that cannot retreat), and the two deck-agnostic checks.
* `tests/fixtures/the_gust_that_ends_the_game_step131.json` — the observation,
  pinned, because `records/` is transient and a re-harvest renumbers it.
* `utils/gate_the_gust_that_ends_the_game.py` — `--census`, `--live-census`,
  and the two-arm gate with its `--control` row.

---

Related: [The trap that locks our own door (Marnie's Grimmsnarl ex, step 72)](marnie-the-relay-inherits-the-seat-2026-08-15.md)
is the *other* hole in the same jam ladder, found from the other side — there the
knockout came from a route `can_ko` could not see at all.
