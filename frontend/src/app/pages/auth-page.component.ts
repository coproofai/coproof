import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { NgIf } from '@angular/common';
import { TaskService } from '../task.service';

@Component({
  selector: 'app-auth-page',
  standalone: true,
  imports: [RouterLink, FormsModule, NgIf],
  template: `
    <div class="auth-wrap">
      <div class="auth-card">
        <h2>Configurar Access Token</h2>
        <form (submit)="$event.preventDefault()">
          <textarea [(ngModel)]="accessToken" name="accessToken" rows="6" placeholder="Pega aquí el JWT access_token"></textarea>
          <button class="primary-btn" type="button" (click)="saveToken()">Guardar Token</button>
          <a class="secondary-btn" routerLink="/menu">Continuar al menú</a>
        </form>
        <p *ngIf="message" class="message">{{ message }}</p>
      </div>
    </div>
  `,
  styles: [`
    .auth-wrap {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #f7f7f7;
      padding: 24px;
    }
    .auth-card {
      width: 320px;
      background: #fff;
      border-radius: 10px;
      border: 1px solid #e5e7eb;
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
      padding: 28px;
      text-align: center;
    }
    h2 { margin: 0 0 20px 0; color: #444; }
    form { display: flex; flex-direction: column; gap: 12px; }
    textarea {
      padding: 10px;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      font-size: 0.95rem;
      resize: vertical;
      font-family: inherit;
    }
    .primary-btn {
      margin-top: 6px;
      display: block;
      background: #333;
      color: #fff;
      padding: 12px;
      border-radius: 6px;
      font-weight: 700;
      border: none;
      cursor: pointer;
    }
    .primary-btn:hover { background: #555; }
    .secondary-btn {
      display: block;
      margin-top: 4px;
      color: #444;
      font-size: 0.9rem;
      text-decoration: none;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      padding: 10px;
      font-weight: 600;
    }
    .message {
      margin: 12px 0 0 0;
      background: #ecfdf5;
      border: 1px solid #bbf7d0;
      color: #166534;
      border-radius: 8px;
      padding: 8px;
      font-weight: 600;
      font-size: 0.86rem;
    }
  `]
})
export class AuthPageComponent {
  accessToken = '';
  message = '';

  constructor(private readonly taskService: TaskService) {
    this.accessToken = this.taskService.getAccessToken();
  }

  saveToken() {
    if (!this.accessToken.trim()) {
      this.message = 'Debes ingresar un access token.';
      return;
    }
    this.taskService.setAccessToken(this.accessToken);
    this.message = 'Token guardado correctamente.';
  }
}
