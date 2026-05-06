import { Component } from '@angular/core';
import { AsyncPipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Observable, Subject, defer, forkJoin, of, timer } from 'rxjs';
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
  MathlibLookupResult,
  Fl2NlPayload,
  Fl2NlResult,
  SuggestPayload,
} from '../../task.models';

type SearchMode = 'byName' | 'byNL';
type LookupState = 'idle' | 'loading' | 'found' | 'notFound' | 'error';
type SuggestState = 'idle' | 'loading' | 'validating' | 'done' | 'error';
type Fl2NlState = 'idle' | 'translating' | 'done' | 'error';

interface LookupVm {
  state: LookupState;
  result: MathlibLookupResult | null;
  error: string;
}

interface SuggestVm {
  state: SuggestState;
  candidates: string[];
  error: string;
}

interface Fl2NlVm {
  state: Fl2NlState;
  naturalText: string;
  renderedHtml: SafeHtml;
  processingTime: number;
  error: string;
}

interface SuggestRequest {
  nlText: string;
  modelId: string;
  apiKey?: string;
}

interface Fl2NlRequest {
  leanCode: string;
  modelId: string;
  apiKey?: string;
}

const IDLE_LOOKUP_VM: LookupVm = { state: 'idle', result: null, error: '' };
const IDLE_SUGGEST_VM: SuggestVm = { state: 'idle', candidates: [], error: '' };
const IDLE_FL2NL_VM: Fl2NlVm = {
  state: 'idle',
  naturalText: '',
  renderedHtml: '',
  processingTime: 0,
  error: '',
};

const MATHLIB_SUGGEST_SYSTEM_PROMPT =
  'You are a Mathlib4 expert. Given a mathematical statement or theorem name in natural language, ' +
  'list the 5 to 8 most relevant Mathlib4 declaration names (fully qualified, e.g. Nat.succ_pos, ' +
  'Finset.sum_comm, Real.sqrt_sq). Output ONLY the list, one name per line, each prefixed with - (dash and space). ' +
  'No explanations, no additional text.';

const FL2NL_SYSTEM_PROMPT =
  'You are an expert in formal mathematics and mathematical writing. ' +
  'Given one or more Lean 4 theorems (possibly with proofs), produce a structured mathematical exposition in natural language. ' +
  'For EACH theorem or lemma found in the input, output exactly the following structure:\n\n' +
  '**Theorem.** <state the mathematical claim clearly, using LaTeX notation ($...$ inline, $$...$$ display)>\n\n' +
  '*Proof.* <explain the proof strategy and key steps in natural language, using LaTeX where appropriate. ' +
  'If the proof body contains `sorry` or is otherwise left unsolved, write exactly "Unsolved." instead.>\n\n' +
  'Rules:\n' +
  '- Capture the mathematical ESSENCE and meaning of what the Lean statement expresses. Do NOT attempt to solve or prove anything.\n' +
  '- Do NOT reproduce any Lean 4 syntax in your output.\n' +
  '- Do NOT add commentary outside the Theorem/Proof blocks.\n' +
  '- If there are multiple theorems, repeat the Theorem/Proof block for each one in order.';

@Component({
  selector: 'app-proof-search-page',
  standalone: true,
  imports: [FormsModule, AsyncPipe, DecimalPipe, RouterLink],
  templateUrl: './proof-search-page.html',
  styleUrl: './proof-search-page.css',
})
export class ProofSearchPageComponent {
  // Mode
  searchMode: SearchMode = 'byName';

  // Form fields
  mathlibNameInput = '';
  nlDescriptionInput = '';
  selectedModelId = '';
  apiKeyInput = '';
  settingsOpen = false;

  // API key UI state
  maskedKey: string | null = null;
  apiKeySaving = false;
  apiKeyError = '';

  // Subjects (triggers)
  private readonly lookupSubmit$ = new Subject<string | null>();
  private readonly suggestSubmit$ = new Subject<SuggestRequest | null>();
  private readonly fl2nlSubmit$ = new Subject<Fl2NlRequest | null>();

  // Model catalogue — loaded once
  readonly models$: Observable<AvailableModel[]> = defer(() =>
    this.taskService.getAvailableModels()
  ).pipe(
    catchError(() => of([])),
    startWith([] as AvailableModel[]),
    shareReplay(1),
  );

  // ── Mathlib lookup state machine ─────────────────────────────────────
  readonly lookup$: Observable<LookupVm> = this.lookupSubmit$.pipe(
    switchMap(name => {
      if (!name) return of(IDLE_LOOKUP_VM);

      return this.taskService.submitMathlibLookup(name).pipe(
        switchMap(({ task_id }) =>
          timer(2000, 3000).pipe(
            switchMap(() => this.taskService.getMathlibLookupResult(task_id)),
            filter((res: any) => res?.status !== 'pending'),
            take(1),
            timeout(120_000),
          )
        ),
        map((res: any): LookupVm => {
          const r = res as MathlibLookupResult;
          return r.found
            ? { state: 'found', result: r, error: '' }
            : { state: 'notFound', result: r, error: r.error_message };
        }),
        startWith<LookupVm>({ ...IDLE_LOOKUP_VM, state: 'loading' }),
        catchError(err => of<LookupVm>({
          state: 'error',
          result: null,
          error:
            err?.name === 'TimeoutError'
              ? 'Tiempo de espera agotado (120s).'
              : (err?.error?.error ?? err?.message ?? 'Error al buscar la declaración.'),
        })),
      );
    }),
    startWith(IDLE_LOOKUP_VM),
    shareReplay(1),
  );

  // ── NL → Mathlib suggestions state machine ───────────────────────────
  readonly suggest$: Observable<SuggestVm> = this.suggestSubmit$.pipe(
    switchMap(req => {
      if (!req) return of(IDLE_SUGGEST_VM);

      const payload: SuggestPayload = {
        prompt: req.nlText,
        model_id: req.modelId,
        system_prompt: MATHLIB_SUGGEST_SYSTEM_PROMPT,
        ...(req.apiKey ? { api_key: req.apiKey } : {}),
      };

      return this.taskService.submitSuggest(payload).pipe(
        switchMap(({ task_id }) =>
          timer(2000, 3000).pipe(
            switchMap(() => this.taskService.getSuggestResult(task_id)),
            filter((res: any) => res?.status !== 'pending'),
            take(1),
            timeout(60_000),
          )
        ),
        switchMap((res: any): Observable<SuggestVm> => {
          const suggestion: string = (res as any).suggestion ?? '';
          const candidates = suggestion
            .split('\n')
            .map((l: string) => l.replace(/^[-*•]\s*/, '').replace(/`/g, '').trim())
            .filter((l: string) => l.length > 0 && !l.startsWith('#') && !l.includes(' '));

          if (candidates.length === 0) {
            return of<SuggestVm>({ state: 'done', candidates: [], error: '' });
          }

          // Validate each candidate against the lean worker in parallel;
          // only keep those where found === true.
          return forkJoin(
            candidates.map(name => this._lookupSingle$(name))
          ).pipe(
            map(results => {
              const valid = candidates.filter((_, i) => results[i]?.found === true);
              return { state: 'done' as const, candidates: valid, error: '' };
            }),
            startWith<SuggestVm>({ state: 'validating', candidates: [], error: '' }),
          );
        }),
        startWith<SuggestVm>({ ...IDLE_SUGGEST_VM, state: 'loading' }),
        catchError(err => of<SuggestVm>({
          state: 'error',
          candidates: [],
          error:
            err?.name === 'TimeoutError'
              ? 'Tiempo de espera agotado (60s).'
              : (err?.error?.error ?? err?.message ?? 'Error al obtener sugerencias.'),
        })),
      );
    }),
    startWith(IDLE_SUGGEST_VM),
    shareReplay(1),
  );

  // ── FL → NL state machine ────────────────────────────────────────────
  readonly fl2nl$: Observable<Fl2NlVm> = this.fl2nlSubmit$.pipe(
    switchMap(req => {
      if (!req) return of(IDLE_FL2NL_VM);

      const payload: Fl2NlPayload = {
        lean_code: req.leanCode,
        model_id: req.modelId,
        system_prompt: FL2NL_SYSTEM_PROMPT,
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
          naturalText: (res as Fl2NlResult).natural_text,
          renderedHtml: this._renderLatex((res as Fl2NlResult).natural_text),
          processingTime: (res as Fl2NlResult).processing_time_seconds,
          error: '',
        })),
        startWith<Fl2NlVm>({ ...IDLE_FL2NL_VM, state: 'translating' }),
        catchError(err => of<Fl2NlVm>({
          state: 'error',
          naturalText: '',
          renderedHtml: '',
          processingTime: 0,
          error:
            err?.name === 'TimeoutError'
              ? 'Tiempo de espera agotado (300s).'
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

  constructor(
    private readonly taskService: TaskService,
    private readonly sanitizer: DomSanitizer,
  ) {}

  // ── Mode A: lookup by Mathlib name ───────────────────────────────────

  submitLookup(): void {
    const name = this.mathlibNameInput.trim();
    if (!name) return;
    this.fl2nlSubmit$.next(null);
    this.lookupSubmit$.next(name);
  }

  resetLookup(): void {
    this.lookupSubmit$.next(null);
    this.fl2nlSubmit$.next(null);
  }

  // ── Mode B: NL → suggestions ─────────────────────────────────────────

  submitSuggest(): void {
    const nlText = this.nlDescriptionInput.trim();
    if (!nlText || !this.selectedModelId) return;
    const apiKey = !this.maskedKey ? (this.apiKeyInput.trim() || undefined) : undefined;
    this.suggestSubmit$.next({ nlText, modelId: this.selectedModelId, apiKey });
  }

  resetSuggest(): void {
    this.suggestSubmit$.next(null);
    this.resetLookup();
  }

  loadFromSuggestion(name: string): void {
    this.mathlibNameInput = name;
    this.fl2nlSubmit$.next(null);
    this.lookupSubmit$.next(name);
  }

  switchMode(mode: SearchMode): void {
    if (mode === 'byNL' && !this.isLoggedIn) return;
    this.searchMode = mode;
    this.resetLookup();
    this.resetSuggest();
  }

  // ── Shared: FL→NL translation ────────────────────────────────────────

  translateToNL(leanSource: string): void {
    if (!leanSource.trim() || !this.selectedModelId) return;
    const apiKey = !this.maskedKey ? (this.apiKeyInput.trim() || undefined) : undefined;
    this.fl2nlSubmit$.next({ leanCode: leanSource, modelId: this.selectedModelId, apiKey });
  }

  resetFl2nl(): void {
    this.fl2nlSubmit$.next(null);
  }

  // ── Model / API key ──────────────────────────────────────────────────

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
      next: status => {
        this.maskedKey = status.masked_key;
        this.apiKeyInput = '';
      },
      error: err => {
        this.apiKeyError = err?.error?.error ?? 'Error al guardar la clave.';
      },
    });
  }

  // ── Status label helpers ─────────────────────────────────────────────

  getLookupStateLabel(state: LookupState): string {
    const labels: Record<LookupState, string> = {
      idle:     'Escribe un nombre de declaración Mathlib',
      loading:  'Buscando en Mathlib…',
      found:    'Declaración encontrada',
      notFound: 'Declaración no encontrada',
      error:    'Error al buscar',
    };
    return labels[state];
  }

  getSuggestStateLabel(state: SuggestState): string {
    const labels: Record<SuggestState, string> = {
      idle:       'Describe el teorema en lenguaje natural',
      loading:    'Consultando al modelo…',
      validating: 'Verificando sugerencias en Mathlib…',
      done:       'Sugerencias verificadas',
      error:      'Error al obtener sugerencias',
    };
    return labels[state];
  }

  getFl2NlStateLabel(state: Fl2NlState): string {
    const labels: Record<Fl2NlState, string> = {
      idle:        'Carga un .lean para traducirlo a NL',
      translating: 'Traduciendo a lenguaje natural…',
      done:        'Traducción completada',
      error:       'Error en la traducción',
    };
    return labels[state];
  }

  // ── KaTeX rendering ──────────────────────────────────────────────────

  private _lookupSingle$(name: string): Observable<MathlibLookupResult | null> {
    return this.taskService.submitMathlibLookup(name).pipe(
      switchMap(({ task_id }) =>
        timer(2000, 3000).pipe(
          switchMap(() => this.taskService.getMathlibLookupResult(task_id)),
          filter((res: any) => res?.status !== 'pending'),
          take(1),
          timeout(120_000),
        )
      ),
      map((res: any) => res as MathlibLookupResult),
      catchError(() => of(null)),
    );
  }

  private _renderLatex(src: string): SafeHtml {
    const text = src.trim();
    if (!text) {
      return this.sanitizer.bypassSecurityTrustHtml(
        '<p class="tex-empty">Sin contenido para renderizar.</p>',
      );
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const katex = (window as any)['katex'];
    if (!katex) {
      return this.sanitizer.bypassSecurityTrustHtml(
        '<p>KaTeX no está disponible. Recarga la página e inténtalo de nuevo.</p>',
      );
    }

    try {
      let body = text;

      const displayPlaceholders: string[] = [];
      body = body.replace(/\$\$([\s\S]*?)\$\$/g, (_, math) => {
        const idx = displayPlaceholders.length;
        try {
          displayPlaceholders.push(
            '<div class="tex-display">' +
              katex.renderToString(math.trim(), { displayMode: true, throwOnError: false }) +
              '</div>',
          );
        } catch {
          displayPlaceholders.push(`<div class="tex-err">$$${this._escapeHtml(math)}$$</div>`);
        }
        return `\x00DISP${idx}\x00`;
      });

      body = body.replace(/\\\[([\s\S]*?)\\\]/g, (_, math) => {
        const idx = displayPlaceholders.length;
        try {
          displayPlaceholders.push(
            '<div class="tex-display">' +
              katex.renderToString(math.trim(), { displayMode: true, throwOnError: false }) +
              '</div>',
          );
        } catch {
          displayPlaceholders.push(`<div class="tex-err">\\[${this._escapeHtml(math)}\\]</div>`);
        }
        return `\x00DISP${idx}\x00`;
      });

      const inlinePlaceholders: string[] = [];
      body = body.replace(/\$([^$\n]{1,300}?)\$/g, (_, math) => {
        const idx = inlinePlaceholders.length;
        try {
          inlinePlaceholders.push(
            katex.renderToString(math.trim(), { displayMode: false, throwOnError: false }),
          );
        } catch {
          inlinePlaceholders.push(`$${this._escapeHtml(math)}$`);
        }
        return `\x00INLN${idx}\x00`;
      });

      body = this._escapeHtml(body);
      inlinePlaceholders.forEach((html, i) => { body = body.replace(`\x00INLN${i}\x00`, html); });
      displayPlaceholders.forEach((html, i) => { body = body.replace(`\x00DISP${i}\x00`, html); });

      body = body.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
      body = body.replace(/\*([^*\n]+?)\*/g, '<em>$1</em>');

      const paragraphs = body.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
      body = paragraphs
        .map(p => (/^<(div|h[1-6])/.test(p) ? p : `<p>${p.replace(/\n/g, '<br>')}</p>`))
        .join('\n');

      return this.sanitizer.bypassSecurityTrustHtml(body);
    } catch {
      return this.sanitizer.bypassSecurityTrustHtml('<p>Error al renderizar el LaTeX.</p>');
    }
  }

  private _escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
}
