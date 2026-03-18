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
  templateUrl: './lineage-search-page.html',
  styleUrl: './lineage-search-page.css'
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
