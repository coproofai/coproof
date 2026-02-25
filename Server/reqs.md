Análisis de Requerimientos y Arquitectura Funcional del Sistema CoProof

1.0 Introducción al Análisis Funcional

El presente documento tiene como propósito desglosar y estructurar las capacidades funcionales del sistema CoProof, un entorno colaborativo para la demostración formal asistida por inteligencia artificial. Partiendo de un análisis detallado de los casos de uso, los requerimientos funcionales y los requerimientos no funcionales especificados, se derivará una descripción técnica de las funciones de software fundamentales que son necesarias para su implementación. Este análisis sirve como un puente estratégico entre la Especificación de Requerimientos de Software (SRS) y el diseño técnico detallado, garantizando que la arquitectura del sistema esté directamente alineada con los objetivos del producto y las necesidades de sus usuarios.

2.0 Casos de Uso Clave del Sistema CoProof

Los casos de uso son esenciales para comprender el comportamiento del sistema desde la perspectiva del usuario. Definen las interacciones fundamentales entre los distintos tipos de actores (usuarios, administradores, componentes del sistema) y el software, delineando los flujos de trabajo principales que CoProof debe soportar para cumplir su misión. A continuación, se presenta una tabla que resume los casos de uso identificados, los cuales describen las capacidades centrales del sistema, desde la validación de demostraciones hasta la gestión colaborativa de proyectos.

Identificador	Nombre del Caso de Uso	Descripción
CDU-01	Validar una demostración externa.	Permite a un usuario cargar una demostración en formato PDF, imagen o LaTeX para que el sistema verifique su validez formal.
CDU-02	Traducir una demostración externa a Lean.	Permite a un usuario cargar una demostración en un formato aceptado para obtener su equivalente en código del asistente de pruebas Lean.
CDU-03	Consultar una demostración interna en NL o Lean.	Permite a un usuario buscar y visualizar la demostración de un teorema, corolario o lema existente dentro del sistema, tanto en lenguaje natural (NL) como formal (Lean).
CDU-04	Consultar el linaje de un teorema, corolario o lema.	Permite a un usuario consultar qué otros resultados dentro del sistema utilizan un teorema, corolario o lema específico en sus demostraciones, mostrando sus aplicaciones.
CDU-05	Iniciar sesión.	Permite a un usuario con una cuenta existente ingresar al sistema para acceder a funciones autenticadas.
CDU-06	Crear una cuenta.	Permite a un nuevo usuario registrarse en el sistema proporcionando sus datos y verificando su correo electrónico.
CDU-07	Crear un proyecto privado.	Permite a un usuario crear un proyecto con acceso restringido, asignándole como líder y permitiéndole invitar a otros colaboradores.
CDU-08	Crear un proyecto público.	Permite a un usuario crear un proyecto visible y accesible para todos los usuarios del sistema, asignándole como líder.
CDU-09	Consultar proyectos públicos activos.	Permite a un usuario buscar y visualizar la lista de todos los proyectos públicos disponibles en la plataforma.
CDU-10	Abrir un proyecto en sesión individual.	Permite a un usuario con acceso autorizado comenzar a trabajar en un proyecto de manera individual, sin colaboración en tiempo real.
CDU-11	Abrir un proyecto en sesión colaborativa.	Permite a un usuario unirse a un espacio de trabajo colaborativo en tiempo real dentro de un proyecto al que tiene acceso.
CDU-12	Guardar cambios en una sesión individual.	Permite a un usuario guardar los cambios realizados en una sesión individual, generando una solicitud de autorización para el líder del proyecto.
CDU-13	Guardar cambios en una sesión colaborativa.	Permite a un usuario guardar los cambios consolidados de una sesión colaborativa, generando una solicitud de autorización para el líder del proyecto.
CDU-14	Editar premisas globales de un proyecto.	Permite a un usuario modificar la base axiomática de un proyecto, generando una solicitud de autorización para el líder.
CDU-15	Visualizar grafo de proyecto.	Permite a un usuario consultar de forma visual la estructura de un proyecto, incluyendo la meta global y las ramificaciones para alcanzarla.
CDU-16	Modificar un nodo del grafo de un proyecto.	Permite a un usuario realizar diversas acciones sobre un nodo (proveer demostración, solicitar asistencia de IA, ramificar, etc.), lo cual puede generar una solicitud de autorización.
CDU-17	Solicitar una demostración de un nodo a un Agente.	Permite a un usuario solicitar a un agente de IA que genere una demostración completa para un nodo específico del proyecto.
CDU-18	Proveer un plan de demostración de un nodo.	Permite a un usuario proponer un plan en lenguaje natural para demostrar un nodo, dividiéndolo en pasos o casos.
CDU-19	Solicitar un plan de demostración de un nodo a un Agente.	Permite a un usuario solicitar a un agente de IA que sugiera un plan de demostración para un nodo, estructurado en pasos o casos.
CDU-20	Proveer una demostración numérica para un nodo.	Permite a un usuario proporcionar resultados experimentales para demostrar un nodo de tipo "evaluación numérica".
CDU-21	Solicitar una demostración numérica para un nodo.	Permite a un usuario solicitar al sistema que diseñe y ejecute un experimento numérico en el clúster para validar un nodo.
CDU-22	Solicitar una exploración lógica de casos pequeños de un nodo.	Permite a un usuario solicitar al sistema que genere y analice ejemplos pequeños para entender el comportamiento de un nodo en casos simples.
CDU-23	Solicitar una exploración numérica orientada de un nodo.	Permite a un usuario solicitar una exploración numérica con valores y objetivos específicos para analizar un nodo.
CDU-24	Autorizar cambios en un nodo.	Permite al líder de un proyecto revisar y autorizar las solicitudes de cambio propuestas por los colaboradores.
CDU-25	Cerrar sesión.	Permite a un usuario finalizar su sesión activa en el sistema de forma segura.
CDU-26	Configurar cuenta de usuario.	Permite a un usuario modificar su información personal, credenciales o preferencias de seguridad.
CDU-27	Configurar el entorno de trabajo y procesamiento.	Permite a un usuario personalizar la apariencia del entorno, el idioma y los parámetros técnicos para el procesamiento de solicitudes.

Mientras que los casos de uso definen las interacciones funcionales desde la perspectiva del usuario, los siguientes requerimientos los descomponen en especificaciones técnicas medibles, estableciendo los criterios de éxito funcionales y de calidad que la implementación de software deberá satisfacer.

3.0 Especificación de Requerimientos del Sistema

Los requerimientos funcionales y no funcionales del sistema traducen los casos de uso descritos anteriormente en especificaciones concretas y medibles que el software debe cumplir. Los requerimientos funcionales definen con precisión qué debe hacer el sistema, detallando cada una de sus capacidades y comportamientos. Por otro lado, los requerimientos no funcionales establecen cómo debe hacerlo, definiendo atributos de calidad críticos como el rendimiento, la seguridad, la usabilidad y la confiabilidad, los cuales son indispensables para garantizar una experiencia de usuario robusta y profesional.

3.1 Requerimientos Funcionales (RF)

A continuación, se presenta la tabla de requerimientos funcionales que especifican las operaciones y tareas que el sistema CoProof debe ser capaz de ejecutar.

Identificador	Nombre del Requerimiento	Descripción
RF-001	Recibir y validar una demostración de un archivo externo.	El sistema permitirá cargar archivos (PDF, imagen, LaTeX, Lean) y verificará que cumplan con el formato, tamaño y estructura definidos.
RF-002	Traducir una demostración externa a Lean.	El sistema convertirá el contenido de la demostración a una representación formal en Lean mediante el módulo NL2FL, identificando su estructura lógica.
RF-003	Validar demostración con Lean Server	El sistema enviará la representación formal al Lean Server para comprobar su validez, obteniendo un resultado de verificación (válida, inválida o inconclusa).
RF-004	Gestionar y almacenar resultados validados	El sistema almacenará los resultados de las validaciones, incluyendo metadatos como usuario, archivo, formato, estado y fecha.
RF-005	Notificar errores y excepciones.	El sistema notificará cualquier error durante la carga, análisis o verificación, mostrando logs relevantes al usuario.
RF-006	Integrar demostración externa en proyecto activo.	El sistema permitirá al usuario agregar una demostración validada a un proyecto activo existente.
RF-007	Buscar demostraciones dentro del sistema.	El sistema permitirá buscar demostraciones en proyectos activos (públicos o privados) por nombre, área, tipo o autor.
RF-008	Filtrar y visualizar resultados de búsqueda de demostración interna.	El sistema permitirá filtrar resultados de búsqueda y visualizar los metadatos principales de cada demostración.
RF-009	Visualizar una demostración en NL o Lean.	El sistema permitirá visualizar el contenido de una demostración en formato NL o Lean, mostrando sus dependencias y estructura lógica.
RF-010	Controlar el acceso a demostraciones según visibilidad del proyecto.	El sistema aplicará control de acceso para que los usuarios solo consulten demostraciones de proyectos públicos o privados autorizados.
RF-011	Exportar y referenciar una demostración del sistema.	El sistema permitirá exportar una demostración en formato PDF, LaTeX o Lean, y copiar su referencia para citarla.
RF-012	Buscar el linaje de un resultado.	El sistema permitirá consultar qué teoremas, corolarios o lemas utilizan un resultado determinado, mostrando todas sus aplicaciones.
RF-013	Visualizar gráficamente el linaje de demostraciones de un resultado.	El sistema mostrará una representación gráfica del linaje de un resultado, incluyendo sus dependencias directas e indirectas.
RF-014	Exportar y citar linaje de un resultado.	El sistema permitirá exportar el linaje de un resultado en formato PDF, JSON o GraphML.
RF-015	Autenticar usuarios.	El sistema permitirá a los usuarios ingresar con su correo y contraseña para acceder a funciones protegidas.
RF-016	Manejar sesiones de usuario.	El sistema deberá generar, mantener y cerrar sesiones seguras para los usuarios autenticados.
RF-017	Crear cuenta de usuario.	El sistema permitirá crear una nueva cuenta proporcionando correo, nombre y contraseña, y verificando que el correo no esté registrado.
RF-018	Recuperar contraseña de cuenta.	El sistema permitirá restablecer la contraseña mediante un enlace enviado al correo registrado.
RF-019	Verificar correo electrónico	El sistema enviará un enlace de verificación al correo del usuario y activará la cuenta tras la confirmación.
RF-020	Crear un proyecto.	El sistema permitirá crear un nuevo proyecto proporcionando nombre, descripción y tipo (público o privado).
RF-021	Definir visibilidad del proyecto.	El sistema permitirá al creador del proyecto seleccionar si será público o privado.
RF-022	Asignar líder del proyecto.	El sistema registrará al creador del proyecto como su líder, con permisos de administración.
RF-023	Agregar colaboradores a un proyecto privado.	El líder de un proyecto privado podrá invitar a otros usuarios a colaborar.
RF-024	Registrar proyecto en la lista de proyectos activos de un usuario.	El sistema agregará automáticamente un nuevo proyecto a la lista de proyectos activos del usuario y de sus colaboradores.
RF-025	Consultar lista de proyectos públicos activos.	El sistema permitirá visualizar una lista de todos los proyectos públicos activos.
RF-026	Filtrar proyectos públicos.	El sistema permitirá filtrar la lista de proyectos públicos por área temática, líder, fecha o etiquetas.
RF-027	Consultar detalles de un proyecto público.	El sistema permitirá acceder a los detalles de un proyecto público, incluyendo descripción, participantes y demostraciones.
RF-028	Buscar proyectos públicos por nombre o palabra clave.	El sistema permitirá buscar proyectos públicos por nombre o palabra clave en su descripción.
RF-029	Cargar entorno de trabajo de proyecto.	El sistema permitirá abrir un proyecto autorizado y cargar su entorno de trabajo, incluyendo demostraciones y archivos asociados.
RF-030	Verificar permisos de acceso al proyecto.	El sistema validará que el usuario tenga los permisos necesarios para acceder a un proyecto.
RF-031	Abrir sesión individual de trabajo.	El sistema habilitará un entorno de trabajo individual sin sincronización en tiempo real.
RF-032	Abrir sesión colaborativa de trabajo.	El sistema permitirá a varios usuarios conectarse a un proyecto para trabajar de forma colaborativa con cambios en tiempo real.
RF-033	Sincronizar cambios en tiempos real	El sistema mantendrá la coherencia del proyecto compartido reflejando los cambios de cada usuario en el entorno de todos.
RF-034	Generar solicitud de guardado de cambios.	El sistema permitirá solicitar el guardado de los cambios realizados en una sesión activa.
RF-035	Validar integridad y permisos antes del guardado.	El sistema verificará que el usuario tenga permisos para modificar el proyecto y que los cambios no generen conflictos.
RF-036	Guardar cambios en sesión individual.	El sistema consolidará y guardará los cambios de una sesión individual, generando una solicitud de aprobación.
RF-037	Guardar cambios en sesión colaborativa.	El sistema consolidará los cambios de múltiples usuarios en una sesión colaborativa y los registrará en la base de datos.
RF-038	Notificar solicitud de aprobación al líder del proyecto.	El sistema notificará automáticamente al líder del proyecto cuando se genere una nueva solicitud de guardado.
RF-039	Visualizar premisas globales de un proyecto.	El sistema permitirá visualizar las premisas globales (axiomas, definiciones) definidas en un proyecto.
RF-040	Modificar premisas globales de un proyecto.	El sistema permitirá agregar, editar o eliminar premisas globales, asegurando su coherencia formal.
RF-041	Cargar el grafo de un proyecto.	El sistema cargará y representará el grafo del proyecto, mostrando la meta global, teoremas y sus dependencias.
RF-042	Interactuar con nodos del grafo.	El sistema permitirá seleccionar nodos del grafo para consultar detalles de sus resultados y relaciones.
RF-043	Filtrar y resaltar elementos del grafo.	El sistema permitirá aplicar filtros para resaltar nodos específicos (pendientes, completados, etc.).
RF-044	Seleccionar y abrir un nodo del grafo.	El sistema permitirá seleccionar y abrir un nodo del grafo para consultar su estado y acciones disponibles.
RF-045	Habilitar acciones sobre un nodo	El sistema mostrará las acciones disponibles para un nodo según su tipo y estado (proveer demostración, solicitar a Agente, etc.).
RF-046	Aplicar solicitud de Agente para demostrar un nodo.	El sistema permitirá solicitar a un Agente de IA que genere automáticamente una demostración para un nodo.
RF-047	Recibir resultados del Agente para demostrar un nodo.	El sistema recibirá la demostración generada por el Agente y la mostrará al usuario.
RF-048	Subir plan de demostración de un nodo.	El sistema permitirá subir un plan de demostración en lenguaje natural para un nodo, dividiéndolo en pasos o casos.
RF-049	Validar plan de demostración de un nodo.	El sistema verificará que el plan propuesto sea coherente y suficiente para la demostración del nodo a través del LeanServer.
RF-050	Solicitar plan de demostración a un Agente.	El sistema permitirá solicitar a un Agente una propuesta de plan de demostración para un nodo.
RF-051	Validar plan propuesto por un Agente para un nodo.	El sistema validará automáticamente que el plan sugerido por el Agente sea coherente y válido según LeanServer.
RF-052	Subir resultados experimentales para un nodo numérico.	El sistema permitirá subir resultados experimentales para respaldar la validez de un nodo de tipo "evaluación numérica".
RF-053	Validar suficiencia de la demostración numérica.	El sistema analizará los datos experimentales para determinar si son evidencia suficiente para considerar el nodo demostrado.
RF-054	Solicitar el diseño y despliegue de un experimento numérico.	El sistema permitirá solicitar a un Agente la generación de un experimento numérico, que será diseñado y ejecutado en el clúster.
RF-055	Interpretar y validar resultados de la demostración numérica.	El sistema interpretará los resultados del experimento para determinar si las evidencias numéricas son suficientes.
RF-056	Solicitar generación de casos pequeños para exploración lógica.	El sistema permitirá solicitar a un Agente la generación de ejemplos representativos y de tamaño reducido para un nodo.
RF-057	Analizar y visualizar los resultados de la exploración lógica.	El sistema interpretará y presentará los resultados de la exploración lógica con visualizaciones y resúmenes.
RF-058	Solicitar exploración numérica orientada.	El sistema permitirá solicitar una exploración numérica sobre un nodo, especificando valores iniciales, rangos y un objetivo.
RF-059	Analizar y presentar resultados de la exploración numérica.	El sistema procesará e interpretará los resultados de la exploración numérica y mostrará un resumen visual y estadístico.
RF-060	Visualizar solicitudes de autorización pendientes.	El líder del proyecto podrá consultar una lista de solicitudes de autorización pendientes de los colaboradores.
RF-061	Revisar y autorizar o rechazar solicitud de cambios.	El líder del proyecto podrá revisar el detalle de una solicitud de cambio y decidir si la autoriza o rechaza.
RF-062	Cerrar sesión del usuario.	El sistema permitirá al usuario cerrar su sesión activa de forma segura.
RF-063	Actualizar información personal del usuario.	El sistema permitirá al usuario modificar su información personal (nombre, correo, etc.).
RF-064	Cambiar contraseña de usuario.	El sistema permitirá al usuario modificar su contraseña, validando su identidad.
RF-065	Configurar apariencia e idioma del entorno de trabajo.	El sistema permitirá al usuario modificar las preferencias visuales (tema, colores) y el idioma.
RF-066	Seleccionar y configurar modelos de agentes de IA, traductores y clúster.	El sistema permitirá al usuario elegir y configurar los modelos de IA, traductores y la conexión con el clúster.
RF-067	Ajustar parámetros técnicos de procesamiento de solicitudes.	El sistema permitirá definir parámetros operativos para las solicitudes de IA, como número de reintentos y tiempo de espera.

3.2 Requerimientos No Funcionales (RNF)

Los siguientes requerimientos no funcionales definen los estándares de calidad, rendimiento y seguridad que CoProof debe cumplir para ser una plataforma efectiva y confiable.

Identificador	Nombre del Requerimiento	Descripción
RNF-001	Validación de formato de entrada.	El sistema debe validar automáticamente que el archivo cargado pertenezca a los formatos aceptados y rechazar cargas malformadas con mensajes claros.
RNF-002	Tolerancia a errores de conversión inicial.	Si NL2FL no interpreta correctamente el contenido, la aplicación mostrará mensajes claros y accionables explicando la falla y posibles correcciones.
RNF-004	Límite de tamaño y manejo de archivos grandes.	El sistema impondrá límites de tamaño de carga y soportará segmentación o procesamiento en cola para archivos grandes, mostrando el progreso al usuario.
RNF-005	Indicaciones de ambigüedad en la traducción a Lean.	Cuando NL2FL detecte ambigüedades, el código resultante incluirá marcas y comentarios para indicar los puntos ambiguos y notificar al usuario.
RNF-006	Re-tentativa automática en fallos del módulo NL2FL.	En caso de fallo transitorio de NL2FL, el gestor reintentará la conversión automáticamente antes de notificar al usuario.
RNF-007	Búsqueda por metadatos optimizada.	La búsqueda debe permitir consultas por nombre, área y aplicación con respuesta ágil, sugerencias de autocompletado y tolerancia a errores ortográficos.
RNF-008	Manejo de resultados incompletos o corruptos.	Si una demostración está incompleta o corrupta, el sistema marcará las secciones afectadas y advertirá al usuario.
RNF-009	Caché de consultas para latencia reducida.	Se implementará un mecanismo de caché para consultas frecuentes para reducir la latencia y la carga sobre la base de datos.
RNF-010	Visualización del linaje escalable.	El grafo de linaje debe renderizarse de manera legible para proyectos grandes, permitiendo zoom, colapso de subgrafos y agrupamiento de nodos.
RNF-011	Actualización incremental del linaje.	Al consultar el linaje, la aplicación recuperará e integrará nodos de forma incremental para minimizar la transferencia de datos y la latencia.
RNF-012	Marcado de nodos con demostraciones incompletas.	Los nodos con demostraciones incompletas o con errores serán claramente identificables mediante etiquetas y descripciones en la vista de linaje.
RNF-013	Validación fuerte de credenciales en login.	El proceso de inicio de sesión debe aplicar políticas de complejidad y controles contra intentos no autorizados, como bloqueo temporal tras múltiples fallos.
RNF-014	Registro de accesos y sesión.	Cada sesión iniciada registrará hora, origen aproximado y tipo de dispositivo para fines de auditoría y detección de anomalías.
RNF-015	Mecanismo de reintento ante fallo de la Database en login.	Si la base de datos no responde durante el login, el sistema reintentará la operación y notificará claramente al usuario del estado.
RNF-016	Verificación de correo para registro seguro.	La creación de cuentas requerirá verificación por correo mediante tokens con caducidad para confirmar la propiedad del correo.
RNF-017	Validación de unicidad y formato del correo.	Al registrarse, el sistema comprobará que el correo no esté asociado a otra cuenta y que cumpla un formato válido.
RNF-018	Política de contraseñas y ayuda de usuario.	Se mostrarán requisitos mínimos de contraseña y se ofrecerá ayuda para generar contraseñas seguras, con retroalimentación en tiempo real sobre su fortaleza.
RNF-019	Asignación y control de roles en proyectos privados.	Al crear un proyecto privado, el sistema asignará un rol de líder y permitirá definir permisos para colaboradores con trazabilidad.
RNF-020	Restricciones y validaciones de metadatos del proyecto.	Los metadatos del proyecto (nombre, descripción) serán validados por longitud y caracteres permitidos antes de ser guardados.
RNF-021	Manejo de errores de conexión en la creación de proyecto.	Si se pierde la conexión a la base de datos durante la creación de un proyecto, el gestor reintentará y mantendrá los datos temporales de forma segura.
RNF-022	Visibilidad y búsqueda en proyectos públicos.	Los proyectos públicos deben ser indexados y aparecer en listados públicos con metadatos visibles para facilitar su descubrimiento.
RNF-023	Control de consentimiento para acceso público.	Antes de publicar un proyecto, se requerirá la confirmación explícita del propietario sobre el alcance de la publicación.
RNF-024	Protección de datos personales en proyectos públicos.	El sistema debe advertir sobre la posible exposición de datos personales sensibles en proyectos públicos y proporcionar guías para anonimizarlos.
RNF-025	Filtrado y paginación eficiente de proyectos públicos.	La vista de proyectos públicos ofrecerá filtros, ordenamientos y paginación eficientes para grandes volúmenes de datos.
RNF-026	Mensajes claros cuando no hay proyectos disponibles.	Cuando una búsqueda no arroje resultados, la interfaz mostrará mensajes útiles y sugerirá acciones alternativas.
RNF-027	Caching de listas públicas para alta concurrencia.	Las listas públicas y consultas de alto uso se servirán mediante caché o índices para soportar alta concurrencia.
RNF-028	Validación de permisos antes de abrir sesión individual.	Se verificará que el usuario tiene permisos y que el proyecto está disponible antes de iniciar la carga de la sesión.
RNF-029	Recuperación ante fallo de carga del proyecto.	Si la carga de un proyecto falla, el sistema reintentará automáticamente y ofrecerá carga parcial desde caché si es posible.
RNF-030	Tiempo máximo aceptable para apertura de sesión individual.	La apertura de sesión debe completarse en un umbral razonable o proporcionar retroalimentación continua de progreso.
RNF-031	Sincronización inicial segura en sesión colaborativa.	Al unirse a una sesión colaborativa, se sincronizará el estado del grafo con verificación de integridad para asegurar consistencia.
RNF-032	Notificación y gestión de conflictos en tiempo real.	Si se produce un conflicto de edición, la plataforma notificará a los usuarios y ofrecerá herramientas de resolución.
RNF-033	Escalado de sesiones colaborativas con muchos usuarios.	La arquitectura debe soportar múltiples participantes simultáneos manteniendo latencias controladas.
RNF-034	Generación automática de solicitudes de autorización al guardar.	Al guardar cambios, el sistema generará automáticamente una solicitud de autorización al líder con un resumen claro.
RNF-035	Control de precondiciones para guardado individual.	Se verificará que el usuario esté en modo individual y posea permisos antes de permitir el guardado.
RNF-036	Respaldo temporal seguro ante fallo al guardar.	Si la base de datos no está disponible al guardar, los cambios se conservarán en almacenamiento cifrado y se sincronizarán al restablecer la conexión.
RNF-037	Consolidación de modificaciones en sesión colaborativa.	Al guardar, el sistema consolidará las modificaciones de múltiples usuarios en un resumen comprensible para la autorización.
RNF-038	Protección contra pérdida de datos por fallos de sincronización.	Se implementarán mecanismos de versionado y rollback para evitar pérdida de trabajo durante fallos en el proceso de guardado colaborativo.
RNF-039	Notificación de errores de autorización al guardar colaborativo.	Si falla la generación de una solicitud de autorización, todos los participantes serán notificados y se ofrecerá la opción de reintento manual.
RNF-040	Validación sintáctica de premisas globales.	Al editar premisas globales, se validará su sintaxis y consistencia lógica antes de aceptar cambios.
RNF-041	Historial de cambios en premisas globales.	Se mantendrá un historial completo de versiones de las premisas globales para auditoría y restauración.
RNF-042	Mensajes de ayuda y sugerencias para corrección de premisas.	Cuando se detecten premisas inválidas, el sistema ofrecerá mensajes detallados y sugerencias automáticas para la corrección.
RNF-043	Renderizado interactivo y accesible del grafo.	La visualización del grafo será interactiva y accesible, soportando navegación por teclado y compatibilidad con lectores de pantalla.
RNF-044	Fallback a vista simplificada del grafo.	Si el renderizado completo falla, se ofrecerá una vista simplificada o tabular de los nodos y relaciones.
RNF-045	Consistencia de datos grafo-DB al renderizar.	Se validará la integridad entre los datos mostrados en el grafo y la base de datos, indicando discrepancias.
RNF-046	Control granular de acciones sobre nodos.	El sistema verificará permisos específicos por tipo de acción sobre los nodos (editar, proponer, ejecutar).
RNF-047	Registro de cambios provisionales en nodos.	Los cambios provisionales se versionarán por separado y permanecerán invisibles hasta su autorización, permitiendo revertirlos.
RNF-048	Manejo de falta de recursos de agentes o cluster.	Si los asistentes de IA o el clúster no disponen de recursos, se notificará al usuario y se ofrecerán opciones como encolar la tarea o ajustarla.
RNF-049	Autorización automática para cambios de estado del nodo.	Si una acción implica un cambio de estado importante, se generará automáticamente una solicitud de autorización al líder.
RNF-050	Validaciones previas a solicitud a agente.	Antes de enviar una tarea a un agente, se realizarán verificaciones de formato, permisos y disponibilidad de recursos.
RNF-051	Transparencia y trazabilidad de acciones de agentes.	Se mantendrá un registro completo de las acciones de los asistentes de IA, incluyendo parámetros, entradas y resultados para auditoría.
RNF-052	Política de uso justo de recursos del cluster.	Se aplicarán límites de tiempo y consumo de recursos por solicitud para evitar abusos del clúster.
RNF-053	Confirmación de entrada de plan en NL (usuario).	Se validará la sintaxis del plan en NL y se proporcionará retroalimentación sobre errores detectados.
RNF-054	Revisión colaborativa antes de autorizar el plan de demostración.	La plataforma permitirá la previsualización y comentarios colaborativos de un plan antes de su autorización para mejorar su calidad.
RNF-055	Guardado temporal y versiones de planes de demostración.	Se mantendrán versiones temporales de un plan propuesto para facilitar comparaciones y restauración.
RNF-056	Control de cancelación y reintentos al solicitar plan a agente.	Los usuarios podrán cancelar solicitudes a un agente antes de su ejecución y el sistema permitirá reintentos automáticos si se produce un fallo.
RNF-057	Selección y fallback entre agentes.	El sistema seleccionará el agente óptimo y, si falla, ofrecerá fallback a otro agente o colocará la tarea en cola.
RNF-058	Evaluación de suficiencia del plan por LeanServer.	El plan generado por un agente se validará en un servidor de verificación (LeanServer) para comprobar su suficiencia antes de la autorización.
RNF-059	Validación de formato de datos experimentales numéricos.	Los datos numéricos cargados se validarán en estructura, tipos y unidades antes de usarlos en cálculos.
RNF-060	Retención segura de datos numéricos temporales.	Los datos experimentales temporales se guardarán de forma cifrada hasta que sean validados o procesados.
RNF-061	Indicadores de suficiencia estadística en el informe.	El informe de análisis de datos incluirá indicadores estadísticos (tamaño de muestra, etc.) que justifiquen su consideración como demostración.
RNF-062	Planificación y despacho de experimentos en clúster.	Las solicitudes de experimentos se planificarán y despacharán al clúster según disponibilidad y prioridad.
RNF-063	Manejo de falta de recursos en CoProof Cluster.	Cuando el clúster no disponga de recursos, se notificará a los usuarios y se propondrán ajustes de parámetros o reprogramación.
RNF-064	Validación de interpretación de resultados por NL2FL.	La interpretación automática de resultados por NL2FL irá acompañada de métricas de confianza que indiquen su fiabilidad.
RNF-065	Generación de ejemplos representativos en exploración lógica.	La exploración de casos pequeños generará ejemplos representativos y visualizaciones que faciliten la comprensión.
RNF-066	Trazabilidad de parámetros usados en exploraciones lógicas.	Se registrarán los parámetros y configuraciones de cada exploración para asegurar su reproducibilidad.
RNF-067	Reintentos y persistencia de solicitudes ante fallo del cluster.	Si el clúster falla, el sistema guardará la solicitud y la reintentará automáticamente.
RNF-068	Validación de parámetros de entrada en exploración numérica orientada.	Se verificará que los parámetros y objetivos definidos por el usuario sean válidos y coherentes antes de ejecutar la exploración.
RNF-069	Presentación de resultados numéricos con análisis visual.	Los resultados numéricos se presentarán con gráficos, tablas y anotaciones que resalten los hallazgos relevantes.
RNF-070	Control de calidad de resultados y criterios de consistencia.	Se aplicarán criterios mínimos de consistencia y completitud para garantizar la calidad de los resultados antes de presentarlos como válidos.
RNF-071	Flujo seguro para autorización de cambios en nodo.	El módulo de autorización presentará contexto completo, historial y diferencias para que el líder tome decisiones informadas.
RNF-072	Notificación y registro de decisiones de autorización.	Cada decisión de autorización (aprobar/rechazar) se registrará y notificará automáticamente al contribuyente.
RNF-073	Invalidación idempotente de sesión.	La operación de cierre de sesión será idempotente para que múltiples solicitudes no produzcan efectos secundarios.
RNF-074	Cierre de sesión offline con sincronización posterior.	El usuario podrá cerrar sesión sin conexión, y la invalidación se sincronizará con la base de datos al restablecerla.
RNF-075	Cambio de credenciales con autenticación reforzada.	Al modificar credenciales críticas, el sistema exigirá autenticación reforzada para validar la identidad.
RNF-076	Historial y notificación de modificaciones de cuenta.	Cada cambio en la configuración de cuenta se registrará y el sistema notificará al propietario sobre cambios sensibles.
RNF-077	Validación en tiempo real de parámetros de rendimiento y compatibilidad.	Al ajustar parámetros técnicos, el sistema validará en tiempo real su compatibilidad con el clúster y avisará sobre impactos esperados.
RNF-078	Perfiles de configuración y migración entre entornos.	La plataforma permitirá guardar, exportar e importar perfiles de configuración (tema, idioma, parámetros) para facilitar la migración entre dispositivos.

Con el panorama completo de los requerimientos funcionales y no funcionales establecido, el siguiente paso es sintetizar estas especificaciones en una arquitectura de alto nivel. Dicha arquitectura agrupará las capacidades del sistema en funciones lógicas y cohesivas, derivando directamente la estructura del software a partir de sus requisitos.

4.0 Arquitectura Funcional Derivada para CoProof

Esta sección final sintetiza toda la información anterior para proponer una arquitectura funcional de alto nivel para el sistema CoProof. Se describirán los módulos o funciones de software fundamentales que componen el sistema, justificando la existencia de cada uno al vincularlos directamente con los casos de uso y requerimientos específicos que deben satisfacer. Esta estructura modular asegura una separación de responsabilidades clara y facilita el desarrollo, la prueba y el mantenimiento del software.

4.1 Función: Gestión de Usuarios, Autenticación y Acceso

Este componente de software es el responsable de gestionar todo el ciclo de vida de las cuentas de usuario, la autenticación segura, el manejo de sesiones y la aplicación de un control de acceso basado en roles. Es la primera línea de defensa del sistema y garantiza que solo los usuarios autorizados puedan acceder a los recursos y funciones de la plataforma, protegiendo la integridad de los datos y la privacidad de los usuarios.

* Casos de Uso Soportados
  * CDU-05: Iniciar sesión.
  * CDU-06: Crear una cuenta.
  * CDU-25: Cerrar sesión.
  * CDU-26: Configurar cuenta de usuario.
* Requerimientos Clave Implementados
  * RF-015: Autenticar usuarios.
  * RF-016: Manejar sesiones de usuario.
  * RF-017: Crear cuenta de usuario.
  * RF-019: Verificar correo electrónico.
  * RF-063: Actualizar información personal del usuario.
  * RF-064: Cambiar contraseña de usuario.
  * RNF-013: Validación fuerte de credenciales en login.
  * RNF-016: Verificación de correo para registro seguro.
  * RNF-075: Cambio de credenciales con autenticación reforzada.

4.2 Función: Entorno de Trabajo, Proyectos y Colaboración

Este módulo constituye el núcleo del sistema, siendo responsable de la gestión del modelo de datos y el estado de los proyectos. Administra el ciclo de vida de las entidades principales: la creación y visibilidad de proyectos (públicos/privados), la inicialización de sesiones de trabajo (individuales/colaborativas) y la persistencia de los cambios. Una de sus responsabilidades clave es cargar la estructura de datos subyacente del grafo de un proyecto desde la base de datos. Además, implementa la lógica de negocio para el sistema de autorización, permitiendo al líder del proyecto revisar y consolidar las contribuciones de los colaboradores, garantizando así la integridad y coherencia del trabajo.

* Casos de Uso Soportados
  * CDU-07: Crear un proyecto privado.
  * CDU-08: Crear un proyecto público.
  * CDU-10: Abrir un proyecto en sesión individual.
  * CDU-11: Abrir un proyecto en sesión colaborativa.
  * CDU-12: Guardar cambios en una sesión individual.
  * CDU-13: Guardar cambios en una sesión colaborativa.
  * CDU-24: Autorizar cambios en un nodo.
* Requerimientos Clave Implementados
  * RF-020: Crear un proyecto.
  * RF-022: Asignar líder del proyecto.
  * RF-032: Abrir sesión colaborativa de trabajo.
  * RF-033: Sincronizar cambios en tiempos real.
  * RF-037: Guardar cambios en sesión colaborativa.
  * RF-041: Cargar el grafo de un proyecto.
  * RF-061: Revisar y autorizar o rechazar solicitud de cambios.
  * RNF-032: Notificación y gestión de conflictos en tiempo real.

4.3 Función: Procesamiento y Verificación de Demostraciones

Esta función encapsula las capacidades de ingesta y validación de conocimiento matemático externo. Es responsable de recibir demostraciones en diversos formatos (PDF, LaTeX, imagen), coordinar su traducción de lenguaje natural (NL) a lenguaje formal (FL) a través del módulo NL2FL, y finalmente, orquestar la verificación lógica de la prueba traducida utilizando el LeanServer. Su objetivo es automatizar el proceso de formalización y validación, reduciendo la carga de trabajo manual del usuario.

* Casos de Uso Soportados
  * CDU-01: Validar una demostración externa.
  * CDU-02: Traducir una demostración externa a Lean.
* Requerimientos Clave Implementados
  * RF-001: Recibir y validar una demostración de un archivo externo.
  * RF-002: Traducir una demostración externa a Lean.
  * RF-003: Validar demostración con Lean Server.
  * RNF-001: Validación de formato de entrada.
  * RNF-005: Indicaciones de ambigüedad en la traducción a Lean.

4.4 Función: Asistencia por Inteligencia Artificial (Agentes CoProof)

Este módulo representa la capa de inteligencia del sistema, gestionando la interacción con los diversos agentes de IA. Su propósito es asistir activamente al usuario en el proceso de demostración formal. Esto incluye la generación de demostraciones completas para nodos específicos, la proposición de planes de demostración (ramificación) para abordar problemas complejos, y la realización de exploraciones lógicas de casos pequeños para ayudar al usuario a ganar intuición sobre un teorema.

* Casos de Uso Soportados
  * CDU-17: Solicitar una demostración de un nodo a un Agente.
  * CDU-19: Solicitar un plan de demostración de un nodo a un Agente.
  * CDU-22: Solicitar una exploración lógica de casos pequeños de un nodo.
* Requerimientos Clave Implementados
  * RF-046: Aplicar solicitud de Agente para demostrar un nodo.
  * RF-050: Solicitar plan de demostración a un Agente.
  * RF-056: Solicitar generación de casos pequeños para exploración lógica.
  * RNF-051: Transparencia y trazabilidad de acciones de agentes.
  * RNF-057: Selección y fallback entre agentes.

4.5 Función: Cómputo Distribuido y Análisis Numérico (Clúster)

Esta función se encarga de orquestar y gestionar la ejecución de tareas computacionalmente intensivas en el clúster de cómputo. Actúa como intermediario entre las solicitudes del usuario y los recursos de hardware distribuidos. Sus responsabilidades clave incluyen el diseño y despliegue de experimentos para demostraciones numéricas y la ejecución de exploraciones numéricas orientadas a la búsqueda de contraejemplos o al análisis de comportamientos específicos, aprovechando el poder del cómputo paralelo.

* Casos de Uso Soportados
  * CDU-21: Solicitar una demostración numérica para un nodo.
  * CDU-23: Solicitar una exploración numérica orientada de un nodo.
* Requerimientos Clave Implementados
  * RF-054: Solicitar el diseño y despliegue de un experimento numérico.
  * RF-058: Solicitar exploración numérica orientada.
  * RNF-052: Política de uso justo de recursos del cluster.
  * RNF-062: Planificación y despacho de experimentos en clúster.
  * RNF-063: Manejo de falta de recursos en CoProof Cluster.

4.6 Función: Consulta, Visualización y Trazabilidad de Conocimiento

Este componente de software conforma la capa de presentación y exploración del conocimiento almacenado en CoProof. Su función principal es consumir los modelos de datos, como el grafo de proyecto cargado por la función 'Entorno de Trabajo', y renderizarlos en interfaces interactivas para el usuario. Es responsable de las herramientas de consulta que permiten buscar demostraciones y proyectos, así como de la visualización del linaje de teoremas. Implementa la lógica de interacción del usuario con el grafo, incluyendo zoom, selección de nodos y filtrado, haciendo que la base de conocimiento del sistema sea transparente, accesible y navegable.

* Casos de Uso Soportados
  * CDU-03: Consultar una demostración interna en NL o Lean.
  * CDU-04: Consultar el linaje de un teorema, corolario o lema.
  * CDU-09: Consultar proyectos públicos activos.
  * CDU-15: Visualizar grafo de proyecto.
* Requerimientos Clave Implementados
  * RF-007: Buscar demostraciones dentro del sistema.
  * RF-012: Buscar el linaje de un resultado.
  * RF-013: Visualizar gráficamente el linaje de demostraciones de un resultado.
  * RF-025: Consultar lista de proyectos públicos activos.
  * RF-042: Interactuar con nodos del grafo.
  * RF-043: Filtrar y resaltar elementos del grafo.
  * RNF-007: Búsqueda por metadatos optimizada.
  * RNF-010: Visualización del linaje escalable.
