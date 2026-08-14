# Our deck and its engines

[← Documentation index](README.md)

The agent pilots **one specific deck**, listed in `deck.csv` (60 card IDs, one
per line). Most of the strategy only makes sense once you know what these cards
do, so this page is the reference for the rest of the documentation.

`python deck/render_deck_image.py` regenerates a picture of the list at
`deck/deck_en.jpg`.

## The list

**Pokémon (20)**

| Count | Card | Role |
| ---: | --- | --- |
| 4 | **Teal Mask Ogerpon ex** | Attacker and tank. Ability *Teal Dance* attaches a Grass energy from hand and draws a card. Its attack *Myriad Leaf Shower* scales with the energy on **both** actives. |
| 2 | **Applin → Dipplin → Hydrapple ex** (2 of each) | The big ex attacker. *Syrup Storm* scales with the Grass energy across our field; *Ripening Charge* moves energy around; 330 HP makes it the body we pivot to when the active is doomed. |
| 2 | **Chikorita → Bayleef → Meganium** (2 of each) | The accelerator. Meganium's *Wild Growth* makes **every Grass energy count double**, and it attacks for 140 while only giving up one prize. |
| 1 | **Tapu Bulu** | Heavy one-prize attacker: *Wood Hammer* for 220. |
| 2 | **Meowth ex** | The hand engine. *Last-Ditch Catch* searches a Supporter out of the deck when it comes down. |
| 1 | **Fezandipiti ex** | Draw engine and sniper. *Flip the Script* draws 3 if one of our Pokémon was knocked out last turn; *Cruel Arrow* can hit anything on the board. |

**Trainers (22)**

| Count | Card | Role |
| ---: | --- | --- |
| 4 | Lillie's Determination | Shuffle the hand away and draw a fresh one. Our main way out of a dead turn. |
| 4 | Ultra Ball | Search any Pokémon, at the cost of discarding two cards. |
| 4 | Bug Catching Set | Bug-type search. |
| 2 | Boss's Orders | Drag a benched opponent Pokémon into the active spot. |
| 2 | Xerosic's Machinations | The opponent discards down to three cards. |
| 1 | Night Stretcher | Recover a Pokémon or an energy from the discard. |
| 1 | Unfair Stamp | Both players shuffle their hand back and draw a new one — the opponent draws fewer. |
| 1 | Lana's Aid | Recover non-ex Pokémon and energy. |
| 1 | Dawn | Supporter draw. |
| 2 | Poké Pad | Small Pokémon search. |

**Stadium and energy (18)**

| Count | Card | Role |
| ---: | --- | --- |
| 4 | Forest of Vitality | Accelerates Grass energy. Also the card we use to remove hostile stadiums. |
| 14 | Basic Grass Energy | All of our energy. |

## The engines the agent is built around

These combos are why several decision modules exist at all.

### Doubled energy (Meganium)

While Meganium is in play, every Grass energy pays for two. The agent never
counts physical energy when deciding "can this Pokémon attack" — it counts
**effective** energy. This one fact reaches almost every calculation: attack
readiness, how many energies a body still needs, whether an attachment unlocks
an attacker this turn.

A hostile stadium can also *raise* our attack costs, so the effective cost is
recomputed at the start of every decision rather than read from a fixed table.

### The hand refill engine: Meowth ex → Lillie's Determination

Benching Meowth ex searches a Supporter out of the deck. Fetching Lillie's
Determination and playing it rebuilds the entire hand — which is how a dead turn
becomes a live one. The chain has rules on both ends, and they are the reason
several vetoes exist:

- Don't bench Meowth if there is already an attacker ready, if the Supporter for
  the turn is already in hand, or if the Supporter slot has been used.
- Do bench it when the hand is weak, when there is no backup attacker, or when
  the turn would otherwise die.
- The Supporter it fetches **gets played that turn** — the search took the
  turn's only Supporter slot, so digging one up and then playing a different one
  wastes the whole line.

### Search that must pay for itself: Ultra Ball

Ultra Ball costs two cards out of hand. The agent only pays that when the card
it finds gets **used this turn**. The single exception is when item lock is
coming: then Ultra Ball is not a resource we keep, it is a resource that
*expires*, so we dig today for the body we will play tomorrow.

The other half of the question is *what* pays. Those two discards have to come
out of surplus, and the discard scorer prices a card by what it does **now** —
which quietly inverts the value of a Supporter once the turn's Supporter slot is
already spent. A Supporter that cannot be played today looks worthless today,
so it is the first thing offered up to pay a cost, even though it is exactly the
card that carries the next turn. So there is a floor: with the Ultra Ball plus
only two other cards in hand, those two cards *are* the cost, the hand ends the
turn at zero, and the search is refused if either of them is a Supporter. Ending
the turn with the Supporter in hand beats benching a body and having no way to
draw again.

### Free draw after a knockout: Fezandipiti ex

*Flip the Script* draws three cards, once per turn, only if one of our Pokémon
was knocked out during the opponent's last turn — and the condition dies at end
of turn. So the agent has rules for digging it up, getting it onto the bench
before anything shuffles it back, recovering it from the discard, and using the
ability **before** deciding attachments (the three new cards can change what we
attach).

### Energy acceleration: Teal Dance and Ripening Charge

Both put energy in play outside the normal one-per-turn attachment, and both
have caps: pouring energy into a body that is about to be knocked out, or into
one that is already at attack cost, is waste that the agent explicitly avoids.

### The shared stadium: Grand Tree

An instant-evolution stadium that either player can use. The agent derives which
evolution chains our deck can actually complete, picks the body worth building,
and knows when keeping our own Forest of Vitality on the field is worth more.

---

Next: [Strategy](strategy.md) · [Matchups](matchups.md)
