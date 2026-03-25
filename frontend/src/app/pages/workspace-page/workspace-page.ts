import { Component, HostListener, OnDestroy, OnInit } from '@angular/core';
import { JsonPipe, NgClass, NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { TaskService } from '../../task.service';
import {
  NewNodeDto,
  PullRequestItem,
  SorryLocationItem,
  VerificationErrorItem,
  VerifyNodeResponse
} from '../../task.models';

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
  templateUrl: './workspace-page.html',
  styleUrl: './workspace-page.css'
})
export class WorkspacePageComponent implements OnInit, OnDestroy {
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
  computationCode = 'def run(input_data, target):\n    return {"evidence": {"input": input_data, "target": target}, "sufficient": True, "summary": "Demo computation succeeded"}\n';
  computationTargetJson = '{\n  "kind": "range_check",\n  "description": "f(x) in [0, 2] for x in [0,1]"\n}';
  computationInputJson = '{\n  "samples": 1000\n}';
  computationLeanStatement = 'GoalDef';
  computationEntrypoint = 'run';
  computationTimeoutSeconds = 120;

  graphCollapsed = false;
  editorCollapsed = false;
  prsCollapsed = false;

  graphScale = 1;
  graphOffsetX = 0;
  graphOffsetY = 0;
  isGraphPanning = false;
  private graphPanStartX = 0;
  private graphPanStartY = 0;
  private autoRefreshHandle: ReturnType<typeof setInterval> | null = null;

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
      this.startAutoRefresh();
    });
  }

  ngOnDestroy(): void {
    this.stopAutoRefresh();
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

  get isComputationNode(): boolean {
    return this.selectedNode?.node_kind === 'computation';
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
    this.loadGraph(true);
    this.loadOpenPulls();
    this.loadProjectDefinitions();
  }

  private loadGraph(reloadSelectedFile = true) {
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
          refreshSelectedNodeFile = !!stillExists && reloadSelectedFile;
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
    if (!this.selectedNode || this.isComputationNode || !this.leanCode.trim()) {
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
    if (!this.selectedNode || this.isComputationNode || !this.leanCode.trim()) {
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

  createComputationChildNode() {
    if (!this.selectedNode || this.isComputationNode) {
      return;
    }

    this.status = 'Creando nodo de computacion...';
    this.taskService.createComputationChildNode(this.projectId, this.selectedNode.id, {}).subscribe({
      next: (response) => {
        this.lastResponse = response;
        this.status = 'Solicitud de creación enviada. Se creó un PR para el nuevo nodo de computación.';
        this.loadGraph(false);
        this.loadOpenPulls();
      },
      error: (error) => {
        if (this.handleAuthError(error)) {
          this.lastResponse = error?.error || error;
          return;
        }
        this.lastResponse = error?.error || error;
        this.status = this.getBackendErrorMessage(error) || 'No se pudo crear el nodo de computacion.';
      }
    });
  }

  submitCompute() {
    if (!this.selectedNode || !this.isComputationNode || !this.computationCode.trim() || !this.computationLeanStatement.trim()) {
      return;
    }

    const parsedTarget = this.safeParseJson(this.computationTargetJson);
    if (!parsedTarget || typeof parsedTarget !== 'object' || Array.isArray(parsedTarget)) {
      this.status = 'El campo target debe ser un JSON objeto valido.';
      return;
    }

    const parsedInput = this.safeParseJson(this.computationInputJson);

    this.status = 'Enviando computacion...';
    this.taskService.computeNode(this.projectId, this.selectedNode.id, {
      language: 'python',
      code: this.computationCode,
      entrypoint: this.computationEntrypoint.trim() || 'run',
      input_data: parsedInput,
      target: parsedTarget as Record<string, unknown>,
      lean_statement: this.computationLeanStatement.trim(),
      timeout_seconds: this.computationTimeoutSeconds,
    }).subscribe({
      next: (response) => {
        this.lastResponse = this.compactUiResponse(response);
        const backendStatus = (response as { status?: string } | null)?.status;
        if (backendStatus === 'insufficient_evidence') {
          this.status = 'Computacion ejecutada, pero la evidencia fue insuficiente.';
          this.loadGraph(false);
          return;
        }
        if (backendStatus === 'already_computed') {
          this.status = 'Computacion validada. No hubo cambios en repo; estado guardado en DB.';
          this.loadGraph(false);
          this.loadOpenPulls();
          return;
        }
        this.status = 'Computacion enviada. Se creo un PR.';
        this.loadOpenPulls();
      },
      error: (error) => {
        if (this.handleAuthError(error)) {
          this.lastResponse = this.compactUiResponse(error?.error || error);
          return;
        }
        this.lastResponse = this.compactUiResponse(error?.error || error);
        this.status = this.getBackendErrorMessage(error) || 'Computacion con error.';
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
        this.loadGraph(false);
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

  private safeParseJson(value: string): unknown {
    if (!value.trim()) {
      return {};
    }

    try {
      return JSON.parse(value);
    } catch {
      return null;
    }
  }


  private compactUiResponse(payload: unknown): unknown {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      return payload;
    }

    const obj = payload as Record<string, unknown>;
    const result: Record<string, unknown> = { ...obj };

    const computation = obj['computation'];
    if (computation && typeof computation === 'object' && !Array.isArray(computation)) {
      const c = computation as Record<string, unknown>;
      result['computation'] = {
        completed: c['completed'],
        sufficient: c['sufficient'],
        summary: c['summary'],
        error: c['error'],
        processing_time_seconds: c['processing_time_seconds'],
        roundtrip_time_seconds: c['roundtrip_time_seconds'],
        timing_source: c['timing_source'],
        records_count: c['records_count'],
        evidence_preview: c['evidence_preview'],
      };
    }

    return result;
  }

  private handleAuthError(error: any): boolean {
    if (this.taskService.shouldClearAccessTokenOnError(error)) {
      this.taskService.clearAccessToken();
      this.status = 'Tu sesion expiro o es invalida. Vuelve a Auth para pegar un access token nuevo.';
      return true;
    }
    return false;
  }

  private startAutoRefresh() {
    this.stopAutoRefresh();
    this.autoRefreshHandle = setInterval(() => {
      if (!this.projectId || !this.taskService.getAccessToken()) {
        return;
      }

      this.loadOpenPulls();
      this.loadGraph(false);
    }, 3500);
  }

  private stopAutoRefresh() {
    if (this.autoRefreshHandle) {
      clearInterval(this.autoRefreshHandle);
      this.autoRefreshHandle = null;
    }
  }
}
