# El Cluster HPC en CoProof

## ¿Qué es y por qué existe?

CoProof es una plataforma para verificación formal colaborativa de teoremas matemáticos usando Lean 4. Una categoría específica de teoremas puede demostrarse por **exhaustión**: en lugar de construir una prueba deductiva, se verifica que una propiedad se cumple para **todos** los elementos de un conjunto finito de casos. Este tipo de cómputo es inherentemente paralelizable pero costoso en un solo núcleo. Para resolverlo, CoProof delega esos trabajos a un cluster de Raspberry Pi 4 administrado mediante SLURM y OpenMPI.

---

## Arquitectura de integración

```
Frontend Angular
      │
      ▼
  Server (Flask/SocketIO)
      │
      ▼
  Celery  ──►  cluster_computation worker
                      │
                      │  HTTP  POST /jobs
                      ▼
              Cluster REST API  (Flask en SMS, puerto 8765)
                      │
                      │  sbatch / srun
                      ▼
              SLURM  ──►  node1 · node2 · node3
```

El módulo `cluster_computation` es un worker Celery que expone la misma interfaz que el worker `computation` estándar. La plataforma no necesita saber si un trabajo se ejecutó de forma local o distribuida: ambos workers devuelven el mismo esquema de respuesta (`completed`, `sufficient`, `evidence`, `stdout`, `stderr`, etc.).

---

## Cómo se hizo

### Hardware
Cuatro Raspberry Pi 4 Model B conectadas en red privada:

| Rol | Hostname | IP |
|-----|----------|----|
| Gestión (SMS) | sms | 192.168.1.1 |
| Cómputo | node1 | 192.168.1.11 |
| Cómputo | node2 | 192.168.1.12 |
| Cómputo | node3 | 192.168.1.13 |

### Software de cluster
- **OS:** Rocky Linux 10 (aarch64) en todos los nodos.
- **Arranque por red:** Los nodos de cómputo arrancan vía PXE/TFTP y montan su sistema raíz desde NFS (`/srv/nfs/nodeX`), por lo que no requieren tarjeta SD propia.
- **Autenticación inter-nodo:** MUNGE con clave compartida.
- **Gestor de colas:** SLURM. El servidor SMS corre `slurmctld`; cada nodo corre `slurmd`.
- **Computación paralela:** OpenMPI 4 instalado en SMS y en todos los nodos.
- **Framework HPC:** OpenHPC 4.

### API REST del cluster
En el SMS corre `cluster_api/app.py` (Flask). Recibe trabajos vía `POST /jobs`, los encola con `sbatch`/`srun` mediante `job_manager.py`, y expone el estado en `GET /jobs/<id>`. La autenticación usa un `X-API-Key` configurado por variable de entorno.

### Worker de CoProof
`cluster_computation/computation_service.py` actúa como cliente HTTP de esa API:
1. Envía el payload al endpoint `/jobs`.
2. Hace polling con intervalo configurable (`CLUSTER_POLL_INTERVAL`, por defecto 4 s).
3. Cuando SLURM reporta un estado terminal (`COMPLETED`, `FAILED`, etc.), retorna el resultado normalizado al resto de la plataforma.

Los lenguajes de ejecución soportados son `mpi` y `python`.

---

## Ventajas

| Ventaja | Descripción |
|---------|-------------|
| **Escalabilidad horizontal** | SLURM distribuye los trabajos entre los 12 núcleos disponibles (4 por nodo × 3 nodos). Agregar más Pi amplía la capacidad sin cambiar código. |
| **Aislamiento de recursos** | El cómputo pesado no compite con el servidor web ni con los workers de Lean/NL2FL. |
| **Interfaz transparente** | `cluster_computation` tiene la misma API Celery que `computation`; cambiar de backend no requiere modificar el servidor. |
| **Arranque sin estado local** | Los nodos arrancan desde NFS, lo que simplifica mantenimiento: actualizar `/srv/nfs/nodeX` en el SMS propaga el cambio a todos. |
| **Bajo costo** | Hardware ARM de bajo consumo (~5 W por Pi) frente a una VM en la nube para cargas esporádicas. |

---

## Qué tipo de problema resuelve: Proof by Exhaustion

El cluster resuelve **exclusivamente** problemas de demostración por exhaustión (*proof by exhaustion*). La idea es simple: si un conjunto de casos posibles es finito, basta con verificar que la propiedad se cumple en **cada uno** de ellos para considerar el teorema demostrado.

### Mecánica concreta

El módulo `cluster_computation` envía al cluster un payload con tres componentes esenciales:

- **`source_code`**: una función Python `compute(data, target)` que evalúa la propiedad para cada elemento de `data`.
- **`input_data`**: la lista completa de casos a verificar (el espacio de búsqueda).
- **`target`**: el valor o condición que se quiere comprobar (opcional).

El MPI runner del cluster reparte `input_data` entre los ranks disponibles: el rank `r` procesa los elementos `data[r::size]`. Cada rank llama a `compute()` sobre su porción, usando `register_record()` para registrar el resultado por caso. Al terminar, los resultados se agregan y se devuelve:

- `evidence`: lista de casos que satisfacen la propiedad.
- `records`: resultado individual de cada caso evaluado.
- `sufficient`: `true` si la verificación es concluyente (todos los casos pasaron o se encontró evidencia suficiente).

### Ejemplo del smoke test

El smoke test del módulo demuestra esto con una comprobación de primalidad distribuida: se envía el rango `[2..13]` como `input_data`, cada rank verifica si sus números son primos usando división por fuerza bruta, y el resultado final lista los primos encontrados. Tres ranks trabajando en paralelo sobre subconjuntos disjuntos del rango.

### Tipos de propiedades verificables

Cualquier propiedad que pueda comprobarse **elemento a elemento** sobre un conjunto finito es candidata:

- Verificar que una función satisface una especificación para todos los enteros en un rango.
- Comprobar que ninguna combinación de parámetros viola una invariante.
- Confirmar que no existe contraejemplo dentro del espacio de búsqueda definido.
- Validar tablas de verdad, coloraciones, o cualquier estructura enumerable.

---

## Limitaciones actuales

- Los nodos están en una red LAN privada; el acceso externo requiere tunelizar o exponer el SMS mediante una VPN o proxy.
- El sistema de archivos NFS es compartido en lectura/escritura: trabajos que escriben en las mismas rutas deben usar directorios de trabajo únicos (el `job_manager` los crea por `job_id`).
- No hay GPU; las cargas que requieran aceleración hardware deben ejecutarse en otro backend.
