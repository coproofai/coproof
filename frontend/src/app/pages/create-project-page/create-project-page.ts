import { Component } from '@angular/core';
import { AsyncPipe, NgIf, NgFor } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { TaskService } from '../../task.service';
import { AvailableModel, TranslatePayload } from '../../task.models';
import { finalize, timeout, filter, take, switchMap, startWith, catchError, map, shareReplay, tap } from 'rxjs/operators';
import { Observable, Subject, of, timer } from 'rxjs';

type NlState = 'idle' | 'translating' | 'done' | 'error';
interface NlVm { state: NlState; lean: string; attempts: number; error: string; }
const IDLE_NL_VM: NlVm = { state: 'idle', lean: '', attempts: 0, error: '' };

const NL_PROJECT_SYSTEM_PROMPT =
  'You are a Lean 4 expert. Given a natural language description of a math formalization project, ' +
  'produce a structured Lean 4 source file with EXACTLY this structure:\n\n' +
  '1. A SINGLE import line: `import Mathlib`  (never use specific submodule paths)\n' +
  '2. Any required helper `abbrev`, `def`, `noncomputable def`, `structure`, or `instance` ' +
  '   declarations needed to express the goal type — omit this section if no helpers are needed\n' +
  '3. ONE `theorem` or `lemma` declaration with the Lean 4 TYPE of the project goal, ' +
  '   whose body is EXACTLY `:= by sorry` — do NOT attempt a proof\n\n' +
  'RULES:\n' +
  '- Never import specific Mathlib submodules. Use only `import Mathlib`.\n' +
  '- Never prove the theorem. The body MUST be `:= by sorry`.\n' +
  '- Output ONLY a single ```lean ... ``` fenced code block. No prose outside the block.';

@Component({
  selector: 'app-create-project-page',
  standalone: true,
  imports: [AsyncPipe, NgIf, NgFor, FormsModule],
  templateUrl: './create-project-page.html',
  styleUrl: './create-project-page.css'
})
export class CreateProjectPageComponent {
  projectName = '';
  goal = '';
  goalImportsText = '';
  goalDefinitions = '';
  description = '';
  visibility: 'public' | 'private' = 'public';
  statusMessage = '';
  statusKind: 'info' | 'success' | 'error' = 'info';
  loading = false;

  // ── NL2FL tab ──
  goalInputTab: 'nl' | 'manual' = 'manual';
  nlSubTab: 'input' | 'preview' = 'input';
  nlRenderedHtml: SafeHtml = '';
  nlDescription = '';
  nlModelId = '';
  nlApiKeyInput = '';
  nlModels: AvailableModel[] = [];
  nlModelsLoading = false;
  nlMaxRetries = 3;
  nlMaskedKey: string | null = null;
  nlApiKeySaving = false;
  nlApiKeyError = '';

  private readonly nlSubmit$ = new Subject<TranslatePayload | null>();

  readonly nlVm$: Observable<NlVm> = this.nlSubmit$.pipe(
    switchMap(payload => {
      if (!payload) return of(IDLE_NL_VM);
      return this.taskService.submitTranslation(payload).pipe(
        switchMap(({ task_id }) =>
          timer(3000, 3000).pipe(
            switchMap(() => this.taskService.getTranslationResult(task_id)),
            filter((res: any) => res?.status !== 'pending'),
            take(1),
            timeout(660_000),
          )
        ),
        map((res: any): NlVm => ({
          state: 'done',
          lean: res?.final_lean ?? '',
          attempts: res?.attempts ?? 1,
          error: '',
        })),
        tap((vm: NlVm) => {
          if (vm.lean) {
            const parsed = this.parseLeanOutput(vm.lean);
            this.goal = parsed.goal;
            this.goalImportsText = parsed.imports;
            this.goalDefinitions = parsed.definitions;
            this.goalInputTab = 'manual';
          }
        }),
        startWith<NlVm>({ state: 'translating', lean: '', attempts: 0, error: '' }),
        catchError(err => of<NlVm>({
          state: 'error',
          lean: '',
          attempts: 0,
          error: err?.name === 'TimeoutError'
            ? 'Tiempo de espera agotado. El proceso tardó más de 11 minutos.'
            : (err?.error?.error ?? err?.message ?? 'Error al obtener el resultado.'),
        })),
      );
    }),
    startWith(IDLE_NL_VM),
    shareReplay(1),
  );

  constructor(
    private readonly taskService: TaskService,
    private readonly router: Router,
    private readonly sanitizer: DomSanitizer,
  ) {}

  switchNlSubTab(tab: 'input' | 'preview'): void {
    this.nlSubTab = tab;
    if (tab === 'preview') this.renderNlPreview();
  }

  renderNlPreview(): void {
    const src = this.nlDescription.trim();
    if (!src) {
      this.nlRenderedHtml = this.sanitizer.bypassSecurityTrustHtml(
        '<p class="tex-empty">Sin contenido para renderizar.</p>',
      );
      return;
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const katex = (window as any)['katex'];
    if (!katex) {
      this.nlRenderedHtml = this.sanitizer.bypassSecurityTrustHtml(
        '<p>KaTeX no está disponible. Recarga la página e inténtalo de nuevo.</p>',
      );
      return;
    }
    try {
      let body = src;
      const dispPlaceholders: string[] = [];
      body = body.replace(/\$\$([\s\S]*?)\$\$/g, (_, math) => {
        const idx = dispPlaceholders.length;
        try { dispPlaceholders.push('<div class="tex-display">' + katex.renderToString(math.trim(), { displayMode: true, throwOnError: false }) + '</div>'); }
        catch { dispPlaceholders.push(`<div class="tex-err">$$${this._escapeHtml(math)}$$</div>`); }
        return `\x00DISP${idx}\x00`;
      });
      body = body.replace(/\\\[([\s\S]*?)\\\]/g, (_, math) => {
        const idx = dispPlaceholders.length;
        try { dispPlaceholders.push('<div class="tex-display">' + katex.renderToString(math.trim(), { displayMode: true, throwOnError: false }) + '</div>'); }
        catch { dispPlaceholders.push(`<div class="tex-err">\\[${this._escapeHtml(math)}\\]</div>`); }
        return `\x00DISP${idx}\x00`;
      });
      const inlinePlaceholders: string[] = [];
      body = body.replace(/\$([^$\n]{1,300}?)\$/g, (_, math) => {
        const idx = inlinePlaceholders.length;
        try { inlinePlaceholders.push(katex.renderToString(math.trim(), { displayMode: false, throwOnError: false })); }
        catch { inlinePlaceholders.push(`$${this._escapeHtml(math)}$`); }
        return `\x00INLN${idx}\x00`;
      });
      body = this._escapeHtml(body);
      inlinePlaceholders.forEach((html, i) => { body = body.replace(`\x00INLN${i}\x00`, html); });
      dispPlaceholders.forEach((html, i) => { body = body.replace(`\x00DISP${i}\x00`, html); });
      const paragraphs = body.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
      body = paragraphs.map(p => (/^<(div|h[1-6])/.test(p) ? p : `<p>${p.replace(/\n/g, '<br>')}</p>`)).join('\n');
      this.nlRenderedHtml = this.sanitizer.bypassSecurityTrustHtml(body);
    } catch {
      this.nlRenderedHtml = this.sanitizer.bypassSecurityTrustHtml('<p>Error al renderizar el LaTeX.</p>');
    }
  }

  private _escapeHtml(text: string): string {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  switchGoalTab(tab: 'nl' | 'manual'): void {
    this.goalInputTab = tab;
    if (tab === 'nl' && this.nlModels.length === 0 && !this.nlModelsLoading) {
      this.nlModelsLoading = true;
      this.taskService.getAvailableModels().subscribe({
        next: models => { this.nlModels = models; this.nlModelsLoading = false; },
        error: () => { this.nlModels = []; this.nlModelsLoading = false; },
      });
    }
  }

  onNlModelChange(): void {
    this.nlMaskedKey = null;
    this.nlApiKeyError = '';
    if (!this.nlModelId) return;
    this.taskService.getApiKeyStatus(this.nlModelId).subscribe({
      next: s => { this.nlMaskedKey = s.has_key ? s.masked_key : null; },
      error: () => { this.nlMaskedKey = null; },
    });
  }

  saveNlApiKey(): void {
    if (!this.nlApiKeyInput.trim() || !this.nlModelId) return;
    this.nlApiKeySaving = true;
    this.nlApiKeyError = '';
    this.taskService.saveApiKey(this.nlModelId, this.nlApiKeyInput).pipe(
      finalize(() => { this.nlApiKeySaving = false; }),
    ).subscribe({
      next: status => { this.nlMaskedKey = status.masked_key; this.nlApiKeyInput = ''; },
      error: err => { this.nlApiKeyError = err?.error?.error ?? 'Error al guardar la clave.'; },
    });
  }

  translateGoalFromNl(): void {
    if (!this.nlDescription.trim() || !this.nlModelId) return;
    const apiKey = !this.nlMaskedKey ? (this.nlApiKeyInput.trim() || undefined) : undefined;
    this.nlSubmit$.next({
      natural_text: this.nlDescription,
      model_id: this.nlModelId,
      max_retries: this.nlMaxRetries,
      system_prompt: NL_PROJECT_SYSTEM_PROMPT,
      ...(apiKey ? { api_key: apiKey } : {}),
    });
  }

  private parseLeanOutput(lean: string): { goal: string; imports: string; definitions: string } {
    const lines = lean.split(/\r?\n/);
    const importModules: string[] = [];
    const defLines: string[] = [];
    let inDef = false;

    for (const line of lines) {
      const t = line.trim();
      if (!t) { if (inDef) defLines.push(line); continue; }
      if (t.startsWith('import ')) {
        importModules.push(t.slice(7).trim());
        inDef = false;
        continue;
      }
      if (/^(theorem|lemma)\b/.test(t)) { inDef = false; continue; }
      if (/^(abbrev|def|noncomputable|private def|instance|structure|class|open|variable)\b/.test(t)) {
        inDef = true;
      }
      if (inDef) defLines.push(line);
    }

    // Extract goal: reconstruct a self-contained Prop by universally quantifying
    // all theorem parameters over the return type.
    //
    // Algorithm:
    // 1. Find the full `theorem/lemma ... := ...` block.
    // 2. After skipping the name, collect bracketed parameter groups at depth 0.
    // 3. Find the first `:` at depth 0 (not `:=`) — this starts the return type.
    // 4. Build `∀ <params>, <returnType>` if there are explicit params;
    //    otherwise use the return type alone.
    let goalType = '';

    // Grab everything from `theorem`/`lemma` through `:= by sorry`
    const thmMatch = lean.match(/(theorem|lemma)\s+([\s\S]*?):=\s*by\s+sorry/);
    if (thmMatch) {
      const body = thmMatch[2]; // everything between name and `:=`

      // Walk character-by-character to split params from return type
      let depth = 0;
      let returnTypeStart = -1;
      const paramGroups: string[] = [];
      let groupStart = -1;

      for (let i = 0; i < body.length; i++) {
        const ch = body[i];
        if (ch === '(' || ch === '[' || ch === '{') {
          if (depth === 0) groupStart = i;
          depth++;
        } else if (ch === ')' || ch === ']' || ch === '}') {
          depth--;
          if (depth === 0 && groupStart >= 0) {
            paramGroups.push(body.slice(groupStart, i + 1).trim());
            groupStart = -1;
          }
        } else if (ch === ':' && depth === 0 && body[i + 1] !== '=') {
          returnTypeStart = i + 1;
          break;
        }
      }

      if (returnTypeStart >= 0) {
        const returnType = body.slice(returnTypeStart).trim().replace(/\s+/g, ' ');
        if (paramGroups.length > 0) {
          goalType = `∀ ${paramGroups.join(' ')}, ${returnType}`;
        } else {
          goalType = returnType;
        }
      }
    }

    return {
      goal: goalType,
      imports: importModules.join('\n'),
      definitions: defLines.join('\n').trim(),
    };
  }

  createProject() {
    if (!this.projectName.trim()) {
      this.statusKind = 'error';
      this.statusMessage = 'El nombre del proyecto es obligatorio.';
      return;
    }

    if (!this.goal.trim()) {
      this.statusKind = 'error';
      this.statusMessage = 'El objetivo lógico (goal) es obligatorio.';
      return;
    }

    if (!this.taskService.getAccessToken()) {
      this.statusKind = 'error';
      this.statusMessage = 'No hay access token. Agrégalo en Auth antes de crear proyectos.';
      return;
    }

    this.loading = true;
    this.statusKind = 'info';
    this.statusMessage = 'Creando proyecto en backend...';

    this.taskService.createProject({
      name: this.projectName.trim(),
      goal: this.goal.trim(),
      goal_imports: this.parseGoalImports(this.goalImportsText),
      goal_definitions: this.goalDefinitions.trim() || undefined,
      description: this.description.trim() || undefined,
      visibility: this.visibility
    }).pipe(
      // Avoid indefinite UI lock when backend/network hangs.
      timeout(45000),
      finalize(() => {
        this.loading = false;
      })
    ).subscribe({
      next: (project) => {
        this.statusKind = 'success';
        this.statusMessage = `Proyecto '${project.name}' creado.`;
        this.router.navigate(['/workspace'], {
          queryParams: {
            projectId: project.id,
            projectName: project.name,
            sessionType: 'individual'
          }
        });
      },
      error: (error) => {
        const backendMessage = this.extractBackendErrorMessage(error);
        if (this.isAuthError(error, backendMessage)) {
          this.taskService.clearAccessToken();
          this.statusKind = 'error';
          this.statusMessage = 'Tu sesion expiro o es invalida. Vuelve a Auth e inicia sesion con GitHub.';
          return;
        }

        if (error?.name === 'TimeoutError') {
          this.statusKind = 'error';
          this.statusMessage = 'La creacion del proyecto excedio el tiempo de espera. Reintenta en unos segundos.';
          return;
        }

        this.statusKind = 'error';
        this.statusMessage =
          backendMessage ||
          `No se pudo crear el proyecto (HTTP ${error?.status ?? 'desconocido'}).`;
      }
    });
  }

  private extractBackendErrorMessage(error: any): string {
    const payload = error?.error;
    if (typeof payload === 'string') {
      return payload;
    }

    const baseMessage = payload?.message || payload?.error || payload?.msg || '';
    const validationErrors = payload?.validation_errors || payload?.verification?.errors || [];
    if (!Array.isArray(validationErrors) || validationErrors.length === 0) {
      return baseMessage;
    }

    const details = validationErrors
      .slice(0, 6)
      .map((item: any) => {
        const line = item?.line ?? '?';
        const column = item?.column ?? '?';
        const message = item?.message || 'Error de compilacion Lean';
        return `L${line}:C${column} ${message}`;
      });

    const extra = validationErrors.length > 6
      ? `\n... y ${validationErrors.length - 6} error(es) mas.`
      : '';

    const detailBlock = details.join('\n');
    return [baseMessage, detailBlock].filter(Boolean).join('\n') + extra;
  }

  private isAuthError(error: any, backendMessage: string): boolean {
    return this.taskService.shouldClearAccessTokenOnError({
      ...error,
      error: {
        ...(error?.error || {}),
        message: backendMessage || error?.error?.message,
      }
    });
  }

  private parseGoalImports(rawImports: string): string[] | undefined {
    const imports = rawImports
      .split(/\r?\n/)
      .map(line => line.trim())
      .filter(line => !!line)
      .map(line => line.startsWith('import ') ? line.slice(7).trim() : line)
      .filter(line => !!line);

    return imports.length > 0 ? Array.from(new Set(imports)) : undefined;
  }
}
