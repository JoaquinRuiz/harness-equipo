# Distribución por proyecto (Fase 6)

Comprobado el 2026-10-14 con `lab/distribucion_proyecto.sh` (configuración vacía, TaskFlow y harness-equipo
desde GitHub, sin modelo): dentro del clon de TaskFlow,

```
claude plugin marketplace add JoaquinRuiz/harness-equipo --scope project
claude plugin install equipo@harness-equipo --scope project
```

escriben este `.claude/settings.json` en la raíz del proyecto:

```json
{
  "extraKnownMarketplaces": {
    "harness-equipo": {
      "source": {
        "source": "github",
        "repo": "JoaquinRuiz/harness-equipo"
      }
    }
  },
  "enabledPlugins": {
    "equipo@harness-equipo": true
  }
}
```

- `claude plugin list` dentro de TaskFlow: `equipo@harness-equipo` 0.3.1, alcance de proyecto, **activado**; en
  otro directorio: el mismo plugin, **desactivado**.
- `git status` lo muestra como `?? .claude/`: es el fichero que el equipo commitea para que cualquiera que abra
  el proyecto con Claude Code reciba el marketplace y el plugin. Junto con `.harness-equipo` (que activa los
  hooks), es todo lo que el repo necesita.
- Tiempo de `marketplace add` + `install` con alcance de proyecto en la prueba: 3,1 s (D14, alcance de usuario: 3,3 s).
