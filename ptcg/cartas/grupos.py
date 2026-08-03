"""Grupos de carta derivados: lineas evolutivas y conjuntos estrategicos.

Extraido VERBATIM de main.py por utils/extraer_puros.py
(docs/main-refactor-arquitectura.md). Aqui NO hay logica: solo constantes que
dependen unicamente de literales. Este modulo no puede importar estado ni tocar
el simulador -- lo vigila utils/lint_arquitectura.py (R2).

main.py lo reexporta con `import *`, asi que el `__all__` del final tiene que
listar TODOS los nombres, incluidos los que empiezan por `_` (que `import *`
omitiria si no).
"""

from ptcg.cartas.ids import Applin, Bayleef, Chikorita, Dipplin, Hydrapple_ex, Meganium, Teal_Mask_Ogerpon_ex




# Nuestras DOS lineas de evolucion, de basico a etapa 2.
EVO_LINES = (
    (Applin, Dipplin, Hydrapple_ex),
    (Chikorita, Bayleef, Meganium),
)



# =============================================================================
# GRAND TREE (id 1249): MOTOR DE EVOLUCION INSTANTANEA
# -----------------------------------------------------------------------------
# Con el estadio en mesa (lo haya bajado quien lo haya bajado) ganamos, UNA VEZ
# POR TURNO y GRATIS, una cadena entera Basico -> Fase 1 -> Fase 2 sacada del
# mazo. Es la jugada de desarrollo mas rentable del turno: no gasta la carta de
# la mano, no gasta el adjunte, no gasta el ataque y ademas ADELGAZA el mazo.
#
# QUE CUERPO CONSTRUIR (regla del user, generalizada a cualquier mazo):
#   * Si ya tenemos en juego una de nuestras Etapas 2 y NO la otra, se completa
#     LA QUE FALTA -> el bono `GT_VALOR_DIVERSIFICAR`. En este mazo eso es
#     exactamente "con Meganium en juego -> Hydrapple ex" y "con Hydrapple ex en
#     juego -> Meganium".
#   * Si YA tenemos las dos (o ninguna), decide el VALOR del cuerpo resultante
#     (`_gt_valor_cuerpo`: PV + bono por Habilidad) -> gana la copia del cuerpo
#     mas fuerte. En este mazo eso es "con ambos en juego -> un segundo
#     Hydrapple ex" (330 PV + Ripening Charge frente a 160 PV de Meganium).
#     `GT_VALOR_DIVERSIFICAR` (1200) es deliberadamente mayor que cualquier
#     diferencia de cuerpo razonable, para que la diversificacion mande cuando
#     aplica.
#   * A igualdad, se prefiere el Basico con MAS energia ya invertida (misma
#     convencion que la rama EVOLVE: `9000 + energia`).
#
# MATCHUPS: contra un rival que INMUNIZA a nuestros Pokemon ex (Crustle,
# Sylveon...), la Etapa 2 ex se descarta y la cadena se queda EXPRESAMENTE en
# Fase 1 (`stage2_id == 0`): el paso 2 de la carta es opcional ("puede"), y
# regalar un cuerpo de 2 premios que no puede danar al muro es peor que no
# evolucionar. Espeja el veto de la rama EVOLVE de Hydrapple ex vs Crustle.
# =============================================================================

# Bandas de score de la HABILIDAD del estadio (rama ABILITY). Van por encima de
# la evolucion desde la mano (Meganium 35000 / Hydrapple ex 33000) porque Grand
# Tree NO consume la carta de la mano: si ambas jugadas estan disponibles,
# primero la gratis.
GT_SCORE_CADENA_COMPLETA = 36000
GT_SCORE_SOLO_FASE1 = 34000
# Bono al FETCH (Ultra Ball / Bug Catching Set / Poke Pad / Night Stretcher) del
# Basico que habilita el estadio, y a bajarlo despues de la mano. Deliberadamente
# pequenos: son desempates, no deben pisar las prioridades ya existentes.
GT_FETCH_BONUS = 600
GT_PLAY_BASICO_BONUS = 500
# Componentes del valor de un plan (ver la cabecera del bloque).
GT_VALOR_ETAPA2 = 2000
GT_VALOR_DIVERSIFICAR = 1200
GT_PENAL_ACTIVO_CONDENADO = 1500



# Requisitos de energia EFECTIVA para atacar, por carta (fuente unica de verdad).
# len(energies) YA es energia efectiva (la observacion duplica la Planta por
# Wild Growth), asi que se compara directamente contra estos valores.
# Nighttime Mine (carta 1266): "los ataques de cada Pokemon Tera en juego (de
# LOS DOS jugadores) cuestan {C} mas". OJO con el numero: 1266 tambien es el id
# del ATAQUE Splashing_Dodge_Atk, pero son espacios de nombres distintos
# (card_table vs attack_table).
#
# Nos afecta de lleno: Teal Mask Ogerpon ex es nuestro UNICO Tera y llevamos 4.
# Con la mina en mesa su ataque pasa de 3 a 4 energias. Medido sobre el meta
# real (decks_competidores/, top-300): el 80% de las listas Alakazam la lleva a
# 2 copias, y Alakazam es el 19.7% del meta.
#
# Verificado contra el motor (30 partidas): con la mina en mesa y 3 energias el
# menu NO ofrece ATTACK (13 casos); con 4 si (22). Sin mina, 3 basta (56). El
# agente creia que Ogerpon estaba listo y no lo estaba.
Nighttime_Mine = 1266
# Nuestros Pokemon Tera, los unicos a los que la mina les sube el coste.
OUR_TERA_IDS = {Teal_Mask_Ogerpon_ex}


__all__ = [
    'EVO_LINES',
    'GT_SCORE_CADENA_COMPLETA',
    'GT_SCORE_SOLO_FASE1',
    'GT_FETCH_BONUS',
    'GT_PLAY_BASICO_BONUS',
    'GT_VALOR_ETAPA2',
    'GT_VALOR_DIVERSIFICAR',
    'GT_PENAL_ACTIVO_CONDENADO',
    'Nighttime_Mine',
    'OUR_TERA_IDS',
]
