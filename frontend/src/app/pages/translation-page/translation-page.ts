import { Component } from '@angular/core';
import { AsyncPipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Observable, Subject, defer, of, timer } from 'rxjs';
import {
  catchError,
  filter,
  finalize,
  map,
  shareReplay,
  startWith,
  switchMap,
  take,
  tap,
  timeout,
} from 'rxjs/operators';
import { TaskService } from '../../task.service';
import { AvailableModel, TranslatePayload, TranslationResult } from '../../task.models';

type TranslationState = 'idle' | 'translating' | 'valid' | 'invalid' | 'error';

interface TranslationVm {
  state: TranslationState;
  result: TranslationResult | null;
  serverError: string;
}

interface TranslateRequest {
  naturalText: string;
  modelId: string;
  apiKey?: string;
  maxRetries: number;
  systemPrompt: string;
}

const IDLE_VM: TranslationVm = { state: 'idle', result: null, serverError: '' };

const DEFAULT_SYSTEM_PROMPT =
  "You are an expert in Lean 4 formal mathematics. Transcribe the following natural language mathematical statement into a Lean 4 statement. Break the input into goal and steps, make their equivalentes in Lean 4 and integrate them in the output. Make it fast and precise, you only have 3 minutes to answer. Reply ONLY with a single" + 
  "```lean code block and nothing else."

@Component({
  selector: 'app-translation-page',
  standalone: true,
  imports: [FormsModule, AsyncPipe, DecimalPipe],
  templateUrl: './translation-page.html',
  styleUrl: './translation-page.css',
})
export class TranslationPageComponent {
  // Form fields
  naturalText = '';
  selectedModelId = '';
  apiKeyInput = '';
  systemPrompt = DEFAULT_SYSTEM_PROMPT;
  maxRetries = 3;

  // Settings panel toggle
  settingsOpen = false;

  // Natural-language column tab
  nlTab: 'input' | 'preview' = 'input';
  nlRenderedHtml: SafeHtml = '';
  // API key UI state (updated imperatively from one-shot HTTP calls)
  maskedKey: string | null = null;
  apiKeySaving = false;
  apiKeyError = '';

  // Accordion state for attempt history
  expandedAttempts = new Set<number>();

  // Trigger for the main translation pipeline
  private readonly submit$ = new Subject<TranslateRequest | null>();

  // Model catalogue — loaded once, async piped in template
  readonly models$: Observable<AvailableModel[]> = defer(() =>
    this.taskService.getAvailableModels()
  ).pipe(
    catchError(() => of([])),
    startWith([] as AvailableModel[]),
    shareReplay(1),
  );

  // Main translation state machine driven by submit$
  readonly vm$: Observable<TranslationVm> = this.submit$.pipe(
    switchMap(req => {
      if (!req) return of(IDLE_VM);

      const payload: TranslatePayload = {
        natural_text: req.naturalText,
        model_id: req.modelId,
        max_retries: req.maxRetries,
        system_prompt: req.systemPrompt,
        ...(req.apiKey ? { api_key: req.apiKey } : {}),
      };

      return this.taskService.submitTranslation(payload).pipe(
        // DEBUG — remove after diagnosis
        tap(res => console.log('[TranslationPage] submit response:', res)),
        switchMap(({ task_id }) =>
          timer(2000, 3000).pipe(
            switchMap(() => this.taskService.getTranslationResult(task_id)),
            filter((res: any) => res?.status !== 'pending'),
            take(1),
            timeout(600_000), // 10 minutes — NL2FL can take many retries
          )
        ),
        map((res: any): TranslationVm => ({
          state: (res as TranslationResult).valid ? 'valid' : 'invalid',
          result: res as TranslationResult,
          serverError: '',
        })),
        startWith<TranslationVm>({ ...IDLE_VM, state: 'translating' }),
        catchError(err => of<TranslationVm>({
          state: 'error',
          result: null,
          serverError:
            err?.name === 'TimeoutError'
              ? 'Tiempo de espera agotado. El proceso tardó más de 10 minutos.'
              : (err?.error?.error ?? err?.message ?? 'Error al obtener el resultado.'),
        })),
      );
    }),
    startWith(IDLE_VM),
    shareReplay(1),
  );

  get isLoggedIn(): boolean {
    return !!this.taskService.getCurrentUserIdFromToken();
  }

  constructor(private readonly taskService: TaskService, private readonly sanitizer: DomSanitizer) {}

  switchNlTab(tab: 'input' | 'preview'): void {
    this.nlTab = tab;
    if (tab === 'preview') {
      this.renderNlPreview();
    }
  }

  renderNlPreview(): void {
    const src = this.naturalText.trim();
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

      const displayPlaceholders: string[] = [];
      // $$...$$ display math
      body = body.replace(/\$\$([\s\S]*?)\$\$/g, (_, math) => {
        const idx = displayPlaceholders.length;
        try {
          displayPlaceholders.push(
            '<div class="tex-display">' +
              katex.renderToString(math.trim(), { displayMode: true, throwOnError: false }) +
              '</div>',
          );
        } catch {
          displayPlaceholders.push(
            `<div class="tex-err">$$${this._escapeHtml(math)}$$</div>`,
          );
        }
        return `\x00DISP${idx}\x00`;
      });
      // \[...\] display math
      body = body.replace(/\\\[([\s\S]*?)\\\]/g, (_, math) => {
        const idx = displayPlaceholders.length;
        try {
          displayPlaceholders.push(
            '<div class="tex-display">' +
              katex.renderToString(math.trim(), { displayMode: true, throwOnError: false }) +
              '</div>',
          );
        } catch {
          displayPlaceholders.push(
            `<div class="tex-err">\\[${this._escapeHtml(math)}\\]</div>`,
          );
        }
        return `\x00DISP${idx}\x00`;
      });
      // $...$ inline math
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

      const paragraphs = body.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
      body = paragraphs
        .map(p => (/^<(div|h[1-6])/.test(p) ? p : `<p>${p.replace(/\n/g, '<br>')}</p>`))
        .join('\n');

      this.nlRenderedHtml = this.sanitizer.bypassSecurityTrustHtml(body);
    } catch {
      this.nlRenderedHtml = this.sanitizer.bypassSecurityTrustHtml(
        '<p>Error al renderizar el LaTeX.</p>',
      );
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

  submit(): void {
    if (!this.naturalText.trim() || !this.selectedModelId) return;
    this.expandedAttempts.clear();
    // Send the raw api key only when there is no saved key for this model.
    // If maskedKey is set the server will load the key from DB automatically.
    const apiKey = !this.maskedKey ? (this.apiKeyInput.trim() || undefined) : undefined;
    const req: TranslateRequest = {
      naturalText: this.naturalText,
      modelId: this.selectedModelId,
      apiKey,
      maxRetries: this.maxRetries,
      systemPrompt: this.systemPrompt,
    };
    console.log('[TranslationPage] submit() maskedKey=', this.maskedKey,
                'apiKeyInput.length=', this.apiKeyInput.length,
                'sending apiKey=', apiKey ? `${apiKey.slice(0,8)}... (len ${apiKey.length})` : 'undefined (rely on DB)');
    this.submit$.next(req);
  }

  reset(): void {
    this.expandedAttempts.clear();
    this.submit$.next(null);
  }

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
    console.log('[TranslationPage] saveApiKey() model=', this.selectedModelId,
                'key.length=', this.apiKeyInput.trim().length,
                'prefix=', this.apiKeyInput.trim().slice(0, 8));
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

  toggleAttempt(n: number): void {
    if (this.expandedAttempts.has(n)) {
      this.expandedAttempts.delete(n);
    } else {
      this.expandedAttempts.add(n);
    }
  }

  getStatusLabel(state: TranslationState): string {
    const labels: Record<TranslationState, string> = {
      idle:        'Esperando entrada',
      translating: 'Traduciendo y verificando…',
      valid:       'Demostración correcta',
      invalid:     'Verificación fallida',
      error:       'Error del servidor',
    };
    return labels[state];
  }
}
