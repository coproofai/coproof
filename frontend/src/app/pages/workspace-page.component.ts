import { Component, OnInit } from '@angular/core';
import { JsonPipe, NgClass, NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { NewNodeDto, PullRequestItem, TaskService } from '../task.service';

interface ViewNode extends NewNodeDto {
  x: number;
  y: number;
}

interface ViewEdge {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

@Component({
  selector: 'app-workspace-page',
  standalone: true,
  imports: [NgIf, NgFor, NgClass, FormsModule, JsonPipe],
  template: `
    <header class="top-header">
      <div>
        <h1>Proyecto: {{ projectName || 'Workspace' }}</h1>
        <small>{{ sessionLabel }}</small>
      </div>
      <div class="header-actions">
        <button (click)="reloadAll()">Recargar</button>
      </div>
    </header>

    <p *ngIf="status" class="status">{{ status }}</p>

    <div class="workspace-grid" *ngIf="projectId; else noProjectSelected">
      <section class="panel graph-panel">
        <h2>Grafo de Dependencias</h2>
        <div class="graph-canvas" *ngIf="viewNodes.length > 0; else emptyGraph">
          <svg viewBox="0 0 980 520" preserveAspectRatio="xMidYMid meet">
            <line
              *ngFor="let edge of edges"
              class="graph-link"
              [attr.x1]="edge.x1"
              [attr.y1]="edge.y1"
              [attr.x2]="edge.x2"
              [attr.y2]="edge.y2"
            ></line>

            <g
              *ngFor="let node of viewNodes"
              class="graph-node"
              [class.selected]="selectedNode?.id === node.id"
              [ngClass]="node.state"
              (click)="selectNode(node)"
            >
              <circle [attr.cx]="node.x" [attr.cy]="node.y" r="28"></circle>
              <text [attr.x]="node.x" [attr.y]="node.y + 44">{{ node.name }}</text>
            </g>
          </svg>
        </div>

        <ng-template #emptyGraph>
          <p>No hay nodos en este proyecto.</p>
        </ng-template>
      </section>

      <section class="panel editor-panel">
        <h2>Editor de Nodo</h2>
        <ng-container *ngIf="selectedNode; else selectNodeHint">
          <p class="meta"><strong>Nodo:</strong> {{ selectedNode.name }}</p>
          <p class="meta"><strong>Estado:</strong> {{ selectedNode.state }}</p>
          <p class="meta"><strong>Archivo:</strong> {{ nodePath || '...' }}</p>

          <textarea
            [(ngModel)]="leanCode"
            name="leanCode"
            rows="14"
            placeholder="Contenido .lean del nodo seleccionado"
          ></textarea>

          <div class="actions">
            <button (click)="verifySelectedNode()">Verify</button>
            <button (click)="submitSolve()">Submit Solve</button>
            <button (click)="submitSplit()">Submit Split</button>
          </div>

          <pre *ngIf="lastResponse" class="response">{{ lastResponse | json }}</pre>
        </ng-container>

        <ng-template #selectNodeHint>
          <p>Selecciona un nodo del grafo para cargar su archivo .lean.</p>
        </ng-template>
      </section>

      <section class="panel pr-panel">
        <h2>Pull Requests Abiertos</h2>
        <div class="pr-list" *ngIf="openPulls.length > 0; else emptyPrs">
          <div class="pr-item" *ngFor="let pr of openPulls">
            <div>
              <p class="pr-title">#{{ pr.number }} - {{ pr.title }}</p>
              <p class="pr-meta">{{ pr.head }} → {{ pr.base }} · {{ pr.author }}</p>
            </div>
            <div class="pr-actions">
              <a [href]="pr.url" target="_blank" rel="noopener">Abrir</a>
              <button (click)="mergePullRequest(pr)">Merge</button>
            </div>
          </div>
        </div>

        <ng-template #emptyPrs>
          <p>No hay PRs abiertos para este proyecto.</p>
        </ng-template>
      </section>
    </div>

    <ng-template #noProjectSelected>
      <div class="panel">
        <p>Falta projectId en la URL. Ve a "Open Workspace" y selecciona un proyecto.</p>
      </div>
    </ng-template>
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
    .header-actions button {
      border: none;
      border-radius: 8px;
      background: #111827;
      color: #fff;
      font-weight: 700;
      padding: 9px 12px;
      cursor: pointer;
    }
    .workspace-grid {
      display: grid;
      grid-template-columns: 1.2fr 1.2fr 1fr;
      gap: 12px;
      min-height: 65vh;
    }
    .panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 12px; }
    h2 { margin: 0 0 10px 0; color: #555; font-size: 1rem; }
    .graph-canvas {
      position: relative;
      min-height: 520px;
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      overflow: hidden;
    }
    svg { width: 100%; height: 100%; }
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
    .graph-node.validated circle { fill: #dcfce7; }
    .graph-node.sorry circle { fill: #fee2e2; }
    .graph-node.selected circle { stroke: #111827; stroke-width: 3; }
    .graph-node text {
      font-size: 11px;
      text-anchor: middle;
      font-weight: 600;
      fill: #333;
      user-select: none;
      pointer-events: none;
    }
    .meta {
      margin: 0 0 6px 0;
      color: #444;
      font-size: 0.9rem;
    }
    textarea {
      width: 100%;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      padding: 10px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.84rem;
      box-sizing: border-box;
      resize: vertical;
    }
    .actions {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 8px;
    }
    .actions button {
      border: none;
      border-radius: 8px;
      background: #1f2937;
      color: #fff;
      padding: 8px;
      cursor: pointer;
      font-size: 0.83rem;
      font-weight: 700;
    }
    .response {
      margin-top: 10px;
      background: #f8fafc;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 10px;
      max-height: 220px;
      overflow: auto;
      font-size: 0.8rem;
    }
    .pr-list { display: flex; flex-direction: column; gap: 8px; }
    .pr-item {
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 10px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .pr-title {
      margin: 0 0 5px 0;
      font-weight: 700;
      font-size: 0.9rem;
      color: #333;
    }
    .pr-meta {
      margin: 0;
      color: #666;
      font-size: 0.8rem;
    }
    .pr-actions {
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-width: 86px;
    }
    .pr-actions a,
    .pr-actions button {
      text-align: center;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      padding: 6px;
      background: #fff;
      color: #111827;
      text-decoration: none;
      cursor: pointer;
      font-size: 0.8rem;
    }
    .status {
      margin: 10px 0;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      border-radius: 8px;
      padding: 10px;
      color: #1e3a8a;
      font-weight: 600;
    }
    @media (max-width: 1280px) {
      .workspace-grid { grid-template-columns: 1fr; }
    }
  `]
})
export class WorkspacePageComponent implements OnInit {
  projectId = '';
  projectName = '';
  sessionLabel = 'Sesión Individual';

  status = '';
  nodes: NewNodeDto[] = [];
  viewNodes: ViewNode[] = [];
  selectedNode: NewNodeDto | null = null;
  nodePath = '';
  leanCode = '';
  lastResponse: unknown = null;
  openPulls: PullRequestItem[] = [];

  constructor(
    private readonly route: ActivatedRoute,
    private readonly taskService: TaskService
  ) {}

  ngOnInit(): void {
    this.route.queryParamMap.subscribe((params) => {
      this.projectId = params.get('projectId') || '';
      this.projectName = params.get('projectName') || '';
      const sessionType = params.get('sessionType');
      this.sessionLabel = sessionType === 'collaborative' ? 'Sesión Colaborativa' : 'Sesión Individual';
      this.reloadAll();
    });
  }

  get edges(): ViewEdge[] {
    const byId = new Map(this.viewNodes.map((node) => [node.id, node]));
    return this.viewNodes
      .filter((node) => node.parent_node_id)
      .map((node) => {
        const parent = byId.get(node.parent_node_id || '');
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
      .filter((edge): edge is ViewEdge => edge != null);
  }

  reloadAll() {
    if (!this.projectId) {
      return;
    }
    if (!this.taskService.getAccessToken()) {
      this.status = 'No hay access token. Cárgalo desde Auth para usar el workspace.';
      return;
    }

    this.status = 'Cargando grafo y PRs...';
    this.loadGraph();
    this.loadOpenPulls();
  }

  private loadGraph() {
    this.taskService.getSimpleGraph(this.projectId).subscribe({
      next: (response) => {
        this.projectName = response.project_name || this.projectName;
        this.nodes = response.nodes || [];
        this.viewNodes = this.buildLayout(this.nodes);

        if (this.selectedNode) {
          const stillExists = this.nodes.find((node) => node.id === this.selectedNode?.id);
          this.selectedNode = stillExists || null;
        }
        if (!this.selectedNode && this.nodes.length > 0) {
          this.selectNode(this.nodes[0]);
        }

        this.status = `Grafo cargado: ${this.nodes.length} nodos.`;
      },
      error: (error) => {
        this.status = error?.error?.error || 'No se pudo cargar el grafo.';
      }
    });
  }

  private loadOpenPulls() {
    this.taskService.listOpenPullRequests(this.projectId).subscribe({
      next: (response) => {
        this.openPulls = response.pulls || [];
      },
      error: () => {
        this.openPulls = [];
      }
    });
  }

  selectNode(node: NewNodeDto) {
    this.selectedNode = node;
    this.nodePath = '';
    this.leanCode = '';
    this.lastResponse = null;

    this.taskService.getNodeLeanFile(this.projectId, node.id).subscribe({
      next: (response) => {
        this.nodePath = response.path;
        this.leanCode = response.content || '';
      },
      error: (error) => {
        this.status = error?.error?.error || 'No se pudo cargar el archivo .lean del nodo.';
      }
    });
  }

  verifySelectedNode() {
    if (!this.selectedNode) {
      return;
    }
    this.status = 'Verificando nodo/import tree...';
    this.taskService.verifyNode(this.projectId, this.selectedNode.id).subscribe({
      next: (response) => {
        this.lastResponse = response;
        this.status = 'Verificación completada.';
      },
      error: (error) => {
        this.lastResponse = error?.error || error;
        this.status = 'La verificación devolvió error.';
      }
    });
  }

  submitSolve() {
    if (!this.selectedNode || !this.leanCode.trim()) {
      return;
    }
    this.status = 'Enviando solve...';
    this.taskService.solveNode(this.projectId, this.selectedNode.id, this.leanCode).subscribe({
      next: (response) => {
        this.lastResponse = response;
        this.status = 'Solve enviado. Se creó un PR.';
        this.loadOpenPulls();
      },
      error: (error) => {
        this.lastResponse = error?.error || error;
        this.status = 'Solve con error.';
      }
    });
  }

  submitSplit() {
    if (!this.selectedNode || !this.leanCode.trim()) {
      return;
    }
    this.status = 'Enviando split...';
    this.taskService.splitNode(this.projectId, this.selectedNode.id, this.leanCode).subscribe({
      next: (response) => {
        this.lastResponse = response;
        this.status = 'Split enviado. Se creó un PR.';
        this.loadOpenPulls();
      },
      error: (error) => {
        this.lastResponse = error?.error || error;
        this.status = 'Split con error.';
      }
    });
  }

  mergePullRequest(pr: PullRequestItem) {
    this.status = `Mergeando PR #${pr.number}...`;
    this.taskService.mergePullRequest(this.projectId, pr.number).subscribe({
      next: (response) => {
        this.lastResponse = response;
        this.status = `PR #${pr.number} mergeado.`;
        this.loadOpenPulls();
        this.loadGraph();
      },
      error: (error) => {
        this.lastResponse = error?.error || error;
        this.status = `No se pudo mergear PR #${pr.number}.`;
      }
    });
  }

  private buildLayout(nodes: NewNodeDto[]): ViewNode[] {
    if (nodes.length === 0) {
      return [];
    }

    const byId = new Map(nodes.map((node) => [node.id, node]));
    const levelMemo = new Map<string, number>();

    const resolveLevel = (node: NewNodeDto): number => {
      const cached = levelMemo.get(node.id);
      if (cached != null) {
        return cached;
      }
      if (!node.parent_node_id) {
        levelMemo.set(node.id, 0);
        return 0;
      }

      const parent = byId.get(node.parent_node_id);
      if (!parent) {
        levelMemo.set(node.id, 0);
        return 0;
      }

      const level = resolveLevel(parent) + 1;
      levelMemo.set(node.id, level);
      return level;
    };

    nodes.forEach((node) => resolveLevel(node));

    const buckets = new Map<number, NewNodeDto[]>();
    for (const node of nodes) {
      const level = levelMemo.get(node.id) ?? 0;
      const existing = buckets.get(level) || [];
      existing.push(node);
      buckets.set(level, existing);
    }

    const maxLevel = Math.max(...Array.from(buckets.keys()), 0);

    return nodes.map((node) => {
      const level = levelMemo.get(node.id) ?? 0;
      const bucket = buckets.get(level) || [];
      const index = bucket.findIndex((item) => item.id === node.id);
      const xStep = 860 / (bucket.length + 1);
      const yStep = maxLevel === 0 ? 0 : 360 / maxLevel;

      return {
        ...node,
        x: 60 + xStep * (index + 1),
        y: 80 + yStep * level
      };
    });
  }
}
