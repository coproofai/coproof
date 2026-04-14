# CoProof — Hoja de Ruta · Entrega Final

**Fecha límite:** 7 de Mayo de 2026  
**Equipo:** 3 integrantes  
**Proceso:** Zero-Known-Bugs antes de cada cierre de sprint

---

## Calendario de sprints

| Sprint | Fechas | Objetivo |
|---|---|---|
| **Sprint 1** | 14 — 20 Abr | Vistas faltantes + fixes de acceso y perfil |
| **Sprint 2** | 21 — 27 Abr | Lenguaje natural + traductor formal + LaTeX viewer |
| **Sprint 3** | 28 Abr — 30 Abr | IA de sugerencias + MPI/Slurm computation mode |
| **Freeze de features** | **30 Abr** | No se agrega funcionalidad nueva a partir de aquí |
| **Testing completo** | 30 Abr — 6 May | Tests de todas las features, zero bugs conocidos |
| **Entrega Final** | **7 Mayo** | Tag `v1.0.0`, PR a `main` aprobado, demo listo |

---

## Sprint 1 — Acceso, vistas y perfil (14–20 Abr)

### Features
- [ ] Corregir flujo de login / logout (token expirado, redirect correcto)
- [ ] Conectar vistas sin funcionalidad: configuración de cuenta, entorno, búsqueda de proyectos
- [ ] Implementar vista de perfil de usuario (datos desde GitHub OAuth)
- [ ] Mejorar visuals generales (consistencia de colores, tipografía, espaciado)

### Tests requeridos
- [ ] Test E2E de login → creación de proyecto → logout
- [ ] Tests unitarios para componentes de vistas conectadas

### Criterio de cierre
Milestone `Sprint 1` en GitHub en 0 issues abiertos con `priority:high`.

---

## Sprint 2 — Lenguaje natural y LaTeX (21–27 Abr)

### Features
- [ ] Visor de LaTeX inline en la interfaz (renderizado de fórmulas matemáticas)
- [ ] Input de lenguaje natural para descripción de nodos/teoremas
- [ ] Traductor lenguaje natural → Lean formal (integración con servicio de traducción)
- [ ] Vista de comparación: lenguaje natural ↔ código Lean generado

### Tests requeridos
- [ ] Tests de integración para el endpoint de traducción
- [ ] Tests del componente de LaTeX viewer (renderiza, no rompe en strings vacíos)

### Criterio de cierre
Milestone `Sprint 2` en GitHub en 0 issues abiertos con `priority:high`.

---

## Sprint 3 — IA y cómputo HPC (28–30 Abr)

### Features
- [ ] Integración de sugerencias de IA: dado un nodo, ofrecer hints de demostración
- [ ] Modo de ejecución MPI con OpenMPI en clúster HPC con Slurm (`computation_service` + nuevo `celery task`)
- [ ] UI para seleccionar modo de ejecución: local vs. clúster Slurm

### Tests requeridos
- [ ] Tests del servicio de sugerencias (mock de la respuesta del modelo)
- [ ] Tests del dispatcher de tareas de cómputo (local vs. Slurm)

### Criterio de cierre
Todos los Issues del Sprint 3 cerrados. Feature freeze activado.

---

## Semana de testing completo (30 Abr — 6 May)

- [ ] Tests escritos para **todas** las features del sistema (ver lista en issues con label `testing`)
- [ ] Sesión de usabilidad en pasillo con al menos 2 personas externas al equipo
- [ ] Bugs encontrados registrados como Issues y resueltos antes del 5 de Mayo
- [ ] Milestone `Zero Known Bugs` en 0 issues abiertos
- [ ] Actualizar `docs/spolsky-plan.md` con estado final de cada punto del Joel Test
- [ ] Crear tag `v1.0.0` desde `main`

---

## Regla de proceso (obligatoria en todos los sprints)

> Antes de iniciar cualquier historia de usuario nueva, el tablero de Issues no debe tener bugs etiquetados con `priority:high` en estado abierto. Si los hay, el miembro asignado los resuelve primero.

Ver detalles en [docs/spolsky-plan.md](docs/spolsky-plan.md).
