"""Probabilidad hipergeometrica del robo.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from math import comb as _comb


def _prob_al_menos(exitos, poblacion, robo, k):
    """Hipergeometrica: P(robar AL MENOS `k` copias) sacando `robo` cartas de
    un mazo de `poblacion` con `exitos` copias vivas.

    Es el UNICO sitio del fichero donde el agente razona con azar; el resto
    decide con el tablero visible. `exitos` sale de la creencia de mazo
    (`CARTAS_ACTIVAS_EN_MAZO`), que cuenta lo que NO se ha visto: mazo + premios
    boca abajo. Por eso el llamador mete tambien los premios en `poblacion` --
    son cartas indistinguibles del mazo desde nuestro lado--, lo que deja la
    estimacion LIGERAMENTE conservadora (en el registro_004: 11 Plantas no
    vistas en 48 -> 0.60, frente al 0.63 real de las 10 que quedaban en el mazo
    de 42). Conservador es lo que se quiere en un gate."""
    if k <= 0:
        return 1.0
    if exitos <= 0 or robo <= 0 or poblacion <= 0 or k > exitos:
        return 0.0
    robo = min(robo, poblacion)
    if k > robo:
        return 0.0
    fallos = poblacion - exitos
    total = _comb(poblacion, robo)
    if total <= 0:
        return 0.0
    menos_de_k = 0
    for i in range(0, k):
        if i > exitos or (robo - i) > fallos or (robo - i) < 0:
            continue
        menos_de_k += _comb(exitos, i) * _comb(fallos, robo - i)
    return max(0.0, min(1.0, 1.0 - menos_de_k / total))

__all__ = [
    '_prob_al_menos',
]
