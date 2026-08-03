"""Tablas de carta derivadas del simulador: `card_table` y `attack_table`.

Extraido VERBATIM de main.py en la Ola 2 del refactor
(docs/main-refactor-arquitectura.md).

No son constantes literales (salen de `cg.api`), pero SI son deterministas y de
solo lectura: se construyen una vez al importar y nadie las muta -- comprobado
con `utils/pureza.py`. Esa es justo la diferencia con `ATTACK_ENERGY_REQ`, que
parece una tabla fija y en realidad es estado de TURNO (el impuesto de Nighttime
Mine la reescribe en cada `agent()`), y por eso aquella se queda en main.py
hasta la Ola 3.

OJO al moverlas de sitio: los modulos que hacen `from ptcg.cartas.tablas import
card_table` CONGELAN el binding al importar. En produccion da igual (nadie las
reasigna), pero un test que parchee `main.card_table` ya no les llega. Por eso
sus CONSUMIDORES siguen en main.py hasta la Ola 3, donde se decide quien posee
el estado de modulo.
"""

from cg.api import all_card_data, all_attack

all_card = all_card_data()
card_table = {c.cardId: c for c in all_card}
# Tabla ataque-id -> objeto Attack (name/damage/energies). Los `card.attacks`
# son IDs (ints), no objetos, por lo que _op_best_damage_vs (que hace
# getattr(id, 'damage')) siempre da 0. Esta tabla permite RESOLVER el dano real
# del ataque del activo rival cuando se necesita (ver _op_active_attack_damage_to).
attack_table = {a.attackId: a for a in all_attack()}


# Indice NOMBRE -> dato de carta: `evolvesFrom` guarda el NOMBRE de la
# pre-evolucion, asi que subir una cadena exige resolver nombres. Cubre TODAS
# las cartas del entorno (no solo las de nuestro mazo): las lineas que hay que
# leer aqui son las RIVALES.
_CARD_BY_NAME = {}

# Indice inverso NOMBRE -> cartas que evolucionan DE ese nombre. Complementa a
# `_CARD_BY_NAME` (que sube por la cadena) para poder BAJAR por ella y saber en
# que termina una linea rival. Cubre TODAS las cartas del entorno.
_EVOLUCIONES_POR_NOMBRE = {}


__all__ = [
    'all_card',
    'card_table',
    'attack_table',
    '_CARD_BY_NAME',
    '_EVOLUCIONES_POR_NOMBRE',
]
