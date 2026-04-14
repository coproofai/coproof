# CoProof — Plan de Calidad basado en el Joel Test

**Equipo:** 3 integrantes · Proyecto escolar  
**Fecha de evaluación:** Abril 2026

---

## Resumen ejecutivo

El Joel Test define 12 prácticas cuya presencia o ausencia es un indicador directo de la madurez del proceso de desarrollo. Este documento evalúa el estado actual del proyecto CoProof frente a cada punto, justifica cada veredicto con evidencia del repositorio, y propone un plan de acción para los puntos no cubiertos. Se concluye con una tabla resumen.

---

## Evaluación detallada

---

### 1. ¿Usas control de versiones?

**Estado: ✅ Cumplido**

El proyecto no solo usa Git como sistema de control de versiones local, sino que GitHub es un componente de arquitectura de primer nivel. El servidor backend implementa autenticación OAuth contra GitHub, crea repositorios por proyecto, administra ramas y pull requests mediante la API REST de GitHub, y procesa webhooks `push` para reindexar el contenido Lean. Esto queda evidenciado en `server/app/api/`, los servicios `git_service` y `validation_service`, y la integración descrita en `docs/arquitectura_proyecto.md`. La pérdida total de código es prácticamente imposible en este contexto.

---

### 2. ¿Puedes hacer un build en un solo paso?

**Estado: ✅ Cumplido**

El archivo `docker-compose.yml` en la raíz del repositorio orquesta todos los servicios del sistema: `web` (Flask), `celery_worker`, `lean-worker`, `computation-worker`, `frontend` (Angular + Nginx), `db` (PostgreSQL) y `redis`. Un único comando:

```bash
docker compose up --build
```

compila todas las imágenes, aplica migraciones y levanta el stack completo listo para uso. No requiere pasos manuales adicionales. Cumple el criterio de build reproducible en un paso incluso en una máquina limpia.

---

### 3. ¿Haces builds diarios?

**Estado: ⚠️ No implementado — Plan disponible**

Actualmente no existe ningún archivo en `.github/workflows/` ni equivalente. Si un miembro rompe una parte del sistema (por ejemplo, una regresión en el parser de errores de Lean), el equipo puede tardar en darse cuenta porque no hay ningún proceso automatizado que valide el estado del repositorio tras cada `push`.

**Plan de implementación:**

Crear un workflow de GitHub Actions en `.github/workflows/ci.yml` que se dispare en cada `push` a `main` o `develop`:

```yaml
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker images
        run: docker compose build
      - name: Run backend tests
        run: docker compose run --rm web python -m pytest
      - name: Run frontend lint
        run: docker compose run --rm frontend npm run lint
```

Para un equipo de 3 personas, esto garantiza que el `main` siempre compile y que los errores se detecten en minutos en lugar de días.

---

### 4. ¿Tienes una base de datos de bugs?

**Estado: ❌ No implementado — Requerido · Plan detallado**

No existe ningún sistema formal de seguimiento de errores. Bugs conocidos se gestionan de forma verbal o en notas dispersas, lo cual es incompatible con un proceso de calidad mínimo.

**Plan de implementación con GitHub Issues:**

GitHub Issues es la herramienta más adecuada para este proyecto dado que el código ya vive en GitHub. Los pasos concretos son:

**Paso 1 — Habilitar Issues en el repositorio**
En la configuración del repositorio en GitHub: *Settings → General → Features → Issues* (activar si no está activo).

**Paso 2 — Crear un sistema de etiquetas**
Ir a *Issues → Labels* y crear las siguientes etiquetas:

| Etiqueta | Color | Significado |
|---|---|---|
| `bug` | `#d73a4a` (rojo) | Error confirmado en el sistema |
| `regression` | `#e4e669` | Funcionalidad que antes funcionaba |
| `lean-worker` | `#0075ca` | Bug en el servicio Lean |
| `backend` | `#5319e7` | Bug en Flask/API |
| `frontend` | `#f9d0c4` | Bug en Angular |
| `priority:high` | `#b60205` | Bloquea entrega o demo |
| `priority:low` | `#c2e0c6` | No urgente |
| `needs-repro` | `#e99695` | No se ha podido reproducir |

**Paso 3 — Plantilla de reporte de bug**
Crear el archivo `.github/ISSUE_TEMPLATE/bug_report.md`:

```markdown
---
name: Bug report
about: Reportar un error en CoProof
labels: bug, needs-repro
---

**Pasos para reproducir**
1. ...
2. ...

**Comportamiento esperado**
<!--Qué debería ocurrir-->

**Comportamiento observado**
<!--Qué ocurre en realidad-->

**Entorno**
- Servicio afectado: [ ] backend [ ] lean-worker [ ] frontend
- Rama / commit: 
- Docker compose version:

**¿Está corregido?**
- [ ] Sí — PR #
- [ ] No
```

**Paso 4 — Uso cotidiano**
Cada vez que se encuentre un bug (propio o de otro miembro), abrir un Issue antes de tocar código. Asignarlo a quien lo resolverá. Cuando se cierre el PR asociado, cerrar el Issue desde el mensaje del commit usando `Closes #N`.

**Paso 5 — Milestone de "zero bugs known"**
Crear un Milestone llamado `Zero Known Bugs` para agrupar todos los bugs abiertos. Antes de cada entrega, el milestone debe estar en 0 issues abiertos.

---

### 5. ¿Corriges bugs antes de escribir código nuevo?

**Estado: ⚠️ No formalizado — Plan disponible**

No existe una política explícita en el repositorio. Sin embargo, la existencia de notas en `memory/repo/project_ii_notes.md` demuestra que el equipo ha identificado bugs recurrentes (por ejemplo, la condición de race condition en el merge de PRs o el manejo incorrecto de HTTP 422 en el frontend). Lo problemático es que no hay un proceso que garantice que un bug conocido se resuelva antes de avanzar.

**Plan de implementación:**

Adoptar la siguiente regla de equipo, documentada en el README del repositorio:

> **Regla de prioridades:** Antes de iniciar cualquier historia de usuario nueva, el tablero de Issues no debe tener bugs etiquetados con `priority:high` en estado abierto. Si los hay, el miembro asignado los resuelve primero.

Esta regla es suficiente para un equipo de 3 personas y no requiere herramientas adicionales más allá del sistema de Issues descrito en el punto 4.

---

### 6. ¿Tienes un calendario actualizado?

**Estado: ⚠️ No implementado — Plan disponible**

No hay ningún archivo de planificación, Gantt, ni hoja de ruta formal en el repositorio. En un proyecto escolar esto es especialmente crítico porque las entregas tienen fechas fijas que no se pueden negociar.

**Plan de implementación:**

Usar **GitHub Milestones** como calendario ligero:

1. Crear un Milestone por cada entrega del semestre (por ejemplo: *Avance 3*, *Demo Final*, *Entrega Final*) con su fecha límite real.
2. Asignar cada Issue y PR al Milestone correspondiente.
3. La barra de progreso del Milestone muestra automáticamente el porcentaje completado.
4. Revisar el estado del Milestone activo en cada reunión de equipo (mínimo semanal).

Complementariamente, mantener un archivo `ROADMAP.md` en la raíz con las features comprometidas por entrega. Este archivo se actualiza cuando el scope cambia, dejando evidencia del cambio.

---

### 7. ¿Tienes una especificación?

**Estado: ✅ Cumplido**

El proyecto cuenta con documentación de especificación en múltiples niveles:

- **Historias de usuario:** `docs/historias-usuario.tex` cubre flujos completos con criterios de aceptación medibles por cada historia.
- **Arquitectura:** `docs/arquitectura_proyecto.md` define componentes, responsabilidades, patrones de diseño y contratos de capa.
- **Diseño de backend:** `docs/diseño_backend_avance_2.md` especifica el esquema de base de datos, los triggers, las entidades y las decisiones técnicas con justificación.
- **Wireframes:** El directorio `wireframes/` contiene prototipos HTML de todas las vistas principales del sistema.
- **Diagramas:** `docs/diagrama_clases_server.tex`, `diagrama_clases_frontend.tex`, `diagrama_clases_lean.tex` describen la estructura orientada a objetos de cada servicio.

La existencia de esta documentación previa al código evita los problemas de diseño tardío que Spolsky señala en este punto. El riesgo es que la documentación quede desactualizada; se recomienda actualizar el documento de arquitectura cada vez que se modifique un contrato de servicio.

---

### 8. ¿Los programadores tienen condiciones de trabajo tranquilas?

**Estado: 🚫 No aplica en su totalidad — Explicación**

Este punto asume un entorno laboral donde la gerencia puede decidir sobre oficinas, cubículos o espacios abiertos. En un proyecto escolar, las condiciones de trabajo son responsabilidad individual de cada integrante del equipo y no pueden ser controladas a nivel de proyecto.

Sin embargo, el principio subyacente —proteger el estado de *flow* de los programadores— sí puede aplicarse de forma adaptada:

- **Acordar bloques de trabajo sin interrupciones:** Definir ventanas de trabajo concentrado (por ejemplo, sábados de 10:00 a 13:00) en las que el equipo no se interrumpe entre sí por mensajes de texto.
- **Comunicación asíncrona por defecto:** Preferir Issues y comentarios en PRs sobre llamadas de voz no agendadas para preguntas que no son urgentes.

Este punto no puede implementarse completamente por la naturaleza del proyecto, pero el principio puede adoptarse parcialmente.

---

### 9. ¿Usas las mejores herramientas que el dinero puede comprar?

**Estado: ✅ Cumplido**

El stack tecnológico es moderno, bien soportado y adecuado para el problema:

- **Lean 4** para verificación formal: es el estado del arte en asistentes de prueba interactivos.
- **Flask + SQLAlchemy + Alembic** para el backend: maduros, con ecosistema amplio y migraciones versionadas.
- **Angular 19** con standalone components para el frontend: framework empresarial con tipado fuerte.
- **PostgreSQL** como base de datos relacional con soporte JSONB y triggers nativos.
- **Redis + Celery** para colas de tareas asíncronas: solución probada a escala.
- **Docker + Docker Compose** para desarrollo reproducible y despliegue.
- **GitHub** como repositorio remoto y plataforma de colaboración.

Todas estas herramientas son de acceso libre o gratuito para equipos pequeños y de código abierto, eliminando la barrera económica. El equipo no usa herramientas desactualizadas ni workarounds por falta de acceso a mejores alternativas.

---

### 10. ¿Tienes testers?

**Estado: ⚠️ No hay testers dedicados — Plan disponible**

Con solo 3 integrantes en el equipo, no es factible asignar un rol exclusivo de tester. Tampoco es realista contratar o incorporar a alguien externo en un contexto escolar.

**Plan de implementación:**

Adoptar un esquema de **revisión cruzada obligatoria**:

1. **Ningún PR se fusiona sin revisión de al menos un compañero distinto al autor.** El revisor no solo lee el código: ejecuta `docker compose up --build` y prueba manualmente el flujo afectado.
2. **Lista de verificación de PR:** Crear `.github/pull_request_template.md` con una checklist mínima:

```markdown
## Checklist del revisor
- [ ] El build no está roto (`docker compose up --build` exitoso)
- [ ] El flujo principal del cambio funciona manualmente
- [ ] No se introdujeron variables de entorno secretas en el código
- [ ] Los endpoints nuevos tienen validación de payload
- [ ] El Issue correspondiente está referenciado (`Closes #N`)
```

3. **Rotación de roles:** En cada sprint, uno de los miembros actúa como "tester de entrega": dedica la última sesión antes de la entrega exclusivamente a ejecutar los flujos de usuario completos desde el frontend, registrando cualquier defecto como Issue.

---

### 11. ¿Los candidatos escriben código durante la entrevista?

**Estado: 🚫 No aplica — Explicación**

Este punto es irrelevante por la naturaleza del proyecto. El equipo no tiene un proceso de contratación porque fue asignado o formado al inicio del semestre. No existe un proceso de selección de candidatos que diseñar ni implementar. Ninguna adaptación de este punto tiene sentido en el contexto de un proyecto escolar con equipo fijo.

---

### 12. ¿Haces pruebas de usabilidad en el pasillo?

**Estado: ⚠️ No implementado — Plan disponible**

No hay evidencia de sesiones de prueba con usuarios externos al equipo de desarrollo. Dado que el sistema tiene una interfaz de usuario orientada a matemáticos y estudiantes de lógica formal, la usabilidad es un vector de riesgo real: lo que parece obvio para quien programó la interfaz puede ser completamente opaco para un usuario nuevo.

**Plan de implementación:**

En proyectos escolares, el "pasillo" son los compañeros de clase, el profesor, o incluso familiares técnicos.

1. **Antes de cada entrega, realizar al menos una sesión informal con una persona externa al equipo.** El observador le pide al participante que realice una tarea específica (por ejemplo: "crea un proyecto, agrega un nodo hoja y valida la prueba") sin dar instrucciones adicionales.
2. **Registrar los puntos de fricción** como Issues con la etiqueta `ux` en el sistema de bug tracking.
3. **No intervenir durante la sesión.** Solo observar dónde el usuario se detiene, duda o comete errores.

Con cinco participantes (Jakob Nielsen demostró que cinco usuarios revelan el 85% de los problemas de usabilidad) el equipo puede obtener retroalimentación accionable antes de cada demo.

---

## Tabla resumen

| # | Punto | Estado | Justificación |
|---|---|---|---|
| 1 | Control de versiones | ✅ Cumplido | Git + GitHub como componente de arquitectura central; integración OAuth, PRs y webhooks. |
| 2 | Build en un paso | ✅ Cumplido | `docker compose up --build` construye y levanta todo el stack desde cero. |
| 3 | Builds diarios / CI | ⚠️ Por implementar | No existe `.github/workflows/`. Plan: GitHub Actions con build + tests en cada push. |
| 4 | Base de datos de bugs | ❌ Por implementar | No hay sistema de tracking. Plan: GitHub Issues con plantillas, etiquetas y Milestones. |
| 5 | Bugs antes de código nuevo | ⚠️ Por implementar | Sin política formal. Plan: regla de equipo documentada en README + uso del tablero de Issues. |
| 6 | Calendario actualizado | ⚠️ Por implementar | Sin planificación formal. Plan: GitHub Milestones por entrega + archivo `ROADMAP.md`. |
| 7 | Especificación / Spec | ✅ Cumplido | User stories, arquitectura, diseño de BD, wireframes y diagramas de clases documentados. |
| 8 | Condiciones tranquilas | 🚫 No aplica completamente | Proyecto escolar; condiciones individuales. Se puede adoptar el principio con bloques de trabajo acordados. |
| 9 | Mejores herramientas | ✅ Cumplido | Stack moderno: Lean 4, Angular, Flask, PostgreSQL, Redis, Docker, GitHub — todas gratuitas. |
| 10 | Testers | ⚠️ Por implementar | Equipo de 3, sin dedicated testers. Plan: revisión cruzada obligatoria + rotación de rol tester en cada entrega. |
| 11 | Código en entrevistas | 🚫 No aplica | Equipo escolar fijo, sin proceso de contratación posible ni necesario. |
| 12 | Usabilidad en el pasillo | ⚠️ Por implementar | Sin sesiones con usuarios externos. Plan: sesiones informales con compañeros antes de cada entrega. |

**Puntos implementados o con plan activo: 10 / 12**  
**Puntos que no aplican por naturaleza del proyecto: 2 / 12** (puntos 8 y 11)

---

## Priorización del plan

Para maximizar el impacto con el tiempo disponible de un equipo de 3 personas, se recomienda implementar en este orden:

1. **Bug database (punto 4)** — Acción inmediata. Requiere 30 minutos de configuración en GitHub Issues. Prioridad máxima por requerimiento explícito del proyecto.
2. **CI básico (punto 3)** — Una tarde de trabajo. Previene regresiones silenciosas en los módulos más críticos (lean-worker, API de merge).
3. **Revisión cruzada de PRs (punto 10)** — Cambio de proceso, sin costo técnico. Solo requiere acuerdo del equipo y agregar el template de PR al repositorio.
4. **Regla de bugs primero (punto 5)** — Una línea en el README y visibilidad del tablero de Issues es suficiente.
5. **Milestones de entrega (punto 6)** — 20 minutos en GitHub. Proporciona visibilidad inmediata del estado del sprint.
6. **Usabilidad en pasillo (punto 12)** — Agendar una sesión de 30 minutos con compañeros la semana previa a cada demo.
