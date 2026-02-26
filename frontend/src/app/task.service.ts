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

export interface NewProjectDto {
  id: string;
  name: string;
  description?: string;
  goal: string;
  visibility: 'public' | 'private';
  url: string;
  remote_repo_url: string;
  default_branch: string;
  tags: string[];
  author_id: string;
}

export interface NewNodeDto {
  id: string;
  name: string;
  url: string;
  project_id: string;
  parent_node_id: string | null;
  state: 'validated' | 'sorry';
}

export interface SimpleGraphResponse {
  project_id: string;
  project_name: string;
  count: number;
  nodes: NewNodeDto[];
}

export interface AccessibleProjectsResponse {
  projects: NewProjectDto[];
  total: number;
}

export interface NodeFileResponse {
  project_id: string;
  node_id: string;
  path: string;
  content: string;
}

export interface PullRequestItem {
  number: number;
  title: string;
  url: string;
  head: string;
  base: string;
  author: string;
  created_at: string;
  updated_at: string;
}

export interface OpenPullsResponse {
  project_id: string;
  count: number;
  pulls: PullRequestItem[];
}

export interface CreateProjectPayload {
  name: string;
  goal: string;
  description?: string;
  visibility?: 'public' | 'private';
  tags?: string[];
}

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

  createProject(payload: CreateProjectPayload): Observable<NewProjectDto> {
    return this.http.post<NewProjectDto>(`${this.apiBaseUrl}/projects`, payload, {
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
    return this.http.get<NodeFileResponse>(`${this.apiBaseUrl}/projects/${projectId}/nodes/${nodeId}/file`, {
      headers: this.authHeaders()
    });
  }

  verifyNode(projectId: string, nodeId: string): Observable<unknown> {
    return this.http.post(`${this.apiBaseUrl}/projects/${projectId}/nodes/${nodeId}/verify`, {}, {
      headers: this.authHeaders()
    });
  }

  solveNode(projectId: string, nodeId: string, leanCode: string): Observable<unknown> {
    return this.http.post(`${this.apiBaseUrl}/projects/${projectId}/nodes/${nodeId}/solve`, {
      lean_code: leanCode
    }, {
      headers: this.authHeaders()
    });
  }

  splitNode(projectId: string, nodeId: string, leanCode: string): Observable<unknown> {
    return this.http.post(`${this.apiBaseUrl}/projects/${projectId}/nodes/${nodeId}/split`, {
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