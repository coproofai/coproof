import { Component, HostListener, OnDestroy, OnInit } from '@angular/core';
import { AsyncPipe, JsonPipe, NgClass, NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Observable, Subject, forkJoin, of, timer } from 'rxjs';
import { catchError, filter, map, shareReplay, startWith, switchMap, take, timeout } from 'rxjs/operators';
import { TaskService } from '../../task.service';
import {
  AvailableModel,
  NewNodeDto,
  PrFileEntry,
  PullRequestItem,
  SorryLocationItem,
  SuggestPayload,
  SuggestResult,
  TranslatePayload,
  TranslationResult,
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

type TexState = 'idle' | 'loading' | 'ready' | 'error';
interface TexVm {
  state: TexState;
  path: string;
  source: string;
  renderedHtml: SafeHtml;
  error: string;
}
const IDLE_TEX_VM: TexVm = { state: 'idle', path: '', source: '', renderedHtml: '', error: '' };

interface Toast {
  id: number;
  message: string;
  type: 'info' | 'success' | 'error';
}

@Component({
  selector: 'app-workspace-page',
  standalone: true,
  imports: [NgIf, NgFor, NgClass, FormsModule, JsonPipe, AsyncPipe],
  templateUrl: './workspace-page.html',
  styleUrl: './workspace-page.css'
})
export class WorkspacePageComponent implements OnInit, OnDestroy {
  projectId = '';
  projectName = '';
  isProjectOwner = false;
  sessionLabel = 'Sesión Individual';

  private _status = '';
  private _toastNext = 0;
  toasts: Toast[] = [];

  get status(): string { return this._status; }
  set status(msg: string) {
    this._status = msg;
    if (!msg) return;
    const type = this._toastType(msg);
    const id = ++this._toastNext;
    this.toasts = [...this.toasts, { id, message: msg, type }];
    setTimeout(() => this.dismissToast(id), 5000);
  }
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
  prExpandedMap: Map<number, boolean> = new Map();
  prFilesMap: Map<number, PrFileEntry[]> = new Map();
  prFilesLoadingMap: Map<number, boolean> = new Map();
  prTexViewMap: Map<number, Map<string, 'source' | 'rendered'>> = new Map();
  prFileCollapsedMap: Map<number, Set<string>> = new Map();
  computationCode = 'def run(input_data, target):\n    return {"evidence": {"input": input_data, "target": target}, "sufficient": True, "summary": "Demo computation succeeded"}\n';
  computationTargetJson = '{\n  "kind": "range_check",\n  "description": "f(x) in [0, 2] for x in [0,1]"\n}';
  computationInputJson = '[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]';
  computationLeanStatement = 'GoalDef';
  computationEntrypoint = 'run';
  computationTimeoutSeconds = 120;
  computationLanguage: 'python' | 'mpi' = 'python';

  activeTab: 'node' | 'tex' | 'prs' | 'defs' = 'node';
  sidebarCollapsed = false;
  graphCollapsed = false;
  sectionEditor = true;
  sectionActions = true;
  sectionResults = true;
  sectionPreview = true;
  texViewMode: 'source' | 'preview' = 'source';

  activeAction: 'solve' | 'split' | 'compute' | 'ai-auto' | 'create-computation' | null = null;
  actionMode: 'nl' | 'fl' | 'ai' = 'fl';
  actionLeanCode = '';
  isVerifying = false;
  isActionRunning = false;
  lastResultSource = '';

  // Model selector (used by Resolver FL tab to drive FL→NL tex generation)
  solveModels: AvailableModel[] = [];
  solveModelsLoading = false;
  solveModelId = '';
  solveMaskedKey: string | null = null;
  solveApiKeyInput = '';
  solveApiKeySaving = false;
  solveApiKeyError = '';
  // Model selector (used by Dividir FL→NL tex generation)
  splitModelId = '';
  splitMaskedKey: string | null = null;
  splitApiKeyInput = '';
  splitApiKeySaving = false;
  splitApiKeyError = '';
  // Model selector (NL → FL → Solve pipeline, "Resolver / Lenguaje Natural" tab)
  nlSolveModelId = '';
  nlSolveMaskedKey: string | null = null;
  nlSolveApiKeyInput = '';
  nlSolveApiKeySaving = false;
  nlSolveApiKeyError = '';
  nlSolveText = '';
  nlSolvePhase = '';
  nlSolveShowPreview = false;
  nlSolveRendered: SafeHtml = '';
  // Model selector (NL → FL → Split pipeline, "Dividir / Lenguaje Natural" tab)
  nlSplitModelId = '';
  nlSplitMaskedKey: string | null = null;
  nlSplitApiKeyInput = '';
  nlSplitApiKeySaving = false;
  nlSplitApiKeyError = '';
  nlSplitText = '';
  nlSplitPhase = '';
  nlSplitShowPreview = false;
  nlSplitRendered: SafeHtml = '';
  // Model selector + prompt (used by IA Auto pipeline)
  aiAutoModelId = '';
  aiAutoMaskedKey: string | null = null;
  aiAutoApiKeyInput = '';
  aiAutoApiKeySaving = false;
  aiAutoApiKeyError = '';
  aiAutoPrompt = '';
  aiAutoPhase = '';          // current phase label shown inside the submenu
  // Model selector for create-computation (used to generate .tex via FL→NL, same as split child nodes)
  createComputeModelId = '';
  createComputeMaskedKey: string | null = null;
  createComputeApiKeyInput = '';
  createComputeApiKeySaving = false;
  createComputeApiKeyError = '';
  createComputePhase = '';
  // Model selector for execute-computation (used to generate enhanced .tex after Lean verification)
  computeModelId = '';
  computeMaskedKey: string | null = null;
  computeApiKeyInput = '';
  computeApiKeySaving = false;
  computeApiKeyError = '';
  get isBlocked(): boolean { return this.isVerifying || this.isActionRunning; }

  sidebarWidth = 420;
  isResizing = false;
  private resizeStartX = 0;
  private resizeStartWidth = 0;

  private readonly texNodeId$ = new Subject<string | null>();
  readonly texVm$: Observable<TexVm> = this.texNodeId$.pipe(
    switchMap(nodeId => {
      if (!nodeId) return of(IDLE_TEX_VM);
      return this.taskService.getNodeTexFile(this.projectId, nodeId).pipe(
        map(r => ({
          state: 'ready' as const,
          path: r.path,
          source: r.content || '',
          renderedHtml: this._renderTexHtml(r.content || ''),
          error: '',
        })),
        startWith<TexVm>({ state: 'loading', path: '', source: '', renderedHtml: '', error: '' }),
        catchError(err => {
          const msg = this.getBackendErrorMessage(err) || 'No se pudo cargar el archivo .tex del nodo.';
          return of<TexVm>({ state: 'error', path: '', source: '', renderedHtml: '', error: msg });
        }),
      );
    }),
    startWith(IDLE_TEX_VM),
    shareReplay(1),
  );

  graphScale = 1;
  graphOffsetX = 0;
  graphOffsetY = 0;
  isGraphPanning = false;
  private graphPanStartX = 0;
  private graphPanStartY = 0;
  private autoRefreshHandle: ReturnType<typeof setInterval> | null = null;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly taskService: TaskService,
    private readonly sanitizer: DomSanitizer
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

    // Load available models for the Resolver FL→NL tex generation
    this.solveModelsLoading = true;
    this.taskService.getAvailableModels().subscribe({
      next: models => { this.solveModels = models; this.solveModelsLoading = false; },
      error: () => { this.solveModels = []; this.solveModelsLoading = false; },
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

  get compTargetPlaceholder(): string {
    return this.computationLanguage === 'mpi'
      ? '{\n  "kind": "range_check",\n  "lo": 0,\n  "hi": 1\n}'
      : '{\n  "kind": "range_check",\n  "description": "f(x) in [0,1] for x in [0,1]"\n}';
  }

  get compInputPlaceholder(): string {
    return this.computationLanguage === 'mpi'
      ? '[0, 0.25, 0.5, 0.75, 1.0]'
      : '{\n  "samples": 1000\n}';
  }

  get compCodePlaceholder(): string {
    return this.computationLanguage === 'mpi'
      ? 'def run(input_data, target):\n    lo, hi = target["lo"], target["hi"]\n    records = [{"x": x, "fx": x**2, "ok": lo <= x**2 <= hi} for x in (input_data or [])]\n    sufficient = bool(records) and all(r["ok"] for r in records)\n    return {"evidence": records, "sufficient": sufficient, "summary": f"{len(records)} samples ok={sufficient}", "records": records}'
      : 'def run(input_data, target):\n    return {"evidence": {"input": input_data, "target": target}, "sufficient": True, "summary": "ok", "records": []}';
  }

  get compCodeLabel(): string {
    return this.computationLanguage === 'mpi' ? 'Código MPI (Python + mpi4py)' : 'Código Python';
  }

  @HostListener('window:mouseup')
  onWindowMouseUp() {
    this.isResizing = false;
    this.stopGraphPan();
  }

  @HostListener('window:mousemove', ['$event'])
  onWindowMouseMove(e: MouseEvent) {
    if (!this.isResizing) return;
    const delta = this.resizeStartX - e.clientX;
    this.sidebarWidth = Math.max(280, Math.min(720, this.resizeStartWidth + delta));
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

  dismissToast(id: number): void {
    this.toasts = this.toasts.filter(t => t.id !== id);
  }

  private _toastType(msg: string): 'info' | 'success' | 'error' {
    const low = msg.toLowerCase();
    if (/error|no se pudo|fall|inv[aá]lid|expir|no hay/.test(low)) return 'error';
    if (/exit|enviado|mergeado|cargado|creado|validado|terminada|cre[oó]|solve/.test(low)) return 'success';
    return 'info';
  }

  startResize(e: MouseEvent): void {
    this.isResizing = true;
    this.resizeStartX = e.clientX;
    this.resizeStartWidth = this.sidebarWidth;
    e.preventDefault();
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

  private loadGraph(reloadSelectedFile = true, silent = false) {
    this.taskService.getSimpleGraph(this.projectId).subscribe({
      next: (response) => {
        this.projectName = response.project_name || this.projectName;
        this.isProjectOwner = response.is_owner === true;
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

        if (!silent) {
          this.status = `Grafo cargado: ${this.nodes.length} nodos.`;
        }
      },
      error: (error) => {
        if (this.handleAuthError(error)) {
          return;
        }
        if (!silent) {
          this.status = this.getBackendErrorMessage(error) || 'No se pudo cargar el grafo.';
        }
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
    this.lastResultSource = '';
    this.isNodeFileLoading = true;
    this.texViewMode = 'source';
    this.activeAction = null;
    this.texNodeId$.next(this.activeTab === 'tex' ? node.id : null);
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
    if (!this.selectedNode || this.isBlocked) {
      return;
    }
    this.isVerifying = true;
    this.lastResultSource = 'Verificación';
    this.status = 'Verificando nodo/import tree...';
    this.taskService.verifyNode(this.projectId, this.selectedNode.id).subscribe({
      next: (response: VerifyNodeResponse) => {
        this.isVerifying = false;
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
        this.isVerifying = false;
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

  submitSolve(code?: string) {
    if (!this.selectedNode || this.isComputationNode || this.isBlocked) {
      return;
    }
    if (!this.solveModelId) {
      this.status = 'Debes seleccionar un modelo para Resolver (necesario para generar el .tex).';
      return;
    }
    const leanPayload = (code ?? this.leanCode).trim();
    if (!leanPayload) return;
    const apiKey = !this.solveMaskedKey ? (this.solveApiKeyInput.trim() || undefined) : undefined;
    this.isActionRunning = true;
    this.lastResultSource = 'Resolver (Lean)';
    this.status = 'Verificando código Lean…';
    // Lean compilation typically finishes in ~10–20 s; after that the backend
    // moves to FL→NL tex generation which can take up to 2 min.
    const texPhaseTimer = setTimeout(() => {
      if (this.isActionRunning) {
        this.status = 'Compilación Lean correcta. Generando archivo .tex…';
      }
    }, 20000);
    this.taskService.solveNode(this.projectId, this.selectedNode.id, leanPayload, this.solveModelId, apiKey).subscribe({
      next: (response) => {
        clearTimeout(texPhaseTimer);
        this.isActionRunning = false;
        this.lastResponse = response;
        const backendStatus = (response as { status?: string } | null)?.status;
        if (backendStatus === 'already_solved') {
          this.status = 'Solve validado. No hubo cambios en archivo, se guardo estado en la base de datos.';
          this.loadGraph();
          this.loadOpenPulls();
          return;
        }
        this.status = 'Solve enviado con .tex actualizado. Se creó un PR.';
        this.loadOpenPulls();
      },
      error: (error) => {
        clearTimeout(texPhaseTimer);
        this.isActionRunning = false;
        if (this.handleAuthError(error)) {
          this.lastResponse = error?.error || error;
          return;
        }
        this.lastResponse = error?.error || error;
        this.status = this.getBackendErrorMessage(error) || 'Solve con error.';
      }
    });
  }

  submitSplit(code?: string) {
    if (!this.selectedNode || this.isComputationNode || this.isBlocked) {
      return;
    }
    if (!this.splitModelId) {
      this.status = 'Debes seleccionar un modelo para Dividir (necesario para generar los .tex).';
      return;
    }
    const leanPayload = (code ?? this.leanCode).trim();
    if (!leanPayload) return;
    const apiKey = !this.splitMaskedKey ? (this.splitApiKeyInput.trim() || undefined) : undefined;
    this.isActionRunning = true;
    this.lastResultSource = 'Dividir (Lean)';
    this.status = 'Verificando código Lean…';
    const texPhaseTimer = setTimeout(() => {
      if (this.isActionRunning) {
        this.status = 'Compilación Lean correcta. Generando archivos .tex para nodo padre e hijos…';
      }
    }, 20000);
    this.taskService.splitNode(this.projectId, this.selectedNode.id, leanPayload, this.splitModelId, apiKey).subscribe({
      next: (response) => {
        clearTimeout(texPhaseTimer);
        this.isActionRunning = false;
        this.lastResponse = response;
        const created = (response as { created_lemmas?: string[] } | null)?.created_lemmas ?? [];
        this.status = `Split enviado con .tex actualizados (padre + ${created.length} hijo${created.length !== 1 ? 's' : ''}). Se creó un PR.`;
        this.loadOpenPulls();
      },
      error: (error) => {
        clearTimeout(texPhaseTimer);
        this.isActionRunning = false;
        if (this.handleAuthError(error)) {
          this.lastResponse = error?.error || error;
          return;
        }
        this.lastResponse = error?.error || error;
        this.status = this.getBackendErrorMessage(error) || 'Split con error.';
      }
    });
  }

  createComputationChildNode() {
    if (!this.selectedNode || this.isComputationNode || this.isBlocked) return;
    if (!this.createComputeModelId) {
      this.status = 'Debes seleccionar un modelo para generar el archivo .tex del nodo.';
      return;
    }
    this.isActionRunning = true;
    this.createComputePhase = 'Creando nodo de computación…';
    this.status = 'Creando nodo de computacion...';

    const apiKey = !this.createComputeMaskedKey ? (this.createComputeApiKeyInput.trim() || undefined) : undefined;

    this.taskService.createComputationChildNode(this.projectId, this.selectedNode.id, {
      model_id: this.createComputeModelId,
      ...(apiKey ? { api_key: apiKey } : {}),
    }).subscribe({
      next: (response) => {
        this.isActionRunning = false;
        this.createComputePhase = '';
        this.lastResponse = response;
        this.status = 'Solicitud de creación enviada. Se creó un PR para el nuevo nodo de computación.';
        this.loadGraph(false);
        this.loadOpenPulls();
      },
      error: (error) => {
        this.isActionRunning = false;
        this.createComputePhase = '';
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
    if (!this.selectedNode || !this.isComputationNode || this.isBlocked || !this.computationCode.trim() || !this.computationLeanStatement.trim()) {
      return;
    }

    const parsedTarget = this.safeParseJson(this.computationTargetJson);
    if (!parsedTarget || typeof parsedTarget !== 'object' || Array.isArray(parsedTarget)) {
      this.status = 'El campo target debe ser un JSON objeto valido.';
      return;
    }

    const parsedInput = this.safeParseJson(this.computationInputJson);

    this.isActionRunning = true;
    this.lastResultSource = 'Ejecutar Computación';
    this.status = 'Enviando computacion...';
    const computeApiKey = !this.computeMaskedKey ? (this.computeApiKeyInput.trim() || undefined) : undefined;
    this.taskService.computeNode(this.projectId, this.selectedNode.id, {
      language: this.computationLanguage,
      code: this.computationCode,
      entrypoint: this.computationEntrypoint.trim() || 'run',
      input_data: parsedInput,
      target: parsedTarget as Record<string, unknown>,
      lean_statement: this.computationLeanStatement.trim(),
      timeout_seconds: this.computationTimeoutSeconds,
      ...(this.computeModelId ? { model_id: this.computeModelId } : {}),
      ...(this.computeModelId && computeApiKey ? { api_key: computeApiKey } : {}),
    }).subscribe({
      next: (response) => {
        this.isActionRunning = false;
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
        this.isActionRunning = false;
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

  discardPullRequest(pr: PullRequestItem) {
    this.status = `Descartando PR #${pr.number}...`;
    this.taskService.closePullRequest(this.projectId, pr.number).subscribe({
      next: (response) => {
        this.lastResponse = response;
        this.status = `PR #${pr.number} descartado.`;
        this.prExpandedMap.delete(pr.number);
        this.prFilesMap.delete(pr.number);
        this.prTexViewMap.delete(pr.number);
        this.loadOpenPulls();
      },
      error: (error) => {
        if (this.handleAuthError(error)) {
          this.lastResponse = error?.error || error;
          return;
        }
        this.lastResponse = error?.error || error;
        this.status = `No se pudo descartar PR #${pr.number}.`;
      }
    });
  }

  togglePrExpand(pr: PullRequestItem) {
    const expanded = !this.prExpandedMap.get(pr.number);
    this.prExpandedMap.set(pr.number, expanded);
    if (expanded && !this.prFilesMap.has(pr.number)) {
      this.loadPrFiles(pr);
    }
  }

  private loadPrFiles(pr: PullRequestItem) {
    this.prFilesLoadingMap.set(pr.number, true);
    this.taskService.getPullRequestFiles(this.projectId, pr.number).subscribe({
      next: (res) => {
        console.debug('[PR files] raw response:', JSON.stringify(res, null, 2));
        this.prFilesMap.set(pr.number, res.files || []);
        this.prFilesLoadingMap.set(pr.number, false);
      },
      error: (err) => {
        console.error('[PR files] error:', err);
        this.prFilesMap.set(pr.number, []);
        this.prFilesLoadingMap.set(pr.number, false);
      }
    });
  }

  getTexViewMode(prNumber: number, filename: string): 'source' | 'rendered' {
    return this.prTexViewMap.get(prNumber)?.get(filename) ?? 'source';
  }

  togglePrFileTexView(prNumber: number, filename: string) {
    if (!this.prTexViewMap.has(prNumber)) {
      this.prTexViewMap.set(prNumber, new Map());
    }
    const m = this.prTexViewMap.get(prNumber)!;
    m.set(filename, m.get(filename) === 'rendered' ? 'source' : 'rendered');
  }

  renderPrFileContent(content: string): SafeHtml {
    return this._renderTexHtml(content);
  }

  isPrFileCollapsed(prNumber: number, filename: string): boolean {
    return this.prFileCollapsedMap.get(prNumber)?.has(filename) ?? false;
  }

  togglePrFileCollapse(prNumber: number, filename: string) {
    if (!this.prFileCollapsedMap.has(prNumber)) {
      this.prFileCollapsedMap.set(prNumber, new Set());
    }
    const s = this.prFileCollapsedMap.get(prNumber)!;
    if (s.has(filename)) { s.delete(filename); } else { s.add(filename); }
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

  setActiveAction(action: 'solve' | 'split' | 'compute' | 'ai-auto' | 'create-computation'): void {
    this.activeAction = this.activeAction === action ? null : action;
    if (this.activeAction) {
      this.actionLeanCode = this.leanCode;
    }
  }

  onSolveModelChange(): void {
    this.solveMaskedKey = null;
    this.solveApiKeyError = '';
    if (!this.solveModelId) return;
    this.taskService.getApiKeyStatus(this.solveModelId).subscribe({
      next: s => { this.solveMaskedKey = s.has_key ? s.masked_key : null; },
      error: () => { this.solveMaskedKey = null; },
    });
  }

  saveSolveApiKey(): void {
    if (!this.solveApiKeyInput.trim() || !this.solveModelId) return;
    this.solveApiKeySaving = true;
    this.solveApiKeyError = '';
    this.taskService.saveApiKey(this.solveModelId, this.solveApiKeyInput).subscribe({
      next: status => { this.solveMaskedKey = status.masked_key; this.solveApiKeyInput = ''; this.solveApiKeySaving = false; },
      error: err => { this.solveApiKeyError = err?.error?.error ?? 'Error al guardar la clave.'; this.solveApiKeySaving = false; },
    });
  }

  onSplitModelChange(): void {
    this.splitMaskedKey = null;
    this.splitApiKeyError = '';
    if (!this.splitModelId) return;
    this.taskService.getApiKeyStatus(this.splitModelId).subscribe({
      next: s => { this.splitMaskedKey = s.has_key ? s.masked_key : null; },
      error: () => { this.splitMaskedKey = null; },
    });
  }

  saveSplitApiKey(): void {
    if (!this.splitApiKeyInput.trim() || !this.splitModelId) return;
    this.splitApiKeySaving = true;
    this.splitApiKeyError = '';
    this.taskService.saveApiKey(this.splitModelId, this.splitApiKeyInput).subscribe({
      next: status => { this.splitMaskedKey = status.masked_key; this.splitApiKeyInput = ''; this.splitApiKeySaving = false; },
      error: err => { this.splitApiKeyError = err?.error?.error ?? 'Error al guardar la clave.'; this.splitApiKeySaving = false; },
    });
  }

  onNlSolveModelChange(): void {
    this.nlSolveMaskedKey = null;
    this.nlSolveApiKeyError = '';
    if (!this.nlSolveModelId) return;
    this.taskService.getApiKeyStatus(this.nlSolveModelId).subscribe({
      next: s => { this.nlSolveMaskedKey = s.has_key ? s.masked_key : null; },
      error: () => { this.nlSolveMaskedKey = null; },
    });
  }

  saveNlSolveApiKey(): void {
    if (!this.nlSolveApiKeyInput.trim() || !this.nlSolveModelId) return;
    this.nlSolveApiKeySaving = true;
    this.nlSolveApiKeyError = '';
    this.taskService.saveApiKey(this.nlSolveModelId, this.nlSolveApiKeyInput).subscribe({
      next: status => { this.nlSolveMaskedKey = status.masked_key; this.nlSolveApiKeyInput = ''; this.nlSolveApiKeySaving = false; },
      error: err => { this.nlSolveApiKeyError = err?.error?.error ?? 'Error al guardar la clave.'; this.nlSolveApiKeySaving = false; },
    });
  }

  onNlSolveTextChange(): void {
    if (this.nlSolveShowPreview) this.nlSolveRendered = this._renderTexHtml(this.nlSolveText);
  }

  toggleNlSolvePreview(): void {
    this.nlSolveShowPreview = !this.nlSolveShowPreview;
    if (this.nlSolveShowPreview) this.nlSolveRendered = this._renderTexHtml(this.nlSolveText);
  }

  onNlSplitModelChange(): void {
    this.nlSplitMaskedKey = null;
    this.nlSplitApiKeyError = '';
    if (!this.nlSplitModelId) return;
    this.taskService.getApiKeyStatus(this.nlSplitModelId).subscribe({
      next: s => { this.nlSplitMaskedKey = s.has_key ? s.masked_key : null; },
      error: () => { this.nlSplitMaskedKey = null; },
    });
  }

  saveNlSplitApiKey(): void {
    if (!this.nlSplitApiKeyInput.trim() || !this.nlSplitModelId) return;
    this.nlSplitApiKeySaving = true;
    this.nlSplitApiKeyError = '';
    this.taskService.saveApiKey(this.nlSplitModelId, this.nlSplitApiKeyInput).subscribe({
      next: status => { this.nlSplitMaskedKey = status.masked_key; this.nlSplitApiKeyInput = ''; this.nlSplitApiKeySaving = false; },
      error: err => { this.nlSplitApiKeyError = err?.error?.error ?? 'Error al guardar la clave.'; this.nlSplitApiKeySaving = false; },
    });
  }

  onNlSplitTextChange(): void {
    if (this.nlSplitShowPreview) this.nlSplitRendered = this._renderTexHtml(this.nlSplitText);
  }

  toggleNlSplitPreview(): void {
    this.nlSplitShowPreview = !this.nlSplitShowPreview;
    if (this.nlSplitShowPreview) this.nlSplitRendered = this._renderTexHtml(this.nlSplitText);
  }

  onAiAutoModelChange(): void {
    this.aiAutoMaskedKey = null;
    this.aiAutoApiKeyError = '';
    if (!this.aiAutoModelId) return;
    this.taskService.getApiKeyStatus(this.aiAutoModelId).subscribe({
      next: s => { this.aiAutoMaskedKey = s.has_key ? s.masked_key : null; },
      error: () => { this.aiAutoMaskedKey = null; },
    });
  }

  saveAiAutoApiKey(): void {
    if (!this.aiAutoApiKeyInput.trim() || !this.aiAutoModelId) return;
    this.aiAutoApiKeySaving = true;
    this.aiAutoApiKeyError = '';
    this.taskService.saveApiKey(this.aiAutoModelId, this.aiAutoApiKeyInput).subscribe({
      next: status => { this.aiAutoMaskedKey = status.masked_key; this.aiAutoApiKeyInput = ''; this.aiAutoApiKeySaving = false; },
      error: err => { this.aiAutoApiKeyError = err?.error?.error ?? 'Error al guardar la clave.'; this.aiAutoApiKeySaving = false; },
    });
  }

  onCreateComputeModelChange(): void {
    this.createComputeMaskedKey = null;
    this.createComputeApiKeyError = '';
    if (!this.createComputeModelId) return;
    this.taskService.getApiKeyStatus(this.createComputeModelId).subscribe({
      next: s => { this.createComputeMaskedKey = s.has_key ? s.masked_key : null; },
      error: () => { this.createComputeMaskedKey = null; },
    });
  }

  saveCreateComputeApiKey(): void {
    if (!this.createComputeApiKeyInput.trim() || !this.createComputeModelId) return;
    this.createComputeApiKeySaving = true;
    this.createComputeApiKeyError = '';
    this.taskService.saveApiKey(this.createComputeModelId, this.createComputeApiKeyInput).subscribe({
      next: status => { this.createComputeMaskedKey = status.masked_key; this.createComputeApiKeyInput = ''; this.createComputeApiKeySaving = false; },
      error: err => { this.createComputeApiKeyError = err?.error?.error ?? 'Error al guardar la clave.'; this.createComputeApiKeySaving = false; },
    });
  }

  onComputeModelChange(): void {
    this.computeMaskedKey = null;
    this.computeApiKeyError = '';
    if (!this.computeModelId) return;
    this.taskService.getApiKeyStatus(this.computeModelId).subscribe({
      next: s => { this.computeMaskedKey = s.has_key ? s.masked_key : null; },
      error: () => { this.computeMaskedKey = null; },
    });
  }

  saveComputeApiKey(): void {
    if (!this.computeApiKeyInput.trim() || !this.computeModelId) return;
    this.computeApiKeySaving = true;
    this.computeApiKeyError = '';
    this.taskService.saveApiKey(this.computeModelId, this.computeApiKeyInput).subscribe({
      next: status => { this.computeMaskedKey = status.masked_key; this.computeApiKeyInput = ''; this.computeApiKeySaving = false; },
      error: err => { this.computeApiKeyError = err?.error?.error ?? 'Error al guardar la clave.'; this.computeApiKeySaving = false; },
    });
  }

  // ── NL Solve pipeline (Resolver / Lenguaje Natural) ─────────────────────

  submitNlSolve(): void {
    if (!this.selectedNode || this.isComputationNode || this.isBlocked) return;
    if (!this.nlSolveModelId) {
      this.status = 'Debes seleccionar un modelo para la traducción NL→FL.';
      return;
    }
    const text = this.nlSolveText.trim();
    if (!text) {
      this.status = 'Escribe la descripción en lenguaje natural del enunciado que quieres resolver.';
      return;
    }

    const apiKey = !this.nlSolveMaskedKey ? (this.nlSolveApiKeyInput.trim() || undefined) : undefined;
    this.isActionRunning = true;
    this.lastResultSource = 'Resolver (NL)';
    this.nlSolvePhase = 'Cargando contexto del nodo…';
    this.status = 'Resolver NL: cargando contexto del nodo…';

    const nodeId = this.selectedNode.id;
    // Fetch .tex, current .lean (already in memory), and Definitions.lean in parallel
    forkJoin({
      tex: this.taskService.getNodeTexFile(this.projectId, nodeId).pipe(
        catchError(() => of({ content: '', path: '' }))
      ),
      defs: this.taskService.getProjectDefinitions(this.projectId).pipe(
        catchError(() => of({ content: '', path: '' }))
      ),
    }).subscribe(({ tex, defs }) => {
      const texContent = tex.content?.trim() || '';
      const leanContent = this.leanCode?.trim() || '';
      const defsContent = defs.content?.trim() || '';

      // Build context included in the prompt so the model can preserve
      // theorem name, imports, and the LaTeX statement being proved.
      const contextParts: string[] = [];
      if (texContent) contextParts.push(`=== Current .tex (LaTeX theorem statement) ===\n${texContent}`);
      if (leanContent) contextParts.push(`=== Current .lean (use the same theorem name and imports) ===\n${leanContent}`);
      const context = contextParts.join('\n\n');

      const nl2flSystemPrompt =
        'You are an expert in Lean 4 formal mathematics. Transcribe the following natural language mathematical statement into a Lean 4 proof. ' +
        'The context section contains the existing .tex statement and the current .lean skeleton for this node — ' +
        'you MUST use the exact same theorem name and keep all existing imports from the .lean skeleton. ' +
        'Always write `import Definitions` (never `import Mathlib` directly) when the skeleton uses it. ' +
        'Break the input into goal and proof steps, translate each to Lean 4 and integrate them. ' +
        'Make it fast and precise, you only have 3 minutes to answer. Reply ONLY with a single ' +
        '```lean code block and nothing else.';

      this.nlSolvePhase = 'Traduciendo a Lean (NL→FL)…';
      this.status = 'Resolver NL: traduciendo a Lean…';

      const fullPrompt = context
        ? `${text}\n\n${context}`
        : text;

      const payload: TranslatePayload = {
        natural_text: fullPrompt,
        model_id: this.nlSolveModelId,
        ...(apiKey ? { api_key: apiKey } : {}),
        max_retries: 3,
        system_prompt: nl2flSystemPrompt,
        ...(defsContent ? { definitions_content: defsContent } : {}),
      };
      this.taskService.submitTranslation(payload).subscribe({
        next: ({ task_id }) => this._pollNlSolveFl(task_id, apiKey),
        error: err => this._nlSolveError(err, 'Error al enviar al traductor NL→FL.'),
      });
    });
  }

  private _pollNlSolveFl(taskId: string, apiKey: string | undefined): void {
    this._pollResult<TranslationResult>(
      taskId,
      id => this.taskService.getTranslationResult(id),
      result => {
        if (!result.valid || !result.final_lean?.trim()) {
          this._nlSolveError(null,
            `NL→FL no pudo generar Lean válido tras ${result.attempts} intento(s).`);
          return;
        }
        this.nlSolvePhase = 'Verificando Lean y generando .tex…';
        this.status = 'Resolver NL: verificando Lean y generando .tex…';
        this._nlRunSolve(result.final_lean.trim(), apiKey);
      },
      err => this._nlSolveError(err, 'Error en la traducción NL→FL.'),
    );
  }

  private _nlRunSolve(leanCode: string, apiKey: string | undefined): void {
    if (!this.selectedNode) { this._nlSolveError(null, 'Nodo no seleccionado.'); return; }

    const texPhaseTimer = setTimeout(() => {
      if (this.isActionRunning) {
        this.nlSolvePhase = 'Compilación Lean correcta. Generando .tex…';
        this.status = 'Resolver NL: compilación Lean correcta. Generando .tex…';
      }
    }, 20000);

    this.taskService.solveNode(
      this.projectId, this.selectedNode.id, leanCode, this.nlSolveModelId, apiKey
    ).subscribe({
      next: response => {
        clearTimeout(texPhaseTimer);
        this.isActionRunning = false;
        this.nlSolvePhase = '';
        this.lastResponse = response;
        const backendStatus = (response as { status?: string } | null)?.status;
        if (backendStatus === 'already_solved') {
          this.status = 'Resolver NL completado. El nodo ya estaba resuelto (sin cambios).';
          this.loadGraph();
          this.loadOpenPulls();
          return;
        }
        this.status = 'Resolver NL completado. Se generó el .tex y se creó un PR.';
        this.loadOpenPulls();
      },
      error: err => {
        clearTimeout(texPhaseTimer);
        this._nlSolveError(err, 'Error al verificar y crear PR.');
      },
    });
  }

  private _nlSolveError(error: any, fallback: string): void {
    this.isActionRunning = false;
    this.nlSolvePhase = '';
    if (error && this.handleAuthError(error)) {
      this.lastResponse = error?.error || error;
      return;
    }
    if (error) this.lastResponse = error?.error || error;
    this.status = this.getBackendErrorMessage(error) || fallback;
  }

  // ── IA Auto pipeline ─────────────────────────────────────────────────────

  submitAiAuto(): void {
    if (!this.selectedNode || this.isComputationNode || this.isBlocked) return;
    if (!this.aiAutoModelId) {
      this.status = 'Debes seleccionar un modelo para IA Auto.';
      return;
    }

    const nodeId = this.selectedNode.id;
    const apiKey = !this.aiAutoMaskedKey ? (this.aiAutoApiKeyInput.trim() || undefined) : undefined;

    this.isActionRunning = true;
    this.lastResultSource = 'IA Auto';
    this.aiAutoPhase = 'Consultando IA…';
    this.status = 'IA Auto: consultando modelo…';

    // Load the node's .tex as context; fall back to the Lean source if unavailable.
    // Fetch .tex (agent context) and Definitions.lean (NL2FL verification) in parallel
    forkJoin({
      tex: this.taskService.getNodeTexFile(this.projectId, nodeId).pipe(
        catchError(() => of({ content: '', path: '' }))
      ),
      defs: this.taskService.getProjectDefinitions(this.projectId).pipe(
        catchError(() => of({ content: '', path: '' }))
      ),
    }).subscribe(({ tex, defs }) => {
      const texContent = tex.content?.trim() || '';
      const leanContent = this.leanCode?.trim() || '';
      const defsContent = defs.content?.trim() || '';
      // Agent gets the .tex as context so its suggestion is theorem-aware
      const agentContext = texContent || leanContent;

      const systemPrompt =
        'You are a mathematical proof assistant. ' +
        'Given a theorem (provided as context), describe ONE direct proof strategy in no more than 5 sentences. ' +
        'Write only the mathematical argument itself — no Lean or Mathlib references, ' +
        'no alternative approaches, no historical background, no notation explanations.';

      const suggestPayload: SuggestPayload = {
        prompt: this.aiAutoPrompt.trim() || 'Suggest a proof strategy for this theorem.',
        model_id: this.aiAutoModelId,
        ...(apiKey ? { api_key: apiKey } : {}),
        system_prompt: systemPrompt,
        context: agentContext,
      };

      this.taskService.submitSuggest(suggestPayload).subscribe({
        next: ({ task_id }) => this._pollAiSuggest(task_id, apiKey, texContent, leanContent, defsContent),
        error: err => this._aiAutoError(err, 'Error al enviar solicitud a la IA.'),
      });
    });
  }

  private _pollAiSuggest(
    taskId: string, apiKey: string | undefined,
    texContent: string, leanContent: string, defsContent: string,
  ): void {
    this._pollResult<SuggestResult>(
      taskId,
      id => this.taskService.getSuggestResult(id),
      result => {
        this.aiAutoPhase = 'Traduciendo estrategia a Lean (NL→FL)…';
        this.status = 'IA Auto: traduciendo estrategia a Lean…';
        this._aiAutoRunNl2fl(result.suggestion, apiKey, texContent, leanContent, defsContent);
      },
      err => this._aiAutoError(err, 'Error en la consulta a la IA.'),
    );
  }

  private _aiAutoRunNl2fl(
    naturalText: string, apiKey: string | undefined,
    texContent: string, leanContent: string, defsContent: string,
  ): void {
    const contextParts: string[] = [];
    if (texContent) contextParts.push(`=== Current .tex (LaTeX theorem statement) ===\n${texContent}`);
    if (leanContent) contextParts.push(`=== Current .lean (use the same theorem name and imports) ===\n${leanContent}`);
    const context = contextParts.join('\n\n');

    const nl2flSystemPrompt =
      'You are an expert in Lean 4 formal mathematics. Transcribe the following natural language mathematical statement into a Lean 4 proof. ' +
      'The context section contains the existing .tex statement and the current .lean skeleton for this node — ' +
      'you MUST use the exact same theorem name and keep all existing imports from the .lean skeleton. ' +
      'Always write `import Definitions` (never `import Mathlib` directly) when the skeleton uses it. ' +
      'Break the input into goal and proof steps, translate each to Lean 4 and integrate them. ' +
      'Make it fast and precise, you only have 3 minutes to answer. Reply ONLY with a single ' +
      '```lean code block and nothing else.';

    const fullPrompt = context ? `${naturalText}\n\n${context}` : naturalText;

    const payload: TranslatePayload = {
      natural_text: fullPrompt,
      model_id: this.aiAutoModelId,
      ...(apiKey ? { api_key: apiKey } : {}),
      max_retries: 3,
      system_prompt: nl2flSystemPrompt,
      ...(defsContent ? { definitions_content: defsContent } : {}),
    };
    this.taskService.submitTranslation(payload).subscribe({
      next: ({ task_id }) => this._pollAiNl2fl(task_id, apiKey),
      error: err => this._aiAutoError(err, 'Error al enviar al traductor NL→FL.'),
    });
  }

  private _pollAiNl2fl(taskId: string, apiKey: string | undefined): void {
    this._pollResult<TranslationResult>(
      taskId,
      id => this.taskService.getTranslationResult(id),
      result => {
        if (!result.valid || !result.final_lean?.trim()) {
          this._aiAutoError(null,
            `NL→FL no pudo generar Lean válido tras ${result.attempts} intento(s).`);
          return;
        }
        this.aiAutoPhase = 'Verificando Lean y generando .tex…';
        this.status = 'IA Auto: verificando Lean y generando .tex…';
        this._aiAutoRunSolve(result.final_lean.trim(), apiKey);
      },
      err => this._aiAutoError(err, 'Error en la traducción NL→FL.'),
    );
  }

  private _aiAutoRunSolve(leanCode: string, apiKey: string | undefined): void {
    if (!this.selectedNode) { this._aiAutoError(null, 'Nodo no seleccionado.'); return; }

    const texPhaseTimer = setTimeout(() => {
      if (this.isActionRunning) {
        this.aiAutoPhase = 'Compilación Lean correcta. Generando .tex…';
        this.status = 'IA Auto: compilación Lean correcta. Generando .tex…';
      }
    }, 20000);

    this.taskService.solveNode(
      this.projectId, this.selectedNode.id, leanCode, this.aiAutoModelId, apiKey
    ).subscribe({
      next: response => {
        clearTimeout(texPhaseTimer);
        this.isActionRunning = false;
        this.aiAutoPhase = '';
        this.lastResponse = response;
        const backendStatus = (response as { status?: string } | null)?.status;
        if (backendStatus === 'already_solved') {
          this.status = 'IA Auto completado. El nodo ya estaba resuelto (sin cambios).';
          this.loadGraph();
          this.loadOpenPulls();
          return;
        }
        this.status = 'IA Auto completado. Se generó el .tex y se creó un PR.';
        this.loadOpenPulls();
      },
      error: err => {
        clearTimeout(texPhaseTimer);
        this._aiAutoError(err, 'Error al verificar y crear PR.');
      },
    });
  }

  private _aiAutoError(error: any, fallback: string): void {
    this.isActionRunning = false;
    this.aiAutoPhase = '';
    if (error && this.handleAuthError(error)) {
      this.lastResponse = error?.error || error;
      return;
    }
    if (error) this.lastResponse = error?.error || error;
    this.status = this.getBackendErrorMessage(error) || fallback;
  }

  // ── NL Split pipeline (Dividir / Lenguaje Natural) ──────────────────────

  submitNlSplit(): void {
    if (!this.selectedNode || this.isComputationNode || this.isBlocked) return;
    if (!this.nlSplitModelId) {
      this.status = 'Debes seleccionar un modelo para la traducción NL→FL.';
      return;
    }
    const text = this.nlSplitText.trim();
    if (!text) {
      this.status = 'Describe cómo quieres dividir el teorema en lenguaje natural.';
      return;
    }

    const apiKey = !this.nlSplitMaskedKey ? (this.nlSplitApiKeyInput.trim() || undefined) : undefined;
    this.isActionRunning = true;
    this.lastResultSource = 'Dividir (NL)';
    this.nlSplitPhase = 'Cargando contexto del nodo…';
    this.status = 'Dividir NL: cargando contexto del nodo…';

    const nodeId = this.selectedNode.id;
    forkJoin({
      tex: this.taskService.getNodeTexFile(this.projectId, nodeId).pipe(
        catchError(() => of({ content: '', path: '' }))
      ),
      defs: this.taskService.getProjectDefinitions(this.projectId).pipe(
        catchError(() => of({ content: '', path: '' }))
      ),
    }).subscribe(({ tex, defs }) => {
      const texContent = tex.content?.trim() || '';
      const leanContent = this.leanCode?.trim() || '';
      const defsContent = defs.content?.trim() || '';

      const contextParts: string[] = [];
      if (texContent) contextParts.push(`=== Current .tex (LaTeX theorem statement) ===\n${texContent}`);
      if (leanContent) contextParts.push(`=== Current .lean (root theorem skeleton — use the same theorem name and imports) ===\n${leanContent}`);
      const context = contextParts.join('\n\n');

      const nl2flSystemPrompt =
        'You are an expert in Lean 4 formal mathematics. ' +
        'Given a description of how to split a theorem into sub-goals, produce a single Lean 4 file that: ' +
        '1. Keeps the root theorem with exactly the same name and statement as in the current .lean skeleton. ' +
        '2. Introduces one or more helper lemmas (each proved by `sorry`). ' +
        '3. CRITICAL: the root theorem proof body MUST call every defined lemma by name directly — ' +
        'no intermediate helper chains (e.g. lemmaA calls lemmaB which root calls lemmaA is NOT allowed); ' +
        'root must reference each lemma itself. Do NOT use `sorry` in the root proof body. ' +
        'Always write `import Definitions` (never `import Mathlib` directly) when the skeleton uses it. ' +
        'Use the exact same theorem name from the skeleton. ' +
        'Make it fast and precise, you only have 3 minutes to answer. Reply ONLY with a single ' +
        '```lean code block and nothing else.';

      this.nlSplitPhase = 'Traduciendo plan a Lean (NL→FL)…';
      this.status = 'Dividir NL: traduciendo plan a Lean…';

      const fullPrompt = context ? `${text}\n\n${context}` : text;

      const payload: TranslatePayload = {
        natural_text: fullPrompt,
        model_id: this.nlSplitModelId,
        ...(apiKey ? { api_key: apiKey } : {}),
        max_retries: 3,
        system_prompt: nl2flSystemPrompt,
        ...(defsContent ? { definitions_content: defsContent } : {}),
      };
      this.taskService.submitTranslation(payload).subscribe({
        next: ({ task_id }) => this._pollNlSplitFl(task_id, apiKey),
        error: err => this._nlSplitError(err, 'Error al enviar al traductor NL→FL.'),
      });
    });
  }

  private _pollNlSplitFl(taskId: string, apiKey: string | undefined): void {
    this._pollResult<TranslationResult>(
      taskId,
      id => this.taskService.getTranslationResult(id),
      result => {
        if (!result.valid || !result.final_lean?.trim()) {
          this._nlSplitError(null,
            `NL→FL no pudo generar Lean válido tras ${result.attempts} intento(s).`);
          return;
        }
        this.nlSplitPhase = 'Dividiendo y generando .tex…';
        this.status = 'Dividir NL: dividiendo y generando .tex…';
        this._nlRunSplit(result.final_lean.trim(), apiKey);
      },
      err => this._nlSplitError(err, 'Error en la traducción NL→FL.'),
    );
  }

  private _nlRunSplit(leanCode: string, apiKey: string | undefined): void {
    if (!this.selectedNode) { this._nlSplitError(null, 'Nodo no seleccionado.'); return; }

    const texPhaseTimer = setTimeout(() => {
      if (this.isActionRunning) {
        this.nlSplitPhase = 'Compilación Lean correcta. Generando .tex para padre e hijos…';
        this.status = 'Dividir NL: generando .tex…';
      }
    }, 20000);

    this.taskService.splitNode(
      this.projectId, this.selectedNode.id, leanCode, this.nlSplitModelId, apiKey
    ).subscribe({
      next: response => {
        clearTimeout(texPhaseTimer);
        this.isActionRunning = false;
        this.nlSplitPhase = '';
        this.lastResponse = response;
        const created = (response as { created_lemmas?: string[] } | null)?.created_lemmas ?? [];
        this.status = `Dividir NL completado. .tex generados (padre + ${created.length} hijo${created.length !== 1 ? 's' : ''}). Se creó un PR.`;
        this.loadOpenPulls();
      },
      error: err => {
        clearTimeout(texPhaseTimer);
        this._nlSplitError(err, 'Error al dividir y crear PR.');
      },
    });
  }

  private _nlSplitError(error: any, fallback: string): void {
    this.isActionRunning = false;
    this.nlSplitPhase = '';
    if (error && this.handleAuthError(error)) {
      this.lastResponse = error?.error || error;
      return;
    }
    if (error) this.lastResponse = error?.error || error;
    this.status = this.getBackendErrorMessage(error) || fallback;
  }

  // ── IA Auto (Dividir) pipeline ────────────────────────────────────────────

  submitAiSplit(): void {
    if (!this.selectedNode || this.isComputationNode || this.isBlocked) return;
    if (!this.aiAutoModelId) {
      this.status = 'Debes seleccionar un modelo para IA Auto.';
      return;
    }

    const nodeId = this.selectedNode.id;
    const apiKey = !this.aiAutoMaskedKey ? (this.aiAutoApiKeyInput.trim() || undefined) : undefined;

    this.isActionRunning = true;
    this.lastResultSource = 'IA Auto (Dividir)';
    this.aiAutoPhase = 'Consultando IA…';
    this.status = 'IA Auto Dividir: consultando modelo…';

    forkJoin({
      tex: this.taskService.getNodeTexFile(this.projectId, nodeId).pipe(
        catchError(() => of({ content: '', path: '' }))
      ),
      defs: this.taskService.getProjectDefinitions(this.projectId).pipe(
        catchError(() => of({ content: '', path: '' }))
      ),
    }).subscribe(({ tex, defs }) => {
      const texContent = tex.content?.trim() || '';
      const leanContent = this.leanCode?.trim() || '';
      const defsContent = defs.content?.trim() || '';
      const agentContext = texContent || leanContent;

      const systemPrompt =
        'You are a mathematical proof assistant. ' +
        'Given a theorem (provided as context), describe ONE way to split it into ' +
        'simpler sub-goals or helper lemmas that together prove the theorem. ' +
        'Write only the mathematical argument — no Lean or Mathlib references, ' +
        'no alternative approaches, no historical background, no notation explanations. ' +
        'State each sub-goal as a clear natural-language claim, then explain briefly how they combine. ' +
        'Only state the claims of sub-goals, the only argument needed is the original goal one.';

      const suggestPayload: SuggestPayload = {
        prompt: this.aiAutoPrompt.trim() || 'Suggest how to split this theorem into simpler sub-goals or lemmas.',
        model_id: this.aiAutoModelId,
        ...(apiKey ? { api_key: apiKey } : {}),
        system_prompt: systemPrompt,
        context: agentContext,
      };

      this.taskService.submitSuggest(suggestPayload).subscribe({
        next: ({ task_id }) => this._pollAiSplitSuggest(task_id, apiKey, texContent, leanContent, defsContent),
        error: err => this._aiAutoError(err, 'Error al enviar solicitud a la IA.'),
      });
    });
  }

  private _pollAiSplitSuggest(
    taskId: string, apiKey: string | undefined,
    texContent: string, leanContent: string, defsContent: string,
  ): void {
    this._pollResult<SuggestResult>(
      taskId,
      id => this.taskService.getSuggestResult(id),
      result => {
        this.aiAutoPhase = 'Traduciendo plan a Lean (NL→FL)…';
        this.status = 'IA Auto Dividir: traduciendo plan a Lean…';
        this._aiAutoSplitRunNl2fl(result.suggestion, apiKey, texContent, leanContent, defsContent);
      },
      err => this._aiAutoError(err, 'Error en la consulta a la IA.'),
    );
  }

  private _aiAutoSplitRunNl2fl(
    naturalText: string, apiKey: string | undefined,
    texContent: string, leanContent: string, defsContent: string,
  ): void {
    const contextParts: string[] = [];
    if (texContent) contextParts.push(`=== Current .tex (LaTeX theorem statement) ===\n${texContent}`);
    if (leanContent) contextParts.push(`=== Current .lean (root theorem skeleton — use the same theorem name and imports) ===\n${leanContent}`);
    const context = contextParts.join('\n\n');

    const nl2flSystemPrompt =
      'You are an expert in Lean 4 formal mathematics. ' +
      'Given a description of how to split a theorem into sub-goals, produce a single Lean 4 file that: ' +
      '1. Keeps the root theorem with exactly the same name and statement as in the current .lean skeleton. ' +
      '2. Introduces one or more helper lemmas (each proved by `sorry`). ' +
      '3. CRITICAL: the root theorem proof body MUST call every defined lemma by name directly — ' +
      'no intermediate helper chains (e.g. lemmaA calls lemmaB which root calls lemmaA is NOT allowed); ' +
      'root must reference each lemma itself. Do NOT use `sorry` in the root proof body. ' +
      'Always write `import Definitions` (never `import Mathlib` directly) when the skeleton uses it. ' +
      'Use the exact same theorem name from the skeleton. ' +
      'Make it fast and precise, you only have 3 minutes to answer. Reply ONLY with a single ' +
      '```lean code block and nothing else.';

    const fullPrompt = context ? `${naturalText}\n\n${context}` : naturalText;

    const payload: TranslatePayload = {
      natural_text: fullPrompt,
      model_id: this.aiAutoModelId,
      ...(apiKey ? { api_key: apiKey } : {}),
      max_retries: 3,
      system_prompt: nl2flSystemPrompt,
      ...(defsContent ? { definitions_content: defsContent } : {}),
    };
    this.taskService.submitTranslation(payload).subscribe({
      next: ({ task_id }) => this._pollAiSplitNl2fl(task_id, apiKey),
      error: err => this._aiAutoError(err, 'Error al enviar al traductor NL→FL.'),
    });
  }

  private _pollAiSplitNl2fl(taskId: string, apiKey: string | undefined): void {
    this._pollResult<TranslationResult>(
      taskId,
      id => this.taskService.getTranslationResult(id),
      result => {
        if (!result.valid || !result.final_lean?.trim()) {
          this._aiAutoError(null,
            `NL→FL no pudo generar Lean válido tras ${result.attempts} intento(s).`);
          return;
        }
        this.aiAutoPhase = 'Dividiendo y generando .tex…';
        this.status = 'IA Auto Dividir: dividiendo y generando .tex…';
        this._aiAutoRunSplit(result.final_lean.trim(), apiKey);
      },
      err => this._aiAutoError(err, 'Error en la traducción NL→FL.'),
    );
  }

  private _aiAutoRunSplit(leanCode: string, apiKey: string | undefined): void {
    if (!this.selectedNode) { this._aiAutoError(null, 'Nodo no seleccionado.'); return; }

    const texPhaseTimer = setTimeout(() => {
      if (this.isActionRunning) {
        this.aiAutoPhase = 'Compilación Lean correcta. Generando .tex para padre e hijos…';
        this.status = 'IA Auto Dividir: generando .tex…';
      }
    }, 20000);

    this.taskService.splitNode(
      this.projectId, this.selectedNode.id, leanCode, this.aiAutoModelId, apiKey
    ).subscribe({
      next: response => {
        clearTimeout(texPhaseTimer);
        this.isActionRunning = false;
        this.aiAutoPhase = '';
        this.lastResponse = response;
        const created = (response as { created_lemmas?: string[] } | null)?.created_lemmas ?? [];
        this.status = `IA Auto Dividir completado. .tex generados (padre + ${created.length} hijo${created.length !== 1 ? 's' : ''}). Se creó un PR.`;
        this.loadOpenPulls();
      },
      error: err => {
        clearTimeout(texPhaseTimer);
        this._aiAutoError(err, 'Error al dividir y crear PR.');
      },
    });
  }

  /**
   * Generic polling helper using RxJS timer.  Polls `getter(taskId)` every
   * `intervalMs` ms, skipping 'pending' responses, and completes on the first
   * non-pending result.  Errors out after `timeoutMs` (default 10 min) — the
   * same window used by the Translation page.
   */
  private _pollResult<T>(
    taskId: string,
    getter: (id: string) => Observable<T | { status: string }>,
    onDone: (result: T) => void,
    onError: (err: any) => void,
    intervalMs = 2500,
    timeoutMs = 600_000,
  ): void {
    timer(0, intervalMs).pipe(
      switchMap(() => getter(taskId)),
      filter(res => (res as { status?: string }).status !== 'pending'),
      take(1),
      timeout(timeoutMs),
    ).subscribe({
      next: res => {
        if (!this.isActionRunning) return;
        onDone(res as T);
      },
      error: err => onError(err),
    });
  }

  switchToTexPreview() {
    this.texViewMode = 'preview';
  }

  switchToTexTab() {
    this.activeTab = 'tex';
    if (this.selectedNode) {
      this.texNodeId$.next(this.selectedNode.id);
    }
  }

  private loadTexFile(nodeId: string) {
    // Loading is now handled reactively by texVm$ / texNodeId$.
    void nodeId;
  }

  private _renderTexHtml(src: string): SafeHtml {
    const text = src.trim();
    if (!text) {
      return this.sanitizer.bypassSecurityTrustHtml('<p class="tex-empty">Sin contenido para renderizar.</p>');
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const katex = (window as any)['katex'];
    if (!katex) {
      return this.sanitizer.bypassSecurityTrustHtml('<p>KaTeX no está disponible aún. Intenta de nuevo en un momento.</p>');
    }
    try {
      let body = text;
      const bodyMatch = body.match(/\\begin\{document\}([\s\S]*?)\\end\{document\}/);
      if (bodyMatch) { body = bodyMatch[1]; }

      const displayPlaceholders: string[] = [];
      body = body.replace(/\$\$([\s\S]*?)\$\$/g, (_, math) => {
        const idx = displayPlaceholders.length;
        try { displayPlaceholders.push('<div class="tex-display">' + katex.renderToString(math.trim(), { displayMode: true, throwOnError: false }) + '</div>'); }
        catch { displayPlaceholders.push(`<div class="tex-err">$$${this.escapeHtml(math)}$$</div>`); }
        return `\x00DISP${idx}\x00`;
      });
      body = body.replace(/\\\[([\s\S]*?)\\\]/g, (_, math) => {
        const idx = displayPlaceholders.length;
        try { displayPlaceholders.push('<div class="tex-display">' + katex.renderToString(math.trim(), { displayMode: true, throwOnError: false }) + '</div>'); }
        catch { displayPlaceholders.push(`<div class="tex-err">\\[${this.escapeHtml(math)}\\]</div>`); }
        return `\x00DISP${idx}\x00`;
      });
      const inlinePlaceholders: string[] = [];
      body = body.replace(/\$([^$\n]{1,300}?)\$/g, (_, math) => {
        const idx = inlinePlaceholders.length;
        try { inlinePlaceholders.push(katex.renderToString(math.trim(), { displayMode: false, throwOnError: false })); }
        catch { inlinePlaceholders.push(`$${this.escapeHtml(math)}$`); }
        return `\x00INLN${idx}\x00`;
      });
      body = this.escapeHtml(body);
      inlinePlaceholders.forEach((html, i) => { body = body.replace(`\x00INLN${i}\x00`, html); });
      displayPlaceholders.forEach((html, i) => { body = body.replace(`\x00DISP${i}\x00`, html); });
      // Bold/italic Markdown — applied after HTML escaping
      body = body.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
      body = body.replace(/\*([^*\n]+?)\*/g, '<em>$1</em>');
      body = body.replace(/\\section\{([^}]{1,120})\}/g, '<h2 class="tex-h2">$1</h2>');
      body = body.replace(/\\subsection\{([^}]{1,120})\}/g, '<h3 class="tex-h3">$1</h3>');
      body = body.replace(/\\subsubsection\{([^}]{1,120})\}/g, '<h4 class="tex-h4">$1</h4>');
      body = body.replace(/\\textbf\{([^}]{1,200})\}/g, '<strong>$1</strong>');
      body = body.replace(/\\textit\{([^}]{1,200})\}/g, '<em>$1</em>');
      body = body.replace(/\\emph\{([^}]{1,200})\}/g, '<em>$1</em>');
      body = body.replace(/\\texttt\{([^}]{1,200})\}/g, '<code>$1</code>');
      body = body.replace(/\\\\(\s*)/g, '<br>');
      body = body.replace(/\\newline/g, '<br>');
      body = body.replace(/\\begin\{itemize\}([\s\S]*?)\\end\{itemize\}/g, (_, c) => {
        const items = c.split('\\item').slice(1).map((s: string) => `<li>${s.trim()}</li>`).join('');
        return `<ul class="tex-list">${items}</ul>`;
      });
      body = body.replace(/\\begin\{enumerate\}([\s\S]*?)\\end\{enumerate\}/g, (_, c) => {
        const items = c.split('\\item').slice(1).map((s: string) => `<li>${s.trim()}</li>`).join('');
        return `<ol class="tex-list">${items}</ol>`;
      });
      body = body.replace(/\\[a-zA-Z]+(\*?)(\{[^}]*\}|\[[^\]]*\])*/g, '');
      body = body.replace(/[{}]/g, '');
      const paragraphs = body.split(/\n\n+/).map((p: string) => p.trim()).filter(Boolean);
      body = paragraphs.map((p: string) => {
        if (/^<(h[1-6]|div|ul|ol)/.test(p)) return p;
        return `<p>${p.replace(/\n/g, ' ')}</p>`;
      }).join('\n');
      return this.sanitizer.bypassSecurityTrustHtml(body);
    } catch {
      return this.sanitizer.bypassSecurityTrustHtml('<p>Error al renderizar el TeX.</p>');
    }
  }

  renderTexPreview() {
    // Rendering is now handled reactively inside texVm$.
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

      // loadOpenPulls() is intentionally excluded here: it calls api.github.com
      // on every tick and saturates the network. PRs are refreshed after explicit
      // user actions (merge, solve, split, compute) and on page load instead.
      this.loadGraph(false, true);
    }, 600000);
  }

  private stopAutoRefresh() {
    if (this.autoRefreshHandle) {
      clearInterval(this.autoRefreshHandle);
      this.autoRefreshHandle = null;
    }
  }
}
