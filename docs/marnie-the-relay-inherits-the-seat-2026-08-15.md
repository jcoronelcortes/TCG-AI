# The trap that locks our own door (Boss's Orders, turn 8)

[← Documentation index](README.md)

Our active could neither attack nor retreat, three charged Teal Mask Ogerpon ex
sat behind it, and the agent spent its Boss's Orders gusting a **bare Munkidori**
— a body that cannot attack. So their knockout never came, the seat never opened,
and the attackers stayed on the bench. The two-prize Marnie's Grimmsnarl ex that
a benched Ogerpon knocks out for **540** scored last of the four candidates.

---

## The board

`records/registro_008_pasos_071_hasta_073.json`, step 72, turn 8, episode
93486866 — **LOST**. Six prizes each, nothing taken yet.

```
US (6 prizes)                            THEM (6 prizes)
active Tapu Bulu 20/140, 0 en.           active Marnie's Morgrem 100, 2 en.
       Wood Hammer costs 4               bench  Munkidori 100/110, 1 en.
       retreat costs 3                          Munkidori  80/110, 0 en.
       no Grass and no Switch in hand            Marnie's Grimmsnarl ex
bench  Teal Mask Ogerpon ex 180, 3 en.            310/320, 5 en.
       Hydrapple ex 300, 0 en.                   Froslass 90, 0 en.
       Teal Mask Ogerpon ex 160, 3 en.
       Teal Mask Ogerpon ex 180, 0 en.
       Chikorita 70
hand   Meganium ×2 (no Bayleef under
       them), Boss's Orders
```

Playing the Boss's was right: it was the only thing the turn could do. The
question was **which body**.

---

## What the ladder answered, and why

Our active cannot attack, so the target selector runs in **nuisance mode**
(`_RULES_GUST_NUISANCE`), which prices every candidate by what it would cost the
opponent to *escape* it:

| candidate | prizes | net jam | harmless | score |
|---|---|---|---|---|
| Munkidori 1 en. | 1 | 1−1 = 0 | no | −200 |
| Munkidori 0 en. | 1 | 1−0 = 1 | **yes** | **2100** ← chosen |
| **Grimmsnarl ex 5 en.** | **2** | 2−5 = −3 | no | **−200** ← last |
| Froslass 0 en. | 1 | 1−0 = 1 | **yes** | 2100 |

`net_stuck` (500 + 100 × the unpayable retreat) and
`without_a_ko_prefer_the_dead_body` (+1500) are both **trap** reasoning, and the
trap is a purchase only if we can *spend* the turn it buys.

We could not. Our active neither attacked nor retreated and the hand was two
Meganium with nothing under them. What the trap actually bought was that **their
knockout never came** — and their knockout was the only key to our own seat.
Freezing them froze us behind a body that would not move until it died.

---

## The route that was missing

`can_ko` in `_ctx_gust_target` asks two questions, and both need a usable active:

1. does our **ACTIVE** knock this out today?
2. does a benched body knock it out after we **RETREAT** today?

There is a third, and when the seat is locked it is the only one alive:

3. **they knock our active out, we PROMOTE, and the promoted body attacks what we
   gusted.**

Down that route every candidate on this board is lethal — so the choice collapses
to what the knockout **pays**:

| candidate | their reply on our 20 HP Tapu Bulu | our benched Ogerpon (3 en.) from the seat |
|---|---|---|
| Munkidori 1 en. | 60 → **opens** | 150 vs 90 HP |
| Munkidori 0 en. | 0 → **shut** | 120 vs 70 HP |
| **Grimmsnarl ex 5 en.** | 180 → **opens** | **540 vs 300 HP** |
| Froslass 0 en. | 0 → **shut** | 120 vs 90 HP |

The 540 is why the biggest body is also the softest: **Myriad Leaf Shower counts
the energy on BOTH actives**, so their own five energies pay for the attack, and
Marnie's Grimmsnarl ex is weak to Grass.

And that is the prize race the user named: their two-prize body spends its attack
on our one-prize corpse (6→5), our relay cashes two (6→4), and the exchange keeps
that shape. The bare Munkidori sells the same seat for one prize; the Froslass and
the other Munkidori do not open it at all.

---

## The change

One reading, `_gust_relay_cashes_the_seat` in
[ptcg/decision/boss_orders.py](../ptcg/decision/boss_orders.py), asked by **both
halves of the card** — deliberately, because two models of the same question is
how this card came to justify a play with one reading and aim it with another.

Three conditions plus a prize floor, none of them naming a card or a matchup:

1. **the seat is locked** — our active does not attack this turn even with the
   attachment still to come, and cannot pay its way out (no Switch, not enough
   energy for its retreat);
2. **their knockout still leaves a game** — `op_prize > prize_count(our active)`;
3. **this body opens the seat** (`_op_active_attack_damage_to` ≥ our active's HP)
   **and our bench cashes it** (`_bench_attacker_can_ko` from a seat that costs no
   retreat, with our active's energy off the field and its bench one body
   smaller).

| half | consumer | rung |
|---|---|---|
| **which body** | `_RULES_GUST_NUISANCE` | `the_relay_inherits_the_seat`, `20000 + 2000 × prizes` |
| **whether to play it** | `_RULES_BOSS_PLAY` | `gust_sells_the_locked_seat`, `BOSS_SCORE_RELAY_SEAT_GUST` = 3900 |

The play rung sits **one above the trap** (3700) — same board, but with a prize at
the end of it — and **under** every branch that takes a prize today
(`BOSS_SCORE_PRIZE_RANK_BASE` 5200) and under a refill, whose hand can still
rebuild. The flag is also added to `_boss_reason_with_prize`, without which
`gust_without_purpose` kills it: that veto reads **their current active**, and the
body that opens our seat is the one we are about to put there.

The play half was not decoration. Strip the trappable bodies from the recorded
board and the old ladder falls to `no_value` and **ends the turn**, with the
two-prize exchange still on the table and every piece of it still true.

Neutralisable through `THE_RELAY_INHERITS_THE_SEAT`
([ptcg/cards/ids.py](../ptcg/cards/ids.py)) so the two-arm gate can see its own
change (**R7**).

---

## The numbers

**Corpus**, two arms walked side by side with the flag rebound:

| corpus | decisions | flips |
|---|---|---|
| `records/` — the real harvested games | 136 (20 records) | **1** |
| `tests/corpus/` — the frozen fifty | 3 580 (50 records) | **0** |

The single flip is `registro_008`, turn 8, `[1] → [2]` — **the board the user
reported, and nothing else**. Across every other real decision on disk the rule is
silent.

**Firing census** (`utils/census_the_relay_inherits_the_seat.py`, 200 games,
candidate arm driving with a neutralised shadow on every frame), criterion
written before running it: **0.05 flips/game**.

| list | target menus | flips | **aim** (bigger prize) | **play** (a Boss's the base declined) | other |
|---|---|---|---|---|---|
| `marnie_grimmsnarl_1` | 1.22/game | **0.06/game** | **9** | 0 | 2 |
| `alakazam_1` | 1.70/game | 0.00/game | — | — | — |

Above the criterion, and the signal is clean: **nine of eleven flips are the
rule's own sentence** — a strictly more valuable body — with only two knock-ons.

**The `play` column is zero, and that is a reading rather than a broken counter**
(both detectors are exercised against the two fixtures in the test file). It says
the two halves overlap almost perfectly in practice: wherever the relay state
exists, the *trap* reason has already bought the Supporter, so the play rung
rarely changes what gets played. It earns its place as a **consistency fix** —
demonstrated on the recorded board, where stripping the trappable bodies drops the
old ladder to `no_value` — and not as a source of new plays. Reported as measured.

The zero against Alakazam is the matchup and not a bug: that ladder has its own
`alakazam_line_do_not_promote_the_attacker` FORBID above this rung, so the rule
never gets to decide there. The state it needs is narrow either way — a locked
active, a charged bench, a Boss's in hand and a target menu on the same turn.

**Winrate** (`utils/gate_the_relay_inherits_the_seat.py`, 1 500 paired seeds vs
`marnie_grimmsnarl_1`, seats alternating):

| row | wins | delta | prizes |
|---|---|---|---|
| candidate | 1464 / 1500 = 97.60 % | **+0.27 pp** (z +0.46, p 0.64) | +0.014 |
| **control** (flag against itself) | 1460 / 1500 = 97.33 % | **+0.00 pp** exactly | +0.000 |

Read it as **positive in sign and NOT significant**. The control row is a clean
zero — both arms landed on the identical 1460/1500, which is what a paired-seed
control is supposed to look like and confirms the two arms really are the same
tree with one flag moved — so the +0.27 pp does clear its own noise floor. But
+0.27 pp is four games in 1 500 at p 0.64, and against this list the reference bot
is already losing 97 % of the time: there is almost no room left for a rule that
speaks on one board in seventeen games to move the number. **The winrate is not
what is keeping this change.** What is keeping it is the board, the corpus flip
that is exactly that board, and a census whose flips are 9-of-11 the rule's own
sentence.

---

## Status

Suite green (3 004 passed), architecture lint clean, purity unchanged. Pinned by
[tests/test_the_relay_inherits_the_seat.py](../tests/test_the_relay_inherits_the_seat.py)
— 17 assertions against the **real step**, with the three specificity halves that
matter: unlock the seat and the rule goes quiet (the board becomes the one
`opponent_line_higher_evolution` was already written for, and reaches the same
body through the retreat route); take their prizes down to one, or leave our bench
with nothing charged, and the trap is right again.

---

Related: [The gust target without a KO is the body that cannot
attack](../tests/test_boss_target_without_ko_is_the_dead_body.py) ·
[A full bench is not a second
attacker](a-full-bench-is-not-a-second-attacker-2026-08-15.md) · [The promotion is
the seat the search completes](lucario-the-seat-the-search-completes-2026-08-14.md)
