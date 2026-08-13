"""Card tables derived from the simulator: `card_table` and `attack_table`.

Extracted VERBATIM from main.py in wave 2 of the refactor
(docs/project-history.md).

They are not literal constants (they come from `cg.api`), but they ARE
deterministic and read-only: they are built once at import time and nobody
mutates them -- verified with `utils/purity.py`. That is exactly the difference
with `ATTACK_ENERGY_REQ`, which looks like a fixed table and is really TURN
state (the Nighttime Mine tax rewrites it on every `agent()` call), which is why
that one stayed in main.py until wave 3.

CAREFUL when moving them: modules that do `from ptcg.cartas.tablas import
card_table` FREEZE the binding at import time. In production it makes no
difference (nobody reassigns them), but a test that patches `main.card_table`
no longer reaches them. That is why their CONSUMERS stayed in main.py until
wave 3, where it was decided who owns the module-level state.
"""

import re

from cg.api import CardType, all_card_data, all_attack

all_card = all_card_data()
card_table = {c.cardId: c for c in all_card}
# Table attack-id -> Attack object (name/damage/energies). The `card.attacks`
# entries are IDs (ints), not objects, so _op_best_damage_vs (which does
# getattr(id, 'damage')) always returns 0. This table is what makes it possible
# to RESOLVE the real damage of the opposing active's attack when it is needed
# (see _op_active_attack_damage_to).
attack_table = {a.attackId: a for a in all_attack()}


# Index NAME -> card data: `evolvesFrom` stores the NAME of the pre-evolution,
# so walking a chain upwards means resolving names. It covers ALL the cards in
# the environment (not just the ones in our deck): the lines that have to be
# read here are the OPPONENT's.
_CARD_BY_NAME = {}

# Reverse index NAME -> cards that evolve FROM that name. It complements
# `_CARD_BY_NAME` (which walks up the chain) so the chain can also be walked
# DOWN, to know what an opposing line ends in. It covers ALL the cards in the
# environment.
_EVOLUTIONS_BY_NAME = {}


# The printed rules text of every card, lowercased and with the newlines
# flattened, so a clause can be matched as one sentence.
_PRINTED_TEXT = {
    cid: re.sub(r'\s+', ' ',
                ' '.join((s.text or '') for s in (c.skills or [])).lower())
    for cid, c in card_table.items()}


# =============================================================================
# THE TWO HALVES OF "THE HAND RESET GOES LAST"
# -----------------------------------------------------------------------------
# A card that SHUFFLES OUR HAND INTO THE DECK (or discards it) destroys every
# card still sitting in the hand, so anything that was going to SPEND one of
# those cards has to happen FIRST. That is an ORDER relation between two plays,
# and neither of the two scores can express it: each is priced on its own merits
# and they meet in the same tier, where the higher number simply wins.
#
# Both sets are read off the PRINTED TEXT of every card in the environment, not
# off a curated list, because that is exactly what the property is. It holds for
# our deck and for any other, today's cards and tomorrow's: whichever refill the
# deck runs (Lillie's Determination, Lacey, Judge, Carmine, the Unfair Stamp...)
# and whichever charging ability sits on the board (Teal Dance, Ripening Charge,
# Inferno Fandango...), the arithmetic is the same.
#
# CAREFUL -- the opposite order is the right one for the abilities that PRODUCE
# cards. Flip the Script draws 3, and drawing them BEFORE a reset only feeds them
# back into the deck; that is why `_lillie_blocks_fez_ability` / the Unfair Stamp
# blocker put the refill FIRST and the draw AFTER. The discriminator is not
# "ability vs Supporter", it is which way the cards flow: what the hand PAYS goes
# before the reset, what the hand RECEIVES goes after it.
# =============================================================================

# Plays that empty OUR hand THE MOMENT they resolve.
#
# "shuffle your hand into your deck" (Lillie's Determination, Lacey),
# "each player shuffles their hand into their deck" (the Unfair Stamp, Judge,
# Harlequin) and "discard your hand" (Carmine, Larry's Skill) all leave the hand
# at zero before drawing again. Amarys and its kind are deliberately NOT here:
# their discard happens "at the end of this turn", so nothing that is played
# during the turn loses its cost to them.
#
# Pokemon are excluded: this set answers "which PLAY from hand wipes the hand",
# and a Pokemon's ability text is read by the other set.
HAND_RESET_PLAY_IDS = frozenset(
    cid for cid, c in card_table.items()
    if c.cardType != CardType.POKEMON
    and 'at the end of this turn' not in _PRINTED_TEXT[cid]
    and (re.search(r'shuffle[sd]? (?:your|their) hand into (?:your|their) deck',
                   _PRINTED_TEXT[cid])
         or re.search(r'discard (?:your|their) hand', _PRINTED_TEXT[cid])))

# Abilities whose COST is a card taken out of our hand.
#
# The printed phrase is always the same -- "...a card from your hand" -- whether
# the ability attaches it (Teal Dance, Ripening Charge, Inferno Fandango),
# discards it (N's Zoroark ex's Trade) or puts it at the bottom of the deck
# (Quaquaval's Up-Tempo). Meowth ex's Last-Ditch Catch reads "when you play this
# Pokemon FROM YOUR HAND onto your Bench": it names the hand as the ORIGIN OF THE
# BODY, never as a card it spends, and the "card from your hand" wording is what
# keeps it (and every trigger like it) out.
HAND_COST_ABILITY_IDS = frozenset(
    cid for cid, c in card_table.items()
    if c.cardType == CardType.POKEMON
    and re.search(r'cards? from your hand', _PRINTED_TEXT[cid]))

# The subset that gives the hand back everything it takes from it.
#
# HOW MANY it takes: every one of them names the hand the same way ("...card
# from your hand"), and the ones that take more than one say so with a digit --
# "discard 2 cards from your hand" (Team Rocket's Porygon-Z), "attach up to 2
# basic {R} energy cards from your hand" (Ethan's Ho-Oh ex, Clawitzer,
# Bloodmoon Ursaluna). Everything else spends exactly one. The "up to N" ones
# are priced at their MAXIMUM: the claim this set makes has to hold for the
# worst case.
#
# HOW MANY it gives back: the cards it DRAWS in the same sentence. Teal Dance
# ("draw a card"), N's Zoroark ex's Trade ("draw 2 cards") and Lunatone's
# Moonlight Dance ("draw 3 cards") take one and hand at least one back;
# Ripening Charge attaches and HEALS, and hands nothing back.
#
# WHY THE DISTINCTION EARNS ITS KEEP: an ability in this set leaves the hand
# exactly as big as it found it, so it can be moved ahead of a play that pays
# by discarding from hand WITHOUT ever costing that play its cost. One that is
# not in it shrinks the hand, and a search left with fewer cards than its cost
# is a search that dies in hand -- the failure `_ub_engine_refresh_pivot` was
# written for. Order is free for the first family and a trade-off for the
# second, which is why only the first is reordered (`ptcg/turn/finalize.py`).
_HAND_COST_COUNT = re.compile(r'(?:up to )?(\d+)[^.]{0,40}? cards from your hand')
_HAND_GIVES_BACK = re.compile(r'draw (\d+|a|another) cards?')


def _cards_counted(match, default):
    """The digit the clause names, `default` when it names none or is absent."""
    if match is None:
        return default
    return int(match.group(1)) if match.group(1).isdigit() else 1


HAND_NEUTRAL_ABILITY_IDS = frozenset(
    cid for cid in HAND_COST_ABILITY_IDS
    if _cards_counted(_HAND_GIVES_BACK.search(_PRINTED_TEXT[cid]), 0)
    >= _cards_counted(_HAND_COST_COUNT.search(_PRINTED_TEXT[cid]), 1))

# =============================================================================
# THE SMALLER DESTROYER: the play that does not WIPE the hand, it PICKS from it
# -----------------------------------------------------------------------------
# `HAND_RESET_PLAY_IDS` above is the total destroyer -- it takes the whole hand
# and nothing in it survives. This set is the partial one: a play whose COST is
# discarding a FIXED NUMBER of cards from our hand, chosen by us.
#
#     Ultra Ball      "you can use this card only if you discard 2 other
#                      cards from your hand"
#     Secret Box      "...discard 3 other cards from your hand"
#     Morty's Conviction / Iris's Fighting Spirit / Canari
#                     "...discard another card from your hand"
#
# It destroys less than a reset does, and for the ORDER question that changes
# nothing: the cards it takes are gone all the same, and the card an ability
# was going to spend is one of the ones it may take -- a spare Basic Energy is
# exactly what a discard scorer reads as surplus.
#
# Pokemon are excluded for the same reason as in `HAND_RESET_PLAY_IDS`: this
# set answers "which PLAY from hand spends other cards in it", and a Pokemon's
# ability text is read by `HAND_COST_ABILITY_IDS`.
# =============================================================================
HAND_DISCARD_COST_PLAY_IDS = frozenset(
    cid for cid, c in card_table.items()
    if c.cardType != CardType.POKEMON
    and re.search(r'discard (?:\d+|another|a) (?:other )?cards? from your hand',
                  _PRINTED_TEXT[cid]))

# =============================================================================
# THE HAND RECYCLER: the half of the reset that FEEDS THE DECK
# -----------------------------------------------------------------------------
# `HAND_RESET_PLAY_IDS` above answers "does this play wipe my hand?", and for
# the ORDER question that is the whole property: a card that is about to be
# destroyed has to be spent first, and it makes no difference whether it is
# destroyed into the deck or into the discard pile.
#
# Against a MILL deck the difference is the entire game. Their win condition is
# our deck reaching zero, so where the hand LANDS is the only thing that
# matters: "shuffle your hand into your deck" (Lillie's Determination, Lacey,
# the Unfair Stamp, Judge) hands cards BACK to the clock they are running down,
# and "discard your hand" (Carmine, Larry's Skill) helps them finish it.
#
# This subset is therefore NOT a rewording of the one above -- it is the
# narrower claim, and only it may be read as "the card that answers a mill".
# Same discipline as its parent: derived from the printed text, so it holds for
# whichever refill the deck ends up running.
HAND_TO_DECK_PLAY_IDS = frozenset(
    cid for cid in HAND_RESET_PLAY_IDS
    if re.search(r'shuffle[sd]? (?:your|their) hand into (?:your|their) deck',
                 _PRINTED_TEXT[cid]))


__all__ = [
    'all_card',
    'card_table',
    'attack_table',
    'HAND_RESET_PLAY_IDS',
    'HAND_TO_DECK_PLAY_IDS',
    'HAND_COST_ABILITY_IDS',
    'HAND_NEUTRAL_ABILITY_IDS',
    'HAND_DISCARD_COST_PLAY_IDS',
    '_CARD_BY_NAME',
    '_EVOLUTIONS_BY_NAME',
]
