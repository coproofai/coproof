import { Component } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../auth.service';
import { Observable } from 'rxjs';
import { AsyncPipe } from '@angular/common';

interface MenuItem {
  title: string;
  description: string;
  route: string;
  protected?: boolean;
}

@Component({
  selector: 'app-menu-page',
  standalone: true,
  imports: [NgFor, NgIf, AsyncPipe, RouterLink],
  templateUrl: './menu-page.html',
  styleUrl: './menu-page.css'
})
export class MenuPageComponent {
  isLoggedIn$: Observable<boolean>;

  constructor(private readonly auth: AuthService) {
    this.isLoggedIn$ = this.auth.isLoggedIn$;
  }

  publicItems: MenuItem[] = [
    { title: 'Validar Demostración',  description: 'Verifica la corrección de una demostración en Lean 4.',         route: '/validation' },
    { title: 'Traducir a Lean',       description: 'Convierte lenguaje natural matemático a código Lean 4.',          route: '/translation', protected: true },
    { title: 'Buscar Demostración',   description: 'Explora demostraciones formales registradas en la plataforma.',   route: '/proof-search' },
    { title: 'Buscar Linaje',         description: 'Rastrea el árbol de dependencias de un teorema o proyecto.',       route: '/lineage-search' },
    { title: 'Buscar Proyectos',      description: 'Navega proyectos públicos disponibles en la plataforma.',         route: '/project-search' },
  ];

  workspaceItems: MenuItem[] = [
    { title: 'Crear Proyecto',        description: 'Inicia un nuevo proyecto de demostración formal en tu cuenta.',   route: '/create-project',  protected: true },
    { title: 'Abrir Workspace',       description: 'Accede al editor interactivo de grafos y nodos de un proyecto.',  route: '/open-workspace',  protected: true },
    { title: 'Cuenta',                description: 'Configura tu perfil y credenciales de acceso.',                   route: '/account-config',  protected: true },
  ];
}
