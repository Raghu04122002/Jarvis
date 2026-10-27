// ---- Enums ----

export type TaskStatus =
  | "created"
  | "planning"
  | "waiting_for_approval"
  | "running"
  | "verifying"
  | "completed"
  | "failed"
  | "cancelled";

export type TaskPriority = "low" | "normal" | "high" | "urgent";

export type StepStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped"
  | "cancelled";

export type AgentExecutionStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "timeout";

export type MemoryType =
  | "project_memory"
  | "user_preference"
  | "task_history"
  | "decision"
  | "conversation_summary";

export type MemoryScope = "global" | "project";

export type ApprovalStatus = "pending" | "approved" | "denied" | "expired";

export type RiskLevel = "safe" | "requires_approval" | "blocked";

// ---- Task ----

export interface Task {
  id: string;
  request: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  project_id: string | null;
  parent_task_id: string | null;
  plan: string[];
  current_step: number | null;
  result: string | null;
  error: string | null;
  metadata: Record<string, string>;
  version: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TaskSummary {
  id: string;
  title: string;
  status: TaskStatus;
  priority: TaskPriority;
  created_at: string;
  updated_at: string;
}

export interface ChatRequest {
  message: string;
  project_id?: string;
  priority?: TaskPriority;
}

export interface ChatResponse {
  task_id?: string;
  title: string;
  status: string;
  priority?: TaskPriority;
  plan?: string[];
  message: string;
  answer?: string;
}

export interface DispatchResponse {
  task_id: string;
  message: string;
}

// ---- Task Steps ----

export interface TaskStep {
  id: string;
  task_id: string;
  sequence: number;
  description: string;
  status: StepStatus;
  depends_on: string[];
  result: string | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

// ---- Agent Execution ----

export interface AgentExecution {
  id: string;
  task_id: string;
  agent_name: string;
  prompt: string;
  project_path: string;
  status: AgentExecutionStatus;
  exit_code: number | null;
  stdout: string | null;
  stderr: string | null;
  duration_ms: number | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

// ---- Project ----

export interface Project {
  id: string;
  name: string;
  local_path: string;
  github_repo: string | null;
  default_branch: string;
  stack: string[];
  preferred_agent: string | null;
  deployment: Record<string, string>;
  instructions: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  local_path: string;
  stack: string[];
  preferred_agent: string | null;
  created_at: string;
}

export interface CreateProjectRequest {
  name: string;
  local_path: string;
  github_repo?: string;
  default_branch?: string;
  stack?: string[];
  preferred_agent?: string;
  deployment?: Record<string, string>;
  instructions?: string;
}

export interface UpdateProjectRequest {
  name?: string;
  local_path?: string;
  github_repo?: string | null;
  default_branch?: string;
  stack?: string[];
  preferred_agent?: string | null;
  deployment?: Record<string, string>;
  instructions?: string;
}

// ---- Memory ----

export interface Memory {
  id: string;
  memory_type: MemoryType;
  scope: MemoryScope;
  project_id: string | null;
  key: string;
  content: string;
  tags: string[];
  metadata: Record<string, unknown>;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface MemorySummary {
  id: string;
  memory_type: MemoryType;
  scope: MemoryScope;
  project_id: string | null;
  key: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface CreateMemoryRequest {
  memory_type: MemoryType;
  key: string;
  content: string;
  project_id?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

export interface UpdateMemoryRequest {
  content?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

// ---- Approval ----

export interface ApprovalRequestFull {
  id: string;
  task_id: string;
  tool_name: string;
  operation: string;
  risk_level: RiskLevel;
  description: string;
  context: Record<string, unknown>;
  status: ApprovalStatus;
  decided_by: string | null;
  decision_reason: string | null;
  expires_at: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface ApprovalSummary {
  id: string;
  task_id: string;
  tool_name: string;
  operation: string;
  status: ApprovalStatus;
  created_at: string;
}

export interface ApprovalDecision {
  decided_by?: string;
  reason?: string;
}

// ---- Schedule ----

export type ScheduleType = "one_time" | "recurring" | "interval" | "conditional";

export type ScheduledTaskStatus =
  | "active"
  | "paused"
  | "completed"
  | "cancelled"
  | "failed";

export interface ScheduledTask {
  id: string;
  name: string;
  description: string;
  schedule_type: ScheduleType;
  cron_expression: string | null;
  interval_seconds: number | null;
  run_at: string | null;
  condition: string | null;
  task_request: string;
  task_priority: string;
  project_id: string | null;
  status: ScheduledTaskStatus;
  last_run_at: string | null;
  next_run_at: string | null;
  run_count: number;
  max_runs: number | null;
  failure_count: number;
  max_failures: number;
  last_task_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ScheduledTaskSummary {
  id: string;
  name: string;
  schedule_type: ScheduleType;
  status: ScheduledTaskStatus;
  next_run_at: string | null;
  run_count: number;
  created_at: string;
}

export interface CreateScheduledTaskRequest {
  name: string;
  description?: string;
  schedule_type: ScheduleType;
  cron_expression?: string;
  interval_seconds?: number;
  run_at?: string;
  condition?: string;
  task_request: string;
  task_priority?: string;
  project_id?: string;
  max_runs?: number;
  max_failures?: number;
  metadata?: Record<string, unknown>;
}

export interface UpdateScheduledTaskRequest {
  name?: string;
  description?: string;
  cron_expression?: string;
  interval_seconds?: number;
  run_at?: string;
  condition?: string;
  task_request?: string;
  task_priority?: string;
  max_runs?: number;
  max_failures?: number;
  metadata?: Record<string, unknown>;
}

// ---- Computer ----

export type ComputerOperation =
  | "screenshot"
  | "get_screen_info"
  | "list_windows"
  | "open_application"
  | "focus_window"
  | "mouse_click"
  | "mouse_move"
  | "type_text"
  | "key_press"
  | "scroll";

// ---- Workflow ----

export type WorkflowStepStatus = "completed" | "failed" | "skipped";

export type WorkflowStatus = "completed" | "failed" | "needs_human";

export interface WorkflowStepResult {
  name: string;
  status: WorkflowStepStatus;
  agent: string | null;
  tool: string | null;
  output: string;
  error: string | null;
  duration_ms: number;
}

export interface WorkflowResult {
  task_id: string;
  issue_number: number;
  repo: string;
  status: WorkflowStatus;
  branch: string | null;
  pr_url: string | null;
  ci_status: string | null;
  changes_summary: string;
  test_summary: string;
  steps: WorkflowStepResult[];
  error: string | null;
}

export interface DevWorkflowRequest {
  issue_number: number;
  project_id: string;
  priority?: string;
}

// ---- Health ----

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
}

// ---- SSE ----

export interface SSEEvent {
  type: string;
  task_id: string;
  timestamp: string;
  data: Record<string, unknown>;
}
