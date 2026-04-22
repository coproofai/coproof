import { Injectable, NgZone } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  AccessibleProjectsResponse,
  ApiKeyStatus,
  AvailableModel,
  ComputeNodePayload,
  CreateComputationChildPayload,
  CreateProjectPayload,
  DefinitionsFileResponse,
  NodeFileResponse,
  OpenPullsResponse,
  ProjectDto,
  SimpleGraphResponse,
  TaskResult,
  TexFileResponse,
  TranslatePayload,
  TranslationResult,
  VerifyCompilerResult,
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
    const normalizedToken = this.normalizeAccessToken(token);
    localStorage.setItem(this.accessTokenKey, normalizedToken);
  }

  getAccessToken(): string {
    return localStorage.getItem(this.accessTokenKey) || '';
  }

  getTokenType(token?: string): 'access' | 'refresh' | null {
    const raw = (token ?? this.getAccessToken() ?? '').trim();
    if (!raw) {
      return null;
    }

    const parts = raw.split('.');
    if (parts.length < 2) {
      return null;
    }

    try {
      const payloadJson = this.decodeBase64Url(parts[1]);
      const payload = JSON.parse(payloadJson);
      const type = payload?.type;
      if (type === 'access' || type === 'refresh') {
        return type;
      }
      return null;
    } catch {
      return null;
    }
  }

  clearAccessToken() {
    localStorage.removeItem(this.accessTokenKey);
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('auth_user');
  }

  shouldClearAccessTokenOnError(error: any): boolean {
    const status = error?.status;
    const msg = this.extractBackendErrorMessage(error).toLowerCase();

    if (!msg) {
      return false;
    }

    const jwtHints = [
      'signature verification failed',
      'token has expired',
      'not enough segments',
      'missing authorization header',
      'invalid header',
      'invalid token',
      'bad authorization header',
      'subject must be a string',
      'only non-refresh tokens are allowed',
      'token is invalid',
      'token has been revoked',
      'jwt',
    ];

    const hasJwtHint = jwtHints.some((hint) => msg.includes(hint));
    if (!hasJwtHint) {
      return false;
    }

    return status === 401;
  }

  private extractBackendErrorMessage(error: any): string {
    const payload = error?.error;

    if (typeof payload === 'string') {
      return payload;
    }

    return payload?.message || payload?.error || payload?.msg || '';
  }

  private normalizeAccessToken(rawToken: string): string {
    const trimmed = (rawToken || '').trim();
    if (!trimmed) {
      return '';
    }

    if (/^bearer\s+/i.test(trimmed)) {
      return trimmed.replace(/^bearer\s+/i, '').trim();
    }

    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try {
        const parsed = JSON.parse(trimmed);
        const candidate = typeof parsed?.access_token === 'string' ? parsed.access_token.trim() : '';
        if (candidate) {
          return /^bearer\s+/i.test(candidate)
            ? candidate.replace(/^bearer\s+/i, '').trim()
            : candidate;
        }
      } catch {
      }
    }

    return trimmed;
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

  getNodeTexFile(projectId: string, nodeId: string): Observable<TexFileResponse> {
    return this.http.get<TexFileResponse>(`${this.apiBaseUrl}/nodes/${projectId}/${nodeId}/tex-content`, {
      headers: this.authHeaders()
    });
  }

  submitLeanSnippet(code: string): Observable<{ task_id: string }> {
    return this.http.post<{ task_id: string }>(
      `${this.apiBaseUrl}/nodes/tools/verify-snippet`,
      { code }
    );
  }

  getLeanSnippetResult(taskId: string): Observable<VerifyCompilerResult | { status: 'pending' }> {
    return this.http.get<VerifyCompilerResult | { status: 'pending' }>(
      `${this.apiBaseUrl}/nodes/tools/verify-snippet/${taskId}/result`
    );
  }

  verifyNode(projectId: string, nodeId: string): Observable<VerifyNodeResponse> {
    return this.http.post<VerifyNodeResponse>(`${this.apiBaseUrl}/nodes/${projectId}/${nodeId}/verify-import-tree`, {}, {
      headers: this.authHeaders()
    });
  }

  solveNode(projectId: string, nodeId: string, leanCode: string, modelId?: string, apiKey?: string): Observable<unknown> {
    const body: Record<string, unknown> = { lean_code: leanCode };
    if (modelId) body['model_id'] = modelId;
    if (apiKey) body['api_key'] = apiKey;
    return this.http.post(`${this.apiBaseUrl}/nodes/${projectId}/${nodeId}/solve`, body, {
      headers: this.authHeaders()
    });
  }

  splitNode(projectId: string, nodeId: string, leanCode: string, modelId?: string, apiKey?: string): Observable<unknown> {
    const body: Record<string, unknown> = { lean_code: leanCode };
    if (modelId) body['model_id'] = modelId;
    if (apiKey) body['api_key'] = apiKey;
    return this.http.post(`${this.apiBaseUrl}/nodes/${projectId}/${nodeId}/split`, body, {
      headers: this.authHeaders()
    });
  }

  createComputationChildNode(projectId: string, nodeId: string, payload: CreateComputationChildPayload): Observable<unknown> {
    return this.http.post(`${this.apiBaseUrl}/nodes/${projectId}/${nodeId}/children/computation`, payload, {
      headers: this.authHeaders()
    });
  }

  computeNode(projectId: string, nodeId: string, payload: ComputeNodePayload): Observable<unknown> {
    return this.http.post(`${this.apiBaseUrl}/nodes/${projectId}/${nodeId}/compute`, payload, {
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

  // --- NL2FL / Translation ---

  submitTranslation(payload: TranslatePayload): Observable<{ task_id: string }> {
    return this.http.post<{ task_id: string }>(
      `${this.apiBaseUrl}/translate/submit`,
      payload,
      { headers: this.authHeaders() }
    );
  }

  getTranslationResult(taskId: string): Observable<TranslationResult | { status: 'pending' }> {
    return this.http.get<TranslationResult | { status: 'pending' }>(
      `${this.apiBaseUrl}/translate/${taskId}/result`
    );
  }

  getAvailableModels(): Observable<AvailableModel[]> {
    return this.http.get<AvailableModel[]>(`${this.apiBaseUrl}/translate/models`);
  }

  saveApiKey(modelId: string, apiKey: string): Observable<ApiKeyStatus> {
    return this.http.post<ApiKeyStatus>(
      `${this.apiBaseUrl}/translate/api-key`,
      { model_id: modelId, api_key: apiKey },
      { headers: this.authHeaders() }
    );
  }

  getApiKeyStatus(modelId: string): Observable<ApiKeyStatus> {
    return this.http.get<ApiKeyStatus>(
      `${this.apiBaseUrl}/translate/api-key/${modelId}`,
      { headers: this.authHeaders() }
    );
  }

  // --- FL → NL (converse translation) ---

  submitFl2nl(payload: import('./task.models').Fl2NlPayload): Observable<{ task_id: string }> {
    return this.http.post<{ task_id: string }>(
      `${this.apiBaseUrl}/translate/fl2nl/submit`,
      payload,
      { headers: this.authHeaders() }
    );
  }

  getFl2nlResult(taskId: string): Observable<import('./task.models').Fl2NlResult | { status: 'pending' }> {
    return this.http.get<import('./task.models').Fl2NlResult | { status: 'pending' }>(
      `${this.apiBaseUrl}/translate/fl2nl/${taskId}/result`
    );
  }
}