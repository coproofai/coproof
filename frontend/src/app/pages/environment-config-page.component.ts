import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgIf } from '@angular/common';

@Component({
  selector: 'app-environment-config-page',
  standalone: true,
  imports: [FormsModule, NgIf],
  template: `
    <div class="wrap">
      <div class="card">
        <h3>Ajustes de Entorno y Servidor</h3>

        <div class="section">
          <h4>Modelos de Asistencia (AI)</h4>
          <label><input type="checkbox" [(ngModel)]="aiModel1" name="ai1" /> Formalizer Pro (Lógica)</label>
          <label><input type="checkbox" [(ngModel)]="aiModel2" name="ai2" /> Data-Viz Engine (Numérico)</label>
          <label><input type="checkbox" [(ngModel)]="aiModel3" name="ai3" /> Project Planner (Estratégico)</label>
        </div>

        <div class="section">
          <h4>Cluster de Cómputo</h4>
          <label>URL del Endpoint</label>
          <input [(ngModel)]="endpoint" name="endpoint" type="url" />
          <button class="secondary" (click)="testConnection()">Probar Conexión</button>
          <p *ngIf="connectionStatus" class="connection">{{ connectionStatus }}</p>
        </div>

        <button class="primary" (click)="save()">Guardar Configuración de Entorno</button>
        <p *ngIf="statusMessage" class="status">{{ statusMessage }}</p>
      </div>
    </div>
  `,
  styles: [`
    .wrap { min-height: calc(100vh - 120px); display: flex; align-items: center; justify-content: center; }
    .card {
      width: 100%;
      max-width: 560px;
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
      padding: 22px;
    }
    h3 { margin: 0 0 16px 0; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; color: #555; }
    .section { margin-bottom: 14px; border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; background: #f9fafb; }
    h4 { margin: 0 0 10px 0; color: #444; }
    label { display: block; margin-bottom: 8px; color: #555; font-weight: 600; }
    input[type='url'] { width: 100%; box-sizing: border-box; border: 1px solid #d1d5db; border-radius: 8px; padding: 10px; }
    .secondary {
      margin-top: 10px;
      width: 100%;
      border: 1px solid #9ca3af;
      border-radius: 8px;
      background: #fff;
      color: #374151;
      padding: 10px;
      font-weight: 700;
      cursor: pointer;
    }
    .primary {
      width: 100%;
      border: none;
      border-radius: 8px;
      background: #1f2937;
      color: #fff;
      padding: 10px;
      font-weight: 700;
      cursor: pointer;
    }
    .connection, .status {
      margin: 10px 0 0 0;
      border-radius: 8px;
      padding: 9px;
      font-size: 0.9rem;
      font-weight: 600;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      color: #1e3a8a;
    }
    .status { background: #ecfdf5; border-color: #bbf7d0; color: #166534; }
  `]
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
