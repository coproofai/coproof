import { ChangeDetectorRef, Component, NgZone, OnDestroy } from '@angular/core';
import { DecimalPipe, NgClass, NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, timer } from 'rxjs';
import { filter, switchMap, take, takeUntil, timeout } from 'rxjs/operators';
import { TaskService } from '../../task.service';
import { VerifyCompilerResult } from '../../task.models';

type ValidationState = 'idle' | 'loading' | 'valid' | 'invalid' | 'error';

@Component({
  selector: 'app-validation-page',
  standalone: true,
  imports: [NgClass, NgFor, NgIf, FormsModule, DecimalPipe],
  templateUrl: './validation-page.html',
  styleUrl: './validation-page.css'
})
export class ValidationPageComponent implements OnDestroy {
  code = '';
  fileName = '';
  state: ValidationState = 'idle';
  result: VerifyCompilerResult | null = null;
  serverError = '';

  private readonly destroy$ = new Subject<void>();
  private readonly cancel$  = new Subject<void>();

  constructor(
    private readonly taskService: TaskService,
    private readonly zone: NgZone,
    private readonly cdr: ChangeDetectorRef,
  ) {}

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    if (!file.name.endsWith('.lean')) {
      this.serverError = 'Solo se aceptan archivos .lean';
      this.state = 'error';
      return;
    }
    this.fileName = file.name;
    const reader = new FileReader();
    reader.onload = (e) => {
      this.code = (e.target?.result as string) ?? '';
      this.state = 'idle';
      this.result = null;
      this.serverError = '';
    };
    reader.readAsText(file);
  }

  validate(): void {
    if (!this.code.trim()) return;
    this.cancel$.next(); // cancel any in-flight poll
    this.state = 'loading';
    this.result = null;
    this.serverError = '';

    // Run the entire subscription inside Angular's zone so that the
    // timer's setInterval is zone-patched and CD fires automatically.
    this.zone.run(() => {
      this.taskService.submitLeanSnippet(this.code).pipe(
        switchMap(({ task_id }) => {
          console.log('[Validation] Task dispatched:', task_id);
          return timer(500, 500).pipe(
            switchMap(() => this.taskService.getLeanSnippetResult(task_id)),
            filter((res: any) => {
              console.log('[Validation] Poll response:', res);
              return res?.status !== 'pending';
            }),
            take(1),
            timeout(60_000),
          );
        }),
        takeUntil(this.cancel$),
        takeUntil(this.destroy$),
      ).subscribe({
        next: (res: any) => {
          console.log('[Validation] next() fired, inAngularZone:', NgZone.isInAngularZone(), res);
          this.result = res as VerifyCompilerResult;
          this.state = this.result.valid ? 'valid' : 'invalid';
          this.cdr.detectChanges();
          console.log('[Validation] state after detectChanges:', this.state);
        },
        error: (err) => {
          console.error('[Validation] error() fired, inAngularZone:', NgZone.isInAngularZone(), err);
          this.serverError = err?.name === 'TimeoutError'
            ? 'Tiempo de espera agotado. El servidor Lean no respondió.'
            : (err?.error?.error ?? 'Error al obtener el resultado.');
          this.state = 'error';
          this.cdr.detectChanges();
        }
      });
    });
  }

  clearAll(): void {
    this.cancel$.next();
    this.code = '';
    this.fileName = '';
    this.state = 'idle';
    this.result = null;
    this.serverError = '';
  }

  get statusLabel(): string {
    const map: Record<ValidationState, string> = {
      idle: 'Esperando entrada',
      loading: 'Verificando...',
      valid: 'Demostración correcta',
      invalid: 'Errores encontrados',
      error: 'Error del servidor',
    };
    return map[this.state];
  }

  trackByIndex(index: number): number { return index; }
}
