import {
  HeartPulse,
  Thermometer,
  Activity,
  AlertCircle,
  Stethoscope,
  Brain,
  Pill,
  Search,
  Tag,
  ArrowRight,
  Zap,
  Globe,
  Database,
  Cpu,
  FileJson,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import type { ComponentType } from 'react';

// ============================================================================
// Per-Tool Internal Flow Visualization
// Shows EXACTLY how each of the 10 MCP tools runs internally
// ============================================================================

interface FlowStep {
  label: string;
  sublabel?: string;
  icon: ComponentType<{ className?: string }>;
  kind: 'input' | 'compute' | 'external' | 'local' | 'output';
}

interface ToolPattern {
  title: string;
  tools: { name: string; label: string; icon: ComponentType<{ className?: string }> }[];
  source: string;
  flow: FlowStep[];
  branches?: { from: number; to: number; label: string }[];
  facts: { icon: ComponentType<{ className?: string }>; label: string; value: string; color: string }[];
  sourceCode: string;
  sampleInput: string;
  sampleOutput: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

const PATTERNS: ToolPattern[] = [
  // ─── Pattern 1: Pure Computation (6 CDSS scoring tools) ───
  {
    title: 'Pure Computation',
    tools: [
      { name: 'cdss_wells_score', label: 'Wells Score', icon: HeartPulse },
      { name: 'cdss_curb65', label: 'CURB-65', icon: Thermometer },
      { name: 'cdss_cha2ds2_vasc', label: 'CHA2DS2-VASc', icon: Activity },
      { name: 'cdss_heart_score', label: 'HEART Score', icon: AlertCircle },
      { name: 'cdss_qsofa', label: 'qSOFA', icon: Stethoscope },
      { name: 'cdss_phq9', label: 'PHQ-9', icon: Brain },
    ],
    source: 'cdss/scoring.py + cdss/mcp_server.py',
    flow: [
      { label: 'tools/call', sublabel: 'JSON-RPC request with args', icon: FileJson, kind: 'input' },
      { label: 'Pydantic parse', sublabel: 'validate input types & ranges', icon: CheckCircle2, kind: 'compute' },
      { label: 'calculate_*()', sublabel: 'pure Python arithmetic', icon: Cpu, kind: 'compute' },
      { label: 'map score → level', sublabel: 'if-else branching', icon: Cpu, kind: 'compute' },
      { label: 'Pydantic output', sublabel: 'structured result', icon: FileJson, kind: 'output' },
    ],
    facts: [
      { icon: Zap, label: 'Latency', value: '< 10ms', color: 'text-emerald-300' },
      { icon: Globe, label: 'External calls', value: '0', color: 'text-emerald-300' },
      { icon: CheckCircle2, label: 'Determinism', value: '100% pure function', color: 'text-emerald-300' },
      { icon: AlertTriangle, label: 'Failure modes', value: 'Input validation only', color: 'text-slate-300' },
    ],
    sourceCode: `@mcp.tool()
async def cdss_wells_score(
    clinical_signs_dvt: bool,
    pe_most_likely: bool,
    heart_rate_over_100: bool,
    ...
) -> str:
    inp = WellsInput(clinical_signs_dvt=..., ...)
    result = calculate_wells_score(inp)
    return result.model_dump_json()`,
    sampleInput: '{ clinical_signs_dvt: true, pe_most_likely: true, heart_rate_over_100: false, ... }',
    sampleOutput: '{ score: 6.0, risk_level: "moderate", recommendation: "D-dimer then CTPA", ... }',
    color: 'text-blue-300',
    bgColor: 'bg-blue-500/5',
    borderColor: 'border-blue-500/30',
  },

  // ─── Pattern 2: Hybrid Local KB + API (Drug Interactions) ───
  {
    title: 'Hybrid Local KB + API',
    tools: [
      { name: 'cdss_drug_interactions', label: 'Drug Interaction Check', icon: Pill },
    ],
    source: 'cdss/drug_interactions.py + cdss/mcp_server.py',
    flow: [
      { label: 'tools/call', sublabel: '{ current_meds[], proposed_meds[] }', icon: FileJson, kind: 'input' },
      { label: 'local KB check', sublabel: '6 high-risk pairs hardcoded', icon: Database, kind: 'local' },
      { label: 'RxNorm resolve', sublabel: 'drug_name → RxCUI', icon: Globe, kind: 'external' },
      { label: 'RxNorm interactions', sublabel: 'GET /interaction/list.json', icon: Globe, kind: 'external' },
      { label: 'dedupe + merge', sublabel: 'by description prefix', icon: Cpu, kind: 'compute' },
      { label: 'DrugInteractionResult', sublabel: 'interactions + contraindicated flag', icon: FileJson, kind: 'output' },
    ],
    facts: [
      { icon: Zap, label: 'Latency', value: '500ms – 2s', color: 'text-amber-300' },
      { icon: Globe, label: 'External calls', value: '2 per drug (RxNorm)', color: 'text-amber-300' },
      { icon: Database, label: 'Fallback KB', value: '6 pairs (warfarin+aspirin, SSRI+MAOI, ...)', color: 'text-emerald-300' },
      { icon: AlertTriangle, label: 'Failure modes', value: 'API timeout → local KB only', color: 'text-amber-300' },
    ],
    sourceCode: `async def check_interactions(current, proposed):
    # Step 1: local known pairs
    for d1, d2 in pairs(all_drugs):
        if frozenset([d1,d2]) in KNOWN_INTERACTIONS:
            interactions.append(KNOWN_INTERACTIONS[...])
    # Step 2: RxNorm API (if available)
    rxcuis = [await _resolve_rxcui(d) for d in drugs]
    api_results = await _check_rxnorm_interactions(rxcuis)
    # Step 3: dedupe by description`,
    sampleInput: '{ current_medications: ["warfarin", "aspirin"] }',
    sampleOutput: '{ interactions: [{pair:["warfarin","aspirin"], severity:"major", ...}], contraindicated: false }',
    color: 'text-purple-300',
    bgColor: 'bg-purple-500/5',
    borderColor: 'border-purple-500/30',
  },

  // ─── Pattern 3: Two-step External API (PubMed) ───
  {
    title: 'Two-Step External API',
    tools: [
      { name: 'pubmed_search', label: 'PubMed Search', icon: Search },
    ],
    source: 'mcp_server.py → NCBI eUtils',
    flow: [
      { label: 'tools/call', sublabel: '{ query: "headache meningitis" }', icon: FileJson, kind: 'input' },
      { label: 'esearch.fcgi', sublabel: 'GET /esearch + term + retmax=5', icon: Globe, kind: 'external' },
      { label: 'parse PMIDs', sublabel: 'extract idlist[]', icon: Cpu, kind: 'compute' },
      { label: 'esummary.fcgi', sublabel: 'GET /esummary + id=pmid1,pmid2,...', icon: Globe, kind: 'external' },
      { label: 'shape results', sublabel: '{title, authors, journal, year, url}[]', icon: Cpu, kind: 'compute' },
      { label: 'JSON result', sublabel: 'up to 5 articles', icon: FileJson, kind: 'output' },
    ],
    facts: [
      { icon: Zap, label: 'Latency', value: '1 – 3s', color: 'text-amber-300' },
      { icon: Globe, label: 'External calls', value: '2 HTTP (esearch + esummary)', color: 'text-amber-300' },
      { icon: Database, label: 'API', value: 'NCBI eUtils (free, no key)', color: 'text-emerald-300' },
      { icon: AlertTriangle, label: 'Failure modes', value: 'timeout 15s · empty idlist → empty result', color: 'text-amber-300' },
    ],
    sourceCode: `@mcp.tool()
async def pubmed_search(query: str) -> str:
    # Step 1: search for IDs
    r1 = await client.get(f"{base}/esearch.fcgi",
        params={"db":"pubmed","term":query,"retmax":5})
    id_list = r1.json()["esearchresult"]["idlist"]
    # Step 2: fetch summaries
    r2 = await client.get(f"{base}/esummary.fcgi",
        params={"db":"pubmed","id":",".join(id_list)})
    # Step 3: shape & return`,
    sampleInput: '{ query: "atrial fibrillation stroke prevention" }',
    sampleOutput: '{ results: [{title:"...", authors:"Lip GY, ...", year:"2010", pmid:"20801886", url:"..."}], count: 5 }',
    color: 'text-emerald-300',
    bgColor: 'bg-emerald-500/5',
    borderColor: 'border-emerald-500/30',
  },

  // ─── Pattern 4: Single External API (DrugBank/OpenFDA) ───
  {
    title: 'Single External API',
    tools: [
      { name: 'drugbank_lookup', label: 'DrugBank Lookup', icon: Pill },
    ],
    source: 'mcp_server.py → OpenFDA',
    flow: [
      { label: 'tools/call', sublabel: '{ drug_name: "metformin" }', icon: FileJson, kind: 'input' },
      { label: 'OpenFDA drug/label', sublabel: 'GET /drug/label.json?search=generic_name', icon: Globe, kind: 'external' },
      { label: 'extract fields', sublabel: 'warnings, interactions, adverse_rxn, indications', icon: Cpu, kind: 'compute' },
      { label: 'truncate 500 chars', sublabel: 'cap each field for prompt size', icon: Cpu, kind: 'compute' },
      { label: 'JSON result', sublabel: '8 fields + source URL', icon: FileJson, kind: 'output' },
    ],
    facts: [
      { icon: Zap, label: 'Latency', value: '500ms – 1.5s', color: 'text-amber-300' },
      { icon: Globe, label: 'External calls', value: '1 HTTP', color: 'text-emerald-300' },
      { icon: Database, label: 'API', value: 'OpenFDA (free, no key)', color: 'text-emerald-300' },
      { icon: AlertTriangle, label: 'Failure modes', value: 'brand vs generic name · 404 returns error JSON', color: 'text-amber-300' },
    ],
    sourceCode: `@mcp.tool()
async def drugbank_lookup(drug_name: str) -> str:
    resp = await client.get(
        "https://api.fda.gov/drug/label.json",
        params={"search": f'openfda.generic_name:"{drug_name}"', "limit": 1},
    )
    label = resp.json()["results"][0]
    return json.dumps({
        "warnings": extract_first("warnings"),
        "drug_interactions": extract_first("drug_interactions"),
        ...
    })`,
    sampleInput: '{ drug_name: "metformin" }',
    sampleOutput: '{ drug: "metformin", brand_name: "Glucophage", warnings: "...", drug_interactions: "...", source: "OpenFDA" }',
    color: 'text-amber-300',
    bgColor: 'bg-amber-500/5',
    borderColor: 'border-amber-500/30',
  },

  // ─── Pattern 5: Pure Local Dataset Lookup (ICD-11) ───
  {
    title: 'Local Dataset Lookup',
    tools: [
      { name: 'icd11_lookup', label: 'ICD-11 Lookup', icon: Tag },
    ],
    source: 'mcp_server.py (offline, no API)',
    flow: [
      { label: 'tools/call', sublabel: '{ condition: "type 2 diabetes" }', icon: FileJson, kind: 'input' },
      { label: 'hardcoded dataset', sublabel: '~40 ICD-11 codes embedded in code', icon: Database, kind: 'local' },
      { label: 'keyword match', sublabel: 'any(word in title.lower() for word in query.split())', icon: Cpu, kind: 'compute' },
      { label: 'take top 5', sublabel: 'results[:5]', icon: Cpu, kind: 'compute' },
      { label: 'JSON result', sublabel: 'codes + browse URLs', icon: FileJson, kind: 'output' },
    ],
    facts: [
      { icon: Zap, label: 'Latency', value: '< 5ms', color: 'text-emerald-300' },
      { icon: Globe, label: 'External calls', value: '0 (offline)', color: 'text-emerald-300' },
      { icon: Database, label: 'Data', value: '~40 conditions hardcoded (WHO ICD-11 2024-01)', color: 'text-amber-300' },
      { icon: AlertTriangle, label: 'Failure modes', value: 'unknown condition → empty results[]', color: 'text-amber-300' },
    ],
    sourceCode: `@mcp.tool()
async def icd11_lookup(condition: str) -> str:
    icd11_db = [
        ("5A11", "Type 2 diabetes mellitus"),
        ("BA00", "Essential hypertension"),
        ("CA40", "Asthma"),
        # ... ~40 entries total
    ]
    query_lower = condition.lower()
    results = [
        {"code": code, "title": title, "url": f"..."}
        for code, title in icd11_db
        if any(w in title.lower() for w in query_lower.split())
    ]
    return json.dumps({"results": results[:5], ...})`,
    sampleInput: '{ condition: "migraine" }',
    sampleOutput: '{ results: [{code:"8A80.0",title:"Migraine without aura",url:"..."},{code:"8A80.1",title:"Migraine with aura",...}], count: 2 }',
    color: 'text-pink-300',
    bgColor: 'bg-pink-500/5',
    borderColor: 'border-pink-500/30',
  },
];

// ============================================================================
// Sub-components
// ============================================================================

const STEP_COLORS: Record<FlowStep['kind'], { bg: string; border: string; text: string; label: string }> = {
  input:    { bg: 'bg-slate-500/10',   border: 'border-slate-500/40',   text: 'text-slate-300',   label: 'INPUT' },
  compute:  { bg: 'bg-blue-500/10',    border: 'border-blue-500/40',    text: 'text-blue-300',    label: 'COMPUTE' },
  external: { bg: 'bg-amber-500/10',   border: 'border-amber-500/40',   text: 'text-amber-300',   label: 'EXTERNAL' },
  local:    { bg: 'bg-emerald-500/10', border: 'border-emerald-500/40', text: 'text-emerald-300', label: 'LOCAL' },
  output:   { bg: 'bg-purple-500/10',  border: 'border-purple-500/40',  text: 'text-purple-300',  label: 'OUTPUT' },
};

function FlowStepBox({ step }: { step: FlowStep }) {
  const Icon = step.icon;
  const style = STEP_COLORS[step.kind];
  return (
    <div className={`rounded-lg border ${style.border} ${style.bg} p-2.5 w-[160px] shrink-0`}>
      <div className={`text-[8px] font-mono uppercase tracking-wider ${style.text} mb-1`}>
        {style.label}
      </div>
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon className={`w-3.5 h-3.5 ${style.text}`} />
        <span className="text-xs font-bold">{step.label}</span>
      </div>
      {step.sublabel && (
        <p className="text-[9px] text-muted-foreground font-mono leading-tight">{step.sublabel}</p>
      )}
    </div>
  );
}

function PatternCard({ pattern }: { pattern: ToolPattern }) {
  return (
    <div className={`rounded-xl border-2 ${pattern.borderColor} ${pattern.bgColor} p-4 space-y-3`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className={`text-base font-bold ${pattern.color}`}>{pattern.title}</h3>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-background/60 border border-border text-muted-foreground font-mono">
              {pattern.tools.length} {pattern.tools.length === 1 ? 'tool' : 'tools'}
            </span>
          </div>
          <div className="text-[10px] text-muted-foreground font-mono">{pattern.source}</div>
        </div>
        <div className="flex flex-wrap gap-1 justify-end max-w-[420px]">
          {pattern.tools.map((t) => {
            const Icon = t.icon;
            return (
              <div key={t.name} className={`flex items-center gap-1 px-2 py-0.5 rounded ${pattern.bgColor} border ${pattern.borderColor}`}>
                <Icon className={`w-3 h-3 ${pattern.color}`} />
                <span className="text-[10px] font-mono">{t.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Flow diagram */}
      <div className="flex items-center gap-1 overflow-x-auto pb-2">
        {pattern.flow.map((step, i) => (
          <div key={i} className="flex items-center gap-1 shrink-0">
            <FlowStepBox step={step} />
            {i < pattern.flow.length - 1 && (
              <ArrowRight className="w-4 h-4 text-muted-foreground shrink-0" />
            )}
          </div>
        ))}
      </div>

      {/* Facts row */}
      <div className="grid grid-cols-4 gap-2">
        {pattern.facts.map((f, i) => {
          const Icon = f.icon;
          return (
            <div key={i} className="bg-background/40 border border-border rounded-md px-2 py-1.5">
              <div className="flex items-center gap-1 mb-0.5">
                <Icon className={`w-3 h-3 ${f.color}`} />
                <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">{f.label}</span>
              </div>
              <div className={`text-[11px] font-semibold ${f.color}`}>{f.value}</div>
            </div>
          );
        })}
      </div>

      {/* Code + IO example */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">Implementation</div>
          <pre className="text-[10px] font-mono bg-background/60 border border-border rounded-md p-2 overflow-x-auto leading-relaxed whitespace-pre-wrap">
            {pattern.sourceCode}
          </pre>
        </div>
        <div className="space-y-2">
          <div>
            <div className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">Sample Input</div>
            <pre className="text-[10px] font-mono bg-background/60 border border-border rounded-md p-2 overflow-x-auto whitespace-pre-wrap break-all">
              {pattern.sampleInput}
            </pre>
          </div>
          <div>
            <div className="text-[9px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">Sample Output</div>
            <pre className="text-[10px] font-mono bg-background/60 border border-border rounded-md p-2 overflow-x-auto whitespace-pre-wrap break-all">
              {pattern.sampleOutput}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Summary banner
// ============================================================================

function SummaryBanner() {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-start gap-3">
        <Cpu className="w-5 h-5 text-primary shrink-0 mt-0.5" />
        <div className="flex-1">
          <h3 className="text-sm font-bold mb-1">How the 10 MCP tools actually run</h3>
          <p className="text-xs text-muted-foreground">
            Despite sharing the same MCP protocol at the transport layer (JSON-RPC over stdio), each tool
            has a different <span className="text-foreground font-semibold">internal execution pattern</span>.
            The 5 patterns below cover all 10 tools — grouped by what happens
            <span className="italic"> after </span>
            the FastMCP server receives a <code className="px-1 rounded bg-background/60">tools/call</code> message.
          </p>
          <div className="flex flex-wrap gap-3 mt-2 text-[11px]">
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-slate-400"></span>
              <span className="text-muted-foreground">INPUT — JSON-RPC parse</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-400"></span>
              <span className="text-muted-foreground">COMPUTE — in-process Python</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span className="text-muted-foreground">LOCAL — hardcoded KB lookup</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-amber-400"></span>
              <span className="text-muted-foreground">EXTERNAL — HTTP call</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-purple-400"></span>
              <span className="text-muted-foreground">OUTPUT — JSON return</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main component
// ============================================================================

export default function McpToolInternals() {
  return (
    <div className="flex-1 overflow-auto space-y-4">
      <SummaryBanner />
      {PATTERNS.map((p) => (
        <PatternCard key={p.title} pattern={p} />
      ))}
    </div>
  );
}
