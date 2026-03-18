import { Component } from '@angular/core';
import { NgFor } from '@angular/common';
import { RouterLink } from '@angular/router';

interface MenuItem {
  title: string;
  route: string;
}

@Component({
  selector: 'app-menu-page',
  standalone: true,
  imports: [NgFor, RouterLink],
  templateUrl: './menu-page.html',
  styleUrl: './menu-page.css'
})
export class MenuPageComponent {
  menuItems: MenuItem[] = [
    { title: 'Validar Demostración', route: '/validation' },
    { title: 'Traducir a Lean', route: '/translation' },
    { title: 'Buscar Demostración', route: '/proof-search' },
    { title: 'Buscar Linaje', route: '/lineage-search' },
    { title: 'Crear Proyecto (Privado o Público)', route: '/create-project' },
    { title: 'Buscar Proyectos', route: '/project-search' },
    { title: 'Abrir Workspace', route: '/open-workspace' },
    { title: 'Debug Code Executors', route: '/debug-executors' }
  ];
}
