"""Constantes de puntuacion compartidas por varias fases.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.cartas.ids import Dipplin, Fezandipiti_ex, Hydrapple_ex, Meganium, Pinsir, Tapu_Bulu, Teal_Mask_Ogerpon_ex
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


# Atacantes principales evaluados en los bloques de listo-para-atacar.
MAIN_ATTACKERS = (
    Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
    Tapu_Bulu, Fezandipiti_ex, Meganium, Pinsir,
)


# Ajuste terminal de PROMOCION (ver "SUPERVIVENCIA AL PROMOVER"). El condenado
# baja lo bastante como para ceder ante cualquier superviviente real (el caso
# medido: Ogerpon cargado 4557 -> -1443, por debajo del Hydrapple ex a 259).
PROMO_DOOMED_PENALTY = 6000


# Sin supervivientes, cada premio extra que regalamos cuesta esto.
PROMO_PRIZE_PENALTY = 1500


# El que NOQUEA al activo rival se promueve por encima de cualquiera que no lo
# haga, tanque incluido (user). Por encima del score maximo de las ramas de
# promocion (9500 = `_promote_setup_ko_attacker`) para que sea una GARANTIA y no
# dependa de que el noqueador saque mas base que el tanque: `_ko_prefer_basic_general`
# da 8500+ a un basico de 1 premio y el muro resistente 6100, asi que un
# noqueador a ~4500 podia perder. Entre varios noqueadores decide el score base.
PROMO_KO_BONUS = 20000


# MATCH POINT: al rival le basta con noquear este cuerpo para llevarse el ultimo
# premio. No es un mal intercambio, es perder la partida -> veto, no
# penalizacion. Va por DEBAJO de SCORE_NEVER (-10000) a proposito: otros vetos
# de promocion usan ese valor exacto (p.ej. "la linea Meganium no va al activo")
# y un empate a -10000 dejaria el desempate al azar del orden de opciones, justo
# entre el cuerpo que aguanta y el que nos hace perder.
PROMO_MATCH_POINT_VETO = -30000

__all__ = [
    'SCORE_LD_SUPP_COMPROMETIDO',
    '_SUPP_PLAY_IDS',
    'MAIN_ATTACKERS',
    'PROMO_DOOMED_PENALTY',
    'PROMO_KO_BONUS',
    'PROMO_MATCH_POINT_VETO',
    'PROMO_PRIZE_PENALTY',
]
