import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-auth-page',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="auth-wrap">
      <div class="auth-card">
        <h2>Iniciar Sesión</h2>
        <form>
          <input type="text" placeholder="Correo Electrónico / Usuario" required />
          <input type="password" placeholder="Contraseña" required />
          <a class="primary-btn" routerLink="/menu">Entrar</a>
        </form>
        <a class="auth-link" href="javascript:void(0)">¿Olvidaste tu contraseña?</a>
        <a class="auth-link" href="javascript:void(0)">Crear Nueva Cuenta</a>
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
    input {
      padding: 10px;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      font-size: 0.95rem;
    }
    .primary-btn {
      margin-top: 6px;
      display: block;
      text-decoration: none;
      background: #333;
      color: #fff;
      padding: 12px;
      border-radius: 6px;
      font-weight: 700;
    }
    .primary-btn:hover { background: #555; }
    .auth-link {
      display: block;
      margin-top: 14px;
      color: #777;
      font-size: 0.9rem;
      text-decoration: none;
    }
    .auth-link:hover { text-decoration: underline; }
  `]
})
export class AuthPageComponent {}
