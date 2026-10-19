import { useState } from 'react';
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
  Wrench,
  Activity,
  Stethoscope,
  HeartPulse,
  AlertCircle,
  Brain,
  Thermometer,
  Pill,
  BookOpen,
  Database,
  Server,
  Search,
  Tag,
  FileJson,
  Layers,
  Globe,
  Zap,
  MessageSquare,
  Swords,
  Sparkles,
  ArrowRight,
  Shield,
  Network,
  Workflow as WorkflowIcon,
} from 'lucide-react';
import type { ComponentType } from 'react';
import McpSequenceView from '@/components/McpSequenceView';
import McpToolInternals from '@/components/McpToolInternals';
import { Cpu } from 'lucide-react';

// ============================================================================
// Custom Node Components
// ============================================================================

// -- MCP Server node --
function McpServerNode({ data }: { data: { label: string; subtitle: string; icon: ComponentType<{ className?: string }>; count: string; tools: string[]; borderClass: string; bgClass: string; iconClass: string } }) {
  const Icon = data.icon;
  return (
    <div className={`px-4 py-3 rounded-xl border-2 ${data.borderClass} ${data.bgClass} w-[260px] shadow-lg`}>
      <Handle type="target" position={Position.Top} id="top" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Top} id="top-out" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Bottom} id="bottom-in" style={{ opacity: 0 }} />
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-4 h-4 ${data.iconClass}`} />
        <span className={`font-bold text-sm ${data.iconClass}`}>{data.label}</span>
        <span className="text-[9px] px-1.5 rounded bg-background/70 border border-border text-muted-foreground ml-auto">{data.count}</span>
      </div>
      <p className="text-[10px] text-muted-foreground font-mono mb-2">{data.subtitle}</p>
      <div className="flex flex-wrap gap-1">
        {data.tools.map((t, i) => (
          <span key={i} className={`text-[9px] px-1.5 py-0.5 rounded border ${data.borderClass.replace('border-', 'border-').replace('/40', '/20')} ${data.bgClass} ${data.iconClass}`}>
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

// -- Tool detail node (shows input → output) --
function ToolDetailNode({ data }: { data: { label: string; mcpName: string; icon: ComponentType<{ className?: string }>; inputs: string[]; outputs: string[]; colorClass: string; borderClass: string; bgClass: string } }) {
  const Icon = data.icon;
  return (
    <div className={`px-3 py-2.5 rounded-lg border ${data.borderClass} ${data.bgClass} w-[220px] shadow-md`}>
      <Handle type="target" position={Position.Top} id="top" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className={`w-3.5 h-3.5 ${data.colorClass}`} />
        <span className={`text-xs font-bold ${data.colorClass}`}>{data.label}</span>
      </div>
      <p className="text-[9px] text-muted-foreground font-mono mb-2">{data.mcpName}</p>
      <div className="space-y-1.5">
        <div>
          <div className="text-[8px] uppercase tracking-wider text-muted-foreground font-semibold mb-0.5">Input</div>
          {data.inputs.map((inp, i) => (
            <div key={i} className="text-[9px] text-foreground/70 font-mono leading-tight">{inp}</div>
          ))}
        </div>
        <div className="border-t border-border/30 pt-1">
          <div className="text-[8px] uppercase tracking-wider text-muted-foreground font-semibold mb-0.5">Output</div>
          {data.outputs.map((out, i) => (
            <div key={i} className="text-[9px] text-foreground/70 font-mono leading-tight">{out}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

// -- Agent caller node --
function AgentNode({ data }: { data: { label: string; subtitle: string; icon: ComponentType<{ className?: string }>; borderClass: string; bgClass: string; iconClass: string; badges?: string[] } }) {
  const Icon = data.icon;
  return (
    <div className={`px-3 py-2 rounded-lg border-2 ${data.borderClass} ${data.bgClass} w-[180px] shadow-lg`}>
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top} id="top" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ opacity: 0 }} />
      <div className="flex items-center gap-2 mb-0.5">
        <Icon className={`w-4 h-4 ${data.iconClass}`} />
        <span className={`font-bold text-sm ${data.iconClass}`}>{data.label}</span>
      </div>
      <p className="text-[10px] text-muted-foreground leading-snug">{data.subtitle}</p>
      {data.badges && (
        <div className="flex flex-wrap gap-1 mt-1">
          {data.badges.map((b, i) => (
            <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-background/70 border border-border text-muted-foreground">{b}</span>
          ))}
        </div>
      )}
    </div>
  );
}

// -- External API node --
function ApiNode({ data }: { data: { label: string; subtitle: string; icon: ComponentType<{ className?: string }>; url?: string } }) {
  const Icon = data.icon;
  return (
    <div className="px-3 py-2 rounded-lg border border-amber-500/40 bg-amber-500/5 w-[200px] shadow-md">
      <Handle type="target" position={Position.Top} id="top" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Top} id="top-out" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Bottom} id="bottom-in" style={{ opacity: 0 }} />
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon className="w-3.5 h-3.5 text-amber-400" />
        <span className="text-xs font-bold text-amber-300">{data.label}</span>
      </div>
      <p className="text-[9px] text-muted-foreground leading-tight">{data.subtitle}</p>
      {data.url && <p className="text-[8px] text-amber-400/60 font-mono mt-0.5 truncate">{data.url}</p>}
    </div>
  );
}

// -- Data store node --
function DataNode({ data }: { data: { label: string; subtitle: string; icon: ComponentType<{ className?: string }>; count?: string; colorClass?: string } }) {
  const Icon = data.icon || Database;
  const color = data.colorClass || 'text-emerald-400';
  return (
    <div className="px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 w-[180px] shadow-md">
      <Handle type="target" position={Position.Top} id="top" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <div className="flex items-center gap-2 mb-0.5">
        <Icon className={`w-3.5 h-3.5 ${color}`} />
        <span className="text-xs font-bold">{data.label}</span>
      </div>
      <p className="text-[9px] text-muted-foreground leading-tight">{data.subtitle}</p>
      {data.count && <p className={`text-[10px] font-bold mt-0.5 ${color}`}>{data.count}</p>}
    </div>
  );
}

// -- IO node --
function IONode({ data }: { data: { label: string; subtitle?: string; icon?: ComponentType<{ className?: string }>; variant?: 'input' | 'output' | 'state' } }) {
  const Icon = data.icon || FileJson;
  const variant = data.variant || 'state';
  const styles = {
    input: 'border-blue-500/40 bg-blue-500/5 text-blue-300',
    output: 'border-amber-500/40 bg-amber-500/5 text-amber-300',
    state: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
  };
  return (
    <div className={`px-3 py-2 rounded-md border w-[170px] shadow-sm ${styles[variant]}`}>
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Top} id="top" style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} id="bottom" style={{ opacity: 0 }} />
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon className="w-3.5 h-3.5" />
        <span className="text-xs font-bold">{data.label}</span>
      </div>
      {data.subtitle && <p className="text-[9px] text-muted-foreground leading-tight">{data.subtitle}</p>}
    </div>
  );
}

// -- Swimlane label --
function SwimlaneLabel({ data }: { data: { label: string; color: string } }) {
  return (
    <div className={`text-[10px] font-bold uppercase tracking-widest ${data.color} px-3 py-1 border-l-2 ${data.color.replace('text-', 'border-')} pointer-events-none`}>
      {data.label}
    </div>
  );
}

const nodeTypes = {
  mcpServerNode: McpServerNode,
  toolDetailNode: ToolDetailNode,
  agentNode: AgentNode,
  apiNode: ApiNode,
  dataNode: DataNode,
  ioNode: IONode,
  swimlaneLabel: SwimlaneLabel,
};

// ============================================================================
// Swimlanes
// ============================================================================

type SwimLane = { id: string; label: string; y: number; height: number; bg: string; border: string; labelColor: string };

const LANES: SwimLane[] = [
  { id: 'lane-agents', label: 'LAYER 1 · Agent Callers (LangGraph Pipeline)', y: 0, height: 120, bg: 'rgba(59, 130, 246, 0.035)', border: 'rgba(59, 130, 246, 0.25)', labelColor: 'text-blue-400' },
  { id: 'lane-protocol', label: 'LAYER 2 · MCP Protocol Layer (stdio transport)', y: 140, height: 130, bg: 'rgba(168, 85, 247, 0.035)', border: 'rgba(168, 85, 247, 0.25)', labelColor: 'text-purple-400' },
  { id: 'lane-cdss', label: 'LAYER 3 · CDSS Tools — Deterministic Scoring (cdss/mcp_server.py)', y: 290, height: 420, bg: 'rgba(59, 130, 246, 0.03)', border: 'rgba(59, 130, 246, 0.2)', labelColor: 'text-blue-400' },
  { id: 'lane-research', label: 'LAYER 4 · Research Tools — External API Lookup (mcp_server.py)', y: 730, height: 310, bg: 'rgba(16, 185, 129, 0.035)', border: 'rgba(16, 185, 129, 0.25)', labelColor: 'text-emerald-400' },
  { id: 'lane-external', label: 'LAYER 5 · External APIs & Data Sources', y: 1060, height: 130, bg: 'rgba(245, 158, 11, 0.035)', border: 'rgba(245, 158, 11, 0.25)', labelColor: 'text-amber-400' },
];

const W = 1400;

const swimlaneNodes: Node[] = LANES.flatMap<Node>((lane) => [
  {
    id: lane.id, type: 'group', position: { x: 0, y: lane.y }, data: { label: '' },
    style: { width: W, height: lane.height, background: lane.bg, border: `1px dashed ${lane.border}`, borderRadius: 12, pointerEvents: 'none' },
    draggable: false, selectable: false,
  },
  {
    id: `${lane.id}-label`, type: 'swimlaneLabel', position: { x: 20, y: lane.y + 8 },
    data: { label: lane.label, color: lane.labelColor }, draggable: false, selectable: false,
  },
]);

// ============================================================================
// Content Nodes
// ============================================================================

const contentNodes: Node[] = [
  // === LAYER 1: Agent Callers ===
  { id: 'diagnostician', type: 'agentNode', position: { x: 80, y: 40 }, data: { label: 'Diagnostician', subtitle: 'RAG-enhanced differential diagnosis', icon: Brain, borderClass: 'border-emerald-500', bgClass: 'bg-emerald-500/10', iconClass: 'text-emerald-400', badges: ['RAG', 'CDSS', 'PubMed'] } },
  { id: 'debate', type: 'agentNode', position: { x: 340, y: 40 }, data: { label: 'Debate Round', subtitle: 'Critic vs Diagnostician debate', icon: Swords, borderClass: 'border-purple-500', bgClass: 'bg-purple-500/10', iconClass: 'text-purple-400', badges: ['CDSS scoring'] } },
  { id: 'coordinator', type: 'agentNode', position: { x: 600, y: 40 }, data: { label: 'Coordinator', subtitle: 'Final response synthesis', icon: Sparkles, borderClass: 'border-amber-500', bgClass: 'bg-amber-500/10', iconClass: 'text-amber-400', badges: ['citations'] } },
  { id: 'interviewer', type: 'agentNode', position: { x: 860, y: 40 }, data: { label: 'Interviewer', subtitle: 'SOCRATES history collection', icon: MessageSquare, borderClass: 'border-blue-500', bgClass: 'bg-blue-500/10', iconClass: 'text-blue-400', badges: ['multi-turn'] } },
  { id: 'rag-store', type: 'dataNode', position: { x: 1120, y: 40 }, data: { label: 'ChromaDB RAG', subtitle: 'Medical textbook vectors', icon: BookOpen, count: '~5,000 entries', colorClass: 'text-emerald-400' } },

  // === LAYER 2: MCP Protocol ===
  { id: 'cdss-server', type: 'mcpServerNode', position: { x: 80, y: 170 }, data: { label: 'CDSS MCP Server', subtitle: 'cdss/mcp_server.py · FastMCP · stdio', icon: Server, count: '7 tools', tools: ['Wells', 'CURB-65', 'CHA2DS2-VASc', 'HEART', 'qSOFA', 'PHQ-9', 'DrugInterx'], borderClass: 'border-blue-500/40', bgClass: 'bg-blue-500/5', iconClass: 'text-blue-400' } },
  { id: 'research-server', type: 'mcpServerNode', position: { x: 500, y: 170 }, data: { label: 'Research MCP Server', subtitle: 'mcp_server.py · FastMCP · stdio', icon: Server, count: '3 tools', tools: ['PubMed Search', 'DrugBank Lookup', 'ICD-11 Lookup'], borderClass: 'border-emerald-500/40', bgClass: 'bg-emerald-500/5', iconClass: 'text-emerald-400' } },
  { id: 'bridge', type: 'ioNode', position: { x: 920, y: 180 }, data: { label: 'LangChain Bridge', subtitle: 'cdss/bridge.py @tool wrapper for in-process agent calls', icon: Layers, variant: 'state' } },
  { id: 'fallback', type: 'ioNode', position: { x: 1150, y: 180 }, data: { label: 'Legacy Fallback', subtitle: 'tool_registry.py — sync API if MCP down', icon: Shield, variant: 'state' } },

  // === LAYER 3: CDSS Tool Details ===
  { id: 'wells', type: 'toolDetailNode', position: { x: 30, y: 330 }, data: {
    label: 'Wells Score', mcpName: 'cdss_wells_score', icon: HeartPulse, colorClass: 'text-blue-400', borderClass: 'border-blue-500/30', bgClass: 'bg-blue-500/5',
    inputs: ['clinical_signs_dvt: bool', 'pe_most_likely: bool', 'heart_rate_over_100: bool', 'immobilization_or_surgery: bool', 'previous_dvt_pe: bool', 'hemoptysis: bool', 'malignancy: bool'],
    outputs: ['score: 0–12.5', 'risk_level: low|mod|high', 'recommendation: string'],
  }},
  { id: 'curb65', type: 'toolDetailNode', position: { x: 280, y: 330 }, data: {
    label: 'CURB-65', mcpName: 'cdss_curb65', icon: Thermometer, colorClass: 'text-blue-400', borderClass: 'border-blue-500/30', bgClass: 'bg-blue-500/5',
    inputs: ['confusion: bool', 'urea_over_7: bool', 'resp_rate_over_30: bool', 'low_blood_pressure: bool', 'age_over_65: bool'],
    outputs: ['score: 0–5', 'severity: low|mod|severe', 'mortality_risk: string'],
  }},
  { id: 'cha2ds2', type: 'toolDetailNode', position: { x: 530, y: 330 }, data: {
    label: 'CHA2DS2-VASc', mcpName: 'cdss_cha2ds2_vasc', icon: Activity, colorClass: 'text-blue-400', borderClass: 'border-blue-500/30', bgClass: 'bg-blue-500/5',
    inputs: ['heart_failure: bool', 'hypertension: bool', 'age: int', 'diabetes: bool', 'stroke_history: bool', 'vascular_disease: bool', 'sex_female: bool'],
    outputs: ['score: 0–9', 'annual_stroke_risk: %', 'recommendation: string'],
  }},
  { id: 'heart', type: 'toolDetailNode', position: { x: 780, y: 330 }, data: {
    label: 'HEART Score', mcpName: 'cdss_heart_score', icon: AlertCircle, colorClass: 'text-blue-400', borderClass: 'border-blue-500/30', bgClass: 'bg-blue-500/5',
    inputs: ['history: 0–2', 'ecg: 0–2', 'age: 0–2', 'risk_factors: 0–2', 'troponin: 0–2'],
    outputs: ['score: 0–10', 'risk_level: low|mod|high', 'mace_risk: string'],
  }},
  { id: 'qsofa', type: 'toolDetailNode', position: { x: 30, y: 530 }, data: {
    label: 'qSOFA', mcpName: 'cdss_qsofa', icon: Stethoscope, colorClass: 'text-blue-400', borderClass: 'border-blue-500/30', bgClass: 'bg-blue-500/5',
    inputs: ['resp_rate_over_22: bool', 'altered_mentation: bool', 'systolic_bp_under_100: bool'],
    outputs: ['score: 0–3', 'sepsis_risk: string', 'recommendation: string'],
  }},
  { id: 'phq9', type: 'toolDetailNode', position: { x: 280, y: 530 }, data: {
    label: 'PHQ-9', mcpName: 'cdss_phq9', icon: Brain, colorClass: 'text-blue-400', borderClass: 'border-blue-500/30', bgClass: 'bg-blue-500/5',
    inputs: ['scores: int[9] (each 0–3)'],
    outputs: ['total_score: 0–27', 'severity: 5 levels', 'recommendation: string'],
  }},
  { id: 'drug-check', type: 'toolDetailNode', position: { x: 530, y: 530 }, data: {
    label: 'Drug Interactions', mcpName: 'cdss_drug_interactions', icon: Pill, colorClass: 'text-purple-400', borderClass: 'border-purple-500/30', bgClass: 'bg-purple-500/5',
    inputs: ['current_meds: string[]', 'proposed_meds: string[] (opt)'],
    outputs: ['interactions[]: {pair,sev,desc}', 'contraindicated: bool', 'clinical_notes: string[]'],
  }},
  { id: 'evidence-ref', type: 'ioNode', position: { x: 830, y: 560 }, data: { label: 'Evidence Sources', subtitle: 'Wells 2000 | Lim 2003 | Lip 2010 | Six 2008 | Singer 2016 | Kroenke 2001 | NLM RxNorm', icon: FileJson, variant: 'state' } },

  // === LAYER 4: Research Tool Details ===
  { id: 'pubmed', type: 'toolDetailNode', position: { x: 80, y: 770 }, data: {
    label: 'PubMed Search', mcpName: 'pubmed_search', icon: Search, colorClass: 'text-emerald-400', borderClass: 'border-emerald-500/30', bgClass: 'bg-emerald-500/5',
    inputs: ['query: string', '(e.g. "headache fever meningitis")'],
    outputs: ['results[5]: {title, authors,', '  journal, year, pmid, url}', 'count: int'],
  }},
  { id: 'drugbank', type: 'toolDetailNode', position: { x: 400, y: 770 }, data: {
    label: 'DrugBank Lookup', mcpName: 'drugbank_lookup', icon: Pill, colorClass: 'text-emerald-400', borderClass: 'border-emerald-500/30', bgClass: 'bg-emerald-500/5',
    inputs: ['drug_name: string', '(e.g. "metformin")'],
    outputs: ['brand_name, warnings,', 'drug_interactions,', 'adverse_reactions,', 'indications, source, url'],
  }},
  { id: 'icd11', type: 'toolDetailNode', position: { x: 720, y: 770 }, data: {
    label: 'ICD-11 Lookup', mcpName: 'icd11_lookup', icon: Tag, colorClass: 'text-emerald-400', borderClass: 'border-emerald-500/30', bgClass: 'bg-emerald-500/5',
    inputs: ['condition: string', '(e.g. "type 2 diabetes")'],
    outputs: ['results[5]: {code, title, url}', 'source: WHO ICD-11 2024-01', 'browse_url: string'],
  }},
  { id: 'local-kb', type: 'ioNode', position: { x: 1040, y: 790 }, data: { label: 'Local Fallback KB', subtitle: '~40 ICD-11 codes + 6 high-risk drug pairs hardcoded', icon: Database, variant: 'state' } },

  // === LAYER 5: External APIs ===
  { id: 'api-pubmed', type: 'apiNode', position: { x: 80, y: 1090 }, data: { label: 'PubMed eUtils', subtitle: 'NCBI medical literature database (free, no key)', icon: Globe, url: 'eutils.ncbi.nlm.nih.gov' } },
  { id: 'api-openfda', type: 'apiNode', position: { x: 360, y: 1090 }, data: { label: 'OpenFDA Drug Labels', subtitle: 'FDA drug label data (free, no key)', icon: Globe, url: 'api.fda.gov/drug/label.json' } },
  { id: 'api-rxnorm', type: 'apiNode', position: { x: 640, y: 1090 }, data: { label: 'NLM RxNorm', subtitle: 'Drug interaction checker (free, no key)', icon: Globe, url: 'rxnav.nlm.nih.gov/REST' } },
  { id: 'api-icd11', type: 'apiNode', position: { x: 920, y: 1090 }, data: { label: 'WHO ICD-11', subtitle: 'International Classification of Diseases', icon: Globe, url: 'icd.who.int/browse/2024-01' } },
];

const initialNodes: Node[] = [...swimlaneNodes, ...contentNodes];

// ============================================================================
// Edges
// ============================================================================

const mainEdge = (id: string, source: string, target: string, label?: string, sh?: string, th?: string): Edge => ({
  id, source, target, sourceHandle: sh, targetHandle: th, animated: true, label,
  labelStyle: { fill: 'hsl(215 15% 70%)', fontSize: 10, fontFamily: '"IBM Plex Sans"' },
  labelBgStyle: { fill: 'hsl(220 18% 11%)', fillOpacity: 0.85 }, labelBgPadding: [4, 2] as [number, number],
  style: { stroke: 'hsl(210 80% 55%)', strokeWidth: 2.5 },
  markerEnd: { type: MarkerType.ArrowClosed, color: 'hsl(210 80% 55%)' },
});

const toolEdge = (id: string, source: string, target: string, label: string, sh?: string, th?: string): Edge => ({
  id, source, target, sourceHandle: sh, targetHandle: th, animated: true, label,
  labelStyle: { fill: 'hsl(280 60% 65%)', fontSize: 9, fontFamily: '"IBM Plex Sans"' },
  labelBgStyle: { fill: 'hsl(220 18% 11%)', fillOpacity: 0.85 }, labelBgPadding: [4, 2] as [number, number],
  style: { stroke: 'hsl(280 60% 55%)', strokeWidth: 1.5, strokeDasharray: '6 3' },
  markerEnd: { type: MarkerType.ArrowClosed, color: 'hsl(280 60% 55%)' },
});

const dataEdge = (id: string, source: string, target: string, label: string, sh?: string, th?: string): Edge => ({
  id, source, target, sourceHandle: sh, targetHandle: th, animated: true, label,
  labelStyle: { fill: 'hsl(215 15% 55%)', fontSize: 9, fontFamily: '"IBM Plex Sans"' },
  labelBgStyle: { fill: 'hsl(220 18% 11%)', fillOpacity: 0.85 }, labelBgPadding: [4, 2] as [number, number],
  style: { stroke: 'hsl(150 60% 50%)', strokeWidth: 1.5, strokeDasharray: '6 3' },
  markerEnd: { type: MarkerType.ArrowClosed, color: 'hsl(150 60% 50%)' },
});

const apiEdge = (id: string, source: string, target: string, label: string, sh?: string, th?: string): Edge => ({
  id, source, target, sourceHandle: sh, targetHandle: th, animated: true, label,
  labelStyle: { fill: 'hsl(38 90% 60%)', fontSize: 9, fontFamily: '"IBM Plex Sans"' },
  labelBgStyle: { fill: 'hsl(220 18% 11%)', fillOpacity: 0.85 }, labelBgPadding: [4, 2] as [number, number],
  style: { stroke: 'hsl(38 90% 55% / 0.6)', strokeWidth: 1.5, strokeDasharray: '4 4' },
  markerEnd: { type: MarkerType.ArrowClosed, color: 'hsl(38 90% 55% / 0.6)' },
});

const initialEdges: Edge[] = [
  // === Layer 1 → Layer 2: Agents call MCP servers ===
  toolEdge('e-diag-cdss', 'diagnostician', 'cdss-server', 'scoring call', 'bottom', 'top'),
  toolEdge('e-debate-cdss', 'debate', 'cdss-server', 'validate DDx', 'bottom', 'top'),
  toolEdge('e-diag-research', 'diagnostician', 'research-server', 'PubMed cite', 'bottom', 'top'),
  toolEdge('e-coord-research', 'coordinator', 'research-server', 'evidence lookup', 'bottom', 'top'),
  dataEdge('e-diag-rag', 'diagnostician', 'rag-store', 'RAG query top_k=5'),
  dataEdge('e-bridge-agents', 'bridge', 'debate', 'in-process @tool', undefined, 'top'),
  dataEdge('e-cdss-bridge', 'cdss-server', 'bridge', 'wraps'),
  dataEdge('e-fallback-research', 'research-server', 'fallback', 'if MCP down'),

  // === Layer 2 → Layer 3: CDSS Server distributes to tools ===
  mainEdge('e-cdss-wells', 'cdss-server', 'wells', '', 'bottom', 'top'),
  mainEdge('e-cdss-curb', 'cdss-server', 'curb65', '', 'bottom', 'top'),
  mainEdge('e-cdss-cha', 'cdss-server', 'cha2ds2', '', 'bottom', 'top'),
  mainEdge('e-cdss-heart', 'cdss-server', 'heart', '', 'bottom', 'top'),
  mainEdge('e-cdss-qsofa', 'cdss-server', 'qsofa', '', 'bottom', 'top'),
  mainEdge('e-cdss-phq9', 'cdss-server', 'phq9', '', 'bottom', 'top'),
  mainEdge('e-cdss-drug', 'cdss-server', 'drug-check', '', 'bottom', 'top'),
  dataEdge('e-tools-evidence', 'drug-check', 'evidence-ref', 'all tools cite'),

  // === Layer 2 → Layer 4: Research Server distributes to tools ===
  mainEdge('e-res-pubmed', 'research-server', 'pubmed', '', 'bottom', 'top'),
  mainEdge('e-res-drugbank', 'research-server', 'drugbank', '', 'bottom', 'top'),
  mainEdge('e-res-icd11', 'research-server', 'icd11', '', 'bottom', 'top'),
  dataEdge('e-icd11-local', 'icd11', 'local-kb', '~40 codes fallback'),

  // === Layer 4 → Layer 5: Tools call external APIs ===
  apiEdge('e-pubmed-api', 'pubmed', 'api-pubmed', 'esearch + esummary', 'bottom', 'top'),
  apiEdge('e-drugbank-api', 'drugbank', 'api-openfda', 'GET /drug/label.json', 'bottom', 'top'),
  apiEdge('e-drug-rxnorm', 'drug-check', 'api-rxnorm', 'rxcui + interaction list', 'bottom', 'top'),
  apiEdge('e-icd11-api', 'icd11', 'api-icd11', 'local dataset (offline)', 'bottom', 'top'),
];

// ============================================================================
// Legend
// ============================================================================

function Legend() {
  return (
    <div className="absolute top-4 right-4 bg-card/95 backdrop-blur border border-border rounded-lg p-3 text-[10px] z-20 w-56 shadow-xl pointer-events-none">
      <div className="font-bold text-xs mb-2 flex items-center gap-1.5">
        <Layers className="w-3.5 h-3.5" />
        MCP Architecture Legend
      </div>
      <div className="space-y-1.5 mb-2">
        <div className="font-semibold text-[9px] text-muted-foreground uppercase tracking-wider">Node Types</div>
        <div className="flex items-center gap-2">
          <Brain className="w-3 h-3 text-emerald-400" />
          <span className="text-muted-foreground">Agent (LangGraph node)</span>
        </div>
        <div className="flex items-center gap-2">
          <Server className="w-3 h-3 text-purple-400" />
          <span className="text-muted-foreground">MCP Server (FastMCP)</span>
        </div>
        <div className="flex items-center gap-2">
          <Wrench className="w-3 h-3 text-blue-400" />
          <span className="text-muted-foreground">Tool (input/output schema)</span>
        </div>
        <div className="flex items-center gap-2">
          <Globe className="w-3 h-3 text-amber-400" />
          <span className="text-muted-foreground">External API</span>
        </div>
      </div>
      <div className="border-t border-border pt-2 space-y-1">
        <div className="font-semibold text-[9px] text-muted-foreground uppercase tracking-wider mb-1">Edges</div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-[2px] bg-blue-500" />
          <span className="text-muted-foreground">server → tool dispatch</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-[1.5px]" style={{ borderTop: '1.5px dashed hsl(280 60% 55%)' }} />
          <span className="text-muted-foreground">MCP tool call (stdio)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-[1.5px]" style={{ borderTop: '1.5px dashed hsl(150 60% 50%)' }} />
          <span className="text-muted-foreground">data / state flow</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-[1.5px]" style={{ borderTop: '1.5px dashed hsl(38 90% 55% / 0.6)' }} />
          <span className="text-muted-foreground">external API call</span>
        </div>
      </div>
      <div className="border-t border-border pt-2 mt-2 text-[9px] text-muted-foreground leading-snug">
        <span className="font-bold text-foreground">Transport</span>: stdio (subprocess)
        <br />
        <span className="font-bold text-foreground">Protocol</span>: MCP with legacy fallback
        <br />
        <span className="font-bold text-foreground">All APIs</span>: free, no key required
      </div>
    </div>
  );
}

// ============================================================================
// Stats bar
// ============================================================================

function StatsBar() {
  const stats = [
    { label: 'MCP Servers', value: '2', sub: 'CDSS + Research' },
    { label: 'Total Tools', value: '10', sub: '7 scoring + 3 research' },
    { label: 'External APIs', value: '4', sub: 'PubMed · OpenFDA · RxNorm · WHO' },
    { label: 'RAG Entries', value: '~5,000', sub: 'ChromaDB vector store' },
    { label: 'Transport', value: 'stdio', sub: 'FastMCP subprocess' },
  ];
  return (
    <div className="grid grid-cols-5 gap-3">
      {stats.map((s) => (
        <div key={s.label} className="bg-card border border-border rounded-lg px-3 py-2">
          <div className="text-lg font-bold">{s.value}</div>
          <div className="text-[11px] font-semibold text-foreground/80">{s.label}</div>
          <div className="text-[10px] text-muted-foreground">{s.sub}</div>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

type TabKey = 'architecture' | 'protocol' | 'internals';

function ArchitectureView() {
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  return (
    <div className="flex-1 bg-card border border-border rounded-lg overflow-hidden min-h-[700px] relative">
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
        fitViewOptions={{ padding: 0.08, maxZoom: 0.75, minZoom: 0.3 }}
        minZoom={0.2}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="hsl(220 14% 15%)" gap={24} variant={BackgroundVariant.Dots} />
        <Controls style={{ background: 'hsl(220 18% 11%)', border: '1px solid hsl(220 14% 18%)', borderRadius: 8 }} />
      </ReactFlow>
      <Legend />
    </div>
  );
}

function TabButton({ active, onClick, icon: Icon, label, sub }: { active: boolean; onClick: () => void; icon: typeof Server; label: string; sub: string }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors ${
        active
          ? 'bg-primary/10 border-primary/40 text-primary'
          : 'bg-card border-border text-muted-foreground hover:text-foreground hover:border-border'
      }`}
    >
      <Icon className="w-4 h-4" />
      <div className="text-left">
        <div className="text-sm font-semibold leading-none">{label}</div>
        <div className="text-[10px] mt-0.5 opacity-70">{sub}</div>
      </div>
    </button>
  );
}

export default function Tools() {
  const [tab, setTab] = useState<TabKey>('architecture');

  const subtitle =
    tab === 'architecture'
      ? 'Complete MCP architecture — 5-layer data flow from Agent callers through MCP servers to external APIs'
      : tab === 'protocol'
        ? 'MCP Protocol Sequence — JSON-RPC messages exchanged between Agent, Client, stdio subprocess, and FastMCP server'
        : 'Tool Internals — how each of the 10 MCP tools actually runs once the FastMCP server receives tools/call';

  return (
    <div className="p-6 space-y-4 h-full flex flex-col min-h-0 overflow-hidden">
      <div>
        <h1 className="text-2xl font-bold">MCP Tools</h1>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </div>

      <StatsBar />

      <div className="flex gap-3">
        <TabButton
          active={tab === 'architecture'}
          onClick={() => setTab('architecture')}
          icon={WorkflowIcon}
          label="Architecture"
          sub="who calls whom (5 layers)"
        />
        <TabButton
          active={tab === 'protocol'}
          onClick={() => setTab('protocol')}
          icon={Network}
          label="Protocol Sequence"
          sub="JSON-RPC message flow"
        />
        <TabButton
          active={tab === 'internals'}
          onClick={() => setTab('internals')}
          icon={Cpu}
          label="Tool Internals"
          sub="how each tool runs (5 patterns, 10 tools)"
        />
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        {tab === 'architecture' && <ArchitectureView />}
        {tab === 'protocol' && <McpSequenceView />}
        {tab === 'internals' && <McpToolInternals />}
      </div>
    </div>
  );
}
