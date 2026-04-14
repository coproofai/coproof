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

**Estado: ✅ Implementado**

El archivo `.github/workflows/ci.yml` está activo y se dispara en cada `push` a `main` o `develop` y en cada Pull Request. El pipeline se divide en dos jobs paralelos:

**Job `build` (backend):**
1. `actions/checkout` — clona el repositorio.
2. `docker compose build` — compila todas las imágenes del stack.
3. `docker compose run --rm web python -m pytest tests/ -v` — ejecuta los tests de integración del API Flask contra una base de datos PostgreSQL real (levantada automáticamente como dependencia del servicio `web`).
4. `docker compose down -v` — limpia los volúmenes después de los tests.

**Job `frontend` (Angular + Vitest):**
1. `actions/setup-node@v4` con Node 22 y caché de `npm`.
2. `npm ci` — instalación determinista de dependencias.
3. `npx ng test --configuration=ci` — ejecuta los tests unitarios con la configuración CI de Angular (Vitest, single-run, sin watch).
4. `npm run build -- --configuration=production` — verifica que el bundle de producción compila sin errores TypeScript.

Cualquier fallo en cualquier job bloquea el merge. Los errores se detectan en menos de 5 minutos desde el push.

---

### 4. ¿Tienes una base de datos de bugs?

**Estado: ⚙️ Parcialmente implementado — En progreso**

La plantilla de reporte de bug está creada en `.github/ISSUE_TEMPLATE/bug_report.md` y se activa automáticamente al abrir un nuevo Issue en GitHub. Falta completar la configuración de etiquetas y el Milestone de cero bugs activo.

**Lo que ya está hecho:**
- Plantilla de Issue con campos: pasos para reproducir, comportamiento esperado/observado, servicio afectado, estado de corrección.
- Etiquetas de servicio y prioridad creadas en GitHub Issues (`bug`, `backend`, `frontend`, `lean-worker`, `priority:high`, `priority:low`).

**Lo que falta:**
- Crear las etiquetas `regression`, `needs-repro`, `ux` (*Issues → Labels*).
- Crear el Milestone `Zero Known Bugs` (instrucciones abajo).
- Activar branch protection en `main` para exigir que el CI pase antes de cada merge.

**Instrucciones para el Milestone "Zero Known Bugs":**

1. Ir al repositorio en GitHub → *Issues → Milestones → New milestone*.
2. Nombre: `Zero Known Bugs`. Sin fecha de vencimiento.
3. Cada vez que se abra un Issue con label `bug`, asignarlo a este Milestone.
4. Antes de cada entrega, el Milestone debe mostrar 0 issues abiertos.

**Referencia de etiquetas completa:**

| Etiqueta | Color | Significado |
|---|---|---|
| `bug` | `#d73a4a` | Error confirmado en el sistema |
| `regression` | `#e4e669` | Funcionalidad que antes funcionaba |
| `lean-worker` | `#0075ca` | Bug en el servicio Lean |
| `backend` | `#5319e7` | Bug en Flask/API |
| `frontend` | `#f9d0c4` | Bug en Angular |
| `priority:high` | `#b60205` | Bloquea entrega o demo |
| `priority:low` | `#c2e0c6` | No urgente |
| `needs-repro` | `#e99695` | No se ha podido reproducir |
| `ux` | `#bfd4f2` | Problema de usabilidad detectado en sesión |

**Uso cotidiano:**
Cada vez que se encuentre un bug, abrir un Issue antes de tocar código. Asignarlo al Milestone `Zero Known Bugs` y a quien lo resolverá. Cerrar el Issue desde el commit con `Closes #N`.

---

### 5. ¿Corriges bugs antes de escribir código nuevo?

**Estado: ✅ Implementado**

La regla de prioridades está documentada en el `README.md` raíz del repositorio y es visible para todo el equipo en la página principal del repo en GitHub:

> **Regla de prioridades:** Antes de iniciar cualquier historia de usuario nueva, el tablero de Issues no debe tener bugs etiquetados con `priority:high` en estado abierto. Si los hay, el miembro asignado los resuelve primero.

El sistema de Issues con etiquetas de prioridad (creado en el punto 4) es la herramienta que hace esta regla operativa.

---

### 6. ¿Tienes un calendario actualizado?

**Estado: ✅ Implementado**

El archivo `ROADMAP.md` en la raíz del repositorio define el calendario completo hasta la entrega final del 7 de mayo de 2026:

- **Sprint 1** (14–20 Abr): vistas, acceso, perfil, visuals.
- **Sprint 2** (21–27 Abr): lenguaje natural, traductor formal, LaTeX viewer.
- **Sprint 3** (28–30 Abr): sugerencias IA, modo MPI/Slurm.
- **Feature freeze**: 30 de Abril.
- **Semana de testing**: 30 Abr — 6 May.
- **Entrega final**: 7 de Mayo, tag `v1.0.0`.

Cada sprint tiene un criterio de cierre medible: Milestone del sprint en 0 issues `priority:high` abiertos. El ROADMAP se actualiza al inicio de cada sprint si el scope cambia.

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

**Estado: ⚙️ Parcialmente implementado — En progreso**

Con solo 3 integrantes en el equipo, no es factible asignar un rol exclusivo de tester. Sin embargo, el proceso de revisión ya está parcialmente formalizado.

**Lo que ya está implementado:**
- La plantilla de PR en `.github/PR_TEMPLATE/pull_request_template.md` incluye una checklist obligatoria que el revisor debe completar antes de aprobar el merge:
  - Build no roto.
  - Flujo principal probado manualmente.
  - Sin secretos en el código.
  - Endpoints con validación de payload.
  - Issue referenciado con `Closes #N`.
- El CI bloquea automáticamente cualquier PR cuyos tests fallen, actuando como primera línea de testing automático.

**Lo que falta:**
- Crear las etiquetas faltantes: `regression`, `needs-repro`, `ux` (*Issues → Labels*, colores en la tabla de arriba).
- Crear el Milestone `Zero Known Bugs` (ver instrucciones abajo).
- Activar branch protection en `main` para exigir que el Milestone esté limpio antes de cada merge.

**Instrucciones para el Milestone "Zero Known Bugs":**

1. Ir al repositorio en GitHub → *Issues → Milestones → New milestone*.
2. Nombre: `Zero Known Bugs`. Sin fecha de vencimiento (es un estado permanente, no un sprint).
3. Cada vez que se abra un Issue con label `bug`, asignarlo a este Milestone.
4. Antes de cada entrega, el Milestone debe mostrar 0 issues abiertos.

**Instrucciones para branch protection:**

1. Ir al repositorio en GitHub → *Settings → Branches → Add branch ruleset*.
2. Target: `main`.
3. Activar:
   - **Require a pull request before merging** → *Required approvals: 1*.
   - **Require status checks to pass** → agregar los checks `build` y `frontend` (aparecen tras el primer CI exitoso).
   - **Do not allow bypassing the above settings** (aplicar también a admins).

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
| 3 | Builds diarios / CI | ✅ Implementado | `.github/workflows/ci.yml` activo: build Docker, tests backend (pytest + PostgreSQL real), tests frontend (Angular/Vitest CI config), build de producción. |
| 4 | Base de datos de bugs | ⚙️ En progreso | Plantilla + etiquetas de servicio creadas. Faltan: Milestone zero-bugs y branch protection. |
| 5 | Bugs antes de código nuevo | ✅ Implementado | Regla documentada en README.md raíz, visible en la página del repositorio. |
| 6 | Calendario actualizado | ✅ Implementado | ROADMAP.md con sprints, feature freeze (30 Abr) y entrega final (7 May). |
| 7 | Especificación / Spec | ✅ Cumplido | User stories, arquitectura, diseño de BD, wireframes y diagramas de clases documentados. |
| 8 | Condiciones tranquilas | 🚫 No aplica completamente | Proyecto escolar; condiciones individuales. Se puede adoptar el principio con bloques de trabajo acordados. |
| 9 | Mejores herramientas | ✅ Cumplido | Stack moderno: Lean 4, Angular, Flask, PostgreSQL, Redis, Docker, GitHub — todas gratuitas. |
| 10 | Testers | ⚙️ En progreso | PR template con checklist creado. CI bloquea merges con tests rotos. Falta: branch protection + rotación de rol tester. |
| 11 | Código en entrevistas | 🚫 No aplica | Equipo escolar fijo, sin proceso de contratación posible ni necesario. |
| 12 | Usabilidad en el pasillo | ⚠️ Por implementar | Sin sesiones con usuarios externos. Plan: sesiones informales con compañeros antes de cada entrega. |

**Puntos implementados o completamente activos: 8 / 12** (1, 2, 3, 5, 6, 7, 9, y parcialmente 10)  
**Puntos en progreso activo: 1 / 12** (4 — branch protection + Milestone pendientes)  
**Puntos con plan pendiente: 1 / 12** (12 — sesión de usabilidad agendada en semana de testing)  
**Puntos que no aplican por naturaleza del proyecto: 2 / 12** (8 y 11)  
**Total con cobertura real o planeada: 10 / 12**

---

## Priorización del plan

Para maximizar el impacto con el tiempo disponible de un equipo de 3 personas, se recomienda implementar en este orden:

1. ~~**CI (punto 3)**~~ ✅ Completado.
2. ~~**Bugs antes de código nuevo (punto 5)**~~ ✅ Completado — README actualizado.
3. ~~**Calendario (punto 6)**~~ ✅ Completado — ROADMAP.md creado.
4. **Bug database (punto 4)** — Pendiente: crear Milestone `Zero Known Bugs` y activar branch protection (instrucciones en la sección del punto 10). ~40 minutos en total.
5. **Revisión cruzada / testers (punto 10)** — Pendiente: activar branch protection con required reviews. Instrucciones en la sección del punto 10.
6. **Usabilidad en pasillo (punto 12)** — Agendar sesión con compañeros durante la semana de testing (30 Abr–6 May).
