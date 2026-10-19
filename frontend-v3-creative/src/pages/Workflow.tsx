import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  User,
  Radio,
  Server,
  MessageSquare,
  Brain,
  Swords,
  Sparkles,
  Database,
  Wrench,
  BookOpen,
  Layers,
  FileJson,
  Zap,
  Target,
  BarChart3,
  FileCheck,
  HardDrive,
} from 'lucide-react';
import type { ComponentType } from 'react';

// ============================================================================
// Custom Node Components
// ============================================================================

interface AgentNodeData {
  label: string;
  subtitle: string;
  icon: ComponentType<{ className?: string }>;
  borderClass: string;
  bgClass: string;
  iconClass: string;
  labelClass: string;
  badges?: string[];
}

function AgentNode({ data }: { data: AgentNodeData }) {
  const Icon = data.icon;
  return (
    <div
      className={`px-3 py-2 rounded-lg border-2 ${data.borderClass} ${data.bgClass} w-[180px] shadow-lg`}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top} id="top" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Top} id="top-out" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Bottom} id="bottom-in" style={{ opacity: 0 }} />

      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-4 h-4 ${data.iconClass}`} />
        <span className={`font-bold text-sm ${data.labelClass}`}>{data.label}</span>
      </div>
      <p className="text-[11px] text-muted-foreground leading-snug mb-1.5">{data.subtitle}</p>
      {data.badges && data.badges.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {data.badges.map((b, i) => (
            <span
              key={i}
              className="text-[10px] px-1.5 py-0.5 rounded bg-background/70 border border-border text-muted-foreground"
            >
              {b}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

interface DataNodeData {
  label: string;
  subtitle: string;
  icon?: ComponentType<{ className?: string }>;
  count?: string;
  colorClass?: string;
}

function DataNode({ data }: { data: DataNodeData }) {
  const Icon = data.icon || Database;
  const color = data.colorClass || 'text-emerald-400';
  return (
    <div className="px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 w-[170px] shadow-md">
      <Handle type="target" position={Position.Top} id="top" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Top} id="top-out" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Bottom} id="bottom" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="bottom-out" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <div className="flex items-center gap-2 mb-0.5">
        <Icon className={`w-3.5 h-3.5 ${color}`} />
        <span className="text-xs font-bold">{data.label}</span>
      </div>
      <p className="text-[9px] text-muted-foreground leading-tight">{data.subtitle}</p>
      {data.count && (
        <p className={`text-[10px] font-bold mt-1 ${color}`}>{data.count}</p>
      )}
    </div>
  );
}

interface ToolNodeData {
  label: string;
  subtitle: string;
  icon?: ComponentType<{ className?: string }>;
  count?: string;
  tools?: string[];
}

function ToolNode({ data }: { data: ToolNodeData }) {
  const Icon = data.icon || Wrench;
  return (
    <div className="px-3 py-2 rounded-lg border border-purple-500/40 bg-purple-500/5 w-[200px] shadow-md">
      <Handle type="target" position={Position.Top} id="top" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Top} id="top-out" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Bottom} id="bottom-in" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} id="right" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} id="left" style={{ opacity: 0 }} />
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon className="w-3.5 h-3.5 text-purple-400" />
        <span className="text-xs font-bold text-purple-300">{data.label}</span>
        {data.count && (
          <span className="text-[9px] px-1 rounded bg-purple-500/20 text-purple-300 ml-auto">
            {data.count}
          </span>
        )}
      </div>
      <p className="text-[9px] text-muted-foreground leading-tight mb-1">{data.subtitle}</p>
      {data.tools && (
        <div className="flex flex-wrap gap-0.5">
          {data.tools.map((t, i) => (
            <span
              key={i}
              className="text-[8px] px-1 py-0.5 rounded bg-purple-500/10 text-purple-300/80"
            >
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

interface IONodeData {
  label: string;
  subtitle?: string;
  icon?: ComponentType<{ className?: string }>;
  variant?: 'input' | 'output' | 'state';
}

function IONode({ data }: { data: IONodeData }) {
  const Icon = data.icon || MessageSquare;
  const variant = data.variant || 'input';
  const styles = {
    input: 'border-blue-500/40 bg-blue-500/5 text-blue-300',
    output: 'border-amber-500/40 bg-amber-500/5 text-amber-300',
    state: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
  };
  return (
    <div
      className={`px-3 py-2 rounded-md border w-[160px] shadow-sm ${styles[variant]}`}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top} id="top" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Top} id="top-out" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Bottom} id="bottom-in" style={{ opacity: 0 }} />
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon className="w-3.5 h-3.5" />
        <span className="text-xs font-bold">{data.label}</span>
      </div>
      {data.subtitle && (
        <p className="text-[9px] text-muted-foreground leading-tight">{data.subtitle}</p>
      )}
    </div>
  );
}

// Swimlane label node — just a text block with transparent background
function SwimlaneLabel({ data }: { data: { label: string; color: string } }) {
  return (
    <div
      className={`text-[10px] font-bold uppercase tracking-widest ${data.color} px-3 py-1 border-l-2 ${data.color.replace('text-', 'border-')} pointer-events-none`}
    >
      {data.label}
    </div>
  );
}

const nodeTypes = {
  agentNode: AgentNode,
  dataNode: DataNode,
  toolNode: ToolNode,
  ioNode: IONode,
  swimlaneLabel: SwimlaneLabel,
};

// ============================================================================
// Swimlane backgrounds (group nodes with no parenting — purely visual)
// ============================================================================

type SwimLane = {
  id: string;
  label: string;
  y: number;
  height: number;
  bg: string;
  border: string;
  labelColor: string;
};

const LANES: SwimLane[] = [
  {
    id: 'lane-input',
    label: 'LAYER 1 · Input / Entry',
    y: 0,
    height: 130,
    bg: 'rgba(59, 130, 246, 0.035)',
    border: 'rgba(59, 130, 246, 0.25)',
    labelColor: 'text-blue-400',
  },
  {
    id: 'lane-agents',
    label: 'LAYER 2 · Agent Pipeline (LangGraph V2)',
    y: 150,
    height: 250,
    bg: 'rgba(168, 85, 247, 0.035)',
    border: 'rgba(168, 85, 247, 0.25)',
    labelColor: 'text-purple-400',
  },
  {
    id: 'lane-tools',
    label: 'LAYER 3 · Knowledge & MCP Tool Layer',
    y: 420,
    height: 260,
    bg: 'rgba(16, 185, 129, 0.035)',
    border: 'rgba(16, 185, 129, 0.25)',
    labelColor: 'text-emerald-400',
  },
  {
    id: 'lane-output',
    label: 'LAYER 4 · State · Event Stream · Persistence',
    y: 700,
    height: 220,
    bg: 'rgba(245, 158, 11, 0.035)',
    border: 'rgba(245, 158, 11, 0.25)',
    labelColor: 'text-amber-400',
  },
  {
    id: 'lane-eval',
    label: 'LAYER 5 · Offline Evaluation Harness',
    y: 940,
    height: 180,
    bg: 'rgba(236, 72, 153, 0.035)',
    border: 'rgba(236, 72, 153, 0.25)',
    labelColor: 'text-pink-400',
  },
];

const swimlaneNodes: Node[] = LANES.flatMap<Node>((lane) => [
  // Background rectangle (group node, no parent relationship)
  {
    id: lane.id,
    type: 'group',
    position: { x: 0, y: lane.y },
    data: { label: '' },
    style: {
      width: 1180,
      height: lane.height,
      background: lane.bg,
      border: `1px dashed ${lane.border}`,
      borderRadius: 12,
      pointerEvents: 'none',
    },
    draggable: false,
    selectable: false,
  },
  // Label overlay on the top-left of each lane
  {
    id: `${lane.id}-label`,
    type: 'swimlaneLabel',
    position: { x: 20, y: lane.y + 8 },
    data: { label: lane.label, color: lane.labelColor },
    draggable: false,
    selectable: false,
  },
]);

// ============================================================================
// Content Nodes
// ============================================================================

const contentNodes: Node[] = [
  // ========== LAYER 1: INPUT ==========
  {
    id: 'patient',
    type: 'ioNode',
    position: { x: 180, y: 60 },
    data: {
      label: 'Patient Input',
      subtitle: 'Symptom description',
      icon: User,
      variant: 'input',
    },
  },
  {
    id: 'websocket-entry',
    type: 'ioNode',
    position: { x: 380, y: 60 },
    data: {
      label: 'WebSocket /ws/:sid',
      subtitle: 'Real-time bidirectional',
      icon: Radio,
      variant: 'input',
    },
  },
  {
    id: 'rest-entry',
    type: 'ioNode',
    position: { x: 580, y: 60 },
    data: {
      label: 'REST /api/v1/chat',
      subtitle: 'Sync single-turn',
      icon: Server,
      variant: 'input',
    },
  },

  // ========== LAYER 2: AGENT PIPELINE ==========
  {
    id: 'interviewer',
    type: 'agentNode',
    position: { x: 60, y: 210 },
    data: {
      label: 'Interviewer',
      subtitle: 'SOCRATES history collection with LLM-driven multi-turn questioning',
      icon: MessageSquare,
      borderClass: 'border-blue-500',
      bgClass: 'bg-blue-500/10',
      iconClass: 'text-blue-400',
      labelClass: 'text-blue-300',
      badges: ['interrupt/resume', 'Pydantic schema'],
    },
  },
  {
    id: 'diagnostician',
    type: 'agentNode',
    position: { x: 320, y: 210 },
    data: {
      label: 'Diagnostician',
      subtitle: 'RAG-enhanced differential diagnosis generator (top 3 DDx + confidence)',
      icon: Brain,
      borderClass: 'border-emerald-500',
      bgClass: 'bg-emerald-500/10',
      iconClass: 'text-emerald-400',
      labelClass: 'text-emerald-300',
      badges: ['RAG top_k=5', '3 DDx'],
    },
  },
  {
    id: 'debate',
    type: 'agentNode',
    position: { x: 580, y: 210 },
    data: {
      label: 'Debate Round',
      subtitle: 'Structured Critic↔Diagnostician debate, accept/refute/partially_accept per challenge',
      icon: Swords,
      borderClass: 'border-purple-500',
      bgClass: 'bg-purple-500/10',
      iconClass: 'text-purple-400',
      labelClass: 'text-purple-300',
      badges: ['V2', 'max 3 rounds', 'iterative'],
    },
  },
  {
    id: 'coordinator',
    type: 'agentNode',
    position: { x: 840, y: 210 },
    data: {
      label: 'Coordinator',
      subtitle: 'Synthesises final empathetic patient-facing response with all evidence',
      icon: Sparkles,
      borderClass: 'border-amber-500',
      bgClass: 'bg-amber-500/10',
      iconClass: 'text-amber-400',
      labelClass: 'text-amber-300',
      badges: ['final output'],
    },
  },

  // ========== LAYER 3: TOOLS & KNOWLEDGE ==========
  {
    id: 'chromadb',
    type: 'dataNode',
    position: { x: 330, y: 460 },
    data: {
      label: 'ChromaDB RAG',
      subtitle: 'Medical textbooks + StatPearls vector store',
      icon: BookOpen,
      count: '~5,000 entries',
      colorClass: 'text-emerald-400',
    },
  },
  {
    id: 'cdss-mcp',
    type: 'toolNode',
    position: { x: 560, y: 460 },
    data: {
      label: 'CDSS MCP Server',
      subtitle: 'cdss/mcp_server.py · stdio · deterministic scoring',
      icon: Wrench,
      count: '7 tools',
      tools: ['Wells', 'CURB-65', 'HEART', 'qSOFA', 'PHQ-9', 'CHA2DS2', 'DrugInterx'],
    },
  },
  {
    id: 'research-mcp',
    type: 'toolNode',
    position: { x: 830, y: 460 },
    data: {
      label: 'Research MCP Server',
      subtitle: 'mcp_server.py · stdio · external literature APIs',
      icon: Wrench,
      count: '3 tools',
      tools: ['PubMed', 'DrugBank', 'ICD-11'],
    },
  },
  {
    id: 'bridge',
    type: 'dataNode',
    position: { x: 575, y: 575 },
    data: {
      label: 'LangChain Bridge',
      subtitle: 'cdss/bridge.py @tool wrapper · in-process call',
      icon: Layers,
      colorClass: 'text-purple-400',
    },
  },

  // ========== LAYER 4: OUTPUT / STATE ==========
  {
    id: 'graph-state',
    type: 'ioNode',
    position: { x: 60, y: 730 },
    data: {
      label: 'GraphState',
      subtitle: '11 typed fields incl. debate_rounds, cdss_scores',
      icon: FileJson,
      variant: 'state',
    },
  },
  {
    id: 'ws-events',
    type: 'ioNode',
    position: { x: 320, y: 730 },
    data: {
      label: 'WS Event Stream',
      subtitle: '6 event types streamed real-time',
      icon: Zap,
      variant: 'state',
    },
  },
  {
    id: 'frontend',
    type: 'ioNode',
    position: { x: 580, y: 730 },
    data: {
      label: 'Frontend Components',
      subtitle: 'ChatBubble · DebateView · DiagnosisPanel',
      icon: Radio,
      variant: 'state',
    },
  },
  {
    id: 'database',
    type: 'ioNode',
    position: { x: 840, y: 730 },
    data: {
      label: 'SQLAlchemy DB',
      subtitle: 'sessions / messages / agent_logs',
      icon: HardDrive,
      variant: 'state',
    },
  },
  {
    id: 'ws-types',
    type: 'ioNode',
    position: { x: 320, y: 820 },
    data: {
      label: '6 WS event types',
      subtitle: 'agent_transition · reasoning · message · debate_challenge · debate_response · diagnosis_result',
      icon: Zap,
      variant: 'state',
    },
  },

  // ========== LAYER 5: EVALUATION ==========
  {
    id: 'eval-cases',
    type: 'ioNode',
    position: { x: 60, y: 970 },
    data: {
      label: 'Ground Truth Cases',
      subtitle: '7 clinical cases (EVAL-001..007)',
      icon: Target,
      variant: 'output',
    },
  },
  {
    id: 'eval-score',
    type: 'ioNode',
    position: { x: 320, y: 970 },
    data: {
      label: 'score_single_case()',
      subtitle: 'Top-1/Top-3/Safety + fuzzy match',
      icon: BarChart3,
      variant: 'output',
    },
  },
  {
    id: 'eval-metrics',
    type: 'ioNode',
    position: { x: 580, y: 970 },
    data: {
      label: 'aggregate_metrics()',
      subtitle: 'Top-1 85.7% · Safety 100% · AvgR 2.3',
      icon: BarChart3,
      variant: 'output',
    },
  },
  {
    id: 'eval-reports',
    type: 'ioNode',
    position: { x: 840, y: 970 },
    data: {
      label: 'Reports',
      subtitle: 'evaluation_latest.json + .md',
      icon: FileCheck,
      variant: 'output',
    },
  },
];

const initialNodes: Node[] = [...swimlaneNodes, ...contentNodes];

// ============================================================================
// Edges — 4 types
// ============================================================================

const mainEdge = (id: string, source: string, target: string, label?: string): Edge => ({
  id,
  source,
  target,
  animated: true,
  label,
  labelStyle: { fill: 'hsl(215 15% 70%)', fontSize: 10, fontFamily: '"IBM Plex Sans"' },
  labelBgStyle: { fill: 'hsl(220 18% 11%)', fillOpacity: 0.85 },
  labelBgPadding: [4, 2],
  style: { stroke: 'hsl(210 80% 55%)', strokeWidth: 2.5 },
  markerEnd: { type: MarkerType.ArrowClosed, color: 'hsl(210 80% 55%)' },
});

const dataEdge = (
  id: string,
  source: string,
  target: string,
  label: string,
  sourceHandle?: string,
  targetHandle?: string,
): Edge => ({
  id,
  source,
  target,
  sourceHandle,
  targetHandle,
  animated: true,
  label,
  labelStyle: { fill: 'hsl(215 15% 55%)', fontSize: 9, fontFamily: '"IBM Plex Sans"' },
  labelBgStyle: { fill: 'hsl(220 18% 11%)', fillOpacity: 0.85 },
  labelBgPadding: [4, 2],
  style: { stroke: 'hsl(150 60% 50%)', strokeWidth: 1.5, strokeDasharray: '6 3' },
  markerEnd: { type: MarkerType.ArrowClosed, color: 'hsl(150 60% 50%)' },
});

const toolEdge = (
  id: string,
  source: string,
  target: string,
  label: string,
  sourceHandle?: string,
  targetHandle?: string,
): Edge => ({
  id,
  source,
  target,
  sourceHandle,
  targetHandle,
  animated: true,
  label,
  labelStyle: { fill: 'hsl(280 60% 65%)', fontSize: 9, fontFamily: '"IBM Plex Sans"' },
  labelBgStyle: { fill: 'hsl(220 18% 11%)', fillOpacity: 0.85 },
  labelBgPadding: [4, 2],
  style: { stroke: 'hsl(280 60% 55%)', strokeWidth: 1.5, strokeDasharray: '6 3' },
  markerEnd: { type: MarkerType.ArrowClosed, color: 'hsl(280 60% 55%)' },
});

const loopEdge = (id: string, node: string, label: string): Edge => ({
  id,
  source: node,
  target: node,
  sourceHandle: 'top-out',
  targetHandle: 'top',
  type: 'smoothstep',
  animated: true,
  label,
  labelStyle: { fill: 'hsl(280 60% 70%)', fontSize: 10, fontWeight: 600, fontFamily: '"IBM Plex Sans"' },
  labelBgStyle: { fill: 'hsl(220 18% 11%)', fillOpacity: 0.85 },
  labelBgPadding: [4, 2],
  style: { stroke: 'hsl(280 60% 50%)', strokeWidth: 2 },
  markerEnd: { type: MarkerType.ArrowClosed, color: 'hsl(280 60% 50%)' },
});

const bypassEdge = (id: string, source: string, target: string, label: string): Edge => ({
  id,
  source,
  target,
  animated: true,
  label,
  labelStyle: { fill: 'hsl(38 90% 55% / 0.8)', fontSize: 9, fontStyle: 'italic', fontFamily: '"IBM Plex Sans"' },
  labelBgStyle: { fill: 'hsl(220 18% 11%)', fillOpacity: 0.85 },
  labelBgPadding: [4, 2],
  style: { stroke: 'hsl(38 90% 55% / 0.5)', strokeWidth: 1.5, strokeDasharray: '4 4' },
  markerEnd: { type: MarkerType.ArrowClosed, color: 'hsl(38 90% 55% / 0.5)' },
  type: 'smoothstep',
});

const initialEdges: Edge[] = [
  // === LAYER 1→2: Input enters pipeline ===
  mainEdge('e-patient-ws', 'patient', 'websocket-entry'),
  mainEdge('e-ws-int', 'websocket-entry', 'interviewer'),
  dataEdge('e-rest-int', 'rest-entry', 'interviewer', 'alternative entry'),

  // === LAYER 2: Main agent pipeline ===
  mainEdge('e-int-diag', 'interviewer', 'diagnostician', 'history complete'),
  mainEdge('e-diag-debate', 'diagnostician', 'debate', 'handoff DDx'),
  mainEdge('e-debate-coord', 'debate', 'coordinator', 'approved'),

  // === LAYER 2: Self-loops ===
  loopEdge('e-int-loop', 'interviewer', '⟲ ask more (interrupt/resume)'),
  loopEdge('e-debate-loop', 'debate', '⟲ iterate (max 3 rounds)'),

  // === LAYER 2: Bypass edge ===
  bypassEdge('e-diag-coord-bypass', 'diagnostician', 'coordinator', 'no dispute (V1 compat)'),

  // === LAYER 2→3: Tool / data access (vertical dashed) ===
  dataEdge('e-diag-rag', 'diagnostician', 'chromadb', 'RAG top_k=5', 'bottom', 'top'),
  toolEdge('e-debate-cdss', 'debate', 'cdss-mcp', 'tool call', 'bottom', 'top'),
  toolEdge('e-diag-research', 'diagnostician', 'research-mcp', 'PubMed cite', 'bottom', 'top'),

  // === LAYER 3: CDSS → Bridge → Agent ===
  toolEdge('e-cdss-bridge', 'cdss-mcp', 'bridge', 'in-process', 'bottom', 'top'),

  // === LAYER 2→4: State flow down ===
  dataEdge('e-int-state', 'interviewer', 'graph-state', 'write', 'bottom', 'top'),
  dataEdge('e-coord-state', 'coordinator', 'graph-state', 'write', 'bottom', 'top'),
  dataEdge('e-coord-ws', 'coordinator', 'ws-events', 'emit', 'bottom', 'top'),
  dataEdge('e-debate-ws', 'debate', 'ws-events', 'emit', 'bottom', 'top'),
  dataEdge('e-ws-frontend', 'ws-events', 'frontend', 'stream'),
  dataEdge('e-state-db', 'graph-state', 'database', 'persist'),
  dataEdge('e-ws-types', 'ws-events', 'ws-types', 'emits', 'bottom', 'top'),

  // === LAYER 5: Evaluation flow (self-contained) ===
  mainEdge('e-cases-score', 'eval-cases', 'eval-score', 'invoke'),
  mainEdge('e-score-metrics', 'eval-score', 'eval-metrics', 'aggregate'),
  mainEdge('e-metrics-reports', 'eval-metrics', 'eval-reports', 'generate'),

  // === LAYER 5→4: Harness reads from GraphState type (architectural reuse) ===
  dataEdge('e-eval-state-link', 'graph-state', 'eval-score', 'shared schema'),
];

// ============================================================================
// Legend (absolutely positioned overlay)
// ============================================================================

function Legend() {
  return (
    <div className="absolute top-4 right-4 bg-card/95 backdrop-blur border border-border rounded-lg p-3 text-[10px] z-20 w-64 shadow-xl pointer-events-none">
      <div className="font-bold text-xs mb-2 flex items-center gap-1.5">
        <Layers className="w-3.5 h-3.5" />
        Architecture Legend
      </div>

      <div className="space-y-1.5 mb-2">
        <div className="font-semibold text-[9px] text-muted-foreground uppercase tracking-wider">Agents</div>
        <div className="flex items-center gap-2">
          <MessageSquare className="w-3 h-3 text-blue-400" />
          <span className="text-muted-foreground">Interviewer — SOCRATES</span>
        </div>
        <div className="flex items-center gap-2">
          <Brain className="w-3 h-3 text-emerald-400" />
          <span className="text-muted-foreground">Diagnostician — RAG DDx</span>
        </div>
        <div className="flex items-center gap-2">
          <Swords className="w-3 h-3 text-purple-400" />
          <span className="text-muted-foreground">Debate Round — V2 ⭐</span>
        </div>
        <div className="flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-amber-400" />
          <span className="text-muted-foreground">Coordinator — synthesis</span>
        </div>
      </div>

      <div className="border-t border-border pt-2 space-y-1">
        <div className="font-semibold text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Edges</div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-[2px] bg-blue-500" />
          <span className="text-muted-foreground">main pipeline</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-[1.5px]" style={{ borderTop: '1.5px dashed hsl(150 60% 50%)' }} />
          <span className="text-muted-foreground">data / state flow</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-[1.5px]" style={{ borderTop: '1.5px dashed hsl(280 60% 55%)' }} />
          <span className="text-muted-foreground">MCP tool call</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-purple-400 font-bold">⟲</span>
          <span className="text-muted-foreground">self-loop (iterate)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-[1.5px]" style={{ borderTop: '1.5px dashed hsl(38 90% 55% / 0.5)' }} />
          <span className="text-muted-foreground italic">bypass (no dispute)</span>
        </div>
      </div>

      <div className="border-t border-border pt-2 mt-2 text-[9px] text-muted-foreground leading-snug">
        <span className="font-bold text-foreground">V2 highlights</span>: debate protocol, 2 MCP servers,
        dual-mode CDSS (MCP + LangChain bridge), offline eval harness.
      </div>
    </div>
  );
}

// ============================================================================
// Main Workflow component
// ============================================================================

export default function Workflow() {
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  return (
    <div className="p-6 space-y-4 h-full flex flex-col">
      <div>
        <h1 className="text-2xl font-bold">Agent Workflow</h1>
        <p className="text-sm text-muted-foreground">
          Complete V2 architecture · 5-layer swimlane · 4 agents · 2 MCP servers · RAG · Harness eval
        </p>
      </div>
      <div className="flex-1 bg-card border border-border rounded-lg overflow-hidden min-h-[600px] relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          fitView
          fitViewOptions={{ padding: 0.12, maxZoom: 0.85, minZoom: 0.5 }}
          minZoom={0.35}
          maxZoom={1.8}
          proOptions={{ hideAttribution: true }}
        >
          <Background
            color="hsl(220 14% 15%)"
            gap={24}
            variant={BackgroundVariant.Dots}
          />
          <Controls
            style={{
              background: 'hsl(220 18% 11%)',
              border: '1px solid hsl(220 14% 18%)',
              borderRadius: 8,
            }}
          />
        </ReactFlow>
        <Legend />
      </div>
    </div>
  );
}
