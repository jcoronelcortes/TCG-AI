"""El centinela `_SALTAR` de la puntuacion, en su propio modulo.

Vive aparte del despachador y de las ramas POR UNA RAZON: lo devuelven las ramas
(`ptcg/turno/opciones/*.py`) y lo comprueba quien llama al despachador. Si viviera
en `puntuacion.py`, el despachador importaria las ramas y las ramas al
despachador -- import circular.

Significa "esta rama ya hizo `scores.append` por su cuenta"; es lo que en el
bucle original de `agent()` era un `continue`.
"""

_SALTAR = object()


__all__ = ['_SALTAR']
