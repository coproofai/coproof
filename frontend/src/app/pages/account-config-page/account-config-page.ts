import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgIf } from '@angular/common';

@Component({
  selector: 'app-account-config-page',
  standalone: true,
  imports: [FormsModule, NgIf],
  templateUrl: './account-config-page.html',
  styleUrl: './account-config-page.css'
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
