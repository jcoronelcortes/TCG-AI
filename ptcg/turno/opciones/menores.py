"""Ramas cortas del menu: NUMBER, YES, NO, END y SPECIAL_CONDITION.

Van juntas a proposito: entre las cinco no llegan a 70 lineas y un modulo
de ocho no ayuda a nadie a entender nada.
"""

from cg.api import OptionType, SelectContext, SpecialConditionType
from ptcg.cartas.ids import SCORE_NEVER, SCORE_VETO
from ptcg.estado.agente import ESTADO


def puntuar(tc, o, score):
    """Devuelve el puntaje de `o` para los tipos sin modulo propio."""
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
                # Los dos pasos de Grand Tree son opcionales ("puede buscar"),
                # asi que el simulador puede pedir confirmacion. Se acepta
                # SIEMPRE: no hay forma fiable de saber si el prompt es el paso
                # 1 (buscar la Fase 1) o el paso 2 (la Fase 2), y decir "no" al
                # paso 1 tira la cadena entera. La preferencia por NO construir
                # una Etapa 2 ex contra un rival que las inmuniza se aplica
                # donde si es seguro: en la ELECCION del objetivo
                # (`_gt_planes(..., veta_etapa_ex=True)` deja esa cadena en
                # Fase 1 y hace ganar a la linea no-ex).
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
