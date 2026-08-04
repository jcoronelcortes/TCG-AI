"""Derived card groups: evolution lines and strategic sets.

Extracted VERBATIM from main.py by utils/extraer_puros.py
(docs/project-history.md). There is NO logic here: only constants that
depend solely on literals. This module cannot import state or touch the
simulator -- utils/lint_arquitectura.py (R2) watches it.

main.py re-exports it with `import *`, so the `__all__` at the end has to list
ALL the names, including the ones starting with `_` (which `import *` would
otherwise skip).
"""

from ptcg.cartas.ids import Applin, Bayleef, Chikorita, Dipplin, Hydrapple_ex, Meganium, Teal_Mask_Ogerpon_ex




# Our TWO evolution lines, from basic to stage 2.
EVO_LINES = (
    (Applin, Dipplin, Hydrapple_ex),
    (Chikorita, Bayleef, Meganium),
)



# =============================================================================
# GRAND TREE (id 1249): INSTANT EVOLUTION ENGINE
# -----------------------------------------------------------------------------
# With the stadium on the field (no matter who played it) we gain, ONCE PER TURN
# and FOR FREE, an entire Basic -> Stage 1 -> Stage 2 chain pulled out of the
# deck. It is the most profitable development play of the turn: it does not
# spend the card in hand, it does not spend the attachment, it does not spend the
# attack, and it also THINS the deck.
#
# WHICH BODY TO BUILD (user's rule, generalised to any deck):
#   * If we already have one of our Stage 2s in play and NOT the other, the
#     MISSING one is completed -> the `GT_VALOR_DIVERSIFICAR` bonus. In this deck
#     that is exactly "with Meganium in play -> Hydrapple ex" and "with Hydrapple
#     ex in play -> Meganium".
#   * If we ALREADY have both (or neither), the VALUE of the resulting body
#     decides (`_gt_valor_cuerpo`: HP + a bonus for having an Ability) -> the copy
#     of the stronger body wins. In this deck that is "with both in play -> a
#     second Hydrapple ex" (330 HP + Ripening Charge against Meganium's 160 HP).
#     `GT_VALOR_DIVERSIFICAR` (1200) is deliberately larger than any reasonable
#     body difference, so that diversifying rules when it applies.
#   * On a tie, the Basic with MORE energy already invested is preferred (same
#     convention as the EVOLVE branch: `9000 + energy`).
#
# MATCHUPS: against an opponent that makes our ex Pokemon USELESS (Crustle,
# Sylveon...), the ex Stage 2 is discarded and the chain stops EXPRESSLY at
# Stage 1 (`stage2_id == 0`): step 2 of the card is optional ("may"), and giving
# away a 2-prize body that cannot damage the wall is worse than not evolving. It
# mirrors the veto of the Hydrapple ex EVOLVE branch vs Crustle.
# =============================================================================

# Score bands of the stadium's ABILITY (ABILITY branch). They sit above evolving
# from hand (Meganium 35000 / Hydrapple ex 33000) because Grand Tree does NOT
# consume the card in hand: if both plays are available, the free one first.
GT_SCORE_FULL_CHAIN = 36000
GT_SCORE_STAGE1_ONLY = 34000
# Bonus to the FETCH (Ultra Ball / Bug Catching Set / Poke Pad / Night Stretcher)
# of the Basic the stadium enables, and to putting it down from hand afterwards.
# Deliberately small: they are tie-breakers, they must not step on the existing
# priorities.
GT_FETCH_BONUS = 600
GT_PLAY_BASICO_BONUS = 500
# Components of a plan's value (see the block header).
GT_VALUE_STAGE2 = 2000
GT_VALUE_DIVERSIFY = 1200
GT_PENALTY_DOOMED_ACTIVE = 1500



# EFFECTIVE energy requirements to attack, per card (single source of truth).
# len(energies) is ALREADY effective energy (the observation duplicates Grass
# through Wild Growth), so it is compared directly against these values.
# Nighttime Mine (card 1266): "the attacks of each Tera Pokemon in play (of BOTH
# players) cost {C} more". CAREFUL with the number: 1266 is also the id of the
# ATTACK Splashing_Dodge_Atk, but they are different namespaces (card_table vs
# attack_table).
#
# It hits us squarely: Teal Mask Ogerpon ex is our ONLY Tera and we run 4. With
# the mine on the field its attack goes from 3 to 4 energies. Measured over the
# real meta (decks_competidores/, top-300): 80% of the Alakazam lists run it at
# 2 copies, and Alakazam is 19.7% of the meta.
#
# Verified against the engine (30 games): with the mine on the field and 3
# energies the menu does NOT offer ATTACK (13 cases); with 4 it does (22).
# Without the mine, 3 is enough (56). The agent believed Ogerpon was ready and
# it was not.
Nighttime_Mine = 1266
# Our Tera Pokemon, the only ones whose cost the mine raises.
OUR_TERA_IDS = {Teal_Mask_Ogerpon_ex}


__all__ = [
    'EVO_LINES',
    'GT_SCORE_FULL_CHAIN',
    'GT_SCORE_STAGE1_ONLY',
    'GT_FETCH_BONUS',
    'GT_PLAY_BASICO_BONUS',
    'GT_VALUE_STAGE2',
    'GT_VALUE_DIVERSIFY',
    'GT_PENALTY_DOOMED_ACTIVE',
    'Nighttime_Mine',
    'OUR_TERA_IDS',
]
