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
import { FormsModule } from '@angular/forms';
import { NgFor, NgIf } from '@angular/common';

interface LineageNode {
  id: number;
  name: string;
  type: string;
  desc: string;
  lean: string;
}

interface LineageLink {
  source: number;
  target: number;
}

interface SimNode extends LineageNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

@Component({
  selector: 'app-lineage-search-page',
  standalone: true,
  imports: [FormsModule, NgFor, NgIf],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="max-wrap">
      <h1>Búsqueda de Linaje y Dependencias de Teoremas</h1>

      <div class="controls">
        <input [(ngModel)]="searchInput" placeholder="Buscar Teorema, Lema o Resultado inicial..." />
        <label>Ancestros <input type="number" [(ngModel)]="depthUp" min="0" max="5" /></label>
        <label>Descendencia <input type="number" [(ngModel)]="depthDown" min="0" max="5" /></label>
        <button (click)="search()">Actualizar</button>
      </div>

      <div class="layout">
        <section>
          <h2>Grafo de Linaje de Dependencias</h2>
          <div class="graph-placeholder">
            <svg
              #graphSvg
              class="graph-svg"
              viewBox="0 0 980 500"
              preserveAspectRatio="xMidYMid meet"
              (wheel)="onWheel($event)"
              (pointerdown)="onBackgroundPointerDown($event)"
            >
              <g [attr.transform]="transform">
                <line
                  *ngFor="let link of renderedLinks"
                  class="graph-link"
                  [attr.x1]="link.x1"
                  [attr.y1]="link.y1"
                  [attr.x2]="link.x2"
                  [attr.y2]="link.y2"
                ></line>

                <g
                  *ngFor="let node of visibleNodes"
                  class="graph-node"
                  [class.selected]="selected?.id === node.id"
                  (pointerdown)="onNodePointerDown($event, node.id)"
                  (click)="select(node)"
                >
                  <circle [attr.cx]="node.x" [attr.cy]="node.y" r="27"></circle>
                  <text [attr.x]="node.x" [attr.y]="node.y + 50">{{ node.name }}</text>
                </g>
              </g>
            </svg>
          </div>
        </section>

        <section class="detail-box">
          <h2>Detalle del Nodo Seleccionado</h2>
          <p *ngIf="!selected" class="empty">Selecciona un nodo para ver su descripción.</p>

          <div *ngIf="selected">
            <h3>{{ selected.name }}</h3>
            <p class="type">{{ selected.type }}</p>
            <div class="toggles">
              <label><input type="checkbox" [(ngModel)]="showNatural" /> Lenguaje Natural</label>
              <label><input type="checkbox" [(ngModel)]="showLean" /> Formalismo Lean</label>
            </div>

            <div *ngIf="showNatural" class="content-block">
              <h4>Definición (Natural)</h4>
              <p>{{ selected.desc }}</p>
            </div>

            <div *ngIf="showLean" class="content-block">
              <h4>Código Lean</h4>
              <pre>{{ selected.lean }}</pre>
            </div>
          </div>
        </section>
      </div>
    </div>
  `,
  styles: [`
    .max-wrap { max-width: 1320px; margin: 0 auto; }
    h1 { margin: 0 0 16px 0; }
    .controls {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 14px;
    }
    .controls input[type='text'] {
      flex: 1;
      min-width: 260px;
      padding: 10px;
      border: 2px solid #ccc;
      border-radius: 8px;
    }
    .controls label { display: flex; align-items: center; gap: 6px; font-weight: 600; color: #555; }
    .controls input[type='number'] { width: 62px; padding: 6px; border: 1px solid #ccc; border-radius: 6px; }
    .controls button {
      background: #333;
      color: #fff;
      border: none;
      border-radius: 8px;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
    }
    .layout { display: grid; grid-template-columns: 3fr 1.3fr; gap: 14px; }
    .graph-placeholder {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      min-height: 430px;
      padding: 12px;
      overflow: hidden;
    }
    .graph-svg {
      width: 100%;
      height: 100%;
      min-height: 400px;
      background: #fff;
      touch-action: none;
      cursor: grab;
    }
    .graph-svg:active { cursor: grabbing; }
    .graph-link {
      stroke: #9ca3af;
      stroke-width: 2;
      opacity: 0.9;
    }
    .graph-node { cursor: pointer; }
    .graph-node circle {
      fill: #e5e7eb;
      stroke: #555;
      stroke-width: 2;
      transition: fill 0.15s;
    }
    .graph-node:hover circle { fill: #d1d5db; }
    .graph-node.selected circle {
      fill: #4b5563;
      stroke: #111827;
      stroke-width: 3;
    }
    .graph-node text {
      font-size: 12px;
      text-anchor: middle;
      font-weight: 600;
      fill: #333;
      user-select: none;
      pointer-events: none;
    }
    .detail-box {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 12px;
      min-height: 430px;
    }
    .empty { color: #666; }
    h2 { margin: 0 0 10px 0; color: #555; }
    h3 { margin: 6px 0 4px 0; }
    .type { margin: 0 0 10px 0; color: #777; }
    .toggles { display: flex; gap: 12px; margin-bottom: 10px; font-size: 0.9rem; font-weight: 600; }
    .content-block { border-top: 1px solid #e5e7eb; padding-top: 10px; margin-top: 10px; }
    pre { white-space: pre-wrap; background: #f5f5f5; border-radius: 8px; padding: 10px; margin: 0; }
    @media (max-width: 1100px) {
      .layout { grid-template-columns: 1fr; }
    }
  `]
})
export class LineageSearchPageComponent implements AfterViewInit, OnDestroy {
  @ViewChild('graphSvg', { static: true }) graphSvg!: ElementRef<SVGSVGElement>;

  searchInput = 'Paridad n² + n';
  depthUp = 1;
  depthDown = 2;
  showNatural = true;
  showLean = true;

  readonly allNodes: LineageNode[] = [
    { id: 1, name: 'Axioma de Peano', type: 'Axioma', desc: 'Define los números naturales.', lean: 'inductive Nat ...' },
    { id: 2, name: 'Inducción Matemática', type: 'Lema', desc: 'Principio de inducción en N.', lean: 'theorem nat_induction ...' },
    { id: 3, name: 'Paridad n² + n', type: 'Teorema', desc: 'Demuestra que n²+n es par.', lean: 'theorem parity_n_sq_add_n ...' },
    { id: 4, name: 'Divisibilidad por 2', type: 'Lema', desc: 'Define la paridad por divisibilidad.', lean: 'def even (n : Nat) := ∃ k, n = 2 * k' },
    { id: 5, name: 'Aritmética Básica', type: 'Lema', desc: 'Relaciones básicas de suma y producto.', lean: 'lemma basic_arith ...' },
    { id: 6, name: 'Corolario de Paridad', type: 'Corolario', desc: 'Extensiones de resultados de paridad.', lean: 'corollary parity_cor ...' }
  ];

  readonly allLinks: LineageLink[] = [
    { source: 1, target: 2 },
    { source: 2, target: 3 },
    { source: 4, target: 3 },
    { source: 5, target: 3 },
    { source: 3, target: 6 }
  ];

  visibleNodes: SimNode[] = [];
  selected: SimNode | null = null;

  zoom = 1;
  offsetX = 0;
  offsetY = 0;

  private rafId: number | null = null;
  private lastRenderTs = 0;
  private readonly targetFrameMs = 1000 / 30;
  private draggingNodeId: number | null = null;
    constructor(
      private readonly cdr: ChangeDetectorRef,
      private readonly zone: NgZone
    ) {}

  private dragPointerId: number | null = null;
  private panning = false;
  private panPointerId: number | null = null;
  private panStartX = 0;
  private panStartY = 0;
  private panOriginX = 0;
  private panOriginY = 0;

  get transform(): string {
    return `translate(${this.offsetX} ${this.offsetY}) scale(${this.zoom})`;
  }

  get renderedLinks() {
    const byId = new Map(this.visibleNodes.map((node) => [node.id, node]));
    return this.allLinks
      .filter((link) => byId.has(link.source) && byId.has(link.target))
      .map((link) => {
        const source = byId.get(link.source) as SimNode;
        const target = byId.get(link.target) as SimNode;
        return {
          x1: source.x,
          y1: source.y,
          x2: target.x,
          y2: target.y
        };
      });
  }

  ngAfterViewInit() {
    this.search();
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

  search() {
    const query = this.searchInput.trim().toLowerCase();
    const filtered =
      query.length === 0
        ? this.allNodes
        : this.allNodes.filter((node) => node.name.toLowerCase().includes(query));

    const width = 980;
    const height = 500;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.3;

    this.visibleNodes = filtered.map((node, index) => {
      const angle = (2 * Math.PI * index) / Math.max(filtered.length, 1) - Math.PI / 2;
      return {
        ...node,
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
        vx: 0,
        vy: 0
      };
    });

    this.selected = this.visibleNodes[0] ?? null;
    this.zoom = 1;
    this.offsetX = 0;
    this.offsetY = 0;
    this.cdr.markForCheck();
  }

  select(node: SimNode) {
    this.selected = node;
    this.cdr.markForCheck();
  }

  onWheel(event: WheelEvent) {
    event.preventDefault();
    const point = this.pointerToGraph(event.clientX, event.clientY);
    const previousZoom = this.zoom;
    const delta = event.deltaY < 0 ? 1.12 : 0.88;
    this.zoom = Math.max(0.45, Math.min(2.8, this.zoom * delta));

    this.offsetX = point.screenX - (point.graphX * this.zoom);
    this.offsetY = point.screenY - (point.graphY * this.zoom);

    if (Math.abs(previousZoom - this.zoom) < 0.0001) {
      return;
    }
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

  onNodePointerDown(event: PointerEvent, nodeId: number) {
    event.stopPropagation();
    this.draggingNodeId = nodeId;
    this.dragPointerId = event.pointerId;
  }

  private onPointerMove = (event: PointerEvent) => {
    if (this.dragPointerId === event.pointerId && this.draggingNodeId != null) {
      const point = this.pointerToGraph(event.clientX, event.clientY);
      const node = this.visibleNodes.find((item) => item.id === this.draggingNodeId);
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

  private pointerToGraph(clientX: number, clientY: number) {
    const rect = this.graphSvg.nativeElement.getBoundingClientRect();
    const screenX = ((clientX - rect.left) / rect.width) * 980;
    const screenY = ((clientY - rect.top) / rect.height) * 500;

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
    if (this.visibleNodes.length === 0) {
      return;
    }

    const idToNode = new Map(this.visibleNodes.map((node) => [node.id, node]));

    for (let i = 0; i < this.visibleNodes.length; i++) {
      for (let j = i + 1; j < this.visibleNodes.length; j++) {
        const nodeA = this.visibleNodes[i];
        const nodeB = this.visibleNodes[j];
        const dx = nodeB.x - nodeA.x;
        const dy = nodeB.y - nodeA.y;
        const distSq = dx * dx + dy * dy + 0.01;
        const force = 1200 / distSq;
        const dist = Math.sqrt(distSq);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        nodeA.vx -= fx;
        nodeA.vy -= fy;
        nodeB.vx += fx;
        nodeB.vy += fy;
      }
    }

    const springLength = 145;
    const springK = 0.012;
    for (const link of this.allLinks) {
      const source = idToNode.get(link.source);
      const target = idToNode.get(link.target);
      if (!source || !target) {
        continue;
      }

      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const distance = Math.sqrt(dx * dx + dy * dy) || 1;
      const stretch = distance - springLength;
      const force = stretch * springK;
      const fx = (dx / distance) * force;
      const fy = (dy / distance) * force;

      source.vx += fx;
      source.vy += fy;
      target.vx -= fx;
      target.vy -= fy;
    }

    const centerX = 490;
    const centerY = 250;
    for (const node of this.visibleNodes) {
      if (this.draggingNodeId === node.id) {
        continue;
      }

      node.vx += (centerX - node.x) * 0.0008;
      node.vy += (centerY - node.y) * 0.0008;

      node.vx *= 0.93;
      node.vy *= 0.93;

      node.x += node.vx;
      node.y += node.vy;

      node.x = Math.max(40, Math.min(940, node.x));
      node.y = Math.max(40, Math.min(460, node.y));
    }
  }
}
