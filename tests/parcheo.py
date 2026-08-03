"""Parcheo de nombres del agente que viven repartidos entre `main` y `ptcg/`.

EL PROBLEMA
  `from ptcg.cartas.tablas import card_table` LIGA EL NOMBRE EN EL MODULO QUE
  IMPORTA. No es una vista de la variable original: es otra referencia. Cuando
  main.py hace `import *`, se lleva su propia copia; y trece modulos de `ptcg/`
  tienen la suya. Por eso `monkeypatch.setattr(m, "card_table", ...)` deja de
  llegar a `_our_effective_damage` en cuanto esa funcion se muda a
  `ptcg/calculo/dano.py`: la funcion lee el binding de SU modulo.

  No es un problema de produccion -- ahi nadie reasigna estos nombres -- sino de
  los tests, que inyectan dobles para aislar un caso.

LA SOLUCION
  `parchear()` fija el nombre en TODOS los modulos cargados que lo tengan, asi
  que el test no necesita saber donde vive la funcion que lo consume. Eso lo
  hace inmune a las olas del refactor que aun quedan: mover una funcion de
  modulo ya no rompe el test que la aislaba.

  Para el estado mutable NO hace falta: vive en `ESTADO`, que es un objeto y no
  se reasigna nunca (ver ptcg/estado/agente.py).
"""

import sys
from contextlib import contextmanager


def _modulos_del_agente():
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        nombre = getattr(mod, "__name__", "")
        if nombre == "main" or nombre == "ptcg" or nombre.startswith("ptcg."):
            yield mod


def parchear(monkeypatch, nombre, valor):
    """Fija `nombre = valor` en todos los modulos del agente que lo tengan.

    Devuelve cuantos modulos se tocaron; 0 significa que el nombre no existe en
    ninguno, casi siempre una errata en el test.
    """
    tocados = 0
    for mod in _modulos_del_agente():
        if hasattr(mod, nombre):
            monkeypatch.setattr(mod, nombre, valor, raising=False)
            tocados += 1
    return tocados


@contextmanager
def parcheado(nombre, valor):
    """Igual que `parchear`, pero sin `monkeypatch` y como gestor de contexto.

    Para los tests que instalan un espia a mano con try/finally:

        with parcheado("_debug_log_decision", espia):
            m.agent(obs)
    """
    previos = [(mod, getattr(mod, nombre))
               for mod in _modulos_del_agente() if hasattr(mod, nombre)]
    for mod, _ in previos:
        setattr(mod, nombre, valor)
    try:
        yield len(previos)
    finally:
        for mod, viejo in previos:
            setattr(mod, nombre, viejo)


def instalar(nombre, valor):
    """Fija `nombre = valor` en todos los modulos y devuelve el restaurador.

    Variante para los tests que ya tienen su try/finally montado: sustituye la
    asignacion y la restauracion linea por linea, sin reestructurar el test.

        _restaurar = instalar("_debug_log_decision", espia)
        try:
            m.agent(obs)
        finally:
            _restaurar()
    """
    previos = [(mod, getattr(mod, nombre))
               for mod in _modulos_del_agente() if hasattr(mod, nombre)]
    for mod, _ in previos:
        setattr(mod, nombre, valor)

    def restaurar():
        for mod, viejo in previos:
            setattr(mod, nombre, viejo)
    return restaurar
