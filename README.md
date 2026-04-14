# CoProof

Plataforma colaborativa para demostración formal de teoremas, construida sobre Lean 4, Flask, Angular y GitHub como fuente de verdad.

---

## Stack

| Capa | Tecnología |
|---|---|
| Verificación formal | Lean 4 + Celery worker |
| Backend API | Flask · PostgreSQL · Alembic · Redis |
| Frontend | Angular 21 standalone components |
| Orquestación | Docker Compose |
| CI | GitHub Actions |

---

## Levantamiento en un paso

```bash
docker compose up --build
```

Esto compila todas las imágenes, aplica migraciones y levanta los servicios en:

| Servicio | URL |
|---|---|
| API Flask | http://localhost:5001 |
| Frontend Angular | http://localhost:4200 |

Requiere un archivo `server/.env` con las variables de entorno. Ver `server/README.md` para la configuración completa.

---

## Estructura del repositorio

```
server/        # API Flask + servicios de negocio
lean/          # Worker Celery para verificación Lean
computation/   # Worker Celery para cómputo distribuido
frontend/      # Aplicación Angular
docs/          # Especificación, arquitectura, historias de usuario
wireframes/    # Prototipos HTML de las vistas
diagrams/      # Diagramas LaTeX (clases, calles UML)
.github/       # Workflows de CI y plantillas de Issues / PRs
```

---

## Proceso de desarrollo

### Regla de prioridades (Zero Defects)

> Antes de iniciar cualquier historia de usuario nueva, el tablero de Issues no debe tener bugs etiquetados con `priority:high` en estado abierto. Si los hay, el miembro asignado los resuelve primero.

### Flujo de trabajo

1. Crear un Issue para cada bug o feature antes de tocar código.
2. Asignar el Issue al Milestone del sprint correspondiente.
3. Trabajar en una rama con nombre `feature/<descripcion>` o `fix/<descripcion>`.
4. Abrir un Pull Request hacia `main` completando la checklist del template.
5. El PR requiere al menos una review aprobada y que el CI pase (build + tests).
6. Cerrar el Issue desde el commit del merge con `Closes #N`.

### Labels de bugs

| Label | Significado |
|---|---|
| `bug` | Error confirmado |
| `regression` | Funcionaba antes |
| `priority:high` | Bloquea entrega o demo |
| `priority:low` | No urgente |
| `needs-repro` | No reproducido aún |
| `lean-worker` / `backend` / `frontend` | Servicio afectado |

---

## Tests

```bash
# Backend
docker compose run --rm web python -m pytest tests/ -v

# Frontend
cd frontend && npx ng test --configuration=ci
```

---

## Hoja de ruta

Ver [ROADMAP.md](ROADMAP.md) para el calendario de sprints y la fecha de entrega final.

## Evaluación de calidad

Ver [docs/spolsky-plan.md](docs/spolsky-plan.md) para la evaluación completa del Joel Test.
