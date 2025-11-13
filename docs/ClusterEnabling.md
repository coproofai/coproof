# Progreso de Instalación de OpenHPC en Clúster Raspberry Pi 4

## Contexto General

El proceso de instalación se está realizando en un clúster conformado por **cuatro Raspberry Pi 4**, siguiendo la guía oficial **OpenHPC v3.4 para Rocky Linux 9.3 (aarch64) con Warewulf y SLURM**, con adaptaciones necesarias debido al uso de una **imagen personalizada de Rocky Linux 9.1 para Raspberry Pi**, descargada del repositorio oficial.

Hasta el punto actual del procedimiento, se han completado las fases correspondientes a la instalación del sistema operativo base, la configuración del nodo maestro (SMS) y la instalación de los componentes fundamentales de OpenHPC.

---

## 1. Instalación del Sistema Operativo Base (BOS)

- Se instaló **Rocky Linux 9.1** en el nodo maestro (SMS) utilizando la imagen ARM personalizada.
- Se deshabilitó **SELinux** y el servicio **firewalld** para evitar conflictos con los servicios de aprovisionamiento (DHCP, TFTP, HTTP).
- Se garantizó la resolución local del nombre del host del SMS mediante la actualización de `/etc/hosts`.
- Se verificó la conectividad y funcionalidad de las dos interfaces de red del nodo maestro:
  - `eth0`: conexión a la red externa (LAN o Internet).
  - `eth1`: red interna dedicada al clúster y aprovisionamiento.

---

## 2. Habilitación del Repositorio OpenHPC

- Se instaló el paquete `ohpc-release` desde el repositorio oficial de OpenHPC para habilitar las fuentes de paquetes correspondientes a la arquitectura **aarch64**.
- Se habilitó el repositorio **CRB (CodeReady Builder)** y se verificó el acceso a **EPEL 9**.
- Los repositorios base configurados son:
  - `BaseOS`
  - `AppStream`
  - `Extras`
  - `CRB`
  - `EPEL`

---

## 3. Instalación de Componentes OpenHPC en el Nodo Maestro

### 3.1 Servicios de Aprovisionamiento

- Instalación de los paquetes principales:
  ```bash
  dnf -y install ohpc-base ohpc-warewulf hwloc-ohpc
  ```
- Configuración del servicio NTP con **Chrony**:
  - Se definió el nodo maestro como servidor de tiempo local para el clúster.
  - Se habilitó y reinició el servicio `chronyd`.

### 3.2 Servicios de Gestión de Recursos

- Instalación de los componentes del servidor **SLURM**:
  ```bash
  dnf -y install ohpc-slurm-server
  ```
- Configuración inicial de SLURM:
  - Copia del archivo de configuración por defecto.
  - Ajuste de `SlurmctldHost` con el nombre del nodo maestro.
  - Preparación de `cgroup.conf` y parámetros básicos para nodos de cómputo.

### 3.3 Configuración de Warewulf

- Se configuró Warewulf para usar la interfaz interna del SMS para aprovisionamiento.
- Se habilitaron los servicios necesarios:
  ```bash
  systemctl enable --now httpd dhcpd tftp.socket
  ```
- Se estableció la dirección IP interna y la máscara de red correspondientes.

---

## 4. Creación de la Imagen de los Nodos de Cómputo

### 4.1 Construcción del Entorno Base (Chroot)

- Se creó el directorio raíz de la imagen en:
  ```
  /opt/ohpc/admin/images/rocky9.3
  ```
- Se ejecutó `wwmkchroot` para generar un sistema base Rocky Linux dentro del chroot.
- Se habilitaron los repositorios de **OpenHPC** y **EPEL** dentro del entorno.

### 4.2 Instalación de Componentes para Nodos de Cómputo

- Instalación de paquetes base:
  ```bash
  dnf -y --installroot=$CHROOT install ohpc-base-compute
  ```
- Adición de cliente SLURM, soporte NTP y entorno Lmod:
  ```bash
  dnf -y --installroot=$CHROOT install ohpc-slurm-client chrony lmod-ohpc
  ```
- Habilitación de los servicios `munge` y `slurmd` en el entorno chroot.

### 4.3 Configuración del Sistema en la Imagen

- Se configuraron los montajes NFS para `/home` y `/opt/ohpc/pub`.
- Se exportaron estos directorios desde el SMS y se habilitó el servicio `nfs-server`.
- Se generaron las claves SSH y base de datos de Warewulf para el acceso y sincronización entre nodos.

---

## Estado Actual

El entorno del nodo maestro (SMS) está completamente configurado y operativo con los servicios de:
- **Warewulf** (aprovisionamiento),
- **SLURM** (gestión de recursos),
- **NFS** (almacenamiento compartido),
- **Chrony** (sincronización de tiempo).

Se ha construido la imagen base del sistema para los nodos de cómputo, incluyendo los componentes de OpenHPC y las configuraciones necesarias para el entorno de ejecución distribuido.

El siguiente paso es **ensamblar la imagen VNFS y bootstrap**, registrar los nodos de cómputo y proceder con su **aprovisionamiento e inicio por PXE**.

---

**Documento generado:** noviembre de 2025  
**Referencia técnica:** *OpenHPC Install Guide v3.4 – Rocky 9.3/aarch64 + Warewulf + SLURM*  
**Adaptación práctica:** instalación en clúster Raspberry Pi 4 (imagen Rocky 9.1 ARM64)
