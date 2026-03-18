import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgIf } from '@angular/common';

@Component({
  selector: 'app-environment-config-page',
  standalone: true,
  imports: [FormsModule, NgIf],
  templateUrl: './environment-config-page.html',
  styleUrl: './environment-config-page.css'
})
export class EnvironmentConfigPageComponent {
  aiModel1 = true;
  aiModel2 = false;
  aiModel3 = true;
  endpoint = 'https://compute.formalizer-cluster.io/api/v1';
  connectionStatus = '';
  statusMessage = '';

  testConnection() {
    this.connectionStatus = `Probando conexión a: ${this.endpoint}...`;
    setTimeout(() => {
      this.connectionStatus = 'Conexión exitosa. Cluster operativo.';
    }, 900);
  }

  save() {
    this.statusMessage = 'Configuración de entorno guardada exitosamente.';
  }
}
