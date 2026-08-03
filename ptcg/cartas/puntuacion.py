"""Constantes de puntuacion compartidas por varias fases.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.cartas.ids import Boss_Orders, Dawn, Lanas_Aid, Lillie_Determination, Xerosic_Machinations


# Piso del compromiso: por encima del maximo de cualquier otro Supporter de la
# mano (Xerosic ~7300 es el mas alto) para que el desempate no dependa del mazo.
SCORE_LD_SUPP_COMPROMETIDO = 8000


# --- ¿QUE Supporter se JUGARA este turno? -----------------------------------
# Solo se juega UN Supporter por turno, asi que cualquier decision que GASTE un
# recurso para BUSCAR un Supporter (Meowth ex / Last-Ditch Catch, Poke Pad...)
# necesita saber ANTES quien se va a quedar con ese unico hueco. Estos dos
# helpers son la fuente unica de esa pregunta: despachan al MISMO `_score_*`
# que usa el bucle de scoring, asi que la decision de gastar el recurso y la
# de que Supporter acaba jugandose no pueden contradecirse.
_SUPP_PLAY_IDS = (Boss_Orders, Xerosic_Machinations, Lillie_Determination,
                  Dawn, Lanas_Aid)

__all__ = [
    'SCORE_LD_SUPP_COMPROMETIDO',
    '_SUPP_PLAY_IDS',
]
