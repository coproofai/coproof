# Reporte de Implementación Técnica - Backend CoProof

**Fecha:** 27 de Noviembre, 2025
**Estado:** Implementación de Arquitectura Completa (Fases 1-6 finalizadas)
**Versión:** 1.0 (Pre-Debugging)

## Resumen

Se ha completado la codificación de la arquitectura base del backend para el sistema CoProof. El sistema opera bajo un modelo híbrido innovador: utiliza **Git** como fuente única de verdad para el contenido matemático (archivos .lean) y **PostgreSQL** como un índice relacional de alta velocidad para metadatos y grafos. La aplicación es completamente "stateless" (sin estado), gestionando la concurrencia mediante bloqueos distribuidos en Redis y colas de tareas asíncronas para operaciones pesadas de IA y compilación.

***

## Detalle de Fases Implementadas

### Fase 1: Fundamentos e Infraestructura
Se estableció el esqueleto robusto de la aplicación para asegurar escalabilidad y testabilidad.

*   **Fábrica de Aplicaciones:** Implementación del patrón "Application Factory" en Flask para permitir múltiples instancias y configuraciones dinámicas.
*   **Gestión de Configuración:** Segregación de entornos (Desarrollo, Testing, Producción) mediante variables de entorno y clases de configuración.
*   **Extensiones:** Inicialización centralizada de plugins críticos: SQLAlchemy (Base de Datos), Celery (Tareas Asíncronas), Redis (Caché y Locks) y SocketIO (Tiempo Real).
*   **Manejo de Errores:** Sistema personalizado de excepciones para distinguir errores de negocio (ej. "Recurso Bloqueado") de errores de servidor.
*   **Dockerización:** Definición de contenedores para la aplicación web y los trabajadores (workers) asíncronos.

### Fase 2: Capa de Datos (Modelos Relacionales)
Se implementó el esquema de base de datos PostgreSQL diseñado para actuar como índice del sistema.

*   **Esquema Optimizado:** Uso de UUIDs para claves primarias y tipos JSONB para datos flexibles.
*   **Modelos Principales:**
    *   **Usuarios:** Gestión de identidad y seguridad.
    *   **Proyectos:** Metadatos y vinculación con repositorios remotos.
    *   **GraphIndex:** Índice que apunta a archivos y líneas específicas dentro de Git, sin duplicar el contenido de texto.
    *   **AsyncJobs:** Trazabilidad de tareas largas (IA, Compilación).
*   **Corrección de Tipos:** Ajuste de ENUMs de PostgreSQL para compatibilidad con el ciclo de vida de SQLAlchemy.

### Fase 3: Motor Git "Stateless" (Sin Estado)
El componente más crítico del sistema. Permite manipular repositorios Git en un servidor que no guarda estado persistente entre reinicios.

*   **Gestión de Repositorios (RepoPool):** Sistema de caché LRU (Least Recently Used) en el directorio temporal `/tmp` para mantener clones "bare" de los repositorios y evitar descargas redundantes.
*   **Transacciones Atómicas:** Implementación de un flujo de trabajo seguro: Clonar -> Crear "Worktree" efímero -> Resetear -> Escribir -> Commit -> Push -> Limpiar.
*   **Control de Concurrencia (Redlock):** Uso de bloqueos distribuidos en Redis para asegurar que dos usuarios no modifiquen el mismo proyecto simultáneamente, evitando corrupción de datos.

### Fase 4: Servicios de Dominio y Lógica de Negocio
Capa intermedia que orquesta la lógica entre la API y los datos.

*   **Servicios de Proyecto:** Lógica para crear proyectos y disparar la inicialización asíncrona de repositorios Git.
*   **Motor de Grafo (Graph Engine):**
    *   **Parser:** Módulo basado en expresiones regulares para leer archivos `.lean` y extraer definiciones de teoremas y dependencias.
    *   **Indexer:** Servicio que sincroniza el contenido parseado hacia la base de datos PostgreSQL, manteniendo el grafo actualizado.
*   **Integraciones:** Clientes HTTP para comunicarse con microservicios externos (Agente de IA, Clúster de Cómputo y Compilador Lean).
*   **Esquemas de Validación:** Uso de Marshmallow para validar entradas y salidas de datos, refactorizado en módulos independientes.

### Fase 5: Capa de API (Controladores)
Exposición de la funcionalidad del sistema mediante endpoints RESTful seguros.

*   **Módulos Implementados:**
    *   **Auth:** Registro e inicio de sesión con JWT.
    *   **Proyectos:** CRUD de proyectos y listados públicos con caché.
    *   **Nodos:** Endpoints para leer el grafo (desde DB) y escribir cambios (hacia Git).
    *   **Agente:** Endpoints para solicitar demostraciones automáticas a la IA ("Caja Negra").
    *   **Webhooks:** Endpoint seguro para recibir notificaciones de GitHub (Push events) y disparar la re-indexación automática.

### Fase 6: Tareas Asíncronas e Integraciones
Implementación de Celery para manejar procesos que exceden el tiempo de respuesta de una petición web.

*   **Tareas Git:** Clonado pesado, "Push" asíncrono y compilación completa del proyecto.
*   **Tareas de Agente:**
    *   **Traducción:** Conversión de Lenguaje Natural a Lean usando IA.
    *   **Exploración:** Generación de pasos de demostración.
*   **Sincronización RAG:** Pipeline ETL (Extract, Transform, Load) que toma los nodos indexados y los envía a la base de conocimiento vectorial del Agente.
*   **Verificación:** Tareas separadas para verificación de sintaxis (rápida) y verificación de "verdad matemática" (lenta/compilación).

***

## Resumen de Arquitectura Final

El sistema resultante es una plataforma **modular y escalable**.

1.  **Seguridad:** Autenticación JWT y roles definidos.
2.  **Rendimiento:** Las lecturas son rápidas (golpean PostgreSQL/Redis), mientras que las escrituras garantizan integridad (transacciones Git con Locks).
3.  **Colaboración:** Preparado para sincronización automática bidireccional con GitHub.
4.  **Inteligencia:** Desacopla la lógica de IA en tareas de fondo, permitiendo que la interfaz de usuario siga siendo responsiva mientras se procesan demostraciones complejas.

## Próximos Pasos

El siguiente paso inmediato es la **Depuración (Debugging)**, donde se ejecutarán pruebas integrales para validar la interacción entre estos componentes, asegurar que los bloqueos de Redis funcionan bajo carga y verificar la correcta sincronización entre los archivos Git y el índice SQL.