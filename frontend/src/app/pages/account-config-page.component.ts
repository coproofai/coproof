import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgIf } from '@angular/common';

@Component({
  selector: 'app-account-config-page',
  standalone: true,
  imports: [FormsModule, NgIf],
  template: `
    <div class="wrap">
      <div class="card">
        <h3>Ajustes de Cuenta</h3>

        <div class="field">
          <label>Nombre de Usuario</label>
          <input [(ngModel)]="username" name="username" />
        </div>

        <div class="field">
          <label>Contraseña (Cambiar)</label>
          <input type="password" [(ngModel)]="password" name="password" placeholder="Dejar vacío para no cambiar" />
        </div>

        <div class="field">
          <label>Idioma de la Interfaz</label>
          <select [(ngModel)]="language" name="language">
            <option value="es">Español</option>
            <option value="en">Inglés</option>
            <option value="pt">Portugués</option>
          </select>
        </div>

        <div class="field">
          <label>Tema</label>
          <select [(ngModel)]="theme" name="theme">
            <option value="light">Claro</option>
            <option value="dark">Oscuro</option>
            <option value="system">Sistema</option>
          </select>
        </div>

        <button (click)="save()">Guardar Cambios</button>

        <p *ngIf="message" class="message" [class.error]="error">{{ message }}</p>
      </div>
    </div>
  `,
  styles: [`
    .wrap { min-height: calc(100vh - 120px); display: flex; align-items: center; justify-content: center; }
    .card {
      width: 100%;
      max-width: 520px;
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 22px;
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
    }
    h3 { margin: 0 0 16px 0; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; color: #555; }
    .field { margin-bottom: 12px; display: flex; flex-direction: column; gap: 7px; }
    label { color: #555; font-weight: 700; font-size: 0.9rem; }
    input, select { border: 1px solid #d1d5db; border-radius: 8px; padding: 10px; font-size: 0.95rem; }
    button {
      width: 100%;
      border: none;
      background: #1f2937;
      color: #fff;
      border-radius: 8px;
      padding: 10px;
      font-weight: 700;
      cursor: pointer;
      margin-top: 8px;
    }
    .message {
      margin: 12px 0 0 0;
      border: 1px solid #bbf7d0;
      border-radius: 8px;
      background: #ecfdf5;
      color: #166534;
      padding: 10px;
      font-size: 0.9rem;
      font-weight: 600;
    }
    .message.error { border-color: #fecaca; background: #fef2f2; color: #991b1b; }
  `]
})
export class AccountConfigPageComponent {
  username = 'Usuario_Demo';
  password = '';
  language: 'es' | 'en' | 'pt' = 'es';
  theme: 'light' | 'dark' | 'system' = 'light';
  message = '';
  error = false;

  save() {
    if (this.username.trim().length < 3) {
      this.error = true;
      this.message = 'El nombre de usuario debe tener al menos 3 caracteres.';
      return;
    }

    this.error = false;
    this.message = `Configuración guardada para ${this.username}.`;
    this.password = '';
  }
}
