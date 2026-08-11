# The second copy cannot be the reason (the KEEP floor is a role)

[← Documentation index](../README.md) · Queue item 1 of
[the night of 11 Aug 2026](night-2026-08-11.md)

**The criterion below was written before the change and before the after-number.**
That ordering is the whole point: a policy change whose acceptance test is
written after its measurement has no acceptance test.

---

## The defect

`ptcg/turn/options/card.py`, the Supporter block of the forced discard:

```python
if card.id in _SUPP_PLAY_IDS and card.id in _supp_values:
    _dsv_live = _supp_values.get(card.id, 0) or 0
    _dsv_rivals = [...every OTHER Supporter in hand...]
    if _dsv_rivals:
        if _dsv_live > 0 and _dsv_live > max(_dsv_rivals):
            score = min(score, DISCARD_SUPPORTER_LIVE_KEEP)   # = 2
        elif _dsv_live <= 0 and max(_dsv_rivals) > 0:
            score = max(score, DISCARD_SUPPORTER_DEAD_DROP)   # = 36
```

Sixty lines above it, the ladder already latches Lillie's Determination
(`_lillie_protected_once`: the first copy priced is the out and scores 2, the
spare is released at 72). The block then floors the spare back to 2, because
"the best Supporter I could still play" is exactly as true of the second copy as
of the first. **The latch fires and the general rule undoes it.**

It is [[la-regla-general-va-antes-que-su-caso-especial]] inverted: here the
general rule overwrites its own special case.

## The census before (`python utils/duplicate_protection_audit.py`)

118 discard menus over 50 frozen records; 47 pairs share a score, 12 of them in
the KEEP band (≤ 30):

    score 2   Lillie's Determination  x2   registro_006 turn 4  action 5
    score 2   Lillie's Determination  x2   registro_007 turn 3  action 2  [FORCED]
    score 2   Lillie's Determination  x2   registro_016 turn 1  action 5  [FORCED]
    score 2   Meowth ex               x2   registro_021 turn 5  action 3  [FORCED]
    score 2   Lillie's Determination  x2   registro_028 turn 7  action 4  [FORCED]
    score 8   Teal Mask Ogerpon ex    x2   registro_012 turn 6  action 12
    score 18/20/28  Basic {G} Energy, Meganium (seven more)

Four of the five score-2 pairs are this defect. The fifth is the Meowth ex flip
Wave 1 left standing, and it is NOT this one: a Basic Pokémon is not in
`_SUPP_PLAY_IDS`, so this block never speaks about it.

## The change, in one sentence

**The KEEP floor is a ROLE, and only one card can play it**, so it is handed out
**once per card id per menu**. The spare copies keep whatever price the ladder
gave them.

The DROP branch does **not** latch, and the asymmetry is the argument: "this
Supporter is dead and another one is live" is equally true of every copy, and
every copy really should go. Only the *keep* is a claim on a job — one Supporter
per turn — and a job cannot be held twice.

Card-agnostic, like the block it lives in: it names no card and no deck. It
covers Boss's Orders, Dawn and Lana's Aid, none of which carry a ladder latch of
their own, on the same sentence.

## What has to be true for it to be kept

1. **The census loses the Lillie's pairs and gains nothing.** The four score-2
   Lillie's rows leave the KEEP band (2/72 is the latch working, and the audit
   already reports an unequal pair as not-a-finding). No pair that was outside
   the band enters it.
2. **The Meowth ex pair does not move.** If it does, the change is reaching
   past the Supporter band and the reading of what it does is wrong.
3. **Every suite flip is explained by this one sentence.** A flip in a menu that
   holds a single copy of every priced Supporter falsifies the change outright.
4. **The corpus flips are of the same shape**, reviewed one by one before the
   snapshot is accepted.

**Revert if:** any flip lands in a menu with no duplicated priced Supporter, or
the number of non-Supporters discarded changes anywhere. This change permutes
*which Supporter* is sacrificed; it must never change *how many* other cards are.

---

## What happened when it was measured

### The census after: four options, in four menus, out of 118

Option-by-option diff of the two dumps (`log/latch-lillie/base.json` against
`despues.json`), all 118 menus and every option in them:

    registro_006_alakazam_6      t4  a5  cost    Lillie's Determination  2 -> 72
    registro_007_alakazam_7      t3  a2  FORCED  Lillie's Determination  2 -> 72
    registro_016_crustle_wall_13 t1  a5  FORCED  Lillie's Determination  2 -> 72
    registro_028_crustle_wall_8  t7  a4  FORCED  Lillie's Determination  2 -> 72

Nothing else in the corpus changed by a single point. The KEEP band goes from 12
pairs to 8, and the 8 are a subset of the 12 — **criteria 1 and 2 hold exactly**:
the Meowth ex pair does not move (a Basic is not in `_SUPP_PLAY_IDS`), and no
pair enters the band.

The wider picture the same dump shows, and it is what makes the reading safe:
every other duplicated Supporter pair in the corpus was **already** honest.
Two Boss's Orders tie at 85 in four menus — fodder agreeing it is fodder, because
the layer made some other Supporter the live one. Two Xerosic's Machinations tie
at 60 in two more — the value layer never prices the cap, and about the unpriced
this block says nothing. The four Lillie's rows were the only place a floor was
being handed out twice.

### The suite: 2235 pass, and the one failure is the corpus guard

`tests/test_the_frozen_corpus_runs_on_a_clean_checkout.py` reports exactly four
flipped decisions — the same four records, no others. In every one of them a
spare Lillie's leaves so that something the board can actually use stays:

| record | was discarded | is discarded now | what the change bought |
| --- | --- | --- | --- |
| 006 t4 | Ultra Ball, **Boss's Orders** | Ultra Ball, **spare Lillie's** | keeps the gust |
| 007 t3 | Forest, Poké Pad, Boss's, **Grass** | **spare Lillie's**, Forest, Poké Pad, Boss's | keeps the fuel |
| 016 t1 | Lana's, Night Stretcher, Forest, **Bug Catching Set** | Lana's, **spare Lillie's**, Night Stretcher, Forest | keeps the search |
| 028 t7 | Forest, Xerosic, Meganium, Fez, **Grass** | Forest, **spare Lillie's**, Xerosic, Meganium, Fez | keeps the fuel |

`utils/lint_architecture.py`: no violations, eight rules.

### The clause of the criterion that was falsified, and why

> *"…or the number of non-Supporters discarded changes anywhere."*

**Three of the four flips break it** (007, 016 and 028 each keep a non-Supporter
that used to go). The clause is not reporting a defect in the change; it was
written wrong, and the reason is worth keeping because it is a trap the next
policy change on this ladder will walk into.

That sentence is a real guarantee, but it belongs to the **other** branch. It
comes from the design note of `DISCARD_SUPPORTER_DEAD_DROP`, where 36 was placed
between the highest single-copy Supporter score (35) and the cheapest generic
item (38) *precisely* so that demoting a dead Supporter can never reach past the
Supporter band. Releasing a latch is the opposite motion: the spare falls to the
ladder's own fodder price, 72, which by construction sits **above** the item
band. A repair that says "this copy is spare cardboard" and then forbids it from
outranking an item has forbidden itself. No version of this change could have
satisfied that clause.

What the clause was really guarding — *do not let this throw away something the
board needs* — is not only intact, it runs the other way: in all four flips the
agent now pays with the dead copy instead of with fuel, a search, or a gust. That
is the same sentence as queue item 2, [[pendiente-el-coste-no-se-come-el-combustible-de-lo-que-compra]], arriving from the other side.

**Criteria 1, 2, 3 and 4 hold. The falsified clause is amended, in the open,
with its reason** — and the amendment is a narrowing, not a widening: *within the
Supporter band the DROP branch must still never reach past it, and that branch
was not touched.*

### The registro

`tests/test_the_keep_floor_is_a_role.py`, on `registro_028` turn 7 (the finding)
and turn 12 (the control: two Boss's Orders that hold no role and must go on
tying as fodder). Nine tests. Its own two halves, run before it was believed:
with the latch removed, four of them fail and the five controls stay green.

