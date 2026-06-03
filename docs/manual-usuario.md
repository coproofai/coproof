# Manual de Usuario — CoProof

---

## Verificación de Demostraciones

Permite comprobar si un fragmento de código Lean 4 es formalmente correcto.

1. Escribe o pega el código Lean 4 en el campo de texto. Puedes incluir `import Mathlib` y definiciones auxiliares.
2. Haz clic en **Verificar**. Un indicador de carga aparece mientras el compilador procesa el fragmento.
3. Interpreta el resultado:
   - **Válida** — compiló sin errores; la demostración es correcta.
   - **Con errores** — Lean reportó errores con número de línea y descripción.
   - **Con advertencias** — compiló pero contiene `sorry` u axiomas adicionales.

> Las verificaciones independientes no se guardan. Dentro de un proyecto en el Workspace, los nodos sí quedan registrados.

---

## Traducción de Demostraciones

Convierte enunciados matemáticos en lenguaje natural a Lean 4 verificado, o código Lean 4 a descripción en lenguaje natural.

1. Abre el panel **Configuración** y selecciona el modelo LLM y tu API key.
2. Elige la dirección:
   - **NL → Lean** — el sistema llama al LLM, obtiene código Lean, lo verifica y reintenta automáticamente si hay errores.
   - **Lean → NL** — pega el código Lean y obtén una descripción en lenguaje natural.
3. Para NL → Lean: escribe el enunciado y haz clic en **Traducir a Lean**. Al terminar se muestran el código generado y el historial de intentos.

> Si el código resulta "inválido" tras varios intentos, revisa los errores en el historial y reformula la entrada.

---

## Buscar Demostración en Mathlib

Recupera el código fuente Lean 4 de cualquier declaración de Mathlib4.

- **Por nombre** — escribe el identificador exacto (sensible a mayúsculas) y haz clic en **Buscar**.  
  Ejemplo: `Nat.succ_pos`, `Real.sqrt_sq`.
- **Por lenguaje natural** — describe el teorema; el sistema sugiere candidatos. Haz clic en **Cargar .lean** para ver el código fuente del candidato elegido.

El botón **Traducir a NL (.tex)** envía el código encontrado al traductor Lean → NL (requiere sesión y modelo configurado).

---

## Buscar Linaje de Dependencias

Construye el grafo de dependencias de una declaración de Mathlib4 nivel por nivel.

1. Introduce el nombre exacto de la declaración y selecciona la **Profundidad** (1–4).
2. Navega el grafo interactivo: arrastra nodos, usa la rueda del ratón para zoom, haz clic en un nodo para ver su código en el panel lateral.
3. Desde el panel lateral puedes traducir la declaración a lenguaje natural (requiere sesión y modelo).

> Si el grafo supera 30 nodos, aparece un aviso para reducir la profundidad. Los nodos no resueltos aparecen atenuados con la etiqueta *no encontrado*.

---

## Buscar Proyectos de Formalización

Explora los proyectos registrados en la plataforma.

- **Proyectos Públicos** — visibles sin autenticación. El panel de detalle muestra nombre, descripción, colaboradores, cobertura de nodos y cobertura de hojas. Con sesión activa puedes seguir el proyecto.
- **Mis Proyectos Privados** — requiere autenticación. Muestra si eres *Autor* o *Colaborador*. Para editar, abre el proyecto desde **Abrir Workspace**.

> La **cobertura de hojas** es el indicador más representativo del avance real del proyecto.

---

## Crear Proyecto de Formalización

Requiere autenticación.

1. **Nombre del proyecto** — campo obligatorio.
2. **Define el objetivo (goal)**:
   - Pestaña *Lenguaje Natural* — describe el teorema; la IA lo traduce a Lean 4.
   - Pestaña *Manual* — escribe directamente el enunciado Lean, imports y definiciones auxiliares.
3. **Confirma el enunciado** — selecciona un modelo LLM y genera la vista previa. Si la descripción es correcta, confirma con *"Sí, este es el teorema que quiero probar"*. Si no, usa *Regenerar* o ajusta el goal.
4. Completa **Descripción** y **Visibilidad** (*Público* / *Privado*) y haz clic en **Crear Proyecto**.

> El botón **Crear Proyecto** permanece desactivado si el goal tiene contenido pero no ha sido confirmado.

---

## Workspace

El editor interactivo de proyectos. Requiere autenticación.

### Vista General

La pantalla se divide en:
- **Panel del Grafo** (izquierda) — grafo SVG con todos los nodos y aristas. Controles: zoom con rueda, arrastrar fondo para desplazar, arrastrar nodo para reposicionar.
- **Panel Lateral** (derecha) — pestañas *Nodo*, *TeX*, *PRs*, *Defs* y *Exportar*.

**Estados de los nodos:**

| Estado | Significado |
|--------|-------------|
| `open` | Sin prueba formal; estado inicial. |
| `sorry` | Compila pero contiene `sorry` o errores. |
| `validated` | Compila limpiamente; prueba formalmente correcta. |
| `axiom` | Respaldado por evidencia computacional aprobada por el autor. |

---

### Verificar

Envía el archivo `.lean` actual del nodo al compilador Lean 4.

- Selecciona el nodo → haz clic en **Verificar** en la sección *Acciones*.
- El resultado (*Exitosa / Con sorry / Con errores*) aparece en la sección *Resultados*.
- El visor `.lean` (parte inferior) muestra el código actual del nodo como referencia.

---

### Resolver

Propone una prueba formal completa para el nodo. Si el código compila, se genera el `.tex` del nodo y se abre un Pull Request.

Tres modos disponibles:

- **Lenguaje Formal** — escribe el código Lean directamente en el editor y haz clic en **Confirmar**.
- **Lenguaje Natural** — describe la prueba en texto; la IA la traduce a Lean, la verifica y crea el PR. Una barra de progreso muestra la fase actual.
- **IA Automático** — la IA lee el `.tex` del nodo, propone la estrategia, traduce a Lean, verifica y crea el PR sin intervención manual. Puedes dar una sugerencia inicial opcional.

---

### Dividir

Descompone el teorema en sub-objetivos más simples (nodos hijo). Genera los `.tex` del padre y todos los hijos, y crea un PR con todos los cambios.

Los mismos tres modos que Resolver (Lenguaje Formal, Lenguaje Natural, IA Automático).

Tras hacer merge del PR, el grafo se actualiza con los nodos hijo en estado `open`.

---

### Nodo de Computación

Respalda un enunciado mediante evidencia computacional (Python local o MPI en el clúster de Raspberry Pi).

1. Selecciona el nodo padre → **Nodo Computación** → **Crear Nodo de Computación**.
2. Haz clic en el nuevo nodo hijo → **Ejecutar Computación**.
3. Configura el payload:

   | Campo | Descripción |
   |-------|-------------|
   | **Backend** | `Python (local)` o `MPI (cluster RPI)` |
   | **Entrypoint** | Nombre de la función Python (por defecto `run`) |
   | **Target JSON** | Objeto JSON con la propiedad a verificar |
   | **Input Data JSON** | Lista de datos de entrada |
   | **Código Python** | Función que recibe `(input_data, target)` y retorna `{evidence, sufficient, summary, records}` |
   | **Timeout (s)** | Tiempo máximo (1–900 s) |

4. Para MPI: el runner distribuye `input_data` automáticamente entre los nodos del clúster. Usa la misma firma `run(input_data, target)`.
5. Resultado:
   - `sufficient = True` → se crea un PR; tras el merge del autor, el nodo pasa a `axiom`.
   - `sufficient = False` → no se crea PR; ajusta la lógica y vuelve a ejecutar.

> El modo **Lenguaje Natural** permite describir el experimento en texto libre y la IA genera el payload automáticamente.

---

### Pull Requests y Axiomas

Las acciones *Resolver*, *Dividir* y *Ejecutar Computación* no modifican el repositorio directamente: crean un **Pull Request en GitHub** que el autor del proyecto debe revisar.

- Pestaña **PRs** del panel lateral — lista todos los PRs abiertos con número, título y rama.
- Expande un PR con **▼** para ver los archivos modificados, el diff y la vista renderizada de los `.tex`.
- **Merge** — solo el autor puede aprobar. Fusiona los cambios y actualiza el grafo.
- **Descartar** — cierra el PR sin cambios; el nodo vuelve a su estado anterior.

> **`validated`** = prueba formal completa aceptada por Lean. **`axiom`** = evidencia computacional aprobada por el autor, sin prueba formal en Lean.

---

### Exportar

Genera una versión ensamblada del proyecto completo.

| Tipo | Descripción |
|------|-------------|
| **Lean** | Ensambla todos los `.lean` (hojas primero, raíz al final) y verifica que compilan en conjunto. Descarga el archivo resultante. |
| **.tex** | Genera un documento LaTeX completo formateado por IA con preámbulo, secciones y entornos `\begin{theorem}` / `\begin{lemma}`. |
| **PDF** | Compila el `.tex` en el servidor y produce un PDF descargable. |

> Requiere modelo LLM para las exportaciones `.tex` y PDF. Exporta primero en formato Lean para verificar que todos los nodos compilan correctamente antes de generar el documento.
