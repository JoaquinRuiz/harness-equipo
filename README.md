# harness-equipo

Marketplace de Claude Code con el plugin `equipo`: las reglas de la casa de TaskFlow
como una skill (`nuevo-endpoint`) y cuatro hooks que vigilan resultados, no herramientas.

```
/plugin marketplace add <ruta-o-repo-de-harness-equipo>
/plugin install equipo@harness-equipo
```

| Momento | Hook | Reglas | Qué hace |
|---|---|---|---|
| Entrada (PreToolUse `Read\|Edit\|Write\|Bash`) | `proteger_secretos.sh` | R5 | Bloquea lo que nombra el `.env` |
| Entrada (PreToolUse `Edit\|Write`) | `sin_dependencias_nuevas.sh` | R4 | Bloquea editar ficheros de dependencias |
| Durante (PostToolUse `Edit\|Write\|Bash`) | `comprobar_reglas.py` | R1, R4 | Revisa lo que git ve cambiado y avisa |
| Salida (Stop) | `puerta_de_salida.sh` | R6, R1, R4 | No deja terminar mientras algo falle |

R2 (tests de cada ruta) y R3 (formato de error) se quedan a propósito solo en el
`AGENTS.md` del proyecto y en la skill.

Las convenciones del equipo (capa de datos, ficheros de dependencias, `.env`) y las
comprobaciones viven en `plugins/equipo/scripts/reglas.py`: las usan los hooks y el
auditor del laboratorio.
