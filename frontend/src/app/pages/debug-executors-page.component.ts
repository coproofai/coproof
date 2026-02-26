import { ChangeDetectorRef, Component } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TaskService, TaskResult, WorkerMessage, WorkerResult } from '../task.service';

@Component({
  selector: 'app-debug-executors-page',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule],
  template: `
    <div class="container">
      <h1>Code Executor</h1>

      <div class="editor-section">
        <textarea
          [(ngModel)]="code"
          placeholder="Paste your Lean4 or C code here..."
        ></textarea>
      </div>

      <div class="actions">
        <button (click)="run('lean')" class="btn-lean">Verify with Lean</button>
        <button (click)="run('cluster')" class="btn-cluster">Execute on Cluster</button>
      </div>

      <hr />

      <div class="output-console">
        <div class="console-header">
          <strong>Console Output:</strong>
          <span class="status" [style.color]="statusColor">{{ currentStatus }}</span>
          <span *ngIf="execTime" class="exec-time">{{ execTime }}s</span>
        </div>

        <pre>{{ mainOutput }}</pre>

        <div *ngIf="messages.length > 0" class="messages-wrap">
          <div
            *ngFor="let message of messages"
            class="message-row"
            [style.border-left]="'3px solid ' + getMessageColor(message.severity)"
          >
            <span class="message-meta">[{{ formatSeverity(message.severity) }}{{ formatPosition(message) }}]</span>
            {{ message.message }}
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .container { max-width: 1100px; margin: 0 auto; padding: 6px 0 18px 0; }
    .editor-section textarea {
      width: 100%;
      height: 250px;
      border: 1px solid #ccc;
      padding: 10px;
      border-radius: 5px;
      font-family: Consolas, Monaco, monospace;
      box-sizing: border-box;
    }
    .actions { margin: 14px 0; display: flex; gap: 10px; flex-wrap: wrap; }
    .btn-lean,
    .btn-cluster {
      color: #fff;
      padding: 10px 18px;
      border: none;
      cursor: pointer;
      border-radius: 4px;
      font-weight: 700;
    }
    .btn-lean { background: #4a90e2; }
    .btn-cluster { background: #50b33e; }
    .output-console {
      background: #1e1e1e;
      color: #d4d4d4;
      border-radius: 5px;
      min-height: 120px;
      padding: 16px;
    }
    .console-header {
      border-bottom: 1px solid #333;
      margin-bottom: 8px;
      padding-bottom: 6px;
      position: relative;
      font-size: 0.95rem;
    }
    .status { margin-left: 10px; }
    .exec-time {
      position: absolute;
      right: 0;
      top: 0;
      color: #888;
      font-size: 0.85rem;
    }
    pre { margin: 0; white-space: pre-wrap; font-family: Consolas, Monaco, monospace; }
    .messages-wrap { margin-top: 12px; }
    .message-row {
      padding: 6px 10px;
      margin-bottom: 6px;
      background: #2d2d2d;
      font-size: 0.9em;
    }
    .message-meta { color: #888; margin-right: 6px; }
  `]
})
export class DebugExecutorsPageComponent {
  code = '';
  currentStatus = 'Idle';
  mainOutput = 'Waiting for execution...';
  messages: WorkerMessage[] = [];
  execTime: number | null = null;
  statusColor = '#888';

  constructor(
    private readonly taskService: TaskService,
    private readonly cdr: ChangeDetectorRef
  ) {}

  run(lang: 'lean' | 'cluster') {
    this.resetUI();
    this.currentStatus = `Processing ${lang.toUpperCase()}...`;
    this.statusColor = '#4a90e2';

    this.taskService.startTask(lang, this.code).subscribe({
      next: (response) => this.observeTask(response.task_id),
      error: () => this.handleError('Failed to reach Backend')
    });
  }

  private observeTask(taskId: string) {
    this.taskService.getTaskUpdates(taskId).subscribe({
      next: (update: TaskResult) => {
        if (!update.result) {
          this.currentStatus = update.status;
          this.statusColor = this.getStatusColor(update.status);
          this.cdr.detectChanges();
          return;
        }

        const result = this.normalizeResult(update.result, update.status);
        this.currentStatus = result.status;
        this.statusColor = this.getStatusColor(result.status);
        this.mainOutput = result.mainOutput;
        this.messages = result.messages;
        this.execTime = result.execTime;
        this.cdr.detectChanges();
      },
      error: () => this.handleError('Stream connection lost')
    });
  }

  private normalizeResult(result: WorkerResult, streamStatus: string) {
    return {
      status: result.status || streamStatus,
      mainOutput: result.result || result.output || 'Execution finished',
      messages: Array.isArray(result.messages) ? result.messages : [],
      execTime: result.time ?? result.execution_time ?? null
    };
  }

  getMessageColor(severity?: string): string {
    if (severity?.toLowerCase() === 'error') {
      return '#f44336';
    }

    if (severity?.toLowerCase() === 'warning') {
      return '#ffeb3b';
    }

    return '#4a90e2';
  }

  formatSeverity(severity?: string): string {
    return (severity || 'info').toUpperCase();
  }

  formatPosition(message: WorkerMessage): string {
    if (message.line == null || message.column == null) {
      return '';
    }

    return ` @ Line ${message.line}:${message.column}`;
  }

  private getStatusColor(status: string): string {
    const normalized = status.toUpperCase();

    if (normalized === 'SUCCESS') {
      return '#50b33e';
    }

    if (normalized === 'PENDING' || normalized === 'STARTED' || normalized === 'RETRY') {
      return '#4a90e2';
    }

    return '#f44336';
  }

  private resetUI() {
    this.mainOutput = '';
    this.messages = [];
    this.execTime = null;
  }

  private handleError(msg: string) {
    this.currentStatus = 'ERROR';
    this.statusColor = '#f44336';
    this.mainOutput = msg;
    this.cdr.detectChanges();
  }
}
