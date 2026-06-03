# Resumen Técnico — CoProof (Capítulo III)

> Documento de apoyo para redactar las secciones 3.1–3.4.  
> Contiene información condensada de todos los módulos del sistema.

---

## 3.1 Observación del fenómeno a resolver

Se identificaron cuatro barreras documentadas en la literatura y confirmadas por la práctica del equipo:

**Barrera 1 — Curva de aprendizaje de los demostradores formales.**  
Lean 4 requiere dominio de teoría de tipos dependientes y tácticas de prueba. La mayoría de los matemáticos no tiene formación en ciencias de la computación, por lo que los proyectos de formalización quedan concentrados en una comunidad muy pequeña de especialistas. Los resultados publicados en lenguaje natural no tienen una ruta directa hacia la verificación formal.

**Barrera 2 — Ausencia de herramientas colaborativas especializadas.**  
Los flujos de trabajo existentes en demostradores interactivos (ITPs) son monousuario o usan control de versiones genérico (Git) sin primitivas de colaboración orientadas al dominio matemático. No existe ninguna plataforma que gestione la descomposición estructurada de pruebas entre múltiples colaboradores con verificación formal como mecanismo de control de calidad.

**Barrera 3 — Alucinaciones de los modelos de lenguaje en matemáticas.**  
Los LLMs generan sugerencias de prueba plausibles pero incorrectas con frecuencia documentada. Sin un acoplamiento directo entre la sugerencia del modelo y el compilador formal, cualquier ganancia en productividad viene acompañada de riesgo de error silencioso.

**Barrera 4 — Inaccesibilidad del cómputo HPC para pruebas por exhaustión.**  
Una categoría significativa de resultados matemáticos modernos —desde el teorema de los cuatro colores hasta resultados en combinatoria y teoría de números— requiere verificación computacional exhaustiva. Los matemáticos que podrían beneficiarse de un clúster HPC con MPI no tienen los conocimientos de sistemas necesarios para usarlo. Lean 4 tampoco dispone de un mecanismo nativo para integrar evidencia computacional como artefacto de prueba.

**Datos de soporte:**  
- Repositorio Mathlib4: más de 100 000 teoremas formalizados, sin plataforma colaborativa con control de acceso a nivel de nodo de prueba.  
- Clúster CIMAT (referenciado en el manuscrito): infraestructura MPI disponible pero sin interfaz accesible para matemáticos.  
- Experimentos internos: el compilador Lean 4 rechaza fragmentos inválidos con mensajes de error estructurados, lo que hace factible usarlo como oráculo de verificación en un ciclo de retroalimentación con LLM.

---

## 3.2 Descripción general del proyecto

**CoProof** es una plataforma web colaborativa para verificación formal de teoremas matemáticos. Permite que múltiples usuarios descompongan una demostración en un árbol de nodos, colaboren en la resolución de cada nodo, y obtengan verificación formal automática mediante el compilador Lean 4.

### Módulos del sistema

| Módulo | Tecnología | Rol |
|--------|-----------|-----|
| `server/` | Flask, PostgreSQL, Celery, Redis | API REST + coordinación de negocio |
| `lean/` | Lean 4, Mathlib4 | Motor de verificación formal |
| `nl2fl/` | LLM (OpenAI / Anthropic / Google / DeepSeek), Celery | Traducción lenguaje natural → Lean 4 |
| `agents/` | LLM multi-proveedor, Celery | Sugerencias de demostración en lenguaje natural |
| `computation/` | Python sandbox, subprocess | Ejecución local de pruebas por exhaustión |
| `cluster_computation/` | OpenMPI, SLURM, Python MPI runner | Ejecución distribuida de pruebas por exhaustión |
| `frontend/` | Angular 17, TypeScript, Cypress | Interfaz de usuario |

### Infraestructura física

- **Servidor de aplicación:** contenedores Docker Compose (servidor de desarrollo / nube).
- **Clúster HPC:** 4 × Raspberry Pi 4 Model B — 1 nodo SMS (gestión, 192.168.1.1) + 3 nodos de cómputo (192.168.1.11–13) — 12 núcleos ARM totales.  
  Stack: Rocky Linux 10 · OpenHPC 4 · SLURM · MUNGE · OpenMPI · NFS (arranque por red).

### Cronograma de actividades

| Período | Actividad |
|---------|-----------|
| Semanas 1–2 (antes de sprints) | Especificación: historias de usuario, wireframes, diagramas UML, arquitectura |
| Fase 1–6 (backend secuencial) | Application factory → modelos → Git engine → servicios → API REST → workers async |
| Sprint 1 (14–20 Abr 2026) | Vistas de acceso, perfil y configuración; flujo login/logout |
| Sprint 2 (21–27 Abr 2026) | Visor LaTeX, input lenguaje natural, traductor NL→Lean |
| Sprint 3 (28–30 Abr 2026) | Sugerencias IA, modo de ejecución MPI/SLURM |
| Feature freeze (30 Abr 2026) | Sin funcionalidad nueva a partir de esta fecha |
| Testing completo (30 Abr – 6 May 2026) | 25 TCDs, sesiones de usabilidad, zero known bugs |
| Entrega final (7 May 2026) | Tag `v1.0.0`, demo, documentación |

---

## 3.3 Diseño y experimentación de las etapas

### Tipo de investigación
**Investigación experimental aplicada** con elementos de estudio de caso. Se construyó un prototipo funcional, se validó su comportamiento contra requisitos formales (casos de prueba), y se realizaron sesiones de usabilidad con participantes externos. No es investigación documental ni bibliográfica pura: el sistema produce artefactos ejecutables verificables.

### Recursos utilizados

**Materiales físicos:**
- 4 × Raspberry Pi 4 Model B (4 GB RAM), tarjetas microSD, switch de red, cables Ethernet.
- 3 equipos de desarrollo (laptops con Docker Desktop y VS Code).

**Software (sin costo de licencia):**
- Lean 4 + Mathlib4, Python 3.11, Flask, SQLAlchemy, PostgreSQL, Redis, Celery.
- Angular 17, TypeScript, Cypress, pytest.
- Docker Compose, Rocky Linux 10, OpenHPC 4, SLURM, OpenMPI.
- GitHub (control de versiones, CI/CD con Actions, gestión de Issues y PRs).

**APIs externas (con costo según uso):**
- OpenAI API (GPT-4o): traducción NL→Lean y sugerencias de agentes.
- Anthropic API (Claude): proveedor alternativo para los mismos servicios.
- Google Generative Language API (Gemini): proveedor alternativo.

**Financieros:**
- Hardware Raspberry Pi: inversión única del equipo.
- APIs LLM: consumo por tokens; el sistema acepta clave propia del usuario para no centralizar el costo.

### Lugar de la investigación
Laboratorio del equipo de desarrollo (trabajo remoto coordinado mediante GitHub). Clúster HPC físico en instalaciones del responsable de infraestructura. Sesiones de usabilidad en pasillo con participantes externos al equipo.

### Variables

| Variable | Definición conceptual | Definición operacional | Indicador |
|----------|----------------------|----------------------|-----------|
| **Corrección de la verificación** | El sistema acepta solo código Lean válido | `valid: true/false` devuelto por `lean_service.py` | Tasa de falsos positivos/negativos en TCD-17, TCD-23 |
| **Calidad de traducción NL→Lean** | El LLM produce código que compila correctamente | Porcentaje de intentos que terminan en `valid: true` antes de agotar `max_retries` | TCD-10, TCD-19 |
| **Latencia de verificación** | Tiempo desde envío de tarea hasta respuesta | `processing_time_seconds` en respuesta del worker | TCD-24 (benchmarks de rendimiento) |
| **Suficiencia de exhaustión** | El cómputo cubre todos los casos del espacio de entrada | `sufficient: true` con `records` completos | TCD-08, TCD-09, TCD-18, TCD-21 |
| **Usabilidad** | Capacidad del usuario de completar flujos sin asistencia | Cantidad de fricciones registradas en sesión de pasillo | Sesiones externas + issues con etiqueta `ux` |

### Procedimientos: etapas de desarrollo

**Etapa 1 — Especificación (antes de código):**  
Historias de usuario con criterios de aceptación en formato checkbox. Wireframes como HTML estático para cada vista principal. Diagramas UML de clases para backend, frontend y servicio Lean por separado. Arquitectura documentada (capas, contratos, patrones de diseño).

**Etapa 2 — Backend por fases (6 fases secuenciales):**  
Cada fase tiene alcance definido y condición de salida que debe cumplirse antes de iniciar la siguiente:  
1. Application factory, configuración, Docker, manejo de errores.  
2. Esquema PostgreSQL y modelos SQLAlchemy (`User`, `NewProject`, `NewNode`).  
3. Git engine distribuido con bloqueo (`RepoPool`, `git_transaction`).  
4. Capa de servicios de dominio (`ProjectService`, `AuthService`, `CompilerClient`).  
5. API REST (`/api/v1/auth`, `/api/v1/projects`, `/api/v1/nodes`, webhooks).  
6. Workers Celery asíncronos y notificaciones en tiempo real (SocketIO).

**Etapa 3 — Servicios especializados (workers Celery):**  
- `lean/`: compilación Lean en proceso aislado; parseo de errores del compilador.  
- `nl2fl/`: bucle LLM → compilador → retroalimentación de errores → reintento (hasta `max_retries`).  
- `agents/`: una solicitud al LLM, una respuesta en lenguaje natural, sin compilación.  
- `computation/`: sandbox Python local; `register_record()` inyectado; `compute(data, target)`.  
- `cluster_computation/`: cliente HTTP de la API REST del clúster; polling de estado SLURM; misma interfaz que `computation/`.

**Etapa 4 — Frontend (sprints ágiles):**  
Angular 17 SPA. Autenticación OAuth GitHub con JWT. Vistas: login, dashboard de proyectos, árbol de nodos, editor de nodo (Lean + lenguaje natural), perfil, configuración. Servicios Angular: `AuthService`, `TaskService`, `ProjectService`.

**Etapa 5 — Infraestructura HPC:**  
Instalación de Rocky Linux 10 en 4 Raspberry Pi. Arranque por red (PXE/TFTP/NFS). OpenHPC 4 + SLURM + MUNGE + OpenMPI. API REST Flask en SMS (`cluster_api/app.py`) con autenticación por `X-API-Key`. MPI runner con plantilla Jinja2 que distribuye `input_data` entre ranks.

### Métodos de análisis y validación

- **Pruebas unitarias** (pytest + responses + pytest-mock): cada módulo tiene su propio TCD. Las llamadas HTTP externas (GitHub, LLM APIs, cluster API) se interceptan con la librería `responses`.
- **Pruebas de integración** (pytest-flask + Docker Compose): el backend se levanta contra `coproof_test_db` (PostgreSQL real, base separada de producción).
- **Pruebas E2E** (Cypress): flujos completos de autenticación, creación de proyecto y trabajo con nodos sobre el stack completo.
- **Pruebas de rendimiento** (TCD-24): latencia del worker Lean bajo carga; umbrales definidos en milisegundos.
- **Validación de usabilidad**: dos sesiones con observador silencioso; fricciones registradas como Issues `ux`.
- **Control de calidad continuo**: CI en GitHub Actions con dos jobs paralelos (backend pytest + frontend vitest/build); ningún merge a `main` sin CI verde y revisión aprobada.
- **Limitaciones del método**: el clúster HPC está en red LAN privada, por lo que las pruebas de `cluster_computation` en CI usan mocks. El tiempo de respuesta del LLM depende de la disponibilidad y carga del proveedor externo.

---

## 3.4 Pruebas del proyecto

El sistema cuenta con **25 Test Case Descriptions (TCDs)** que cubren los 10 contenedores del stack. Cada TCD agrupa casos de prueba relacionados por módulo funcional.

### Cobertura por módulo

| TCD | Módulo / capa | Tests representativos | Estado |
|-----|---------------|-----------------------|--------|
| TCD-01 | Auth API (`server/`) | OAuth URL, intercambio de código, refresh JWT, perfil autenticado | ✅ 45/45 |
| TCD-02 | Projects API | CRUD de proyectos, validaciones de payload | ✅ |
| TCD-03 | Nodes API | Crear nodo, actualizar estado, resolver nodo | ✅ |
| TCD-04 | Translation API | Endpoint NL→Lean, errores de proveedor | ✅ |
| TCD-05 | Agents API | Endpoint de sugerencias, mock de LLM | ✅ |
| TCD-06 | GitHub Service / Git Engine | Transacciones git, bloqueo distribuido, webhooks | ✅ |
| TCD-07 | Lean Worker (contrato HTTP) | Submit, polling, estados terminales | ✅ |
| TCD-08 | Computation Worker local | Happy path, timeouts, código inválido | ✅ |
| TCD-09 | Cluster Computation Worker | Submit HTTP, polling SLURM, COMPLETED/FAILED/TIMEOUT | ✅ |
| TCD-10 | NL2FL Worker | Traducción exitosa, bucle de reintento con errores, LLM no disponible | ✅ |
| TCD-11 | Agents Worker | Sugerencia exitosa, proveedor no disponible | ✅ |
| TCD-12 | Angular AuthService | Login, logout, refresh de token, guards | ✅ |
| TCD-13 | Angular TaskService | Peticiones HTTP, manejo de errores | ✅ |
| TCD-14 | Angular authGuard | Redirección si no autenticado | ✅ |
| TCD-15 | E2E Autenticación | Flujo completo login → dashboard | ✅ |
| TCD-16 | E2E Proyectos y Nodos | Crear proyecto → crear nodo → resolver nodo | ✅ |
| TCD-17 | Lean Worker funcional | Código válido acepta, código inválido rechaza con errores | ✅ |
| TCD-18 | Computation Worker funcional | Función Python ejecuta correctamente, `register_record` acumula | ✅ |
| TCD-19 | NL2FL funcional | Traducción de enunciados matemáticos reales | ✅ |
| TCD-20 | Agents Worker funcional | Sugerencias coherentes para contexto matemático | ✅ |
| TCD-21 | Cluster Computation funcional | Polling completo hasta resultado con mock de API | ✅ |
| TCD-22 | Web API + PostgreSQL integración | Endpoints contra base de datos real de pruebas | ✅ |
| TCD-23 | Lean Worker: todos los puntos de entrada | `verify_snippet`, `verify_project_files`, casos borde | ✅ |
| TCD-24 | Lean Worker: rendimiento | Latencia bajo carga, umbrales de tiempo de respuesta | ✅ |
| TCD-25 | Lean Worker: escenarios Mathlib | Teoremas reales de Mathlib4 verificados correctamente | ✅ |

### Comparación con requisitos

| Requisito (historia de usuario) | Mecanismo de verificación | Resultado |
|---------------------------------|--------------------------|-----------|
| Autenticación OAuth con GitHub | TCD-01, TCD-15 E2E | Cumple |
| Crear y gestionar proyectos | TCD-02, TCD-16 E2E | Cumple |
| Descomponer prueba en nodos | TCD-03, TCD-16 E2E | Cumple |
| Verificar código Lean formalmente | TCD-17, TCD-23, TCD-25 | Cumple |
| Traducir lenguaje natural a Lean | TCD-10, TCD-19 | Cumple |
| Recibir sugerencias de IA | TCD-11, TCD-20 | Cumple |
| Ejecutar prueba por exhaustión (local) | TCD-08, TCD-18 | Cumple |
| Ejecutar prueba por exhaustión (clúster HPC) | TCD-09, TCD-21 | Cumple (con mock en CI; validado con clúster físico en smoke test) |
| Interfaz web usable por no especialistas | Sesiones de usabilidad + issues `ux` resueltos | Cumple |
| Zero known bugs antes de entrega | Milestone en GitHub cerrado al 7 May 2026 | Cumple |
