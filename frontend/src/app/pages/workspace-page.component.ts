import {
  AfterViewInit,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  NgZone,
  OnDestroy,
  ViewChild
} from '@angular/core';
import { NgClass, NgFor, NgIf } from '@angular/common';
import { ActivatedRoute } from '@angular/router';

interface Goal {
  id: string;
  name: string;
}

interface NodeItem {
  id: string;
  name: string;
  type: string;
  status: 'proven' | 'in-progress' | 'unproven';
  parent: string | null;
}

interface SimNode extends NodeItem {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface GraphLink {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

@Component({
  selector: 'app-workspace-page',
  standalone: true,
  imports: [NgFor, NgIf, NgClass],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="top-header">
      <div>
        <h1>Proyecto: {{ projectName }}</h1>
        <small>{{ sessionLabel }}</small>
      </div>
      <div class="header-right">
        <button (click)="status = 'Cambios guardados (simulado).'">Guardar Cambios (Commit)</button>
        <div class="badges">
          <span>User_Current</span>
          <span>AdaLovelace</span>
        </div>
      </div>
    </header>

    <div class="workspace-grid">
      <aside class="panel goals-panel">
        <h2>Metas del Proyecto</h2>
        <ul>
          <li *ngFor="let goal of goals" [class.selected]="goal.id === selectedGoalId" (click)="selectGoal(goal.id)">
            {{ goal.name }}
          </li>
        </ul>
      </aside>

      <main class="panel graph-panel">
        <h2>Grafo de Dependencias</h2>
        <div class="graph-canvas">
          <svg
            #graphSvg
            class="graph-lines"
            viewBox="0 0 980 520"
            preserveAspectRatio="xMidYMid meet"
            (wheel)="onWheel($event)"
            (pointerdown)="onBackgroundPointerDown($event)"
          >
            <g [attr.transform]="transform">
              <line
                *ngFor="let edge of currentEdges"
                class="graph-link"
                [attr.x1]="edge.x1"
                [attr.y1]="edge.y1"
                [attr.x2]="edge.x2"
                [attr.y2]="edge.y2"
              ></line>

              <g
                *ngFor="let node of simNodes"
                class="graph-node"
                [class.selected]="selectedNode?.id === node.id"
                [ngClass]="node.status"
                (pointerdown)="onNodePointerDown($event, node.id)"
                (click)="selectNode(node)"
              >
                <circle [attr.cx]="node.x" [attr.cy]="node.y" r="30"></circle>
                <text [attr.x]="node.x" [attr.y]="node.y + 52">{{ node.name }}</text>
              </g>
            </g>
          </svg>
        </div>
      </main>

      <aside class="panel details" *ngIf="selectedNode">
        <h2>Detalles del Nodo</h2>
        <p class="name">{{ selectedNode.name }}</p>
        <p class="meta">Tipo: {{ selectedNode.type }}</p>
        <p class="meta">Estado: {{ selectedNode.status }}</p>
        <h3>Acciones Disponibles</h3>
        <div class="actions">
          <button *ngFor="let action of actions" (click)="status = 'Acción ejecutada: ' + action + ' (simulado).'">
            {{ action }}
          </button>
        </div>
      </aside>
    </div>

    <p *ngIf="status" class="status">{{ status }}</p>
  `,
  styles: [`
    .top-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 12px;
      gap: 10px;
      flex-wrap: wrap;
    }
    h1 { margin: 0; font-size: 1.2rem; }
    .header-right { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
    .header-right button {
      border: none;
      border-radius: 8px;
      background: #111827;
      color: #fff;
      font-weight: 700;
      padding: 9px 12px;
      cursor: pointer;
    }
    .badges span {
      background: #e5e7eb;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 0.8rem;
      margin-right: 6px;
      font-weight: 600;
    }
    .workspace-grid {
      display: grid;
      grid-template-columns: 260px 1fr 320px;
      gap: 12px;
      min-height: 65vh;
    }
    .panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; }
    h2 { margin: 0 0 10px 0; color: #555; font-size: 1rem; }
    ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
    li {
      border-radius: 8px;
      padding: 8px;
      cursor: pointer;
      border: 1px solid transparent;
    }
    li:hover { background: #f3f4f6; }
    li.selected { background: #e5e7eb; border-color: #cbd5e1; font-weight: 700; }
    .graph-canvas {
      position: relative;
      min-height: 520px;
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      overflow: hidden;
    }
    .graph-lines {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      touch-action: none;
      cursor: grab;
    }
    .graph-lines:active { cursor: grabbing; }
    .graph-link {
      stroke: #9ca3af;
      stroke-width: 2;
      opacity: 0.9;
    }
    .graph-node { cursor: pointer; }
    .graph-node circle {
      stroke: #555;
      stroke-width: 2;
      fill: #eee;
    }
    .graph-node.proven circle { fill: #dcfce7; }
    .graph-node.in-progress circle { fill: #fef9c3; }
    .graph-node.unproven circle { fill: #fee2e2; }
    .graph-node.selected circle { stroke: #111827; stroke-width: 3; }
    .graph-node text {
      font-size: 11px;
      text-anchor: middle;
      font-weight: 600;
      fill: #333;
      user-select: none;
      pointer-events: none;
    }
    .name { margin: 0 0 8px 0; font-size: 1.05rem; font-weight: 700; }
    .meta { margin: 0 0 6px 0; color: #555; }
    h3 { margin: 10px 0 8px 0; }
    .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
    .actions button {
      border: 1px solid #d1d5db;
      border-radius: 8px;
      padding: 8px;
      background: #fff;
      font-size: 0.84rem;
      cursor: pointer;
    }
    .status {
      margin-top: 10px;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      border-radius: 8px;
      padding: 10px;
      color: #1e3a8a;
      font-weight: 600;
    }
    @media (max-width: 1180px) {
      .workspace-grid { grid-template-columns: 1fr; }
    }
  `]
})
export class WorkspacePageComponent implements AfterViewInit, OnDestroy {
  @ViewChild('graphSvg', { static: true }) graphSvg!: ElementRef<SVGSVGElement>;

  status = '';
  selectedGoalId = 'g1';
  projectName = 'Cálculo de Límites';
  sessionLabel = 'Sesión Individual';

  zoom = 1;
  offsetX = 0;
  offsetY = 0;

  private rafId: number | null = null;
  private lastRenderTs = 0;
  private readonly targetFrameMs = 1000 / 30;
  private draggingNodeId: string | null = null;
  private dragPointerId: number | null = null;
  private panning = false;
  private panPointerId: number | null = null;
  private panStartX = 0;
  private panStartY = 0;
  private panOriginX = 0;
  private panOriginY = 0;

  readonly goals: Goal[] = [
    { id: 'g1', name: 'Teorema Fundamental del Cálculo (Parte I)' },
    { id: 'g2', name: 'Límite de una Sucesión Convergente' },
    { id: 'g3', name: 'Propiedades de Números Reales' }
  ];

  readonly nodesByGoal: Record<string, NodeItem[]> = {
    g1: [
      { id: 'n1', name: 'Demostrar TFC (Parte I)', type: 'Teorema', status: 'unproven', parent: null },
      { id: 'n2', name: 'Función Acotada', type: 'Lema', status: 'proven', parent: 'n1' },
      { id: 'n3', name: 'Continuidad de Integral', type: 'Corolario', status: 'in-progress', parent: 'n1' },
      { id: 'n4', name: 'Axioma Delta-Épsilon', type: 'Axioma', status: 'proven', parent: 'n3' },
      { id: 'n5', name: 'Lema Sumas de Riemann', type: 'Lema', status: 'unproven', parent: 'n3' }
    ],
    g2: [
      { id: 'n6', name: 'Definición de Límite Épsilon', type: 'Axioma', status: 'proven', parent: null },
      { id: 'n7', name: 'Unicidad del Límite', type: 'Teorema', status: 'unproven', parent: 'n6' }
    ],
    g3: [{ id: 'n8', name: 'Orden Total de R', type: 'Axioma', status: 'proven', parent: null }]
  };

  readonly actions = [
    'Cargar Demostración',
    'Solicitar Demostración (AI)',
    'Cargar Plan',
    'Solicitar Plan (AI)',
    'Cargar Datos',
    'Solicitar Datos (AI)'
  ];

  simNodes: SimNode[] = [];
  selectedNode: SimNode | null = null;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly cdr: ChangeDetectorRef,
    private readonly zone: NgZone
  ) {
    this.route.queryParamMap.subscribe((params) => {
      const name = params.get('projectName');
      const sessionType = params.get('sessionType');

      if (name) {
        this.projectName = name;
      }

      this.sessionLabel = sessionType === 'collaborative' ? 'Sesión Colaborativa' : 'Sesión Individual';
      this.cdr.markForCheck();
    });
  }

  get transform(): string {
    return `translate(${this.offsetX} ${this.offsetY}) scale(${this.zoom})`;
  }

  get currentEdges(): GraphLink[] {
    const byId = new Map(this.simNodes.map((node) => [node.id, node]));
    return this.simNodes
      .filter((node) => node.parent)
      .map((node) => {
        const parent = byId.get(node.parent as string);
        if (!parent) {
          return null;
        }
        return {
          x1: parent.x,
          y1: parent.y,
          x2: node.x,
          y2: node.y
        };
      })
      .filter((edge): edge is GraphLink => edge != null);
  }

  ngAfterViewInit() {
    this.seedNodes();
    this.zone.runOutsideAngular(() => {
      window.addEventListener('pointermove', this.onPointerMove);
      window.addEventListener('pointerup', this.onPointerUp);
      this.startSimulation();
    });
  }

  ngOnDestroy() {
    if (this.rafId != null) {
      cancelAnimationFrame(this.rafId);
    }
    window.removeEventListener('pointermove', this.onPointerMove);
    window.removeEventListener('pointerup', this.onPointerUp);
  }

  selectGoal(goalId: string) {
    this.selectedGoalId = goalId;
    this.seedNodes();
    this.cdr.markForCheck();
  }

  selectNode(node: SimNode) {
    this.selectedNode = node;
    this.cdr.markForCheck();
  }

  onWheel(event: WheelEvent) {
    event.preventDefault();
    const point = this.pointerToGraph(event.clientX, event.clientY);
    const delta = event.deltaY < 0 ? 1.12 : 0.88;
    this.zoom = Math.max(0.45, Math.min(2.8, this.zoom * delta));
    this.offsetX = point.screenX - point.graphX * this.zoom;
    this.offsetY = point.screenY - point.graphY * this.zoom;
  }

  onBackgroundPointerDown(event: PointerEvent) {
    if (event.button !== 0) {
      return;
    }
    this.panning = true;
    this.panPointerId = event.pointerId;
    this.panStartX = event.clientX;
    this.panStartY = event.clientY;
    this.panOriginX = this.offsetX;
    this.panOriginY = this.offsetY;
  }

  onNodePointerDown(event: PointerEvent, nodeId: string) {
    event.stopPropagation();
    this.draggingNodeId = nodeId;
    this.dragPointerId = event.pointerId;
  }

  private onPointerMove = (event: PointerEvent) => {
    if (this.dragPointerId === event.pointerId && this.draggingNodeId != null) {
      const point = this.pointerToGraph(event.clientX, event.clientY);
      const node = this.simNodes.find((item) => item.id === this.draggingNodeId);
      if (!node) {
        return;
      }

      node.x = point.graphX;
      node.y = point.graphY;
      node.vx = 0;
      node.vy = 0;
      return;
    }

    if (this.panning && this.panPointerId === event.pointerId) {
      this.offsetX = this.panOriginX + (event.clientX - this.panStartX);
      this.offsetY = this.panOriginY + (event.clientY - this.panStartY);
    }
  };

  private onPointerUp = (event: PointerEvent) => {
    if (this.dragPointerId === event.pointerId) {
      this.dragPointerId = null;
      this.draggingNodeId = null;
    }

    if (this.panPointerId === event.pointerId) {
      this.panPointerId = null;
      this.panning = false;
    }
  };

  private seedNodes() {
    const sourceNodes = this.nodesByGoal[this.selectedGoalId] ?? [];
    const levelById = new Map<string, number>();

    const resolveLevel = (node: NodeItem): number => {
      const cached = levelById.get(node.id);
      if (cached != null) {
        return cached;
      }
      if (!node.parent) {
        levelById.set(node.id, 0);
        return 0;
      }
      const parent = sourceNodes.find((item) => item.id === node.parent);
      const level = parent ? resolveLevel(parent) + 1 : 0;
      levelById.set(node.id, level);
      return level;
    };

    sourceNodes.forEach((node) => resolveLevel(node));

    const levels = new Map<number, NodeItem[]>();
    sourceNodes.forEach((node) => {
      const level = levelById.get(node.id) ?? 0;
      const bucket = levels.get(level) ?? [];
      bucket.push(node);
      levels.set(level, bucket);
    });

    const maxLevel = Math.max(...Array.from(levels.keys()), 0);

    this.simNodes = sourceNodes.map((node) => {
      const level = levelById.get(node.id) ?? 0;
      const bucket = levels.get(level) ?? [];
      const index = bucket.findIndex((item) => item.id === node.id);
      const xStep = 860 / (bucket.length + 1);
      const yStep = maxLevel === 0 ? 0 : 360 / maxLevel;

      return {
        ...node,
        x: 60 + xStep * (index + 1),
        y: 80 + yStep * level,
        vx: 0,
        vy: 0
      };
    });

    this.selectedNode = this.simNodes[0] ?? null;
    this.zoom = 1;
    this.offsetX = 0;
    this.offsetY = 0;
    this.cdr.markForCheck();
  }

  private pointerToGraph(clientX: number, clientY: number) {
    const rect = this.graphSvg.nativeElement.getBoundingClientRect();
    const screenX = ((clientX - rect.left) / rect.width) * 980;
    const screenY = ((clientY - rect.top) / rect.height) * 520;

    return {
      screenX,
      screenY,
      graphX: (screenX - this.offsetX) / this.zoom,
      graphY: (screenY - this.offsetY) / this.zoom
    };
  }

  private startSimulation() {
    const tick = (timestamp: number) => {
      this.simulateStep();

      if (timestamp - this.lastRenderTs >= this.targetFrameMs) {
        this.lastRenderTs = timestamp;
        this.zone.run(() => this.cdr.detectChanges());
      }

      this.rafId = requestAnimationFrame(tick);
    };
    this.rafId = requestAnimationFrame(tick);
  }

  private simulateStep() {
    if (this.simNodes.length === 0) {
      return;
    }

    const byId = new Map(this.simNodes.map((node) => [node.id, node]));

    for (let i = 0; i < this.simNodes.length; i++) {
      for (let j = i + 1; j < this.simNodes.length; j++) {
        const a = this.simNodes[i];
        const b = this.simNodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distSq = dx * dx + dy * dy + 0.01;
        const force = 1450 / distSq;
        const dist = Math.sqrt(distSq);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        a.vx -= fx;
        a.vy -= fy;
        b.vx += fx;
        b.vy += fy;
      }
    }

    const springLength = 160;
    const springK = 0.012;
    for (const node of this.simNodes) {
      if (!node.parent) {
        continue;
      }
      const parent = byId.get(node.parent);
      if (!parent) {
        continue;
      }

      const dx = node.x - parent.x;
      const dy = node.y - parent.y;
      const distance = Math.sqrt(dx * dx + dy * dy) || 1;
      const stretch = distance - springLength;
      const force = stretch * springK;
      const fx = (dx / distance) * force;
      const fy = (dy / distance) * force;

      parent.vx += fx;
      parent.vy += fy;
      node.vx -= fx;
      node.vy -= fy;
    }

    const centerX = 490;
    const centerY = 260;
    for (const node of this.simNodes) {
      if (this.draggingNodeId === node.id) {
        continue;
      }

      node.vx += (centerX - node.x) * 0.0007;
      node.vy += (centerY - node.y) * 0.0007;

      node.vx *= 0.92;
      node.vy *= 0.92;

      node.x += node.vx;
      node.y += node.vy;

      node.x = Math.max(50, Math.min(930, node.x));
      node.y = Math.max(50, Math.min(470, node.y));
    }
  }
}
