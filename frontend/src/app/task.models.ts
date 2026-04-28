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

export interface UserSummaryDto {
  id: string;
  full_name: string;
  email: string;
}

export interface ProjectDto {
  id: string;
  name: string;
  description?: string;
  goal: string;
  goal_imports?: string[];
  goal_definitions?: string;
  visibility: 'public' | 'private';
  url: string;
  remote_repo_url: string;
  default_branch: string;
  tags: string[];
  author_id: string;
  contributor_ids?: string[];
  author?: UserSummaryDto;
  created_at?: string;
  updated_at?: string;
}

export interface NodeDto {
  id: string;
  name: string;
  url: string;
  project_id: string;
  parent_node_id: string | null;
  state: 'validated' | 'sorry';
  node_kind?: 'proof' | 'computation';
  computation_spec?: Record<string, unknown> | null;
  last_computation_result?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export type NewProjectDto = ProjectDto;
export type NewNodeDto = NodeDto;

export interface SimpleGraphResponse {
  project_id: string;
  project_name: string;
  count: number;
  nodes: NodeDto[];
}

export interface AccessibleProjectsResponse {
  projects: ProjectDto[];
  total: number;
}

export interface NodeFileResponse {
  project_id: string;
  node_id: string;
  path: string;
  content: string;
}

export interface DefinitionsFileResponse {
  project_id: string;
  path: string;
  content: string;
}

export interface TexFileResponse {
  project_id: string;
  node_id: string;
  path: string;
  content: string;
}

export interface VerificationErrorItem {
  line: number;
  column: number;
  message: string;
}

export interface VerifyCompilerResult {
  valid: boolean;
  errors: VerificationErrorItem[];
  processing_time_seconds?: number;
  return_code?: number;
  message_count?: number;
  theorem_count?: number;
}

export interface SorryLocationItem {
  file: string;
  line: number;
  snippet: string;
}

export interface SorryTraceItem {
  file: string;
  line: number;
  snippet: string;
  import_trace: string[];
  depth: number;
  starts_at_entry: boolean;
}

export interface VerifyNodeResponse {
  status: string;
  project_id: string;
  node_id: string;
  entry_file: string;
  reachable_file_count: number;
  reachable_files: string[];
  verification: VerifyCompilerResult;
  has_sorry: boolean;
  sorry_locations: SorryLocationItem[];
  sorry_traces: SorryTraceItem[];
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

export interface PrFileEntry {
  filename: string;
  status: string;
  additions: number;
  deletions: number;
  content: string | null;
}

export interface PullRequestFilesResponse {
  project_id: string;
  pr_number: number;
  files: PrFileEntry[];
}

export interface ContributorDto {
  id: string;
  email: string;
  full_name: string;
}

export interface GitHubInvitationDto {
  id: number;
  repo: string;
  inviter: string | null;
  html_url: string | null;
}

export interface UserProfileDto {
  id: string;
  full_name: string;
  email: string;
  github_id?: string | null;
  github_login?: string | null;
  is_verified?: boolean;
  created_at?: string;
}

export interface OpenPullsResponse {
  project_id: string;
  count: number;
  pulls: PullRequestItem[];
}

export interface CreateProjectPayload {
  name: string;
  goal: string;
  goal_imports?: string[];
  goal_definitions?: string;
  goal_tex?: string;
  description?: string;
  visibility?: 'public' | 'private';
  tags?: string[];
  contributor_ids?: string[];
}

export interface CreateComputationChildPayload {
  name?: string;
  language?: string;
  entrypoint?: string;
  target?: Record<string, unknown>;
  lean_statement?: string;
}

export interface ComputeNodePayload {
  language: string;
  code: string;
  entrypoint?: string;
  input_data?: unknown;
  target: Record<string, unknown>;
  lean_statement: string;
  timeout_seconds?: number;
}

// --- NL2FL / Translation ---

export interface TranslationAttempt {
  attempt: number;
  lean_code: string;
  errors: VerificationErrorItem[];
}

export interface TranslationResult {
  valid: boolean;
  attempts: number;
  final_lean: string;
  history: TranslationAttempt[];
  processing_time_seconds: number;
}

export interface AvailableModel {
  id: string;       // e.g. "openai/gpt-4o"
  name: string;     // e.g. "GPT-4o"
  provider: string; // e.g. "OpenAI"
}

export interface ApiKeyStatus {
  model_id: string;
  masked_key: string | null; // "sk-***...abc", or null when has_key is false
  has_key: boolean;
}

export interface TranslatePayload {
  natural_text: string;
  model_id: string;
  api_key?: string;
  max_retries?: number;
  system_prompt?: string;
  definitions_content?: string;
}

export interface Fl2NlPayload {
  lean_code: string;
  model_id: string;
  api_key?: string;
  system_prompt?: string;
}

export interface Fl2NlResult {
  natural_text: string;
  processing_time_seconds: number;
}

// --- Agents / Suggest ---

export interface SuggestPayload {
  prompt: string;
  model_id: string;
  api_key?: string;
  system_prompt?: string;
  context?: string;
}

export interface SuggestResult {
  suggestion: string;
  model_id: string;
  processing_time_seconds: number;
}