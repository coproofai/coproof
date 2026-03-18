import { ChangeDetectorRef, Component } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TaskService } from '../../task.service';
import { TaskResult, WorkerMessage, WorkerResult } from '../../task.models';

@Component({
  selector: 'app-debug-executors-page',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule],
  templateUrl: './debug-executors-page.html',
  styleUrl: './debug-executors-page.css'
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
