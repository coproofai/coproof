# Resumen Técnico — CoProof (Capítulo IV)

> Documento de apoyo para redactar las secciones 4.1–4.3.  
> Basado en el manuscrito `coproof-manuscript.tex`, los módulos del sistema y los resultados medidos.

---

## 4.1 Análisis de resultados

### Relación con los objetivos planteados

El objetivo general del proyecto era construir una plataforma colaborativa para verificación formal asistida por IA en Lean 4, que resolviera cuatro barreras identificadas: la curva de aprendizaje de los demostradores formales, la ausencia de herramientas colaborativas especializadas, las alucinaciones de los LLM en contextos matemáticos, y la inaccesibilidad del cómputo HPC para pruebas por exhaustión. Los resultados obtenidos muestran que todos los objetivos específicos derivados de esas barreras fueron alcanzados en la versión v1.0.0.

**Objetivo 1 — Reducir la barrera de acceso a Lean 4.**  
Se implementó el pipeline NL2FL (`nl2fl/`): el usuario describe un teorema en lenguaje natural y el sistema produce código Lean 4 válido mediante un LLM con bucle de retroalimentación del compilador. El servicio de agentes (`agents/`) complementa esto ofreciendo sugerencias de estrategia de demostración en lenguaje natural sin requerir que el usuario escriba tácticas. Ambos servicios están operativos y cubiertos por pruebas funcionales (TCD-10, TCD-19, TCD-20).

**Objetivo 2 — Plataforma colaborativa con verificación formal como control de calidad.**  
El flujo completo de split → verify → branch → PR → merge → reindexación está implementado y validado. Ningún cambio en el repositorio de prueba llega a GitHub sin pasar por el compilador Lean 4. El modelo de grafo DAG persiste en PostgreSQL y el contenido fuente en GitHub, ofreciendo auditoría, trazabilidad por PR y la posibilidad de forks independientes de la plataforma. Los 45 casos de prueba de autenticación (TCD-01), los flujos de proyectos (TCD-02) y nodos (TCD-03) y las pruebas E2E (TCD-15, TCD-16) validan el comportamiento colaborativo de extremo a extremo.

**Objetivo 3 — Acoplar sugerencia LLM con verificación formal.**  
El pipeline NL2FL incorpora el compilador como oráculo: si el código generado falla, los mensajes de error de Lean se devuelven al LLM como contexto y se reintenta hasta `max_retries`. Esto elimina la posibilidad de que una traducción inválida alcance el repositorio del usuario.

**Objetivo 4 — Hacer accesible el cómputo HPC para pruebas por exhaustión.**  
El módulo `cluster_computation` permite al usuario enviar una función Python `compute(data, target)` al clúster de Raspberry Pi 4. SLURM distribuye `input_data` entre los 12 núcleos disponibles vía MPI; los resultados se agregan en un esquema estándar (`evidence`, `sufficient`, `records`) y se integran automáticamente en el nodo de prueba como evidencia embebida en Lean. El clúster HPC fue configurado desde cero con Rocky Linux 10, PXE/TFTP/NFS, OpenHPC 4 y OpenMPI.

---

### Resultado cuantitativo principal: benchmark del servicio Lean

El experimento más importante fue el benchmark de verificación sobre 100 teoremas extraídos de Mathlib4 (ejecutado el 27 de noviembre de 2025):

| Métrica | Valor |
|---------|-------|
| Teoremas enviados | 100 |
| Con tácticas / sin tácticas | 48 / 52 |
| Verificaciones exitosas | 96 |
| Fallos (por timeout) | 4 |
| Pruebas mock utilizadas | 0 |
| Tiempo promedio de obtención (s) | 1.02 |
| Latencia promedio de API (s) | 8.42 |
| Tiempo promedio de procesamiento (s) | 8.31 |

El 96 % de tasa de éxito confirma que el worker Lean es operacionalmente correcto para la carga esperada. Los 4 fallos comparten una única causa raíz: la latencia de API superó el umbral de 35 s. Ningún fallo fue atribuible a un error de compilación en los datos de entrada. La ausencia de pruebas mock garantiza que los números reflejan verificación real contra código Lean fuente.

---

### Problemas metodológicos encontrados

**Timeout como techo de tiempo de pared.**  
Teoremas con cadenas de tácticas largas pueden exceder el presupuesto de 45 s del cliente sin ajuste automático. Para el alcance actual (nodos hoja con pruebas cortas) el techo es suficiente; se convierte en limitación para metas extraídas de capas profundas de Mathlib.

**No-determinismo del pipeline NL2FL.**  
Entradas idénticas pueden producir código Lean diferente entre llamadas. No hay caché de traducción, por lo que los costos de tokens LLM se acumulan en cada reintento. La calidad del resultado depende fuertemente de la exposición previa del modelo a sintaxis Lean 4 y a idioms de Mathlib.

**Colaboración de última escritura gana.**  
El Redlock de Redis previene corrupción concurrente del repositorio, pero no media la intención concurrente sobre el mismo nodo. Si dos usuarios intentan resolver el mismo nodo simultáneamente, el primero en completar la operación prevalece; el segundo recibe un error de bloqueo.

**Sandbox del worker de cómputo sin aislamiento de red.**  
El subproceso Python del `computation-worker` corre en el espacio de proceso del contenedor sin restricciones de red, caps de recursos ni límites de tiempo más allá del timeout de la tarea Celery. Esto es adecuado para un prototipo académico controlado, pero insuficiente para un entorno de producción abierto.

**Dependencia de disponibilidad de GitHub.**  
Todas las operaciones de escritura requieren acceso live a la API de GitHub. Una interrupción impide edición de pruebas incluso cuando el contenido está en caché local.

---

### Implicaciones e investigaciones futuras

- **Timeouts adaptativos por nodo:** inferir el presupuesto de tiempo de pared a partir del historial de compilación de cada nodo.
- **Integración LLM con estado de prueba:** alimentar al modelo con el estado táctico actual del nodo en lugar de solo el enunciado en lenguaje natural.
- **Bloqueo optimista y UI de resolución de conflictos:** sustituir el modelo de última escritura gana por un mecanismo de merge semántico para ediciones concurrentes.
- **Sandboxing fuerte para cómputo:** adoptar `nsjail` o `gVisor` para aislar los subprocesos del worker de cómputo.
- **Caché persistente de traducción NL2FL:** reducir costos de tokens y mejorar la reproducibilidad almacenando pares (enunciado, código Lean validado).
- **Exportación como paquete Lean 4:** generación de un proyecto `lake` autocontenido a partir de un grafo de prueba validado completo.
- **Backends adicionales:** soporte de Coq, Isabelle/HOL y Agda como alternativas al worker Lean.

---

## 4.2 Aplicación del proyecto / Puesta en marcha del prototipo

### Stack de servicios desplegado

El prototipo v1.0.0 fue entregado como un stack Docker Compose de 9 contenedores completamente integrados, levantado con un único comando (`docker compose up --build`):

| Servicio | Tecnología | Rol |
|---------|-----------|-----|
| `web` | Flask 3.1.3 + SocketIO | API REST + notificaciones en tiempo real |
| `celery_worker` | Celery 5.6.2 + Redis | Git engine + tareas asíncronas generales |
| `lean-worker` | Celery + Lean 4 (elan) + Mathlib4 | Verificación formal |
| `nl2fl-worker` | Celery + LLM multi-proveedor | Traducción NL → Lean con retroalimentación |
| `agents-worker` | Celery + LLM multi-proveedor | Sugerencias de demostración |
| `computation-worker` | Celery + Python subprocess | Ejecución sandbox de pruebas por exhaustión |
| `frontend` | Angular 21 + Nginx | SPA de interfaz de usuario |
| `db` | PostgreSQL 15 | Índice relacional y metadatos |
| `redis` | Redis 7 | Broker de tareas + Redlock distribuido |

### Validación por componente (resumen de TCDs)

El sistema cuenta con **25 Test Case Descriptions** que cubren todos los contenedores. A continuación se resumen los resultados por área funcional:

**Autenticación y seguridad (TCD-01, TCD-12, TCD-14):**  
- 45/45 casos pasan. OAuth 2.0 con GitHub emite JWT de acceso y refresco. Los tokens se validan en cada endpoint protegido. El `authGuard` de Angular redirige al login si el token está ausente o expirado.  
- Las claves de API de proveedores LLM se almacenan cifradas con AES-256-GCM; ninguna clave viaja en texto plano por la red.

**API de proyectos y nodos (TCD-02, TCD-03, TCD-22):**  
- El flujo completo de creación de proyecto (con pre-compilación del objetivo como gate), split de nodo, solve de nodo y propagación de estado fue validado en integración contra PostgreSQL real (`coproof_test_db`). La E2E TCD-16 recorre el flujo completo con Cypress.

**Verificación formal Lean (TCD-07, TCD-17, TCD-23, TCD-24, TCD-25):**  
- El worker acepta correctamente código válido y rechaza código inválido con mensajes de error estructurados (línea, columna, mensaje).  
- TCD-25 ejecutó escenarios reales de Mathlib4 —incluyendo teoremas de álgebra y análisis— contra el worker en producción. Todos pasaron dentro del presupuesto de tiempo.  
- TCD-24 establece umbrales de latencia: el P95 de tiempo de procesamiento se mantiene dentro del presupuesto aceptable para la interacción en la UI.

**Pipeline NL2FL y agentes (TCD-10, TCD-11, TCD-19, TCD-20):**  
- El bucle de reintento con retroalimentación de errores del compilador fue validado: el sistema produce código compilable en intentos subsecuentes cuando el primer intento falla.  
- El servicio de agentes devuelve sugerencias coherentes en lenguaje natural; las llamadas a proveedores externos se interceptan en prueba con la librería `responses`.

**Worker de cómputo y clúster (TCD-08, TCD-09, TCD-18, TCD-21):**  
- El `computation-worker` local ejecuta la función `compute(data, target)` en sandbox, inyecta `register_record()`, y devuelve `evidence`, `sufficient` y `records` correctamente.  
- El `cluster_computation-worker` hace polling de estado SLURM hasta estado terminal y normaliza la respuesta con el mismo esquema. Validado con mock en CI y con el clúster físico de Raspberry Pi en smoke test.

**Integración continua:**  
- El pipeline CI (GitHub Actions) ejecuta dos jobs en paralelo (backend pytest + frontend Vitest + build de producción) en cada push y PR. Tiempo promedio observado: menos de 5 minutos. Ningún merge a `main` fue aceptado sin CI verde y revisión aprobada.

**Joel Test:**  
- Los 12 criterios de calidad de proceso fueron satisfechos y documentados con artefactos concretos (control de versiones, build en un paso, CI, base de bugs, zero-defects, cronograma, especificación previa, condiciones de trabajo, herramientas, testers, entrevistas técnicas, pruebas de usabilidad en pasillo).

### Escalabilidad y seguridad

**Escalabilidad:** El diseño producer-consumer con Celery permite escalar cualquier worker de forma independiente sin modificar el servidor. El clúster HPC puede ampliarse agregando más nodos al pool de SLURM; el `job_manager` no tiene acoplamiento al número de nodos. El frontend Angular es una SPA estática servida por Nginx, lo que permite distribuirla detrás de un CDN sin cambios.

**Seguridad:** La autenticación es stateless (JWT). Los repositorios de prueba son privados en GitHub y accesibles solo con el token del usuario autenticado. Las claves LLM se cifran en reposo (AES-256-GCM). El Redlock de Redis previene race conditions en operaciones Git. El worker de cómputo corre en un contenedor aislado de los demás servicios.

---

## 4.3 Conclusiones

**Lo que se observó:**  
CoProof demostró ser técnicamente viable como plataforma para verificación formal colaborativa. El servicio Lean verificó el 96 % de 100 teoremas de Mathlib4 sin ningún falso positivo ni uso de pruebas mock; todos los fallos fueron operacionales (timeout), no de corrección. El flujo completo —desde autenticación hasta PR merge con reindexación automática— opera de forma integrada sobre el stack de 9 contenedores.

**Lo que se aprendió:**  
La decisión de usar GitHub como fuente de verdad —en lugar de construir un sistema de control de versiones propio— fue la más consecuente del diseño: redujo la complejidad de implementar colaboración multiusuario con trazabilidad de cambios, al precio de introducir dependencia de disponibilidad de GitHub y latencia de transacción Git en cada operación de escritura. La metodología spec-first, fase a fase, produjo un backend internamente consistente antes de que comenzara la integración con el frontend, reduciendo significativamente los defectos de integración tardía. El Joel Test fue útil como herramienta de auditoría de proceso con artefactos concretos, no como lista de verificación nominal.

**Lo que se demostró:**  
Es posible construir un sistema en el que un LLM produzca código Lean formalmente verificado mediante retroalimentación automática del compilador. Esto valida la hipótesis central del proyecto: el compilador Lean puede actuar como oráculo determinista que filtra las alucinaciones del modelo sin intervención humana en el bucle. El modelo de nodos de cómputo demostró que evidencia computacional puede embeberse en Lean como definición concreta, abriendo una ruta para pruebas híbridas formales/empíricas.

**Lo que se aportó:**  
Una plataforma funcional, de código abierto, con stack completo (frontend, backend, verificación formal, traducción NL, sugerencias IA, cómputo HPC) desplegable con un solo comando. El clúster HPC con Raspberry Pi 4 provee 12 núcleos ARM para ejecución distribuida de pruebas por exhaustión, accesibles desde la UI sin que el usuario escriba ningún código de sistema.

**Si se cumplió lo deseado:**  
Sí. Las 13 features planificadas al inicio del proyecto fueron entregadas en v1.0.0. Los 25 TCDs están implementados y pasan. El Joel Test alcanzó 12/12. La única brecha entre el diseño ideal y el resultado actual está en las limitaciones conocidas: el techo de timeout de Lean para teoremas complejos, el sandbox sin aislamiento de red del worker de cómputo, y el no-determinismo del pipeline NL2FL. Estas limitaciones son conocidas, documentadas y representan líneas claras de trabajo futuro, no defectos ocultos.
