
# Habilitación de Lean 4 y ejecución de Benchmark

## 1. Contenedor y API de Verificación

El sistema utiliza un contenedor Docker basado en Ubuntu 22.04, que instala Lean4 y Mathlib4 mediante `elan`. El contenedor compila Mathlib4 y expone una API Flask (`app.py`) que permite verificar teoremas Lean mediante solicitudes HTTP POST. La API implementa validación de archivos, ejecución segura de Lean y extracción de mensajes y detalles de los teoremas.

## 2. Generación y Ejecución del Benchmark

El benchmark se genera combinando teoremas provistos por LeanDojo y teoremas obtenidos automáticamente desde GitHub (fetch de fuentes). El script `benchmark200.py` gestiona la carga de datos, el fetch de fuentes, la verificación vía API y el registro de tiempos y resultados. La imagen de benchmark utilizada para los resultados está en el directorio raíz (`benchmark_results_20251127_124045.csv` y `benchmark_results_20251127_124045.json`).

## 3. Resultados de la Verificación

- Se verificaron correctamente **96 de 100 teoremas**.
- Hubo **4 excepciones** por timeout (60s).
- El **tiempo medio de ejecución** por teorema fue de **8.4 segundos** (ver gráfico adjunto).

## 4. Estructura de los Archivos Generados

### benchmark_results_*.json
- Contiene:
  - `timestamp`: Fecha y hora de la ejecución.
  - `total_theorems`: Número total de teoremas evaluados.
  - `successful`, `failed`, `verified`: Conteos de resultados.
  - `average_api_latency`, `average_api_processing_time`: Tiempos medios.
  - `results`: Lista detallada de cada teorema, con nombre, estado, tiempos y detalles.

### benchmark_sources_*.json
- Incluye para cada teorema:
  - `source`: Origen (LeanDojo o GitHub).
  - `url`: En caso de fetch, la URL del repositorio.
  - `content`: Código fuente del teorema.

## 5. Proceso de Verificación vía API Flask

### Solicitud
Se envía una petición HTTP POST a `/verify` con el siguiente formato:
```json
{
  "code": "<código Lean del teorema>",
  "filename": "<nombre_archivo>.lean"
}
```

### Respuesta
La API responde con un JSON que incluye:
- `verified`: Indica si la verificación fue exitosa.
- `returnCode`: Código de retorno de Lean.
- `theorems`: Detalles de los teoremas detectados y sus mensajes.
- `messages`: Mensajes de error, advertencia o información.
- `feedback`: Salida estándar y de error de Lean.
- `processingTimeSeconds`: Tiempo de procesamiento.

Ejemplo:
```json
{
  "verified": true,
  "returnCode": 0,
  "theorems": [{"name": "my_theorem", "type": "theorem", ...}],
  "messages": [],
  "feedback": {"stdout": "", "stderr": ""},
  "processingTimeSeconds": 7.9
}
```

## 6. Visualización de Resultados

El archivo de imagen generado (`benchmark_plot_20251127_124045.png`) muestra la distribución de latencias, tiempos de procesamiento y comparación entre fetch y verificación. Permite analizar el rendimiento y los casos de excepción.

---

