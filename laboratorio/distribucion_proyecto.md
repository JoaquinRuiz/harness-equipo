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

## Primera apertura (`lab/primera_apertura.sh`, 2026-10-14)

Clon de TaskFlow con `.claude/settings.json` y `.harness-equipo`, configuración vacía, Claude Code 2.1.294 en
interactivo sin mandar ningún mensaje:

1. Pide confiar en la carpeta. Al aceptarlo, **sin otra pregunta**, añade el marketplace `harness-equipo` (lo
   clona de GitHub), descarga `equipo` 0.3.1 y lo muestra en `/plugin` como «Enabled».
2. **Pero no lo instala:** `claude plugin list` dice «No plugins installed», `/plugin` muestra el error «Plugin
   "equipo" not cached at …/marketplaces/harness-equipo» y **ningún hook se ejecuta**, ni en esa sesión ni al
   volver a abrir (el hook de inicio no apuntó nada en `.git/harness-equipo/`).
3. Con `claude plugin install equipo@harness-equipo --scope project` (una vez, dentro del repo), el error
   desaparece, `git status` sigue limpio y, en la siguiente apertura, el hook de inicio apunta el commit
   (`e824efa`): los hooks actúan.

Conclusión para el vídeo: el `.claude/settings.json` declara el plugin, pero cada persona tiene que instalarlo
una vez. Así lo dicen ahora los README de TaskFlow y de harness-equipo.
