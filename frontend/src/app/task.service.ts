import { Injectable, NgZone } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  AccessibleProjectsResponse,
  CreateProjectPayload,
  DefinitionsFileResponse,
  NodeFileResponse,
  OpenPullsResponse,
  ProjectDto,
  SimpleGraphResponse,
  TaskResult,
  VerifyNodeResponse
} from './task.models';

@Injectable({
  providedIn: 'root'
})
export class TaskService {
  private workerBaseUrl = 'http://localhost:8000';
  private apiBaseUrl = 'http://localhost:5001/api/v1';
  private accessTokenKey = 'access_token';

  constructor(private http: HttpClient, private zone: NgZone) {}

  setAccessToken(token: string) {
    localStorage.setItem(this.accessTokenKey, token.trim());
  }

  getAccessToken(): string {
    return localStorage.getItem(this.accessTokenKey) || '';
  }

  clearAccessToken() {
    localStorage.removeItem(this.accessTokenKey);
  }

  getCurrentUserIdFromToken(): string | null {
    const token = this.getAccessToken();
    if (!token) {
      return null;
    }

    const parts = token.split('.');
    if (parts.length < 2) {
      return null;
    }

    try {
      const payloadJson = this.decodeBase64Url(parts[1]);
      const payload = JSON.parse(payloadJson);
      return typeof payload?.sub === 'string' ? payload.sub : null;
    } catch {
      return null;
    }
  }

  private decodeBase64Url(input: string): string {
    const base64 = input.replace(/-/g, '+').replace(/_/g, '/');
    const padding = (4 - (base64.length % 4)) % 4;
    const normalized = base64 + '='.repeat(padding);
    return atob(normalized);
  }

  private authHeaders(): Record<string, string> {
    const token = this.getAccessToken();
    return token
      ? { Authorization: `Bearer ${token}` }
      : {};
  }

  /**
   * Command: Dispatches the code to the cluster.
   * Returns a Task ID immediately.
   */
  startTask(lang: string, code: string): Observable<{task_id: string}> {
    return this.http.post<{task_id: string}>(`${this.workerBaseUrl}/run/${lang}`, { code });
  }

  /**
   * Observer: Opens an SSE stream to watch the task lifecycle.
   */
  getTaskUpdates(taskId: string): Observable<TaskResult> {
    return new Observable(observer => {
      const eventSource = new EventSource(`${this.workerBaseUrl}/stream/${taskId}`);

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

  createProject(payload: CreateProjectPayload): Observable<ProjectDto> {
    return this.http.post<ProjectDto>(`${this.apiBaseUrl}/projects`, payload, {
      headers: this.authHeaders()
    });
  }

  getAccessibleProjects(): Observable<AccessibleProjectsResponse> {
    return this.http.get<AccessibleProjectsResponse>(`${this.apiBaseUrl}/projects/accessible`, {
      headers: this.authHeaders()
    });
  }

  getSimpleGraph(projectId: string): Observable<SimpleGraphResponse> {
    return this.http.get<SimpleGraphResponse>(`${this.apiBaseUrl}/projects/${projectId}/graph/simple`, {
      headers: this.authHeaders()
    });
  }

  getNodeLeanFile(projectId: string, nodeId: string): Observable<NodeFileResponse> {
    return this.http.get<NodeFileResponse>(`${this.apiBaseUrl}/nodes/${projectId}/${nodeId}/file-content`, {
      headers: this.authHeaders()
    });
  }

  getProjectDefinitions(projectId: string): Observable<DefinitionsFileResponse> {
    return this.http.get<DefinitionsFileResponse>(`${this.apiBaseUrl}/projects/${projectId}/definitions`, {
      headers: this.authHeaders()
    });
  }

  verifyNode(projectId: string, nodeId: string): Observable<VerifyNodeResponse> {
    return this.http.post<VerifyNodeResponse>(`${this.apiBaseUrl}/nodes/${projectId}/${nodeId}/verify-import-tree`, {}, {
      headers: this.authHeaders()
    });
  }

  solveNode(projectId: string, nodeId: string, leanCode: string): Observable<unknown> {
    return this.http.post(`${this.apiBaseUrl}/nodes/${projectId}/${nodeId}/solve`, {
      lean_code: leanCode
    }, {
      headers: this.authHeaders()
    });
  }

  splitNode(projectId: string, nodeId: string, leanCode: string): Observable<unknown> {
    return this.http.post(`${this.apiBaseUrl}/nodes/${projectId}/${nodeId}/split`, {
      lean_code: leanCode
    }, {
      headers: this.authHeaders()
    });
  }

  listOpenPullRequests(projectId: string): Observable<OpenPullsResponse> {
    return this.http.get<OpenPullsResponse>(`${this.apiBaseUrl}/projects/${projectId}/pulls/open`, {
      headers: this.authHeaders()
    });
  }

  mergePullRequest(projectId: string, pullNumber: number): Observable<unknown> {
    return this.http.post(`${this.apiBaseUrl}/projects/${projectId}/pulls/${pullNumber}/merge`, {}, {
      headers: this.authHeaders()
    });
  }
}