import { Component, HostListener, OnInit } from '@angular/core';
import { JsonPipe, NgClass, NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import {
  NewNodeDto,
  PullRequestItem,
  SorryLocationItem,
  TaskService,
  VerificationErrorItem,
  VerifyNodeResponse
} from '../task.service';

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
      <section class="panel graph-panel" [class.collapsed]="graphCollapsed">
        <div class="panel-head">
          <h2>Grafo de Dependencias</h2>
          <div class="panel-actions">
            <button *ngIf="!graphCollapsed" class="ghost" (click)="resetGraphTransform()">Reset View</button>
            <button class="ghost" (click)="graphCollapsed = !graphCollapsed">
              {{ graphCollapsed ? 'Expandir' : 'Colapsar' }}
            </button>
          </div>
        </div>

        <div class="panel-body" *ngIf="!graphCollapsed">
          <div class="graph-canvas" *ngIf="viewNodes.length > 0; else emptyGraph">
            <svg
              [attr.viewBox]="graphViewBox"
              preserveAspectRatio="xMidYMid meet"
              (wheel)="onGraphWheel($event)"
              (mousedown)="onGraphMouseDown($event)"
              (mousemove)="onGraphMouseMove($event)"
              (mouseleave)="stopGraphPan()"
              [class.panning]="isGraphPanning"
            >
              <g [attr.transform]="graphTransform">
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
              </g>
            </svg>
          </div>

          <p class="graph-tip">Drag para mover, rueda para zoom.</p>
        </div>

        <ng-template #emptyGraph>
          <p>No hay nodos en este proyecto.</p>
        </ng-template>
      </section>

      <section class="panel editor-panel" [class.collapsed]="editorCollapsed">
        <div class="panel-head">
          <h2>Editor de Nodo</h2>
          <div class="panel-actions">
            <button class="ghost" (click)="editorCollapsed = !editorCollapsed">
              {{ editorCollapsed ? 'Expandir' : 'Colapsar' }}
            </button>
          </div>
        </div>

        <div class="panel-body" *ngIf="!editorCollapsed">
          <ng-container *ngIf="selectedNode; else selectNodeHint">
            <p class="meta"><strong>Nodo:</strong> {{ selectedNode.name }}</p>
            <p class="meta"><strong>Estado:</strong> {{ selectedNode.state }}</p>
            <p class="meta"><strong>Archivo:</strong> {{ nodePath || '...' }}</p>

            <p *ngIf="isNodeFileLoading" class="meta">Cargando archivo .lean...</p>

            <textarea
              *ngIf="!isNodeFileLoading"
              [(ngModel)]="leanCode"
              name="leanCode"
              rows="12"
              placeholder="Contenido .lean del nodo seleccionado"
            ></textarea>

            <div class="actions">
              <button (click)="verifySelectedNode()">Verify</button>
              <button (click)="submitSolve()">Submit Solve</button>
              <button (click)="submitSplit()">Submit Split</button>
            </div>

            <div class="verify-box" *ngIf="verificationSummary || verificationErrors.length > 0 || sorryLocations.length > 0">
              <p class="meta"><strong>Resultado de verificación:</strong> {{ verificationSummary || 'Sin resumen disponible.' }}</p>

              <p class="meta issue-title" *ngIf="verificationErrors.length > 0">Errores de compilación:</p>
              <ul class="issue-list" *ngIf="verificationErrors.length > 0">
                <li *ngFor="let issue of verificationErrors">
                  L{{ issue.line }}:C{{ issue.column }} - {{ issue.message }}
                </li>
              </ul>

              <p class="meta issue-title" *ngIf="sorryLocations.length > 0">Sorries detectados:</p>
              <ul class="issue-list" *ngIf="sorryLocations.length > 0">
                <li *ngFor="let location of sorryLocations">
                  {{ location.file }}:{{ location.line }} - {{ location.snippet }}
                </li>
              </ul>
            </div>

            <div *ngIf="lastResponse" class="response-wrap">
              <p class="meta"><strong>Respuesta backend</strong></p>
              <pre class="response">{{ lastResponse | json }}</pre>
            </div>

            <div class="preview-card" *ngIf="!isNodeFileLoading && leanCode">
              <div class="preview-head">
                <strong>Preview del Nodo</strong>
                <span>{{ leanCodeLineCount }} líneas</span>
              </div>
              <div class="code-preview">
                <div class="code-line" *ngFor="let line of leanCodeLines; let index = index">
                  <span class="line-no">{{ index + 1 }}</span>
                  <span class="line-code" [innerHTML]="formatLeanLine(line)"></span>
                </div>
              </div>
            </div>

            <div class="definitions-box">
              <h3>Definiciones del Proyecto</h3>
              <p class="meta"><strong>Archivo:</strong> {{ definitionsPath || 'Definitions.lean' }}</p>
              <p class="meta" *ngIf="definitionsLoading">Cargando definiciones...</p>
              <p class="meta" *ngIf="definitionsError">{{ definitionsError }}</p>
              <div class="preview-card" *ngIf="!definitionsLoading && projectDefinitions">
                <div class="preview-head">
                  <strong>Preview Definitions</strong>
                  <span>{{ definitionsLineCount }} líneas</span>
                </div>
                <div class="code-preview definitions-preview">
                  <div class="code-line" *ngFor="let line of definitionsLines; let index = index">
                    <span class="line-no">{{ index + 1 }}</span>
                    <span class="line-code" [innerHTML]="formatLeanLine(line)"></span>
                  </div>
                </div>
              </div>
            </div>
          </ng-container>
        </div>

        <ng-template #selectNodeHint>
          <p>Selecciona un nodo del grafo para cargar su archivo .lean.</p>
        </ng-template>
      </section>

      <section class="panel pr-panel" [class.collapsed]="prsCollapsed">
        <div class="panel-head">
          <h2>Pull Requests Abiertos</h2>
          <div class="panel-actions">
            <button class="ghost" (click)="prsCollapsed = !prsCollapsed">
              {{ prsCollapsed ? 'Expandir' : 'Colapsar' }}
            </button>
          </div>
        </div>

        <div class="panel-body" *ngIf="!prsCollapsed">
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
      grid-template-columns: minmax(340px, 1.05fr) minmax(460px, 1.25fr) minmax(320px, 0.9fr);
      gap: 12px;
      height: calc(100vh - 210px);
      min-height: 560px;
    }
    .panel {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 12px;
      display: flex;
      flex-direction: column;
      min-height: 0;
      overflow: hidden;
    }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
    }
    .panel-actions {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .panel-body {
      flex: 1;
      min-height: 0;
      overflow: auto;
      padding-right: 2px;
    }
    .ghost {
      border: 1px solid #d1d5db;
      border-radius: 8px;
      background: #fff;
      color: #374151;
      font-size: 0.78rem;
      padding: 6px 8px;
      font-weight: 700;
      cursor: pointer;
    }
    h2 { margin: 0; color: #555; font-size: 1rem; }
    .graph-canvas {
      position: relative;
      min-height: 420px;
      height: calc(100% - 24px);
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      overflow: hidden;
    }
    svg { width: 100%; height: 100%; cursor: grab; }
    svg.panning { cursor: grabbing; }
    .graph-tip {
      margin: 8px 0 0 0;
      color: #6b7280;
      font-size: 0.78rem;
    }
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
      overflow-wrap: anywhere;
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
      min-height: 190px;
      max-height: 320px;
    }
    .actions {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 8px;
      margin-bottom: 8px;
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
    .response-wrap {
      margin-top: 8px;
    }
    .response {
      margin-top: 6px;
      background: #f8fafc;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 10px;
      max-height: 220px;
      overflow: auto;
      font-size: 0.8rem;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .verify-box {
      margin-top: 10px;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      background: #f8fafc;
      padding: 10px;
    }
    .issue-title {
      margin-top: 10px;
      margin-bottom: 6px;
      font-weight: 700;
    }
    .issue-list {
      margin: 0;
      padding-left: 20px;
      color: #1f2937;
      font-size: 0.84rem;
      display: grid;
      gap: 4px;
    }
    .definitions-box {
      margin-top: 12px;
      border-top: 1px solid #e5e7eb;
      padding-top: 10px;
    }
    .definitions-box h3 {
      margin: 0 0 8px 0;
      color: #444;
      font-size: 0.95rem;
    }
    .preview-card {
      margin-top: 10px;
      border: 1px solid #d1d5db;
      border-radius: 10px;
      overflow: hidden;
      background: #ffffff;
    }
    .preview-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      background: #f8fafc;
      border-bottom: 1px solid #e5e7eb;
      padding: 8px 10px;
      color: #374151;
      font-size: 0.8rem;
    }
    .code-preview {
      max-height: 280px;
      overflow: auto;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.79rem;
      line-height: 1.42;
      background: #fcfdff;
    }
    .definitions-preview {
      max-height: 220px;
    }
    .code-line {
      display: grid;
      grid-template-columns: 48px minmax(0, 1fr);
      border-bottom: 1px solid #f1f5f9;
    }
    .line-no {
      background: #f8fafc;
      color: #9ca3af;
      border-right: 1px solid #f1f5f9;
      text-align: right;
      padding: 0 8px;
      user-select: none;
    }
    .line-code {
      padding: 0 10px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: #1f2937;
    }
    .line-code .kw {
      color: #0f766e;
      font-weight: 700;
    }
    .line-code .tac {
      color: #7c3aed;
      font-weight: 700;
    }
    .line-code .cm {
      color: #6b7280;
      font-style: italic;
    }
    .pr-list { display: flex; flex-direction: column; gap: 8px; }
    .pr-item {
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 10px;
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
      min-width: 0;
    }
    .pr-title {
      margin: 0 0 5px 0;
      font-weight: 700;
      font-size: 0.9rem;
      color: #333;
      overflow-wrap: anywhere;
    }
    .pr-meta {
      margin: 0;
      color: #666;
      font-size: 0.8rem;
      overflow-wrap: anywhere;
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
      overflow-wrap: anywhere;
    }
    @media (max-width: 1600px) {
      .workspace-grid {
        grid-template-columns: minmax(320px, 1fr) minmax(420px, 1.15fr) minmax(280px, 0.8fr);
      }
    }
    @media (max-width: 1280px) {
      .workspace-grid {
        grid-template-columns: 1fr;
        height: auto;
      }
      .panel {
        max-height: none;
      }
      .panel-body {
        overflow: visible;
      }
      .graph-canvas {
        min-height: 360px;
        height: 360px;
      }
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
  graphViewBox = '0 0 980 520';
  selectedNode: NewNodeDto | null = null;
  nodePath = '';
  leanCode = '';
  isNodeFileLoading = false;
  lastResponse: unknown = null;
  verificationSummary = '';
  verificationErrors: VerificationErrorItem[] = [];
  sorryLocations: SorryLocationItem[] = [];
  definitionsPath = '';
  projectDefinitions = '';
  definitionsLoading = false;
  definitionsError = '';
  openPulls: PullRequestItem[] = [];

  graphCollapsed = false;
  editorCollapsed = false;
  prsCollapsed = false;

  graphScale = 1;
  graphOffsetX = 0;
  graphOffsetY = 0;
  isGraphPanning = false;
  private graphPanStartX = 0;
  private graphPanStartY = 0;

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

  get graphTransform(): string {
    return `translate(${this.graphOffsetX} ${this.graphOffsetY}) scale(${this.graphScale})`;
  }

  get leanCodeLines(): string[] {
    return this.leanCode.split(/\r?\n/);
  }

  get leanCodeLineCount(): number {
    return this.leanCodeLines.length;
  }

  get definitionsLines(): string[] {
    return this.projectDefinitions.split(/\r?\n/);
  }

  get definitionsLineCount(): number {
    return this.definitionsLines.length;
  }

  @HostListener('window:mouseup')
  onWindowMouseUp() {
    this.stopGraphPan();
  }

  onGraphWheel(event: WheelEvent) {
    event.preventDefault();
    const svg = event.currentTarget as SVGElement;
    const rect = svg.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    const oldScale = this.graphScale;
    const factor = event.deltaY < 0 ? 1.1 : 0.9;
    const nextScale = Math.min(2.8, Math.max(0.45, oldScale * factor));

    if (nextScale === oldScale) {
      return;
    }

    const worldX = (mouseX - this.graphOffsetX) / oldScale;
    const worldY = (mouseY - this.graphOffsetY) / oldScale;

    this.graphScale = nextScale;
    this.graphOffsetX = mouseX - worldX * nextScale;
    this.graphOffsetY = mouseY - worldY * nextScale;
  }

  onGraphMouseDown(event: MouseEvent) {
    if (event.button !== 0) {
      return;
    }

    const target = event.target as HTMLElement;
    if (target.closest('.graph-node')) {
      return;
    }

    this.isGraphPanning = true;
    this.graphPanStartX = event.clientX - this.graphOffsetX;
    this.graphPanStartY = event.clientY - this.graphOffsetY;
  }

  onGraphMouseMove(event: MouseEvent) {
    if (!this.isGraphPanning) {
      return;
    }

    this.graphOffsetX = event.clientX - this.graphPanStartX;
    this.graphOffsetY = event.clientY - this.graphPanStartY;
  }

  stopGraphPan() {
    this.isGraphPanning = false;
  }

  resetGraphTransform() {
    this.graphScale = 1;
    this.graphOffsetX = 0;
    this.graphOffsetY = 0;
  }

  formatLeanLine(rawLine: string): string {
    const escaped = this.escapeHtml(rawLine);
    const commentIndex = escaped.indexOf('--');

    let codePart = escaped;
    let commentPart = '';
    if (commentIndex >= 0) {
      codePart = escaped.slice(0, commentIndex);
      commentPart = escaped.slice(commentIndex);
    }

    codePart = codePart.replace(
      /\b(import|theorem|lemma|def|abbrev|by|where|namespace|open|variable|axiom|example)\b/g,
      '<span class="kw">$1</span>',
    );
    codePart = codePart.replace(
      /\b(intro|exact|have|apply|rw|simp|constructor|cases|rcases|refine|aesop|linarith|ring|omega)\b/g,
      '<span class="tac">$1</span>',
    );

    if (commentPart) {
      codePart += `<span class="cm">${commentPart}</span>`;
    }

    return codePart || '&nbsp;';
  }

  private escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
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
    this.loadProjectDefinitions();
  }

  private loadGraph() {
    this.taskService.getSimpleGraph(this.projectId).subscribe({
      next: (response) => {
        this.projectName = response.project_name || this.projectName;
        this.nodes = response.nodes || [];
        this.viewNodes = this.buildLayout(this.nodes);
        this.updateGraphViewBox(this.viewNodes);

        let refreshSelectedNodeFile = false;

        if (this.selectedNode) {
          const stillExists = this.nodes.find((node) => node.id === this.selectedNode?.id);
          this.selectedNode = stillExists || null;
          refreshSelectedNodeFile = !!stillExists;
        }

        if (!this.selectedNode && this.nodes.length > 0) {
          this.selectNode(this.nodes[0]);
        } else if (refreshSelectedNodeFile && this.selectedNode) {
          // Ensure editor reflects latest merged content for the selected node.
          this.selectNode(this.selectedNode);
        }

        this.status = `Grafo cargado: ${this.nodes.length} nodos.`;
      },
      error: (error) => {
        if (this.handleAuthError(error)) {
          return;
        }
        this.status = this.getBackendErrorMessage(error) || 'No se pudo cargar el grafo.';
      }
    });
  }

  private loadOpenPulls() {
    this.taskService.listOpenPullRequests(this.projectId).subscribe({
      next: (response) => {
        this.openPulls = response.pulls || [];
      },
      error: (error) => {
        if (this.handleAuthError(error)) {
          this.openPulls = [];
          return;
        }
        this.openPulls = [];
      }
    });
  }

  selectNode(node: NewNodeDto) {
    this.selectedNode = node;
    this.nodePath = '';
    this.leanCode = '';
    this.lastResponse = null;
    this.verificationSummary = '';
    this.verificationErrors = [];
    this.sorryLocations = [];
    this.isNodeFileLoading = true;
    this.status = `Cargando archivo de ${node.name}...`;

    this.taskService.getNodeLeanFile(this.projectId, node.id).subscribe({
      next: (response) => {
        this.nodePath = response.path;
        this.leanCode = response.content || '';
        this.isNodeFileLoading = false;
        this.status = `Archivo cargado: ${response.path}`;
      },
      error: (error) => {
        if (this.handleAuthError(error)) {
          this.isNodeFileLoading = false;
          return;
        }
        this.isNodeFileLoading = false;
        this.status = this.getBackendErrorMessage(error) || 'No se pudo cargar el archivo .lean del nodo.';
      }
    });
  }

  verifySelectedNode() {
    if (!this.selectedNode) {
      return;
    }
    this.status = 'Verificando nodo/import tree...';
    this.taskService.verifyNode(this.projectId, this.selectedNode.id).subscribe({
      next: (response: VerifyNodeResponse) => {
        this.lastResponse = response;
        const verification = response.verification || { valid: false, errors: [] };
        const errors = verification.errors || [];
        const sorries = response.sorry_locations || [];

        this.verificationErrors = errors;
        this.sorryLocations = sorries;

        if (verification.valid && sorries.length === 0) {
          this.verificationSummary = 'Compilación exitosa y sin sorry.';
          this.applyNodeState(this.selectedNode!.id, 'validated');
        } else if (verification.valid && sorries.length > 0) {
          this.verificationSummary = `Compila, pero contiene ${sorries.length} sorry.`;
          this.applyNodeState(this.selectedNode!.id, 'sorry');
        } else {
          this.verificationSummary = `Falló compilación con ${errors.length} error(es).`;
          this.applyNodeState(this.selectedNode!.id, 'sorry');
        }

        this.status = `Verificación terminada. ${this.verificationSummary}`;
      },
      error: (error) => {
        if (this.handleAuthError(error)) {
          this.lastResponse = error?.error || error;
          this.verificationSummary = '';
          this.verificationErrors = [];
          this.sorryLocations = [];
          return;
        }
        this.lastResponse = error?.error || error;
        this.verificationSummary = '';
        this.verificationErrors = [];
        this.sorryLocations = [];
        this.status = this.getBackendErrorMessage(error) || 'La verificación devolvió error.';
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
        const backendStatus = (response as { status?: string } | null)?.status;
        if (backendStatus === 'already_solved') {
          this.status = 'Solve validado. No hubo cambios en archivo, se guardo estado en la base de datos.';
          this.loadGraph();
          this.loadOpenPulls();
          return;
        }

        this.status = 'Solve enviado. Se creó un PR.';
        this.loadOpenPulls();
      },
      error: (error) => {
        if (this.handleAuthError(error)) {
          this.lastResponse = error?.error || error;
          return;
        }
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
        if (this.handleAuthError(error)) {
          this.lastResponse = error?.error || error;
          return;
        }
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
        if (this.handleAuthError(error)) {
          this.lastResponse = error?.error || error;
          return;
        }
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

  private updateGraphViewBox(nodes: ViewNode[]) {
    if (nodes.length === 0) {
      this.graphViewBox = '0 0 980 520';
      return;
    }

    const minX = Math.min(...nodes.map((node) => node.x)) - 100;
    const maxX = Math.max(...nodes.map((node) => node.x)) + 100;
    const minY = Math.min(...nodes.map((node) => node.y)) - 80;
    const maxY = Math.max(...nodes.map((node) => node.y)) + 120;

    const width = Math.max(300, maxX - minX);
    const height = Math.max(240, maxY - minY);
    this.graphViewBox = `${Math.floor(minX)} ${Math.floor(minY)} ${Math.ceil(width)} ${Math.ceil(height)}`;
  }

  private applyNodeState(nodeId: string, state: 'validated' | 'sorry') {
    this.nodes = this.nodes.map((node) =>
      node.id === nodeId ? { ...node, state } : node
    );
    this.viewNodes = this.viewNodes.map((node) =>
      node.id === nodeId ? { ...node, state } : node
    );
    if (this.selectedNode?.id === nodeId) {
      this.selectedNode = { ...this.selectedNode, state };
    }
  }

  private loadProjectDefinitions() {
    if (!this.projectId) {
      return;
    }

    this.definitionsLoading = true;
    this.definitionsError = '';
    this.projectDefinitions = '';
    this.definitionsPath = '';

    this.taskService.getProjectDefinitions(this.projectId).subscribe({
      next: (response) => {
        this.definitionsPath = response.path;
        this.projectDefinitions = response.content || '';
        this.definitionsLoading = false;
      },
      error: (error) => {
        if (this.handleAuthError(error)) {
          this.definitionsLoading = false;
          return;
        }
        this.definitionsLoading = false;
        this.definitionsError = this.getBackendErrorMessage(error) || 'No se pudieron cargar las definiciones del proyecto.';
      }
    });
  }

  private getBackendErrorMessage(error: any): string {
    return error?.error?.message || error?.error?.error || error?.error?.msg || '';
  }

  private handleAuthError(error: any): boolean {
    const message = this.getBackendErrorMessage(error);
    if (message === 'Signature verification failed' || error?.status === 401 || error?.status === 422) {
      this.taskService.clearAccessToken();
      this.status = 'Tu sesion expiro o es invalida. Vuelve a Auth para pegar un access token nuevo.';
      return true;
    }
    return false;
  }
}
