export type AgentType = 'interviewer' | 'diagnostician' | 'critic' | 'cdss' | 'coordinator' | 'debate_round';

export interface Session {
  id: string;
  title: string;
  status: 'active' | 'completed' | 'archived';
  llm_model: string;
  created_at: string;
  // Backend SessionResponse currently doesn't return updated_at or
  // confidence_score; kept optional so future backend additions don't
  // break existing consumers, but don't rely on them being present.
  updated_at?: string;
  message_count?: number;
  preliminary_diagnosis?: string;
  confidence_score?: number;
  safety_flags?: string[];
  // Backend may include "unknown" or other strings outside the AgentType
  // union (it's whatever name was logged); accept string defensively.
  agent_participation?: (AgentType | string)[];
}

export interface Message {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  agent?: AgentType;
  // Backend ChatMessageOut returns `created_at`; live-WS-derived messages
  // synthesise `timestamp` locally. Both are optional ISO strings.
  timestamp?: string;
  created_at?: string;
  citations?: Citation[];
}

export interface Citation {
  id: string;
  title: string;
  source: string;
  doi?: string;
  abstract?: string;
}

export interface AgentLog {
  id: string;
  session_id: string;
  agent: AgentType;
  event_type: 'transition' | 'reasoning' | 'message' | 'diagnosis';
  content: string;
  timestamp: string;
  completed: boolean;
}

export interface WebSocketEvent {
  // `llm_token` is emitted by the backend during Coordinator streaming
  // (one chunk per LLM token). The frontend accumulates them into a
  // live typewriter bubble that gets finalised by the subsequent
  // `agent_message` event.
  type: 'agent_transition' | 'agent_reasoning' | 'agent_message' | 'diagnosis_result' | 'debate_challenge' | 'debate_response' | 'llm_token' | 'error';
  agent?: AgentType;
  content?: string;
  data?: Record<string, unknown>;
}

export interface DashboardStats {
  total_sessions: number;
  active_sessions: number;
  total_messages: number;
  // Null when no sessions exist yet
  latest_session_date: string | null;
}

// --- Diagnosis Result types ---

export interface DiagnosisEntry {
  diagnosis: string;
  confidence: number; // 0-100
  supporting_evidence: string[];
  against_evidence: string[];
  source: string;
}

export interface CDSSScore {
  tool_name: string;
  score: number;
  max_score?: number;
  risk_level: 'low' | 'moderate' | 'high' | 'critical';
  recommendation: string;
}

export interface CriticReview {
  approval: boolean;
  safety_flag: string;
  issues: Array<{ type: string; description: string; suggestion?: string }>;
  final_assessment: string;
}

export interface DiagnosisResult {
  differential_diagnosis: DiagnosisEntry[];
  recommended_tests: string[];
  reasoning_chain: string;
  critic_review?: CriticReview;
  coordinator_response?: string;
  debate_outcome?: DebateOutcome;
  cdss_scores?: CDSSScore[];
  safety_level?: 'safe' | 'caution' | 'urgent';
}

// --- Debate Protocol types ---

export interface DebateChallenge {
  challenge_id: string;
  type: 'evidence_gap' | 'alternative_diagnosis' | 'risk_underestimation' | 'methodology' | 'general' | 'missed_diagnosis' | 'scoring_error' | 'safety_concern';
  claim: string;
  evidence: string[];
  suggested_action: string;
}

export interface DebateResponse {
  challenge_id: string;
  action: 'accept' | 'refute' | 'partially_accept';
  reasoning: string;
  evidence: string[];
}

export type DebateResolution = 'resolved' | 'escalated' | 'deadlock' | 'pending';

export interface DebateRound {
  round_number: number;
  challenges: DebateChallenge[];
  responses: DebateResponse[];
  resolution: DebateResolution;
}

export interface DebateOutcome {
  rounds: DebateRound[];
  final_verdict: string;
  total_challenges: number;
  accepted: number;
  refuted: number;
  consensus_diagnosis?: Record<string, unknown>;
  summary?: string;
}

// --- Evaluation Harness types ---

export interface EvalCaseDetail {
  case_id: string;
  case_name: string;
  top1_correct: boolean;
  top3_recall: boolean;
  safety_flag_correct: boolean;
  debate_rounds: number;
  challenges_accepted: number;
  challenges_refuted: number;
  total_time_seconds: number;
  ai_primary_diagnosis: string;
  ai_top3: string[];
  ai_safety_flag: string;
  ai_final_assessment: string;
  ground_truth_primary: string;
  ground_truth_safety: string;
  ground_truth_ddx: string[];
  ground_truth_tests: string[];
  debate_summary: Array<{
    round_number: number;
    challenges_count: number;
    responses_count: number;
    resolution: string;
  }>;
  error: string;
}

export interface EvalVariantMetrics {
  top1_accuracy: number;
  top3_recall: number;
  safety_flag_recall: number;
  missed_critical: number;
  debate_rounds_avg: number;
  challenge_acceptance_rate: number;
  diagnosis_revision_rate: number;
  total_cases: number;
}

export interface EvalVariant {
  name: string;
  metrics: EvalVariantMetrics;
  cases: EvalCaseDetail[];
}

export interface EvaluationReport {
  generated_at: string | null;
  variants: EvalVariant[];
  has_data: boolean;
  message?: string;
}

export interface EvalGroundTruth {
  primary_diagnosis: string;
  expected_in_ddx: string[];
  expected_safety_flag: string;
  expected_tests: string[];
  expected_cdss: string[];
}

export interface EvalCaseDefinition {
  case_id: string;
  name: string;
  initial_message: string;
  follow_up_answers: string[];
  ground_truth: EvalGroundTruth;
}

export interface EvaluationCasesResponse {
  total: number;
  cases: EvalCaseDefinition[];
}

export interface EvaluationStatus {
  status: 'idle' | 'running' | 'completed' | 'failed';
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export interface EvaluationRunRequest {
  limit?: number;
  case_id?: string;
}

// --- Agent system / Tools ---

export interface AgentStatus {
  status: string;
  available_models: string[];
  available_tools: string[];
}

export interface McpToolInfo {
  name?: string;
  description?: string;
  [key: string]: unknown;
}

export interface ToolsListResponse {
  tools: McpToolInfo[] | string[];
  protocol: 'MCP' | 'legacy';
}

export const AGENT_COLORS: Record<AgentType, string> = {
  interviewer: '#3b82f6',
  diagnostician: '#16a34a',
  critic: '#dc2626',
  cdss: '#0891b2',
  coordinator: '#f59e0b',
  debate_round: '#a855f7',
};

export const AGENT_CONFIG: Record<AgentType, { label: string; emoji: string; color: string; colorClass: string; bgClass: string; borderClass: string }> = {
  interviewer: { label: 'Interviewer', emoji: '🔵', color: '#3b82f6', colorClass: 'agent-interviewer', bgClass: 'bg-agent-interviewer', borderClass: 'border-agent-interviewer' },
  diagnostician: { label: 'Diagnostician', emoji: '🟢', color: '#16a34a', colorClass: 'agent-diagnostician', bgClass: 'bg-agent-diagnostician', borderClass: 'border-agent-diagnostician' },
  critic: { label: 'Critic', emoji: '🔴', color: '#dc2626', colorClass: 'agent-critic', bgClass: 'bg-agent-critic', borderClass: 'border-agent-critic' },
  cdss: { label: 'CDSS', emoji: '🔷', color: '#0891b2', colorClass: 'text-cyan-400', bgClass: 'bg-cyan-500/10', borderClass: 'border-cyan-500/40' },
  coordinator: { label: 'Coordinator', emoji: '🟡', color: '#f59e0b', colorClass: 'agent-coordinator', bgClass: 'bg-agent-coordinator', borderClass: 'border-agent-coordinator' },
  debate_round: { label: 'Debate', emoji: '🟣', color: '#a855f7', colorClass: 'agent-debate', bgClass: 'bg-agent-debate', borderClass: 'border-agent-debate' },
};
