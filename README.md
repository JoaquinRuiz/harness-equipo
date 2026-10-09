# harness-equipo

Marketplace de Claude Code con el plugin `equipo`: las reglas de la casa de TaskFlow
como una skill (`nuevo-endpoint`) y cuatro hooks (secretos, dependencias, capas y suite
en verde).

```
/plugin marketplace add <ruta-o-repo-de-harness-equipo>
/plugin install equipo@harness-equipo
```

Las reglas comprobables (R1, R3 y la lista de ficheros de dependencias) viven en
`plugins/equipo/scripts/reglas_taskflow.py`: las usan el hook `comprobar_capas.py` y
el auditor del laboratorio.
