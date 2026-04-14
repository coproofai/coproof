import { Component, OnInit } from '@angular/core';
import { NgIf } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../auth.service';

@Component({
  selector: 'app-auth-page',
  standalone: true,
  imports: [NgIf],
  templateUrl: './auth-page.html',
  styleUrl: './auth-page.css'
})
export class AuthPageComponent implements OnInit {
  loading = false;
  error = '';

  constructor(
    private readonly auth: AuthService,
    private readonly route: ActivatedRoute,
    private readonly router: Router
  ) {}

  async ngOnInit(): Promise<void> {
    if (this.auth.isLoggedIn()) {
      this.router.navigate(['/menu']);
      return;
    }

    const code = this.route.snapshot.queryParamMap.get('code');
    if (code) {
      this.loading = true;
      try {
        await this.auth.handleOAuthCallback(code);
        this.router.navigate(['/menu']);
      } catch (e: any) {
        this.error = e?.error?.message || e?.message || 'Error al iniciar sesión con GitHub.';
        this.loading = false;
      }
    }
  }

  async loginWithGitHub(): Promise<void> {
    this.loading = true;
    this.error = '';
    try {
      await this.auth.initiateGitHubLogin();
    } catch (e: any) {
      this.error = e?.error?.message || e?.message || 'No se pudo conectar con el servidor.';
      this.loading = false;
    }
  }
}
