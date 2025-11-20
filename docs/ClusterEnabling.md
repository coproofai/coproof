Guía de Configuración de Cluster OpenHPC con Rocky Linux 10 en Raspberry Pi 4
Por David Alejandro López Torres


Esta documentación describe el proceso completo para configurar un cluster de computación de alto rendimiento utilizando OpenHPC sobre Rocky Linux 10, implementado en cuatro Raspberry Pi 4 Model B. El cluster está compuesto por un nodo de gestión (SMS - System Management Server) y tres nodos de cómputo.
Tabla de Contenidos
Variables de Configuración
Configuración Inicial del Servidor SMS
Configuración de Red
Configuración de NFS
Configuración de DNSMASQ y TFTP
Preparación del Sistema Base para Nodos de Cómputo
Instalación de OpenHPC
Configuración de SLURM
Configuración de los Nodos de Cómputo
Configuración de SSH
Instalación de OpenMPI
Prueba de Validación del Cluster
Variables de Configuración
Las siguientes variables definen la configuración de red y los parámetros del cluster:

Variable	Valor	Descripción
sms_name	sms	Nombre del servidor de gestión
sms_ip	192.168.1.1	Dirección IP del servidor SMS
sms_eth_internal	end0	Interfaz de red interna
internal_network	192.168.1.0	Red interna del cluster
internal_netmask	255.255.255.0	Máscara de subred
ntp_server	mx.pool.ntp.org	Servidor de sincronización de tiempo
num_computes	3	Número de nodos de cómputo
c_ips	192.168.1.11, 192.168.1.12, 192.168.1.13	IPs de los nodos
c_macs	dc:a6:32:21:55:72, dc:a6:32:20:44:6d, dc:a6:32:20:2f:a0	Direcciones MAC
c_names	node1, node2, node3	Nombres de los nodos
Configuración Inicial del Servidor SMS
1.1. Descarga e Instalación del Sistema Operativo
Esta sección describe la preparación inicial del servidor de gestión (SMS), que actuará como controlador principal del cluster.

Pasos previos:

Descargar la imagen de Rocky Linux 10 para Raspberry Pi desde: https://rockylinux.org/download?arch=aarch64
Descargar Balena Etcher desde: https://etcher.balena.io/#download-etcher
Flashear la imagen en la tarjeta SD del SMS
Credenciales por defecto:

Usuario: rocky
Contraseña: rockylinux
1.2. Configuración Básica del Sistema
Una vez iniciado el sistema, se procede a expandir el sistema de archivos, establecer el nombre del servidor y reiniciar.

# Expandir el sistema de archivos a toda la tarjeta SD
rootfs-expand

# Establecer el nombre del servidor
hostnamectl set-hostname sms

# Reiniciar el sistema
reboot
Configuración de Red
Esta sección configura la interfaz de red que conectará el servidor SMS con los nodos de cómputo, estableciendo una red privada para el cluster.

# Crear conexión de red para la LAN del cluster
nmcli con add type ethernet con-name "Cluster-LAN" ifname end0 ip4 192.168.1.1/24

# Configurar la conexión como manual y automática al inicio
nmcli con mod "Cluster-LAN" ipv4.method manual connection.autoconnect yes

# Activar la conexión
nmcli con up "Cluster-LAN"
Configuración de NFS
NFS (Network File System) permite compartir sistemas de archivos entre el servidor SMS y los nodos de cómputo, facilitando el arranque por red y el acceso compartido a datos.

4.1. Instalación y Configuración de NFS
# Instalar utilidades NFS
dnf install nfs-utils -y

# Crear directorio para compartir vía NFS
mkdir -p /srv/nfs/rpi4

# Deshabilitar SELinux temporalmente
setenforce 0

# Deshabilitar SELinux permanentemente
sed -i 's/^SELINUX=.*/SELINUX=disabled/g' /etc/selinux/config

# Detener y deshabilitar el firewall
systemctl stop firewalld
systemctl disable firewalld

# Reiniciar el sistema
reboot

# Habilitar e iniciar el servidor NFS
systemctl enable --now nfs-server

# Reiniciar el servidor NFS
systemctl restart nfs-server

# Exportar los directorios compartidos
exportfs -arv
4.2. Prueba de Funcionamiento de NFS
Estos comandos verifican que NFS está funcionando correctamente antes de continuar con la configuración.

# Crear directorio de prueba
mkdir /mnt/test_nfs

# Montar el recurso NFS localmente
mount -t nfs 192.168.1.1:/srv/nfs/rpi4 /mnt/test_nfs

# Crear archivo de prueba
touch /mnt/test_nfs/hello_cluster

# Verificar que el archivo existe en el directorio original
ls -l /srv/nfs/rpi4/hello_cluster

# Desmontar el recurso NFS
umount /mnt/test_nfs

# Limpiar directorios y archivos de prueba
rm /mnt/test_nfs -rf
rm /srv/nfs/rpi4/hello_cluster
Configuración de DNSMASQ y TFTP
DNSMASQ proporciona servicios de DHCP y DNS para el cluster, mientras que TFTP permite el arranque por red de los nodos de cómputo.

5.1. Instalación de DNSMASQ y TFTP
# Instalar DNSMASQ y servidor TFTP
dnf install dnsmasq tftp -y
5.2. Configuración de DNSMASQ
Editar el archivo /etc/dnsmasq.conf con el siguiente contenido:

vi /etc/dnsmasq.conf
# --- Interface Settings ---
# Solo escuchar en la interfaz LAN del cluster
interface=end0
bind-interfaces

# --- DHCP Settings ---
# Rango: 192.168.1.50 a .150, Tiempo de lease: 12 horas
dhcp-range=192.168.1.50,192.168.1.150,12h

# Establecer la puerta de enlace predeterminada (Opción 3) al servidor SMS
dhcp-option=3,192.168.1.1

# Establecer el servidor DNS (Opción 6) al servidor SMS
dhcp-option=6,192.168.1.1

# Forzar la IP del servidor TFTP (Opción 66)
dhcp-option=66,"192.168.1.1"

# Raspberry Pi Magic (Opción 43)
# Esto envía la etiqueta "Vendor Encapsulated" verificando que es un servidor de arranque Pi
pxe-service=0,"Raspberry Pi Boot"

# --- DNS Settings ---
# DNS upstream (Google)
server=8.8.8.8
server=8.8.4.4
domain-needed
bogus-priv

# --- TFTP Settings ---
enable-tftp
tftp-root=/srv/tftp

# Habilitar registro detallado para DHCP y TFTP (útil para depuración)
log-dhcp
dhcp-boot=start4.elf

# --- Node 1 ---
dhcp-host=dc:a6:32:21:55:72,192.168.1.11,node1
dhcp-mac=set:node1,dc:a6:32:21:55:72

# --- Node 2 ---
dhcp-host=dc:a6:32:20:44:6d,192.168.1.12,node2
dhcp-mac=set:node2,dc:a6:32:20:44:6d

# --- Node 3 ---
dhcp-host=dc:a6:32:20:2f:a0,192.168.1.13,node3
dhcp-mac=set:node3,dc:a6:32:20:2f:a0

# Configurar rutas NFS específicas por nodo
dhcp-option=tag:node1,option:root-path,"192.168.1.1:/srv/nfs/node1,rw"
dhcp-option=tag:node2,option:root-path,"192.168.1.1:/srv/nfs/node2,rw"
dhcp-option=tag:node3,option:root-path,"192.168.1.1:/srv/nfs/node3,rw"
5.3. Iniciar DNSMASQ
# Habilitar e iniciar el servicio DNSMASQ
systemctl enable --now dnsmasq
5.4. Prueba de Funcionamiento de DNSMASQ y TFTP
Estos comandos verifican que los servicios DHCP y TFTP están operativos.

# Verificar que DNSMASQ está escuchando en los puertos UDP
ss -ulpn | grep dnsmasq

# Crear archivo de prueba para TFTP
echo "Hello PXE" > /srv/tftp/test.txt

# Descargar archivo vía TFTP
tftp 192.168.1.1 -c get test.txt

# Verificar que el archivo se descargó correctamente
ls -l test.txt
cat test.txt

# Revisar los logs de DNSMASQ
journalctl -u dnsmasq | tail -n 10
Preparación del Sistema Base para Nodos de Cómputo
Esta sección prepara una imagen base del sistema operativo que será compartida con los nodos de cómputo mediante NFS, permitiendo el arranque por red.

6.1. Descarga y Extracción de la Imagen
# Instalar herramientas necesarias
dnf install kpartx rsync -y

# Descargar la imagen de Rocky Linux 10 para Raspberry Pi
wget -c --show-progress https://dl.rockylinux.org/pub/rocky/10/images/aarch64/Rocky-10-SBC-RaspberryPi.latest.aarch64.raw.xz

# Descomprimir la imagen
unxz Rocky-10-SBC-RaspberryPi.latest.aarch64.raw.xz

# Mapear las particiones de la imagen
kpartx -av Rocky-10-SBC-RaspberryPi.latest.aarch64.raw

# Crear directorios temporales para montar las particiones
mkdir /mnt/tmp_boot /mnt/tmp_root

# Montar la partición de arranque
mount /dev/mapper/loop0p1 /mnt/tmp_boot

# Montar la partición raíz
mount /dev/mapper/loop0p3 /mnt/tmp_root
6.2. Copia de Archivos a Directorios de Red
# Copiar archivos de arranque a TFTP
cp -r /mnt/tmp_boot/* /srv/tftp/

# Sincronizar el sistema raíz a NFS
rsync -xa --progress /mnt/tmp_root/ /srv/nfs/rpi4/

# Desmontar las particiones
umount /mnt/tmp_boot
umount /mnt/tmp_root

# Eliminar el mapeo de particiones
kpartx -d rocky.img

# Limpiar directorios temporales
rmdir /mnt/tmp_boot /mnt/tmp_root
6.3. Configuración de Arranque por Red
Editar el archivo /srv/nfs/rpi4/etc/fstab para comentar todas las líneas (el sistema arrancará desde NFS):

vi /srv/nfs/rpi4/etc/fstab
Contenido (todas las líneas comentadas):

# Todas las líneas originales deben estar comentadas con #
Editar el archivo /srv/tftp/cmdline.txt con los parámetros de arranque:

vi /srv/tftp/cmdline.txt
Contenido:

console=serial0,115200 console=tty1 root=dhcp rootwait elevation=0 selinux=0 cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1 swapaccount=1
6.4. Creación del Sistema de Archivos Inicial (initramfs)
El initramfs es necesario para que los nodos puedan arrancar desde NFS.

# Montar sistemas de archivos virtuales en el entorno chroot
mount --bind /proc /srv/nfs/rpi4/proc
mount --bind /sys /srv/nfs/rpi4/sys
mount --bind /dev /srv/nfs/rpi4/dev
mount --bind /run /srv/nfs/rpi4/run

# Instalar herramientas necesarias en el sistema raíz
dnf --installroot=/srv/nfs/rpi4 install dracut-network nfs-utils -y

# Generar initramfs con soporte NFS
dracut --add nfs --force /boot/initramfs-6.6.77-8.el10.altarch.aarch64+16k.img 6.6.77-8.el10.altarch.aarch64+16k

# Salir del entorno chroot
exit

# Desmontar sistemas de archivos virtuales
umount /srv/nfs/rpi4/proc /srv/nfs/rpi4/sys /srv/nfs/rpi4/dev /srv/nfs/rpi4/run

# Copiar initramfs a TFTP
cp /srv/nfs/rpi4/boot/initramfs-6.6.77-8.el10.altarch.aarch64+16k.img /srv/tftp/initramfs8

# Establecer permisos correctos
chmod 644 /srv/tftp/initramfs8
6.5. Configuración de Red para Nodos de Cómputo
Configurar NetworkManager para que los nodos obtengan su nombre de host vía DHCP:

chroot /srv/nfs/rpi4
vi /etc/NetworkManager/system-connections/end0.nmconnection
Contenido:

[connection]
id=end0
type=ethernet
interface-name=end0

[ipv4]
method=auto
dhcp-hostname-option=true

[ipv6]
addr-gen-mode=default
method=auto
# Limpiar el archivo hostname (se asignará vía DHCP)
echo "" > /etc/hostname

# Salir del entorno chroot
exit
Instalación de OpenHPC
OpenHPC proporciona un conjunto de herramientas y bibliotecas optimizadas para computación de alto rendimiento.

7.1. Instalación en el Servidor SMS
# Habilitar el repositorio CodeReady Builder
dnf config-manager --set-enabled crb

# Instalar repositorio EPEL
dnf install epel-release -y

# Habilitar CodeReady Builder vía comando crb
/usr/bin/crb enable

# Instalar el repositorio OpenHPC
dnf -y install http://repos.openhpc.community/OpenHPC/4/EL_10/aarch64/ohpc-release-4-1.el10.aarch64.rpm

# Instalar paquetes base de OpenHPC
dnf -y install ohpc-base yq

# Instalar MUNGE (autenticación) y SLURM (gestor de trabajos)
dnf install munge ohpc-slurm-server -y
7.2. Instalación en los Nodos de Cómputo
# Instalar utilidades DNF en el sistema raíz compartido
dnf -y --installroot=/srv/nfs/rpi4 install dnf-utils

# Instalar repositorio EPEL
dnf --installroot=/srv/nfs/rpi4 install epel-release -y

# Habilitar CodeReady Builder
dnf --installroot=/srv/nfs/rpi4 config-manager --set-enabled crb

# Instalar el repositorio OpenHPC
dnf -y --installroot=/srv/nfs/rpi4 install http://repos.openhpc.community/OpenHPC/4/EL_10/aarch64/ohpc-release-4-1.el10.aarch64.rpm

# Instalar paquetes base para nodos de cómputo
dnf -y --installroot=/srv/nfs/rpi4 install ohpc-base-compute

# Instalar MUNGE y cliente SLURM
dnf -y --installroot=/srv/nfs/rpi4 install munge ohpc-slurm-client
7.3. Configuración de MUNGE
MUNGE proporciona autenticación entre los nodos del cluster.

# Generar clave de autenticación MUNGE
dd if=/dev/urandom bs=1 count=1024 > /etc/munge/munge.key

# Establecer permisos correctos
chown munge: /etc/munge/munge.key

# Copiar la clave a los nodos de cómputo
cp /etc/munge/munge.key /srv/nfs/rpi4/etc/munge/munge.key

# Establecer permisos en el sistema de archivos compartido
chroot /srv/nfs/rpi4 chown munge:munge /etc/munge/munge.key
chroot /srv/nfs/rpi4 chmod 400 /etc/munge/munge.key

# Habilitar e iniciar el servicio MUNGE
systemctl enable --now munge
Configuración de SLURM
SLURM (Simple Linux Utility for Resource Management) es el gestor de colas y recursos del cluster.

8.1. Configuración Principal de SLURM
Editar el archivo /etc/slurm/slurm.conf:

vi /etc/slurm/slurm.conf
Contenido:

ClusterName=rocky-pi
SlurmctldHost=sms
# Configurar la IP del SMS explícitamente
SlurmctldAddr=192.168.1.1

# User/Auth
AuthType=auth/munge
CredType=cred/munge
SlurmUser=slurm

# Timers
SlurmdTimeout=300
SlurmctldTimeout=300

# Logging
SlurmctldLogFile=/var/log/slurmctld.log
SlurmdLogFile=/var/log/slurmd.log

StateSaveLocation=/var/spool/slurm

# COMPUTE NODES
# Definir los nodos. Sockets=1 CoresPerSocket=4 ThreadsPerCore=1 es estándar para Pi 4
NodeName=node[1-3] NodeAddr=192.168.1.[11-13] Sockets=1 CoresPerSocket=4 ThreadsPerCore=1 State=UNKNOWN

# PARTITIONS
PartitionName=debug Nodes=node[1-3] Default=YES MaxTime=INFINITE State=UP

# Process Tracking
ProctrackType=proctrack/cgroup

# Task Launching (Affinity permite fijación de CPU, Cgroup permite contención de recursos)
TaskPlugin=task/affinity,task/cgroup
8.2. Configuración de Cgroups para SLURM
Editar el archivo /etc/slurm/cgroup.conf:

vi /etc/slurm/cgroup.conf
Contenido:

###
#
# Archivo de configuración de soporte cgroup para Slurm
#
# Ver man slurm.conf y man cgroup.conf para más
# información sobre parámetros de configuración de cgroup
#--
ConstrainCores=yes
ConstrainDevices=yes
ConstrainRAMSpace=yes
ConstrainSwapSpace=no
8.3. Preparación de Directorios y Permisos
# Crear archivo de log del controlador SLURM
touch /var/log/slurmctld.log
chown slurm:slurm /var/log/slurmctld.log
chmod 644 /var/log/slurmctld.log

# Crear directorio de ejecución
mkdir -p /var/run/slurm
chown slurm:slurm /var/run/slurm

# Crear directorio de estado
mkdir -p /var/spool/slurm
chown slurm:slurm /var/spool/slurm
chmod 755 /var/spool/slurm

# Reiniciar el controlador SLURM
systemctl restart slurmctld
Configuración de los Nodos de Cómputo
9.1. Habilitación del Arranque PXE en las Raspberry Pi
En cada Raspberry Pi que actuará como nodo de cómputo, se debe configurar el arranque por red:

# Editar la configuración de EEPROM
sudo -E rpi-eeprom-config --edit
Agregar la siguiente línea:

BOOT_ORDER=0x21
# Reiniciar para aplicar los cambios
sudo reboot
9.2. Creación de Sistemas de Archivos Individuales por Nodo
# Sincronizar el sistema base a cada nodo
rsync -xa /srv/nfs/rpi4/ /srv/nfs/node1
rsync -xa /srv/nfs/rpi4/ /srv/nfs/node2
rsync -xa /srv/nfs/rpi4/ /srv/nfs/node3

# Establecer el hostname de cada nodo
echo "node1" > /srv/nfs/node1/etc/hostname
echo "node2" > /srv/nfs/node2/etc/hostname
echo "node3" > /srv/nfs/node3/etc/hostname

# Exportar los nuevos directorios NFS
exportfs -arv

# Agregar la entrada del SMS al archivo hosts de cada nodo
echo "192.168.1.1 sms" >> /srv/nfs/node1/etc/hosts
echo "192.168.1.1 sms" >> /srv/nfs/node2/etc/hosts
echo "192.168.1.1 sms" >> /srv/nfs/node3/etc/hosts

# Copiar la configuración de cgroups de SLURM a cada nodo
cp /etc/slurm/cgroup.conf /srv/nfs/node1/etc/slurm/
cp /etc/slurm/cgroup.conf /srv/nfs/node2/etc/slurm/
cp /etc/slurm/cgroup.conf /srv/nfs/node3/etc/slurm/
Configuración de SSH
Esta sección configura el acceso SSH sin contraseña desde el servidor SMS a los nodos de cómputo.

10.1. Configuración de SSH en los Nodos
# Habilitar el login root y autenticación por contraseña en todos los nodos
for dir in node1 node2 node3; do
    CONFIG_FILE="/srv/nfs/$dir/etc/ssh/sshd_config"
    sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' $CONFIG_FILE
    sed -i 's/^PermitRootLogin.*/PermitRootLogin yes/' $CONFIG_FILE
    sed -i 's/^#PasswordAuthentication.*/PasswordAuthentication yes/' $CONFIG_FILE
    echo "Updated SSH config for $dir"
done
10.2. Generación e Inyección de Claves SSH
# Generar par de claves SSH
ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""

# Capturar la clave pública
PUBKEY=$(cat /root/.ssh/id_ed25519.pub)

# Inyectar la clave pública en cada nodo
for dir in node1 node2 node3; do
    mkdir -p /srv/nfs/$dir/root/.ssh
    chmod 700 /srv/nfs/$dir/root/.ssh
    echo "$PUBKEY" >> /srv/nfs/$dir/root/.ssh/authorized_keys
    chmod 600 /srv/nfs/$dir/root/.ssh/authorized_keys
    echo "Injected SSH key for $dir"
done
10.3. Deshabilitar Firewall en los Nodos
# Detener y deshabilitar firewalld en todos los nodos
for ip in 192.168.1.11 192.168.1.12 192.168.1.13; do
    echo "Stopping firewall on $ip..."
    ssh root@$ip "systemctl stop firewalld; systemctl disable firewalld"
done
10.4. Prueba del Cluster con SLURM
# Ejecutar un comando simple en todos los nodos para verificar conectividad
srun -N3 -l hostname
Instalación de OpenMPI
OpenMPI es una implementación de la interfaz de paso de mensajes (MPI) para programación paralela.

11.1. Instalación en el Servidor SMS
# Instalar OpenMPI, herramientas de desarrollo y compilador
dnf install openmpi openmpi-devel gcc -y
11.2. Instalación en los Nodos de Cómputo
# Instalar OpenMPI en cada nodo
for dir in node1 node2 node3; do
    echo "Installing OpenMPI on $dir..."
    dnf --installroot=/srv/nfs/$dir install openmpi -y
done
11.3. Configuración de Bibliotecas Compartidas
# Configurar las rutas de bibliotecas de OpenMPI
for dir in node1 node2 node3; do
    echo "/usr/lib64/openmpi/lib" > /srv/nfs/$dir/etc/ld.so.conf.d/openmpi.conf
    chroot /srv/nfs/$dir ldconfig
done
Prueba de Validación del Cluster
Esta sección implementa y ejecuta un programa MPI que calcula el valor de Pi mediante el método de Monte Carlo, verificando el funcionamiento completo del cluster.

12.1. Creación del Programa de Prueba
Crear el archivo pi_mpi.c:

vi pi_mpi.c
Contenido:

#include <mpi.h>
#include <stdio.h>
#include <math.h>

int main(int argc, char* argv[]) {
    int niter = 1000000000; // 1 mil millones de pasos
    double x, y;
    int i;
    double count = 0.0;
    double z;
    double pi;
    int rank, size;
    double start_time, end_time;

    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    // Sincronizar todos los nodos antes de iniciar el temporizador
    MPI_Barrier(MPI_COMM_WORLD);
    start_time = MPI_Wtime();

    // Calcular el ancho de cada rectángulo
    z = 1.0 / (double)niter;

    for (i = rank; i < niter; i += size) {
        x = ((double)i + 0.5) * z;
        y = 4.0 / (1.0 + x * x);
        count += y;
    }

    // Sumar todos los conteos parciales en 'pi' en el Rank 0
    MPI_Reduce(&count, &pi, 1, MPI_DOUBLE, MPI_SUM, 0, MPI_COMM_WORLD);

    // Detener temporizador
    end_time = MPI_Wtime();

    // Solo el Rank 0 imprime el resultado
    if (rank == 0) {
        pi *= z;
        printf("Calculated Pi: %.16f\n", pi);
        printf("Real Pi      : 3.1415926535897932\n");
        printf("Nodes: %d | Tasks: %d | Time: %.4f seconds\n", 
               (size+3)/4, size, end_time - start_time);
    }

    MPI_Finalize();
    return 0;
}
12.2. Compilación del Programa
# Compilar el programa con el compilador MPI
/usr/lib64/openmpi/bin/mpicc pi_mpi.c -o pi_mpi -lm
12.3. Ejecución de Pruebas
# Prueba con un solo nodo y una tarea
srun --mpi=pmi2 -N1 -n1 /root/pi_mpi

# Prueba con los tres nodos y 12 tareas (4 por nodo)
srun --mpi=pmi2 -N3 -n12 /root/pi_mpi
Conclusión
Esta guía ha documentado el proceso completo de configuración de un cluster de computación de alto rendimiento utilizando OpenHPC sobre Rocky Linux 10, implementado en hardware Raspberry Pi 4. El cluster resultante es capaz de ejecutar aplicaciones paralelas mediante MPI y gestionar cargas de trabajo a través del sistema de colas SLURM.

Componentes Instalados
Sistema Operativo: Rocky Linux 10 (aarch64)
Gestor de Recursos: SLURM
Autenticación: MUNGE
Sistema de Archivos Compartido: NFS
Arranque por Red: TFTP/DNSMASQ
Computación Paralela: OpenMPI
Framework HPC: OpenHPC 4
Arquitectura del Cluster
1 Servidor SMS: 192.168.1.1 (Gestión y Control)
3 Nodos de Cómputo: 192.168.1.11-13 (Ejecución de Trabajos)
Total de Núcleos: 16 (4 núcleos × 4 nodos)
El cluster está ahora operativo y listo para ejecutar cargas de trabajo de computación paralela.
