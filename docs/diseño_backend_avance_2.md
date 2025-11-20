# Reporte de Implementación Técnica: Backend y Persistencia de Datos - CoProof

**Avance 2**
**Proyecto:** CoProof - Entorno Colaborativo para Demostración Formal  
**Fecha:** 20 de Noviembre, 2024    
**Estado:** Diseño de Arquitectura y Prototipado Inicial Completado


Se detalla el diseño, la estructura de la base de datos y la arquitectura de software implementada para el backend de la plataforma CoProof. Se ha completado el diseño del esquema relacional optimizado para PostgreSQL y la estructura base de una aplicación Flask modular, escalable y orientada a microservicios, cumpliendo con los requisitos funcionales y no funcionales definidos anteriormente.

---

## 2. Diseño de Base de Datos (PostgreSQL)

Se ha diseñado e implementado un esquema relacional robusto (`coproof_schema`) que prioriza la integridad de los datos, la seguridad y el rendimiento para operaciones de lectura intensiva y colaboración.

### 2.1. Características del Diseño
*   **Aislamiento de Esquema:** Se utiliza un esquema dedicado (`coproof_schema`) para separar lógicamente las tablas de la aplicación de las del sistema.
*   **Identificadores Universales (UUID):** Todas las tablas utilizan claves primarias `UUID` (v4) en lugar de enteros secuenciales. Esto mejora la seguridad (no son predecibles) y facilita una futura migración a sistemas distribuidos o *sharding*.
*   **Datos Semi-estructurados (JSONB):** Se utiliza el tipo de dato binario JSONB de PostgreSQL para campos flexibles como `config_agentes_ia` y `datos_numericos`. Esto permite indexar propiedades internas del JSON sin la rigidez de una tabla relacional pura.
*   **Campos Autocalculados:** Implementación de **Triggers** (`trigger_set_timestamp`) a nivel de base de datos para actualizar automáticamente el campo `updated_at` en cada modificación, garantizando auditoría precisa.

### 2.2. Entidades Principales
*   **Usuarios:** Gestión de identidad, hash de contraseñas (SCRAM-SHA-256 implícito/Bcrypt en app) y perfiles.
*   **Proyectos:** Entidad central que agrupa colaboradores y configuraciones.
*   **NodosGrafo y Dependencias:** Estructura recursiva para modelar el linaje de teoremas. Se separan los nodos (entidades) de sus aristas (dependencias) para consultas de grafo eficientes.
*   **TrabajosAsincronos:** Tabla de gestión de estado para tareas de larga duración (IA, Clúster), desacoplando la respuesta HTTP del procesamiento pesado.

---

## 3. Arquitectura de Software (Flask Backend)

La aplicación backend se ha construido utilizando **Flask**, siguiendo el patrón de **Fábrica de Aplicaciones (Application Factory)** y una arquitectura en capas.

### 3.1. Estructura del Proyecto
El código se ha organizado modularmente para facilitar el mantenimiento y las pruebas:

```text
coproof_backend/
├── app/
│   ├── __init__.py          # Fábrica de la aplicación (inicialización)
│   ├── extensions.py        # Instancias de plugins (DB, JWT, Celery, Cache)
│   ├── models/              # Modelos ORM (SQLAlchemy) mapeados al schema
│   ├── api/                 # Blueprints (Rutas/Endpoints)
│   ├── services/            # Capa de Lógica de Negocio
│   └── tasks.py             # Definición de tareas asíncronas (Celery)
├── config.py                # Configuraciones separadas por entorno
└── wsgi.py                  # Punto de entrada para servidor de producción
```

### 3.2. Patrones y Componentes Implementados

#### A. Modularización con Blueprints (`app/api/`)
La aplicación no es monolítica en su enrutamiento. Se divide en módulos lógicos:
*   `auth_bp`: Rutas de registro, login y recuperación de cuenta.
*   `projects_bp`: Gestión de proyectos, grafo y colaboración.
*   `proofs_bp`: Manejo de archivos externos y validaciones.

#### B. Capa de Servicios (`app/services/`)
Se implementó una capa intermedia entre las rutas y la base de datos.
*   *Propósito:* Las rutas solo manejan la petición HTTP (parsear JSON, códigos de estado). La lógica "dura" (validaciones de negocio, cálculos, orquestación) reside en los servicios. Esto permite reutilizar lógica y facilita los tests unitarios.

#### C. Procesamiento Asíncrono (Celery + Redis)
Para cumplir con los requisitos de interacción con IA y Clúster de Cómputo (tareas que tardan >500ms), se integró **Celery**.
*   **Funcionamiento:** Los endpoints HTTP encolan una tarea y devuelven inmediatamente un `jobId` (HTTP 202 Accepted).
*   **Redis:** Actúa como *Message Broker* para la cola de tareas y como backend de resultados.

#### D. Caché (Flask-Caching)
Se configuró caché en memoria (vía Redis) para endpoints de alto tráfico y baja volatilidad, específicamente para el listado de "Proyectos Públicos", optimizando el tiempo de respuesta.

---

## 4. Endpoints y Capacidades

Se definieron los endpoints RESTful siguiendo las especificaciones de los Casos de Uso (CDU).

| Módulo | Endpoints Clave | Funcionalidad / CDU Asociado |
| :--- | :--- | :--- |
| **Auth** | `/auth/register`, `/auth/login` | Autenticación JWT, creación de cuentas seguras. |
| **Proyectos** | `POST /projects`, `GET /projects/public` | CRUD de proyectos y listado público optimizado con caché. |
| **Grafo** | `GET /projects/{id}/graph` | Recuperación de la estructura de nodos y aristas. |
| **IA/Agentes** | `POST .../agent/generate-proof` | Trigger asíncrono para solicitar demostraciones a la IA. |
| **Archivos** | `POST /proofs/upload-external` | Carga y validación de archivos PDF/LaTeX. |

---

## 5. Stack Tecnológico y Herramientas

Lista de tecnologías seleccionadas e instaladas (`requirements.txt`) para soportar la arquitectura:

*   **Core:** `Python 3.10+`, `Flask 3.0`.
*   **Base de Datos:** `PostgreSQL` (Motor), `SQLAlchemy` (ORM), `Flask-Migrate` (Control de versiones de DB), `psycopg2-binary` (Driver).
*   **Seguridad:** `Flask-JWT-Extended` (Manejo de Tokens), `Werkzeug` (Hashing de contraseñas).
*   **Rendimiento y Async:** `Celery` (Cola de tareas), `Redis` (Broker y Caché), `Gunicorn` + `Gevent` (Servidor WSGI de producción para concurrencia).
*   **Calidad de Código:** `Black` (Formateo), `Pytest` (Pruebas).

---

## 6. Próximos Pasos

1.  **Despliegue de Infraestructura:** Provisionar la base de datos PostgreSQL y la instancia de Redis en el entorno de desarrollo.
2.  **Ejecución de Migraciones:** Ejecutar `flask db upgrade` para materializar el esquema diseñado en la base de datos.
3.  **Integración con Angular:** Configurar `Flask-Cors` con los dominios del cliente Angular y comenzar la integración de los endpoints de autenticación.
4.  **Implementación de WebSockets:** Desarrollar el módulo de sockets (no cubierto en la estructura REST base) para la colaboración en tiempo real (`CDU-11`).