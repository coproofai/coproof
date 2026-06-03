import {
  AfterViewInit,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  ElementRef,
  OnDestroy,
  ViewChild,
} from '@angular/core';
import { AsyncPipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Observable, Subject, Subscription, defer, of, timer } from 'rxjs';
import {
  catchError,
  filter,
  finalize,
  map,
  shareReplay,
  startWith,
  switchMap,
  take,
  timeout,
} from 'rxjs/operators';
import { TaskService } from '../../task.service';
import {
  AvailableModel,
  Fl2NlPayload,
  MathlibLineageEdge,
  MathlibLineageNode,
  MathlibLineageResult,
} from '../../task.models';
import { UserPreferencesService } from '../../user-preferences.service';

// ── Types ─────────────────────────────────────────────────────────────────────
type LineageState = 'idle' | 'loading' | 'done' | 'error';
type Fl2NlState   = 'idle' | 'translating' | 'done' | 'error';

interface LayoutNode extends MathlibLineageNode {
  x: number;
  y: number;
}

interface LineageVm {
  state: LineageState;
  root: string;
  totalNodes: number;
  truncated: boolean;
  processingTime: number;
  error: string;
}

interface Fl2NlVm {
  state: Fl2NlState;
  renderedHtml: SafeHtml;
  processingTime: number;
  error: string;
}

interface LineageRequest { name: string; depth: number; }
interface Fl2NlRequest   { leanCode: string; modelId: string; apiKey?: string; }

const IDLE_LINEAGE_VM: LineageVm = {
  state: 'idle', root: '', totalNodes: 0, truncated: false, processingTime: 0, error: '',
};
const IDLE_FL2NL_VM: Fl2NlVm = {
  state: 'idle', renderedHtml: '', processingTime: 0, error: '',
};

const FL2NL_SYSTEM_PROMPT =
  'You are an expert in formal mathematics and mathematical writing. ' +
  'Given one or more Lean 4 theorems (possibly with proofs), produce a structured mathematical exposition in natural language. ' +
  'For EACH theorem or lemma found in the input, output exactly the following structure:\n\n' +
  '**Theorem.** <state the mathematical claim clearly, using LaTeX notation ($...$ inline, $$...$$ display)>\n\n' +
  '*Proof.* <explain the proof strategy and key steps in natural language, using LaTeX where appropriate. ' +
  'If the proof body contains sorry or is otherwise left unsolved, write exactly "Unsolved." instead.>\n\n' +
  'Rules:\n' +
  '- Capture the mathematical ESSENCE and meaning of what the Lean statement expresses. Do NOT attempt to solve or prove anything.\n' +
  '- Do NOT reproduce any Lean 4 syntax in your output.\n' +
  '- Do NOT add commentary outside the Theorem/Proof blocks.\n' +
  '- If there are multiple theorems, repeat the Theorem/Proof block for each one in order.';

@Component({
  selector: 'app-lineage-search-page',
  standalone: true,
  imports: [FormsModule, AsyncPipe, DecimalPipe, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './lineage-search-page.html',
  styleUrl: './lineage-search-page.css',
})
export class LineageSearchPageComponent implements AfterViewInit, OnDestroy {
  @ViewChild('graphSvg', { static: true }) graphSvg!: ElementRef<SVGSVGElement>;

  // ── Form fields ────────────────────────────────────────────────────────────
  nameInput = '';
  depth = 2;

  // ── Model / API key ────────────────────────────────────────────────────────
  selectedModelId = '';
  apiKeyInput = '';
  maskedKey: string | null = null;
  apiKeySaving = false;
  apiKeyError = '';
  settingsOpen = false;

  // ── Graph state ────────────────────────────────────────────────────────────
  visibleNodes: LayoutNode[] = [];
  private _edgeDefs: MathlibLineageEdge[] = [];
  selectedNode: LayoutNode | null = null;

  // ── Zoom / pan ─────────────────────────────────────────────────────────────
  graphScale = 1;
  graphOffsetX = 0;
  graphOffsetY = 0;
  isGraphPanning = false;
  private graphPanStartX = 0;
  private graphPanStartY = 0;

  // Shell resize
  shellWidth = 320;
  private _resizing = false;
  private _resizeStartX = 0;
  private _resizeStartWidth = 0;

  private draggingNodeId: number | null = null;

  // ── Subjects ───────────────────────────────────────────────────────────────
  private readonly lineageSubmit$ = new Subject<LineageRequest | null>();
  private readonly fl2nlSubmit$   = new Subject<Fl2NlRequest | null>();
  private readonly _subs = new Subscription();

  // ── Model catalogue ────────────────────────────────────────────────────────
  readonly models$: Observable<AvailableModel[]> = defer(() =>
    this.taskService.getAvailableModels()
  ).pipe(
    catchError(() => of([])),
    startWith([] as AvailableModel[]),
    shareReplay(1),
  );

  // ── Lineage state machine ──────────────────────────────────────────────────
  readonly lineage$: Observable<LineageVm> = this.lineageSubmit$.pipe(
    switchMap(req => {
      if (!req) return of(IDLE_LINEAGE_VM);

      return this.taskService.submitMathlibLineage(req.name, req.depth).pipe(
        switchMap(({ task_id }) =>
          timer(2000, 3000).pipe(
            switchMap(() => this.taskService.getMathlibLineageResult(task_id)),
            filter((res: any) => res?.status !== 'pending'),
            take(1),
            timeout(300_000),
          )
        ),
        map((res: any): LineageVm => {
          const r = res as MathlibLineageResult;
          // Populate graph fields (runs inside the pipe so zone-safe)
          this._buildGraph(r);
          return {
            state: 'done',
            root: r.root,
            totalNodes: r.total_nodes,
            truncated: r.truncated,
            processingTime: r.processing_time_seconds,
            error: '',
          };
        }),
        startWith<LineageVm>({ ...IDLE_LINEAGE_VM, state: 'loading' }),
        catchError(err => of<LineageVm>({
          state: 'error',
          root: '', totalNodes: 0, truncated: false, processingTime: 0,
          error: err?.name === 'TimeoutError'
            ? 'Tiempo de espera agotado (5 min).'
            : (err?.error?.error ?? err?.message ?? 'Error al obtener el grafo de linaje.'),
        })),
      );
    }),
    startWith(IDLE_LINEAGE_VM),
    shareReplay(1),
  );

  // ── FL → NL state machine ──────────────────────────────────────────────────
  readonly fl2nl$: Observable<Fl2NlVm> = this.fl2nlSubmit$.pipe(
    switchMap(req => {
      if (!req) return of(IDLE_FL2NL_VM);

      const payload: Fl2NlPayload = {
        lean_code: req.leanCode,
        model_id: req.modelId,
        system_prompt: this.userPrefs.getSystemPrompt('fl2nl', FL2NL_SYSTEM_PROMPT),
        ...(req.apiKey ? { api_key: req.apiKey } : {}),
      };

      return this.taskService.submitFl2nl(payload).pipe(
        switchMap(({ task_id }) =>
          timer(2000, 3000).pipe(
            switchMap(() => this.taskService.getFl2nlResult(task_id)),
            filter((res: any) => res?.status !== 'pending'),
            take(1),
            timeout(300_000),
          )
        ),
        map((res: any): Fl2NlVm => ({
          state: 'done',
          renderedHtml: this._renderLatex((res as any).natural_text ?? ''),
          processingTime: (res as any).processing_time_seconds ?? 0,
          error: '',
        })),
        startWith<Fl2NlVm>({ ...IDLE_FL2NL_VM, state: 'translating' }),
        catchError(err => of<Fl2NlVm>({
          state: 'error',
          renderedHtml: '',
          processingTime: 0,
          error: err?.name === 'TimeoutError'
            ? 'Tiempo de espera agotado (5 min).'
            : (err?.error?.error ?? err?.message ?? 'Error al traducir a lenguaje natural.'),
        })),
      );
    }),
    startWith(IDLE_FL2NL_VM),
    shareReplay(1),
  );

  get isLoggedIn(): boolean {
    return !!this.taskService.getCurrentUserIdFromToken();
  }

  get transform(): string {
    return `translate(${this.graphOffsetX} ${this.graphOffsetY}) scale(${this.graphScale})`;
  }

  get renderedLinks(): Array<{ x1: number; y1: number; x2: number; y2: number }> {
    const byId = new Map(this.visibleNodes.map(n => [n.id, n]));
    return this._edgeDefs
      .filter(e => byId.has(e.source) && byId.has(e.target))
      .map(e => {
        const s = byId.get(e.source)!;
        const t = byId.get(e.target)!;
        return { x1: s.x, y1: s.y, x2: t.x, y2: t.y };
      });
  }

  constructor(
    private readonly taskService: TaskService,
    private readonly sanitizer: DomSanitizer,
    private readonly cdr: ChangeDetectorRef,
    private readonly userPrefs: UserPreferencesService,
  ) {
    const defaultModel = this.userPrefs.getDefaultModelId();
    if (defaultModel) this.selectedModelId = defaultModel;
  }

  ngAfterViewInit() {
    window.addEventListener('mousemove', this._onMouseMove);
    window.addEventListener('mouseup',  this._onMouseUp);
  }

  ngOnDestroy() {
    window.removeEventListener('mousemove', this._onMouseMove);
    window.removeEventListener('mouseup',  this._onMouseUp);
    this._subs.unsubscribe();
  }

  // ── Search ─────────────────────────────────────────────────────────────────

  submitLineage(): void {
    const name = this.nameInput.trim();
    if (!name) return;
    this.selectedNode = null;
    this.fl2nlSubmit$.next(null);
    this.visibleNodes = [];
    this._edgeDefs = [];
    this.lineageSubmit$.next({ name, depth: this.depth });
  }

  resetLineage(): void {
    this.lineageSubmit$.next(null);
    this.fl2nlSubmit$.next(null);
    this.visibleNodes = [];
    this._edgeDefs = [];
    this.selectedNode = null;
    this.graphScale = 1; this.graphOffsetX = 0; this.graphOffsetY = 0;
    this.cdr.markForCheck();
  }

  selectNode(node: LayoutNode): void {
    this.selectedNode = node;
    this.fl2nlSubmit$.next(null);
    this.cdr.markForCheck();
  }

  // ── Shell panel actions ────────────────────────────────────────────────────

  translateToNL(): void {
    if (!this.selectedNode?.lean_source?.trim() || !this.selectedModelId) return;
    const apiKey = !this.maskedKey ? (this.apiKeyInput.trim() || undefined) : undefined;
    this.fl2nlSubmit$.next({
      leanCode: this.selectedNode.lean_source,
      modelId: this.selectedModelId,
      apiKey,
    });
  }

  resetFl2nl(): void {
    this.fl2nlSubmit$.next(null);
  }

  // ── Model / API key ────────────────────────────────────────────────────────

  onModelChange(): void {
    this.maskedKey = null;
    this.apiKeyError = '';
    if (!this.selectedModelId || !this.isLoggedIn) return;
    this.taskService.getApiKeyStatus(this.selectedModelId).subscribe({
      next: s => { this.maskedKey = s.has_key ? s.masked_key : null; },
      error: () => { this.maskedKey = null; },
    });
  }

  saveApiKey(): void {
    if (!this.apiKeyInput.trim() || !this.selectedModelId) return;
    this.apiKeySaving = true;
    this.apiKeyError = '';
    this.taskService.saveApiKey(this.selectedModelId, this.apiKeyInput).pipe(
      finalize(() => { this.apiKeySaving = false; }),
    ).subscribe({
      next: status => { this.maskedKey = status.masked_key; this.apiKeyInput = ''; },
      error: err => { this.apiKeyError = err?.error?.error ?? 'Error al guardar la clave.'; },
    });
  }

  // ── State labels ───────────────────────────────────────────────────────────

  getLineageStateLabel(state: LineageState): string {
    const labels: Record<LineageState, string> = {
      idle:    'Escribe un nombre de declaración Mathlib para explorar su linaje',
      loading: 'Construyendo grafo de dependencias…',
      done:    'Grafo de linaje completado',
      error:   'Error al construir el grafo',
    };
    return labels[state];
  }

  getFl2NlStateLabel(state: Fl2NlState): string {
    const labels: Record<Fl2NlState, string> = {
      idle:        'Selecciona un nodo para ver su .lean y traducirlo',
      translating: 'Traduciendo a lenguaje natural…',
      done:        'Traducción completada',
      error:       'Error en la traducción',
    };
    return labels[state];
  }

  // ── Zoom / pan (same pattern as workspace-page) ───────────────────────────

  onGraphWheel(event: WheelEvent): void {
    event.preventDefault();
    const svg = event.currentTarget as SVGElement;
    const rect = svg.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    const oldScale = this.graphScale;
    const factor = event.deltaY < 0 ? 1.1 : 0.9;
    const nextScale = Math.min(2.8, Math.max(0.35, oldScale * factor));
    if (nextScale === oldScale) return;

    const worldX = (mouseX - this.graphOffsetX) / oldScale;
    const worldY = (mouseY - this.graphOffsetY) / oldScale;
    this.graphScale  = nextScale;
    this.graphOffsetX = mouseX - worldX * nextScale;
    this.graphOffsetY = mouseY - worldY * nextScale;
  }

  onGraphMouseDown(event: MouseEvent): void {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.closest('.graph-node')) return;
    this.isGraphPanning = true;
    this.graphPanStartX = event.clientX - this.graphOffsetX;
    this.graphPanStartY = event.clientY - this.graphOffsetY;
  }

  onGraphMouseMove(event: MouseEvent): void {
    if (this.draggingNodeId != null) {
      const node = this.visibleNodes.find(n => n.id === this.draggingNodeId);
      if (node) {
        const svg = this.graphSvg.nativeElement;
        const rect = svg.getBoundingClientRect();
        const mouseX = event.clientX - rect.left;
        const mouseY = event.clientY - rect.top;
        node.x = (mouseX - this.graphOffsetX) / this.graphScale;
        node.y = (mouseY - this.graphOffsetY) / this.graphScale;
        this.cdr.markForCheck();
      }
      return;
    }
    if (!this.isGraphPanning) return;
    this.graphOffsetX = event.clientX - this.graphPanStartX;
    this.graphOffsetY = event.clientY - this.graphPanStartY;
  }

  stopGraphPan(): void {
    this.isGraphPanning = false;
  }

  onNodeMouseDown(event: MouseEvent, nodeId: number): void {
    event.stopPropagation();
    this.draggingNodeId = nodeId;
  }

  resetGraphTransform(): void {
    this.graphScale = 1; this.graphOffsetX = 0; this.graphOffsetY = 0;
  }

  // ── Shell resize ───────────────────────────────────────────────────────────

  startResize(event: PointerEvent): void {
    this._resizing = true;
    this._resizeStartX = event.clientX;
    this._resizeStartWidth = this.shellWidth;
    (event.target as HTMLElement).setPointerCapture(event.pointerId);
  }

  onResizeMove(event: PointerEvent): void {
    if (!this._resizing) return;
    const delta = this._resizeStartX - event.clientX;
    this.shellWidth = Math.max(220, Math.min(600, this._resizeStartWidth + delta));
  }

  stopResize(): void {
    this._resizing = false;
  }

  // ── Private: global mouse handlers ────────────────────────────────────────

  private readonly _onMouseMove = (event: MouseEvent) => this.onGraphMouseMove(event);
  private readonly _onMouseUp   = () => {
    this.isGraphPanning = false;
    this.draggingNodeId = null;
  };

  // ── Private: hierarchical layout ──────────────────────────────────────────

  private _buildGraph(r: MathlibLineageResult): void {
    const VIEWBOX_W = 980, VIEWBOX_H = 520;
    const rowGap = 110;
    const nodeR = 26;
    const padding = nodeR + 20;

    // Group nodes by depth_level
    const byLevel = new Map<number, MathlibLineageNode[]>();
    for (const n of r.nodes) {
      const lvl = n.depth_level ?? 0;
      if (!byLevel.has(lvl)) byLevel.set(lvl, []);
      byLevel.get(lvl)!.push(n);
    }
    const levels = [...byLevel.keys()].sort((a, b) => a - b);
    const totalRows = levels.length;
    const totalHeight = Math.max(VIEWBOX_H, totalRows * rowGap + padding * 2);

    // Position nodes: depth level → Y row, index-within-level → X
    this.visibleNodes = r.nodes.map((n): LayoutNode => {
      const lvl = n.depth_level ?? 0;
      const levelNodes = byLevel.get(lvl)!;
      const colCount = levelNodes.length;
      const colIndex = levelNodes.indexOf(n);
      const rowIndex = levels.indexOf(lvl);

      const colGap = Math.max(80, (VIEWBOX_W - padding * 2) / colCount);
      const x = padding + colGap * colIndex + colGap / 2;
      const y = padding + rowIndex * rowGap;
      return { ...n, x, y };
    });

    this._edgeDefs = r.edges;
    this.selectedNode = null;
    this.graphScale = 1;
    this.graphOffsetX = 0;
    this.graphOffsetY = (VIEWBOX_H - totalHeight) / 2;
    this.cdr.markForCheck();
  }

  private _pointerToGraph(clientX: number, clientY: number) {
    const rect = this.graphSvg.nativeElement.getBoundingClientRect();
    const mouseX = clientX - rect.left;
    const mouseY = clientY - rect.top;
    return {
      graphX: (mouseX - this.graphOffsetX) / this.graphScale,
      graphY: (mouseY - this.graphOffsetY) / this.graphScale,
    };
  }

  // ── KaTeX rendering ────────────────────────────────────────────────────────

  private _renderLatex(src: string): SafeHtml {
    const text = src.trim();
    if (!text) return this.sanitizer.bypassSecurityTrustHtml('<p class="tex-empty">Sin contenido para renderizar.</p>');

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const katex = (window as any)['katex'];
    if (!katex) return this.sanitizer.bypassSecurityTrustHtml('<p>KaTeX no está disponible. Recarga la página e inténtalo de nuevo.</p>');

    try {
      let body = text;
      const displayPH: string[] = [];
      body = body.replace(/\$\$([\s\S]*?)\$\$/g, (_, m) => {
        const i = displayPH.length;
        try { displayPH.push('<div class="tex-display">' + katex.renderToString(m.trim(), { displayMode: true, throwOnError: false }) + '</div>'); }
        catch { displayPH.push(`<div class="tex-err">$$${this._escapeHtml(m)}$$</div>`); }
        return `\x00D${i}\x00`;
      });
      body = body.replace(/\\\[([\s\S]*?)\\\]/g, (_, m) => {
        const i = displayPH.length;
        try { displayPH.push('<div class="tex-display">' + katex.renderToString(m.trim(), { displayMode: true, throwOnError: false }) + '</div>'); }
        catch { displayPH.push(`<div class="tex-err">\\[${this._escapeHtml(m)}\\]</div>`); }
        return `\x00D${i}\x00`;
      });
      const inlinePH: string[] = [];
      body = body.replace(/\$([^$\n]{1,300}?)\$/g, (_, m) => {
        const i = inlinePH.length;
        try { inlinePH.push(katex.renderToString(m.trim(), { displayMode: false, throwOnError: false })); }
        catch { inlinePH.push(`$${this._escapeHtml(m)}$`); }
        return `\x00I${i}\x00`;
      });
      body = this._escapeHtml(body);
      body = body.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
      body = body.replace(/\*([^*\n]+?)\*/g, '<em>$1</em>');
      const paras = body.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
      body = paras.map(p => (/^<(div|h[1-6])/.test(p) ? p : `<p>${p.replace(/\n/g, '<br>')}</p>`)).join('\n');
      // Substitute KaTeX HTML back LAST so SVG path data is never mangled.
      inlinePH.forEach((h, i) => { body = body.replace(`\x00I${i}\x00`, h); });
      displayPH.forEach((h, i) => { body = body.replace(`\x00D${i}\x00`, h); });
      return this.sanitizer.bypassSecurityTrustHtml(body);
    } catch {
      return this.sanitizer.bypassSecurityTrustHtml('<p>Error al renderizar el LaTeX.</p>');
    }
  }

  private _escapeHtml(text: string): string {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
}

