# Módulo cg.sim

## Propósito

Gestiona la carga de la librería nativa del simulador y define las estructuras auxiliares para interactuar con ella desde Python.

## Contenido principal

- Resolución de la ruta de la librería según el sistema operativo.
- Carga dinámica con `ctypes`.
- Definición de `StartData` y `SerialData`.
- Clase `Battle`, usada como contenedor compartido del estado de la partida (`battle_ptr`, `obs`).

## Notas

Este módulo es un punto de integración con el runtime nativo y debe tratarse con cuidado cuando se cambian dependencias o plataformas.
