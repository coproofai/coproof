import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { NgIf } from '@angular/common';
import { TaskService } from '../../task.service';

@Component({
  selector: 'app-auth-page',
  standalone: true,
  imports: [RouterLink, FormsModule, NgIf],
  templateUrl: './auth-page.html',
  styleUrl: './auth-page.css'
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

    const tokenType = this.taskService.getTokenType(this.accessToken.trim());
    if (tokenType === 'refresh') {
      this.message = 'Pegaste un refresh token. Debes pegar el access_token.';
      return;
    }

    this.taskService.setAccessToken(this.accessToken);
    this.message = 'Token guardado correctamente.';
  }
}
