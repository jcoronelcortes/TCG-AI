"""Scoring constants shared by several phases.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

from ptcg.cards.ids import Dipplin, Fezandipiti_ex, Hydrapple_ex, Meganium, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.cards.ids import Boss_Orders, Dawn, Lanas_Aid, Lillie_Determination, Xerosic_Machinations


# Floor of the commitment: above the maximum of any other Supporter in hand
# (Xerosic ~7300 is the highest) so the tie-break does not depend on the deck.
SCORE_LD_SUPP_COMPROMETIDO = 8000


# --- WHICH Supporter will be PLAYED this turn? ------------------------------
# Only ONE Supporter is played per turn, so any decision that SPENDS a resource
# to SEARCH for a Supporter (Meowth ex / Last-Ditch Catch, Poke Pad...) needs to
# know BEFOREHAND who is going to take that single slot. These two helpers are
# the single source of that answer: they dispatch to the SAME `_score_*` the
# scoring loop uses, so the decision to spend the resource and the decision of
# which Supporter ends up being played cannot contradict each other.
_SUPP_PLAY_IDS = (Boss_Orders, Xerosic_Machinations, Lillie_Determination,
                  Dawn, Lanas_Aid)


# Main attackers evaluated in the ready-to-attack blocks.
MAIN_ATTACKERS = (
    Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
    Tapu_Bulu, Fezandipiti_ex, Meganium, Pinsir,
)


# WHO GOES IN FRONT OF THE MEGA STARMIE LINE. The top of the user's order and
# the gap between its rungs. The band sits ABOVE the sacrifice menu's own top
# rung (6000, the Chikorita of `_doomed_sac_context`) because it is a different
# question with a different answer: that order asks which of two evolution
# lines we would rather spend, this one asks which body pays ONE prize instead
# of two against a deck that one-shots any ex we leave in front. Seven rungs
# 100 apart -- Tapu Bulu, Applin without energy, Applin with energy, Chikorita,
# Dipplin, Bayleef, Meowth ex -- so no two of them can ever tie and have the
# menu order decide. See STARMIE_SAC_PROMOTE_ORDER in ptcg/cards/ids.py.
OPENING_SAC_PROMOTE_TOP = 7000
OPENING_SAC_PROMOTE_STEP = 100


# Terminal PROMOTION adjustment (see "SURVIVAL WHEN PROMOTING"). The doomed body
# drops far enough to yield to any real survivor (the measured case: a charged
# Ogerpon 4557 -> -1443, below the Hydrapple ex at 259).
PROMO_DOOMED_PENALTY = 6000


# With no survivors, each extra prize we hand over costs this much.
PROMO_PRIZE_PENALTY = 1500


# Whoever KNOCKS OUT the opposing active is promoted above anyone who does not,
# tank included (user). Above the maximum score of the promotion branches
# (9500 = `_promote_setup_ko_attacker`) so that it is a GUARANTEE and does not
# depend on the knocker scoring higher base than the tank:
# `_ko_prefer_basic_general` gives 8500+ to a 1-prize basic and the sturdy wall
# 6100, so a knocker at ~4500 could lose. Among several knockers the base score
# decides.
PROMO_KO_BONUS = 20000


# MATCH POINT: the opponent only needs to knock this body out to take the last
# prize. That is not a bad trade, it is losing the game -> veto, not a penalty.
# It goes BELOW SCORE_NEVER (-10000) on purpose: other promotion vetoes use that
# exact value (e.g. "the Meganium line does not go active") and a tie at -10000
# would leave the tie-break to the random order of the options, exactly between
# the body that endures and the one that makes us lose.
PROMO_MATCH_POINT_VETO = -30000


# THE LAST STAND: at their match point every body on our bench pays at least
# their remaining pile, so the price tag stops separating the candidates and
# what is left is who absorbs their reply best (`_mp_last_stand`).
#
# 9450 places it just BELOW the two branches that are about acting FIRST -- the
# guaranteed finisher (9500) and, above everything, the body that knocks out
# (+`PROMO_KO_BONUS`) -- and above the whole cheap-wall family (8500 + hp/10 of
# `_ko_prefer_basic_general`, 9000 for an Applin, 6100 for the sturdy basic):
# when their next knockout ends the game, taking a prize or removing their
# attacker still comes first, and handing over a cheaper corpse no longer does.
PROMO_LAST_STAND = 9450


def _purchase_of_this_turn(card_id, hand, bought_serials):
    """How many copies of `card_id` in `hand` OUR OWN searches bought today.

    The other side of `_SUPP_PLAY_IDS` above, and the same doctrine: the
    decision that SPENDS a resource and the decision that PRICES the hand
    afterwards cannot contradict each other. Here the resource has already been
    spent -- an Ultra Ball, a Meowth ex ability, a Bug Catching Set went and got
    this card -- and the discard ladders, which know only what a card IS, are
    about to price it as if it had always been sitting there.

    A COUNT, not a list of serials, because copies of one card are
    interchangeable: what has to survive the next cost is as many copies as the
    search brought, not the physical ones it brought. `bought_serials` is
    `AGENT_STATE._bought_this_turn` (taken off the MOVE_CARD logs; a DRAW is not
    a purchase). It names no card and no deck.
    """
    if not bought_serials:
        return 0
    return sum(1 for c in hand
               if getattr(c, 'id', None) == card_id
               and getattr(c, 'serial', None) in bought_serials)


__all__ = [
    'SCORE_LD_SUPP_COMPROMETIDO',
    '_SUPP_PLAY_IDS',
    '_purchase_of_this_turn',
    'MAIN_ATTACKERS',
    'PROMO_DOOMED_PENALTY',
    'PROMO_KO_BONUS',
    'PROMO_LAST_STAND',
    'PROMO_MATCH_POINT_VETO',
    'PROMO_PRIZE_PENALTY',
    'OPENING_SAC_PROMOTE_TOP',
    'OPENING_SAC_PROMOTE_STEP',
]
