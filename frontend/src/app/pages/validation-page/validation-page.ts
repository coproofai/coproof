import { Component } from '@angular/core';
import { AsyncPipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Observable, Subject, of, timer } from 'rxjs';
import { catchError, filter, map, shareReplay, startWith, switchMap, take, timeout } from 'rxjs/operators';
import { TaskService } from '../../task.service';
import { VerifyCompilerResult } from '../../task.models';

type ValidationState = 'idle' | 'loading' | 'valid' | 'invalid' | 'error';

interface ValidationVm {
  state: ValidationState;
  result: VerifyCompilerResult | null;
  serverError: string;
}

const IDLE_VM: ValidationVm = { state: 'idle', result: null, serverError: '' };

@Component({
  selector: 'app-validation-page',
  standalone: true,
  imports: [FormsModule, DecimalPipe, AsyncPipe],
  templateUrl: './validation-page.html',
  styleUrl: './validation-page.css'
})
export class ValidationPageComponent {
  code = '';
  fileName = '';
  fileError = '';

  private readonly validate$ = new Subject<string | null>();

  readonly vm$: Observable<ValidationVm> = this.validate$.pipe(
    switchMap(code => {
      if (!code) return of(IDLE_VM);
      return this.taskService.submitLeanSnippet(code).pipe(
        switchMap(({ task_id }) =>
          timer(500, 500).pipe(
            switchMap(() => this.taskService.getLeanSnippetResult(task_id)),
            filter((res: any) => res?.status !== 'pending'),
            take(1),
            timeout(60_000),
          )
        ),
        map((res: any): ValidationVm => ({
          state: res.valid ? 'valid' : 'invalid',
          result: res as VerifyCompilerResult,
          serverError: '',
        })),
        startWith<ValidationVm>({ ...IDLE_VM, state: 'loading' }),
        catchError(err => of<ValidationVm>({
          state: 'error',
          result: null,
          serverError: err?.name === 'TimeoutError'
            ? 'Tiempo de espera agotado. El servidor Lean no respondió.'
            : (err?.error?.error ?? 'Error al obtener el resultado.'),
        })),
      );
    }),
    startWith(IDLE_VM),
    shareReplay(1),
  );

  constructor(private readonly taskService: TaskService) {}

  onFileSelected(event: Event): void {
    this.fileError = '';
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    if (!file.name.endsWith('.lean')) {
      this.fileError = 'Solo se aceptan archivos .lean';
      return;
    }
    this.fileName = file.name;
    const reader = new FileReader();
    reader.onload = (e) => {
      this.code = (e.target?.result as string) ?? '';
    };
    reader.readAsText(file);
  }

  validate(): void {
    if (!this.code.trim()) return;
    this.fileError = '';
    this.validate$.next(this.code);
  }

  clearAll(): void {
    this.code = '';
    this.fileName = '';
    this.fileError = '';
    this.validate$.next(null);
  }

  getStatusLabel(state: ValidationState): string {
    const map: Record<ValidationState, string> = {
      idle: 'Esperando entrada',
      loading: 'Verificando...',
      valid: 'Demostración correcta',
      invalid: 'Errores encontrados',
      error: 'Error del servidor',
    };
    return map[state];
  }
}
