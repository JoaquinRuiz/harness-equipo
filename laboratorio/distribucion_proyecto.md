# Distribución por proyecto (Fase 6)

Para que cualquiera que abra TaskFlow con Claude Code reciba el harness, el repo lleva un
`.claude/settings.json` que declara el marketplace del equipo y activa el plugin:

```json
{
  "extraKnownMarketplaces": {
    "harness-equipo": {
      "source": { "source": "github", "repo": "<usuario>/harness-equipo" }
    }
  },
  "enabledPlugins": {
    "equipo@harness-equipo": true
  }
}
```

- Al abrir el proyecto y confiar en la carpeta, Claude Code ofrece instalar el marketplace y el plugin.
- `<usuario>/harness-equipo` queda pendiente de publicar el repo (no se publica nada con gh mientras esté la
  cuenta de trabajo). Para probarlo en local, la fuente puede ser `{ "source": "directory", "path": "<ruta>" }`.
- No se añade a la rama `main` de TaskFlow: `main` es la base de las tomas de la matriz.
- Alternativa por línea de comandos, ya dentro del proyecto:
  `claude plugin install equipo@harness-equipo --scope project`.
