import { Component } from '@angular/core';
import { NgClass, NgIf } from '@angular/common';

type GuideSection =
  'verificación' | 'traducción' | 'buscar-demostración' | 'buscar-linaje' | 'buscar-proyectos' |
  'crear-proyecto' |
  'ws-general' | 'ws-verificar' | 'ws-resolver' | 'ws-dividir' |
  'ws-computación' | 'ws-prs' | 'ws-exportar';

@Component({
  selector: 'app-guide-page',
  standalone: true,
  imports: [NgClass, NgIf],
  templateUrl: './guide-page.html',
  styleUrl: './guide-page.css',
})
export class GuidePageComponent {
  activeSection: GuideSection = 'verificación';
}
