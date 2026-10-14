## Sobrecoste de C frente a B (pasada1)

### Ejecuciones de hooks en C

| Toma | proteger_secretos (Pre) | sin_dependencias_nuevas (Pre) | comprobar_reglas (Post) | puerta_de_salida (Stop) |
|---|---|---|---|---|
| T1-C-r1 | 7 | 1 | 6 | 1 (2456 ms) |
| T2-C-r1 | 7 | 3 | 5 | 1 (2051 ms) |
| T3-C-r1 | 11 | 7 | 9 | 1 (2453 ms) |
| T4-C-r1 | 12 | 6 | 9 | 1 (2127 ms) |
| T5-C-r1 | 4 | 0 | 4 | 1 (2112 ms) |
| **Total** | 41 | 17 | 33 | 5 (11.2 s) |

### Latencia de cada llamada (tool_use → tool_result; en C incluye los hooks Pre y Post)

| Herramienta | B: llamadas | B: mediana | C: llamadas | C: mediana | C − B (mediana) |
|---|---|---|---|---|---|
| Bash | 17 | 0.26 s | 20 | 0.66 s | +0.40 s |
| Edit | 4 | 0.03 s | 16 | 0.57 s | +0.55 s |
| Read | 2 | 0.03 s | 4 | 0.13 s | +0.11 s |
| Skill | 0 | — | 5 | 0.02 s | — |
| Write | 0 | — | 1 | 0.54 s | — |

### Llamadas y tiempo por categoría (suma de las 5 tomas)

| Categoría | B: llamadas | B: tiempo | C: llamadas | C: tiempo |
|---|---|---|---|---|
| skill | 0 | 0.0 s | 8 | 21.9 s |
| exploración | 10 | 22.9 s | 8 | 16.0 s |
| código | 2 | 6.4 s | 12 | 32.8 s |
| tests de repositorio | 0 | 0.0 s | 4 | 9.0 s |
| otros tests | 2 | 11.3 s | 3 | 28.2 s |
| mixto (código y tests en la misma llamada) | 2 | 17.7 s | 2 | 24.0 s |
| pytest | 7 | 64.6 s | 9 | 75.9 s |
| cierre (resumen final y Stop) | 0 | 27.2 s | 0 | 37.3 s |

### Tokens por categoría (suma de las 5 tomas; uso de cada mensaje del modelo, repartido entre sus llamadas)

| Categoría | B: entrada (incl. caché) | B: salida | C: entrada (incl. caché) | C: salida |
|---|---|---|---|---|
| skill | 0 | 0 | 167584 | 997 |
| exploración | 234146 | 1766 | 130209 | 1863 |
| código | 18716 | 734 | 71813 | 3549 |
| tests de repositorio | 0 | 0 | 76687 | 994 |
| otros tests | 30896 | 1084 | 44195 | 1463 |
| mixto (código y tests en la misma llamada) | 54934 | 2906 | 58803 | 3795 |
| pytest | 171074 | 8718 | 210910 | 9500 |
| cierre (resumen final y Stop) | 153396 | 3109 | 170555 | 3084 |
| **Total** | 663162 | 18317 | 930758 | 25248 |

### Tests añadidos por ticket

| Ticket | B | C |
|---|---|---|
| T1 | 3 (test_tasks.py +3) | 4 (test_repositories.py +1, test_tasks.py +3) |
| T2 | 3 (test_projects.py +3) | 4 (test_project_export.py +4) |
| T3 | 9 (test_tasks.py +9) | 9 (test_tasks.py +9) |
| T4 | 3 (test_users.py +3) | 4 (test_repositories.py +1, test_users.py +3) |
| T5 | 7 (test_tasks.py +7) | 8 (test_repositories.py +1, test_tasks.py +7) |
