"""Short menu branches: NUMBER, YES, NO, END and SPECIAL_CONDITION.

They live together on purpose: between the five of them they do not reach 70
lines, and a module of eight would help nobody understand anything.
"""

from cg.api import OptionType, SelectContext, SpecialConditionType
from ptcg.cartas.ids import SCORE_NEVER, SCORE_VETO
from ptcg.estado.agente import ESTADO


def puntuar(tc, o, score):
    """Returns the score of `o` for the types without a module of their own."""
    _conf_should_attack = tc._conf_should_attack
    _gt_prompt_si_no = tc._gt_prompt_si_no
    _meowth_skip_fetch = tc._meowth_skip_fetch
    can_attack = tc.can_attack
    condition_risky_attack = tc.condition_risky_attack
    context = tc.context

    try:
        if o.type == OptionType.NUMBER:
            score = o.number
        elif o.type == OptionType.YES:
            score = 1
            if _gt_prompt_si_no:
                # Both steps of Grand Tree are optional ("may search"), so the
                # simulator may ask for confirmation. It is ALWAYS accepted:
                # there is no reliable way to tell whether the prompt is step 1
                # (search the Stage 1) or step 2 (the Stage 2), and saying "no"
                # to step 1 throws the whole chain away. The preference for NOT
                # building an ex Stage 2 against an opponent that makes them
                # useless is applied where it is safe: in the CHOICE of the
                # target (`_gt_planes(..., veta_etapa_ex=True)` leaves that chain
                # at Stage 1 and makes the non-ex line win).
                score = 10000
            elif context == SelectContext.ACTIVATE:
    
                score = 10
                if _meowth_skip_fetch:
                    score = SCORE_VETO
            elif context == SelectContext.IS_FIRST:
    
                score = SCORE_VETO
                ESTADO.we_go_first = True
            elif context == SelectContext.COIN_HEAD:
    
                score = 2
        elif o.type == OptionType.NO:
            if _gt_prompt_si_no:
                score = SCORE_VETO
            elif context == SelectContext.IS_FIRST:
                score = 2
                ESTADO.we_go_first = False
            elif context == SelectContext.ACTIVATE and _meowth_skip_fetch:
                score = 10
        elif o.type == OptionType.END:
            if can_attack:
                _end_attack_is_risky = (
                    condition_risky_attack and
                    not (ESTADO.plan.remain_hp is not None and ESTADO.plan.remain_hp <= 0))
                if _conf_should_attack or not _end_attack_is_risky:
                    score = SCORE_NEVER
        elif o.type == OptionType.SPECIAL_CONDITION:
            if context == SelectContext.RECOVER_SPECIAL_CONDITION:
    
                if o.specialConditionType is not None:
                    if o.specialConditionType == SpecialConditionType.PARALYZE:
                        score = 500
                    elif o.specialConditionType == SpecialConditionType.SLEEP:
                        score = 400
                    elif o.specialConditionType == SpecialConditionType.CONFUSE:
                        score = 300
                    elif o.specialConditionType == SpecialConditionType.POISON:
                        score = 200
                    elif o.specialConditionType == SpecialConditionType.BURN:
                        score = 150
            elif context == SelectContext.AFFECT_SPECIAL_CONDITION:
    
                if o.specialConditionType is not None:
                    if o.specialConditionType == SpecialConditionType.PARALYZE:
                        score = 500
                    elif o.specialConditionType == SpecialConditionType.SLEEP:
                        score = 400
                    elif o.specialConditionType == SpecialConditionType.CONFUSE:
                        score = 350
                    elif o.specialConditionType == SpecialConditionType.POISON:
                        score = 200
                    elif o.specialConditionType == SpecialConditionType.BURN:
                        score = 150
        return score
    finally:
        pass


__all__ = ['puntuar']
