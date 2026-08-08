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

__all__ = [
    'SCORE_LD_SUPP_COMPROMETIDO',
    '_SUPP_PLAY_IDS',
    'MAIN_ATTACKERS',
    'PROMO_DOOMED_PENALTY',
    'PROMO_KO_BONUS',
    'PROMO_MATCH_POINT_VETO',
    'PROMO_PRIZE_PENALTY',
    'OPENING_SAC_PROMOTE_TOP',
    'OPENING_SAC_PROMOTE_STEP',
]
