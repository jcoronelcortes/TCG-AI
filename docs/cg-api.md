# Módulo cg.api

## Propósito

Define los tipos de datos, enumeraciones y funciones de alto nivel para interactuar con la API del simulador.

## Contenido principal

- Enumeraciones como `AreaType`, `OptionType`, `SelectContext`, `LogType` y `EnergyType`.
- Dataclasses para estados de partida, cartas, Pokémon, selecciones y observaciones.
- Funciones para convertir diccionarios en dataclasses y viceversa.
- Integración con la búsqueda de estados mediante `search_begin`, `search_step`, `search_end` y `search_release`.

## Uso típico

Se utiliza para transformar la observación cruda del motor de batalla en objetos estructurados que puedan ser consumidos por el agente.
