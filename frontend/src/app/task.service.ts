import { Injectable, NgZone } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface TaskResult {
  status: string;
  result: WorkerResult | null;
}

export interface WorkerMessage {
  line?: number;
  column?: number;
  severity?: string;
  message: string;
}

export interface WorkerResult {
  status?: string;
  result?: string;
  output?: string;
  messages?: WorkerMessage[];
  time?: number;
  execution_time?: number;
  success?: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class TaskService {
  private baseUrl = 'http://localhost:8000';

  constructor(private http: HttpClient, private zone: NgZone) {}

  /**
   * Command: Dispatches the code to the cluster.
   * Returns a Task ID immediately.
   */
  startTask(lang: string, code: string): Observable<{task_id: string}> {
    return this.http.post<{task_id: string}>(`${this.baseUrl}/run/${lang}`, { code });
  }

  /**
   * Observer: Opens an SSE stream to watch the task lifecycle.
   */
  getTaskUpdates(taskId: string): Observable<TaskResult> {
    return new Observable(observer => {
      const eventSource = new EventSource(`${this.baseUrl}/stream/${taskId}`);

      eventSource.onmessage = (event) => {
        // We use zone.run because EventSource runs outside Angular's detection zone
        this.zone.run(() => {
          const data = JSON.parse(event.data);
          observer.next(data);
          
          if (data.status === 'SUCCESS' || data.status === 'FAILURE' || data.status === 'FAILED') {
            eventSource.close();
            observer.complete();
          }
        });
      };

      eventSource.onerror = (error) => {
        this.zone.run(() => observer.error(error));
        eventSource.close();
      };

      return () => eventSource.close();
    });
  }
}