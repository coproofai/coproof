# 🧰 Entorno de Desarrollo Dev-Env

Este contenedor provee un entorno completo de desarrollo con **Jenkins**, **Node.js**, **Angular CLI**, **Lean4**, **Python**, y herramientas esenciales de compilación sobre **Debian Bookworm Slim**.

Incluye:
- Jenkins preinstalado con plugins.
- Usuario administrador configurado automáticamente.
- Supervisor para ejecutar Jenkins como servicio al iniciar el contenedor.
- Entorno de desarrollo con Node.js 20, Angular CLI, Lean4 y Python 3.

---

## 📁 Estructura del Proyecto

```
.
├── Dockerfile
├── plugins.txt
└── supervisord.conf
```

- **Dockerfile** → Construye la imagen base con todas las dependencias.
- **plugins.txt** → Lista de plugins de Jenkins que se instalarán automáticamente.
- **supervisord.conf** → Configura `supervisord` para mantener Jenkins ejecutándose.

---

## ⚙️ Dependencias Incluidas

| Herramienta | Versión | Descripción |
|--------------|----------|-------------|
| Debian | bookworm-slim | Imagen base ligera |
| Java | OpenJDK 17 | Requerido por Jenkins |
| Node.js | 20.x | Plataforma JS moderna |
| Angular CLI | Última estable | CLI para desarrollo frontend |
| Python | 3.x | Utilidades y scripts |
| Lean4 | stable | Formal proof assistant |
| Jenkins | latest | Servidor de automatización |
| Supervisor | latest | Administrador de procesos |

---

## 🧩 Plugins de Jenkins

Los plugins definidos en `plugins.txt` se instalan automáticamente durante el build usando `jenkins-plugin-cli`.

Ejemplo de `plugins.txt`:
```
git
workflow-aggregator
pipeline-github-lib
blueocean
credentials
docker-workflow
job-dsl
matrix-auth
email-ext
github
github-branch-source
pipeline-stage-view
pipeline-model-definition
ssh-agent
timestamper
antisamy-markup-formatter
```

---

## 👤 Usuario Jenkins Predeterminado

Durante la construcción se crea automáticamente un usuario administrador:

| Usuario | Contraseña |
|----------|-------------|
| `admin` | `admin` |

Esto se realiza mediante un script Groovy en `init.groovy.d/basic-security.groovy`.

---

## 🚀 Construcción de la Imagen

Ejecuta en la raíz del proyecto:

```bash
docker build -t dev-env:latest .
```

---

## ▶️ Ejecución del Contenedor

Para iniciar Jenkins y acceder al panel web:

```bash
docker run -it -p 8080:8080 -p 50000:50000 dev-env:latest
```

Luego abre en tu navegador:

👉 [http://localhost:8080](http://localhost:8080)

Si el puerto 8080 está ocupado, puedes usar otro:

```bash
docker run -it -p 8090:8080 -p 50000:50000 dev-env:latest
```

Accede entonces en:

👉 [http://localhost:8090](http://localhost:8090)

---

## 🧱 Persistencia de Datos (opcional)

Si deseas mantener los datos de Jenkins entre reinicios, monta un volumen:

```bash
docker run -it   -p 8080:8080 -p 50000:50000   -v jenkins_home:/var/jenkins_home   dev-env:latest
```

Esto guardará configuraciones, jobs y plugins en el volumen `jenkins_home`.

---

## 🧩 Archivo `supervisord.conf`

El contenedor usa **Supervisor** para ejecutar Jenkins automáticamente:

```ini
[supervisord]
nodaemon=true
logfile=/var/log/supervisor/supervisord.log

[program:jenkins]
command=java -jar /opt/jenkins/jenkins.war --httpPort=8080
directory=/var/jenkins_home
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/jenkins.err.log
stdout_logfile=/var/log/supervisor/jenkins.out.log
user=root
```

---

## 🧩 Notas Adicionales

- Los plugins se instalan usando la versión más reciente de **Jenkins Plugin Installation Manager** desde GitHub.
- El contenedor expone los puertos **8080 (HTTP)** y **50000 (Agente remoto)**.
- El directorio de trabajo por defecto es `/workspace`.
- Puedes usar este entorno tanto para **CI/CD con Jenkins** como para **desarrollo de frontend y backend**.

---

## 🧾 Licencia

Este entorno está basado en software open-source y puede adaptarse libremente para propósitos personales o profesionales.

---
