"""Supporters varios: Dawn, Lana's Aid y eleccion del mejor de la mano.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.cartas.ids import Basic_Grass_Energy, Dawn, Lanas_Aid, Lillie_Determination, SCORE_SUPPORTER_VALUE_BASE, SCORE_VETO
from ptcg.motor.contexto import DecisionContext
from ptcg.motor.reglas import _Ajuste, _ReglaFija, _resolver_con_traza
from ptcg.decision.disrupcion import _stamp_pendiente


def _robo_de_lillie(my_prize):
    """Cartas que roba Lillie's Determination: 6, u 8 con los 6 premios
    intactos (texto de la carta)."""
    return 8 if my_prize == 6 else 6


def _lana_veto_duro(c):
    """Vetos que en el original RETORNAN sin pasar por los ajustes (los
    ajustes de abajo no deben rescatarlos)."""
    if c.state.supporterPlayed:
        return True
    if c.op_is_comfey_deck and sum(
            1 for x in (c.my_state.discard or [])
            if getattr(x, 'id', None) == Basic_Grass_Energy) < 2:
        # vs Comfey (user, registro_005): Lana's SOLO para recuperar >= 2
        # energias (nuestros Pokemon alli son ex: Lana's no los recupera).
        return True
    if _stamp_pendiente(c):
        return True
    return False


_REGLAS_LANA_PLAY = [
    _ReglaFija("veto_duro",
               _lana_veto_duro,
               lambda c: SCORE_VETO),
    # sin_valor puede ser RESCATADO por suelo_linea_mega (fiel al original,
    # donde ese max() vive tras la asignacion del veto por valor).
    _ReglaFija("sin_valor",
               lambda c: c.supp_values.get(Lanas_Aid, 0) <= 0,
               lambda c: SCORE_VETO),
    _ReglaFija("valor_del_supporter",
               lambda c: True,
               lambda c: (SCORE_SUPPORTER_VALUE_BASE
                          + int(c.supp_values.get(Lanas_Aid, 0) * 1.4)
                          + c.supporter_boost)),
]


_AJUSTES_LANA_PLAY = [
    # Linea Meganium activa sin energia jugable: recuperar energia del
    # descarte vale un suelo de 4500.
    _Ajuste("suelo_linea_mega",
            lambda c, s: (not _lana_veto_duro(c)
                          and c.mega_line_active and s < 4500
                          and not c.state.supporterPlayed
                          and c.hand_counts.get(Basic_Grass_Energy, 0) == 0
                          and not c.state.energyAttached
                          and any(x.id == Basic_Grass_Energy
                                  for x in c.my_state.discard)),
            lambda c, s: max(s, 4500)),
    # Regla (user, log 86509038 paso 62 vs Mega Lucario, PERDIDA): sin
    # atacante este turno, Lana's solo supera a Lillie's si HABILITA un
    # ataque; si no, cede (cap 2000, sigue jugable por si Lillie's cae).
    _Ajuste("cede_a_lillie_sin_ataque",
            lambda c, s: (not _lana_veto_duro(c) and s > 0
                          and c.active_cant_attack
                          and c.hand_counts.get(Lillie_Determination, 0) >= 1
                          and not c.state.supporterPlayed
                          and not c.supp_values.get('_lana_enables_attack')),
            lambda c, s: min(s, 2000)),
]


def _score_lanas_aid_play(ctx: DecisionContext, score: int) -> int:
    """Puntua la jugada de Lana's Aid (recupera Pokemon no-ex + Energia del
    descarte). Cuerpo migrado al MOTOR DE REGLAS (fase 4); el `score`
    entrante se ignora (el original lo sobreescribia en todas las ramas)."""
    return _resolver_con_traza("lana->play", _REGLAS_LANA_PLAY,
                               _AJUSTES_LANA_PLAY, ctx, defecto=0)


def _score_dawn_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Dawn (busca Basico + Fase 1 + Fase 2 del mazo).

    Rama extraida del bucle de scoring SIN cambio de comportamiento para que
    `_supp_play_score` (el predictor de "que Supporter se juega este turno")
    pueda consultar la MISMA fuente que decide de verdad."""
    if ctx.state.supporterPlayed:
        return SCORE_VETO
    if _stamp_pendiente(ctx):
        return SCORE_VETO
    _dawn_val = ctx.supp_values.get(Dawn, 0)
    if _dawn_val <= 0:
        return SCORE_VETO
    return (SCORE_SUPPORTER_VALUE_BASE + int(_dawn_val * 1.4)
            + ctx.supporter_boost)

__all__ = [
    '_robo_de_lillie',
    '_lana_veto_duro',
    '_score_lanas_aid_play',
    '_score_dawn_play',
    '_REGLAS_LANA_PLAY',
    '_AJUSTES_LANA_PLAY',
]
