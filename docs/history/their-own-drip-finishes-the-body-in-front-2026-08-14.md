# Their own drip finishes the body in front

[← Documentation index](../README.md) · A card rule of
[the day of 14 Aug 2026](../day-plan-2026-08-14.md)

**The criterion below was written before the change was measured**, in the
gate's own docstring (`utils/gate_their_own_drip_finishes_the_body.py`). That
ordering is the whole point: an acceptance test written after the number is not
an acceptance test.

---

## The record

`records/registro_006_pasos_065_hasta_091.json`, episode 92871474, **step 90**,
turn 6 vs **Marnie's Grimmsnarl ex** — LOST.

Their Grimmsnarl ex had just knocked out our Teal Mask Ogerpon ex and taken the
two prizes that left both piles at **four**. The forced promotion menu offered
exactly two bodies:

    [0] Meowth ex   130/170, no energy         -- Last-Ditch Catch, no attack
    [1] Meganium     50/160, 2 Grass = 4 eff.  -- Solar Beam, 140

and in front of them a **Grimmsnarl ex at 320/320** with four Darkness. On their
bench: **two Froslass** and two Munkidori.

The agent promoted the Meowth ex. `PTCG_DEBUG=1` prints the ladder in two lines:

    [DBG] ctx=4 opciones=2
    [DBG]   #1 idx=0 score=-1461 Meowth ex
    [DBG]   #2 idx=1 score=-6000 Meganium

−6000 is `SCORE_NEVER` (−10000) plus the +4000 of "best attacker": the Meganium
line is **vetoed out of the active spot**, because it is the Wild Growth engine
and it doubles every Grass on our board from the bench. The veto has one
exemption — the KO-aware selector points at this body **and its hit knocks the
opposing active out next turn**. Solar Beam is 140, doubled by their Darkness
weakness = **280**, and 280 < 320. The exemption never opened, a mute ex took
the front, and the turn had no attack in it at all.

## The forty points

Freezing Shroud does not say *your opponent's Pokémon*. It puts one damage
counter on **each Pokémon in play that has an Ability**, and their board is in
play too. The record proves the reading on its own — at every checkup the log
puts counters on our Ogerpon, our Meowth ex, our Meganium **and their own
Munkidori**, and on nothing else of theirs: their Marnie's Impidimp prints no
Ability, and the two Froslass are excluded by the card's own text (they stood at
90/90 all game).

Marnie's Grimmsnarl ex prints one — *Punk Up*, the ability that searched five
Darkness out of their deck at step 73. So it pays the drip like everything else.

The estate already knew this. The note next to `FREEZING_SHROUD_COUNTER` says it
in as many words:

> Munkidori's ammunition SELF-RENEWS: their own Froslass loads 10 per checkup
> onto each Munkidori **and onto the Grimmsnarl ex (they all have an ability)**

and used it for exactly one thing: counting how much ammunition Adrena-Brain
has. The half that says *their attacker is dying too* was never spent.

Two Froslass, and **two checkups** between that menu and their next turn — the
one that opens our turn and the one that follows our attack. Forty. Their 320 HP
body is **280** to us, and 280 is exactly what the Meganium does.

## The line the board had

    checkup   Meganium 50 -> 30      Grimmsnarl ex 320 -> 300
    our turn  Solar Beam 140 x2 weakness = 280   ->   Grimmsnarl ex at 20
    checkup   Grimmsnarl ex 20 -> 0   ->   TWO PRIZES, 4 -> 2

And the prize is safe in a way an ordinary chip is not: the counters land
**between turns**. Before their turn starts the body is already gone, so they
cannot heal it, cannot retreat it, and cannot move the damage off it with
Adrena-Brain — which is theirs to use on their own turn, and their turn never
arrives for that body.

## What changed

One primitive, in `ptcg/calc/damage.py`:

```python
def _op_hp_for_our_ko(target, checkups=1) -> int:
    """The HP OUR attack actually has to cover to knock `target` out."""
    hp = getattr(target, 'hp', 0) or 0
    if hp <= 0:
        return hp
    return max(1, hp - _shroud_damage_to(target, checkups))
```

`_has_ability` reads the condition Freezing Shroud names off the card database
(`skills`) rather than off a hand-kept list, because the counters have to be
projected onto **their** board and their board is whatever deck we drew. The one
list we do keep, `OUR_ABILITY_IDS`, agrees with that reading on all six of its
entries.

**The unit is the checkup, and how many there are depends on whose turn it is.**
This is the whole subtlety:

| decision | checkups | why |
|---|---|---|
| our attack, on our turn | **1** | the checkup that opened this turn is already inside the HP we can see, and the attack ends the turn |
| the forced promotion after a KO | **2** (`CHECKUPS_PER_ROUND`) | it resolves at the end of *their* turn: ours comes next, so one checkup opens it and one follows our attack |
| our voluntary retreat (SWITCH) | **1** | our own turn, the promoted body attacks today |

It is wired into the knockout **tests themselves** rather than asked as a second
question beside them — 28 of them in the attacker/target loop of `agent()`, plus
the eight in `ptcg/calc/damage.py` that read their bench (`_snipe_best_target`,
`_bench_attacker_can_ko`, `_promote_ko_active_prizes`, …). That is only safe
because of one property, which the unit tests pin: **`_op_hp_for_our_ko` returns
the printed HP on every board without a Froslass in play**, so nothing that was
calibrated on the printed number moves.

## What it measured

**Firing census** (`--census`, 40 games/deck, self-play against the reference
bot). How many knockout verdicts the reading softens, per game:

| deck | asked | softened |
|---|---|---|
| `marnie_grimmsnarl` | 172.6/game | **42.5/game** |
| `marnie_grimmsnarl_1` | 179.6/game | **43.3/game** |
| `marnie_grimmsnarl_7` | 176.8/game | **15.6/game** |
| `crustle_kangaskhan` | 163.3/game | **0.00** |
| `alakazam` | 115.0/game | **0.00** |

The two controls are the no-op property, measured rather than asserted.

**Frozen corpus**: exactly **one** flipped decision in 3687 — step 90, the
record this was written from — and **zero** in the fifty frozen Alakazam games,
which have no Froslass in them.

**Rules oracle** (`utils/oracle_their_own_drip_finishes_the_body.py`, K=100,
both seats piloted by our agent, their hand sampled from the legal multiset).
The instrument finds its own boards: the same tree loaded twice with
`SHROUD_KO_READING` rebound to False in one arm, every record replayed side by
side. One board disagreed — step 90 — and it graded:

    con la lectura  Meganium   -> 77/100   margen +1.00
    sin ella        Meowth ex  -> 56/100   margen -0.78
    delta +21 pp / +1.78 margen    suelo del tablero 4 pp / 0.25   -> SUPERA el suelo

**Self-play gate** (1500 games per arm per deck, five decks, 7500 games per arm):

| deck | con la lectura | sin ella | delta | control (mismo código) |
|---|---|---|---|---|
| `marnie_grimmsnarl` | 93.20% | 94.53% | −1.33 | −0.27 |
| `marnie_grimmsnarl_1` | 97.87% | 97.47% | +0.40 | **+1.27** (p=0.03) |
| `marnie_grimmsnarl_7` | 97.87% | 97.40% | +0.47 | +0.20 |
| `crustle_kangaskhan` | 75.73% | 75.67% | +0.07 | +0.20 |
| `alakazam` | 99.40% | 99.60% | −0.20 | +0.07 |
| **AGREGADO** | **92.81%** | **92.93%** | **−0.12** (z=−0.29) | **+0.29** (z=0.70) |

**NEUTRAL**: −0.12 sits inside this very run's noise floor of +0.29. And the
floor is not a formality — the control's `marnie_grimmsnarl_1` row separates by
1.27 pts at p=0.03 **with the same code in both arms**, which is the standing
warning about reading one row of this gate without its `--control` at the same
N. The two control decks (+0.07, −0.20) are the no-op measured a second way.

Read it with the gate's own criterion, written before the number existed: this
is not a preference being tuned but a rule of the game the model was reading
half of, and it is a strict no-op wherever the card is not on the field. Neutral
orders the mark, not the revert. The positive evidence is the record, the unit
tests and the oracle; the gate's answer is that nothing else moved.

Why the winrate cannot see it: against these lists the reference bot is already
losing 93–98% of the games. A rule that turns a lost race into a won one two
turns earlier does not show up in a column that is saturated — which is the
reason `utils/search_oracle.py` exists at all.

## What is still open

* **Their bench, past one checkup.** The reading is asked with one checkup on
  our turn, which is right for the prize that lands before they answer. Their
  wounded Munkidori dying two checkups later is a prize the plan still does not
  count.
* **The mirror of `_op_prize_harvest`.** We now know their active is dying; we
  do not yet total up *how many prizes their own board hands us* over the next
  round, the way `_op_prize_harvest` totals what they take from us.
* **The promoted body has to survive the checkup to attack.** Meganium at 50
  reaches our turn at 30 and swings. At 20 or less it dies first, for a prize,
  and the promotion would be a gift. The survival census does not read the drip
  onto the candidate yet.
