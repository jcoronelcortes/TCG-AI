# Matriz de matchups — agosto 2026

Medición contra los **89 mazos reales del leaderboard** (`deck/rivales_reales/`),
400 partidas por matchup (35 600 en total), ponderada por frecuencia de meta.

```bash
python utils/matriz_matchups.py --partidas 400 --pesos
```

```text
WINRATE ESPERADO EN LADDER (ponderado por meta)
  ponderado :  93.1%   sobre el 98.8% del meta cubierto
  sin pesar :  92.0%
  DIFERENCIAL DE PREMIOS ponderado: +3.905 por partida
  forfeits nuestros: 0 en los 89 matchups
```

## Por arquetipo — donde se pierde de verdad

La tabla por mazo del script ordena por winrate y señala `marnie_grimmsnarl_1`
como mayor pérdida. **Agregando por arquetipo la conclusión cambia:**

| Arquetipo | Meta | Winrate | Premios | Ptos ladder perdidos | Mazos |
|---|---:|---:|---:|---:|---:|
| **crustle_wall** | 8,7 % | **75,3 %** | **+1,94** | **2,15** | 11 |
| marnie_grimmsnarl | 43,4 % | 95,4 % | +4,56 | 2,01 | 12 |
| alakazam | 19,1 % | 95,4 % | +3,40 | 0,88 | 17 |
| ogerpon_verde | 4,2 % | **85,8 %** | **+1,99** | 0,60 | 4 |
| mega_lucario | 1,8 % | 86,5 % | +2,85 | 0,24 | 6 |
| mega_starmie | 1,2 % | 88,2 % | +2,96 | 0,14 | 4 |
| cynthia_garchomp | 5,2 % | 97,6 % | +4,61 | 0,13 | 4 |
| *(resto: 11 arquetipos)* | 12,6 % | 94–99 % | +4 a +5 | 0,40 | 29 |

## Lectura

**Crustle wall es la debilidad real, no Marnie.** Marnie pierde 2,01 puntos de
ladder por PURO VOLUMEN (43 % del meta a un 95,4 % de winrate); Crustle pierde
2,15 con solo el 8,7 %, porque ahí el agente gana el 75 %. Tres señales
independientes coinciden en señalarlo:

1. es el peor winrate del meta (67–88 % según la lista);
2. es el **peor diferencial de premios** (+1,94, frente a +4,56 de Marnie): las
   partidas se deciden por poco, que es donde una regla puede mover la aguja;
3. concentra 11 listas distintas, así que no es una lista rara sino el arquetipo.

**`ogerpon_verde` es el segundo agujero real** (85,8 %, premios +1,99) y no
aparece en el top-3 del script porque pesa poco (4,2 %).

**El winrate solo no arbitra.** Contra Marnie, Alakazam y los diez arquetipos de
cola el agente está por encima del 94 % y el diferencial de premios por encima de
+3,4: ahí queda poco margen, y el bot genérico está saturado.

## Consecuencias para el backlog

- **Invertir en Crustle wall**, no en repartir esfuerzo por el meta. El proyecto
  ya tiene mucho trabajo hecho contra el muro inmune (relevo letal, gusteo tras
  el muro, topes de energía vs Crustle) y aun así es el matchup más débil.
- **Confirma la decisión de NO implementar Cynthia's Roserade**
  ([auditoría](auditoria-cartas-meta-ago2026.md)): el arquetipo es el 5,2 % del
  meta y el agente ya gana el 97,6 % con +4,61 de premios. No hay nada que
  recuperar ahí.

## Nota de método

El diferencial de premios es la métrica con resolución cuando el winrate satura:
una partida se puede ganar sin cobrar los 6 (bench-out, deckout), así que **no es
un winrate disfrazado** — mide otra cosa. Los 0 forfeits en 35 600 partidas dicen
además que el agente no lanza excepciones ni elige opciones inválidas contra
ninguna lista real.
