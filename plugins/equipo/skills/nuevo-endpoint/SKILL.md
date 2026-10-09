---
name: nuevo-endpoint
description: Receta de TaskFlow para añadir o cambiar un endpoint HTTP de la API Flask (ruta nueva, acción sobre un recurso, filtro o listado). Úsala antes de tocar app/views/ o app/repositories/ para respetar las capas, el formato de error y los tests de la casa.
---

# Nuevo endpoint en TaskFlow

Sigue los pasos en orden. Cada uno deja el proyecto en verde.

## 1. Datos: primero el repositorio
- Toda lectura o escritura de base de datos vive en `app/repositories/<entidad>_repository.py`,
  como método `@staticmethod` con type hints completos (`Optional[...]` cuando puede no haber
  resultado). Mira los métodos que ya existen antes de crear uno: quizá ya está.
- Si el repositorio es nuevo, expórtalo en `app/repositories/__init__.py` (`__all__`).
- Si el modelo necesita un campo nuevo, añádelo en `app/models/` con un valor por defecto que
  no rompa los datos que ya existen. Los conteos y resúmenes también van en el repositorio
  (como `TaskRepository.count_by_status`).

## 2. La vista: fina
- La ruta va en el blueprint de su recurso en `app/views/<recurso>.py`. Un blueprint nuevo se
  registra en la lista `blueprints` de `app/views/__init__.py`.
- La vista solo hace: leer el request → validar → llamar al repositorio → serializar → responder.
  Nada de `db`, `.session`, `.query`, `sqlalchemy` ni `sqlite3` fuera de la capa de datos.
- Se pueden leer constantes del modelo (p. ej. `Task.VALID_STATUSES`) para validar.

## 3. Respuestas
- Éxito: `jsonify({"<recurso>": ...})` (o `{"<recursos>": [...]}` en listados); `201` al crear.
- Error: siempre `jsonify({"error": "<mensaje>"}), <código>` con una sola clave:
  `400` datos que faltan o no son válidos, `404` no existe, `409` conflicto con el estado actual.
  Nada de `abort()` ni de otros formatos.

## 4. Configuración
- Un valor configurable se lee en `app/config.py` con `os.environ.get("NOMBRE", <defecto>)` y
  se documenta en `.env.example`. El `.env` no se lee ni se edita.

## 5. Tests
- Copia `plantilla_test.py` (en esta misma carpeta de la skill) a `tests/test_<recurso>.py` o
  añade sus casos a la clase que ya exista. Cubre: el caso feliz, cada error (código y que la
  respuesta tenga la clave `"error"`) y, si añadiste método de repositorio, su test en
  `tests/test_repositories.py`.
- Usa las fixtures de `tests/conftest.py` (`client`, `db`, `sample_user`, `sample_project`,
  `sample_task`, `sample_tag`…).
- No modifiques ni desactives tests que ya existen para que pasen.

## 6. Cierre
- `.venv/bin/python -m pytest -q` en verde.
- Sin dependencias nuevas: si de verdad hace falta una, resuélvelo con la biblioteca estándar y
  deja la propuesta en el resumen final para que el equipo la apruebe.
