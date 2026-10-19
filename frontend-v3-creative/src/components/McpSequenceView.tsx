import { Brain, Layers, Server, Terminal, Globe, FileCode, Zap } from 'lucide-react';

// ============================================================================
// MCP Protocol Sequence Diagram
// Shows actual JSON-RPC message flow: discovery + invocation phases
// ============================================================================

type ActorId = 'agent' | 'client' | 'stdio' | 'server' | 'api';

interface Actor {
  id: ActorId;
  x: number;
  label: string;
  subtitle: string;
  icon: typeof Server;
  color: string;
  border: string;
  bg: string;
}

const ACTORS: Actor[] = [
  { id: 'agent',  x: 90,   label: 'LLM Agent',          subtitle: 'Diagnostician / Debate', icon: Brain,    color: 'text-emerald-300', border: 'border-emerald-500/40', bg: 'bg-emerald-500/10' },
  { id: 'client', x: 370,  label: 'MCP Client',          subtitle: 'app/core/mcp_client.py', icon: FileCode, color: 'text-blue-300',    border: 'border-blue-500/40',    bg: 'bg-blue-500/10' },
  { id: 'stdio',  x: 650,  label: 'stdio Subprocess',    subtitle: 'python3 mcp_server.py',  icon: Terminal, color: 'text-purple-300',  border: 'border-purple-500/40',  bg: 'bg-purple-500/10' },
  { id: 'server', x: 930,  label: 'FastMCP Server',      subtitle: '@mcp.tool() handlers',   icon: Server,   color: 'text-pink-300',    border: 'border-pink-500/40',    bg: 'bg-pink-500/10' },
  { id: 'api',    x: 1210, label: 'External API',        subtitle: 'e.g. PubMed eUtils',     icon: Globe,    color: 'text-amber-300',   border: 'border-amber-500/40',   bg: 'bg-amber-500/10' },
];

type MsgKind = 'spawn' | 'jsonrpc' | 'response' | 'http' | 'local';

interface Message {
  y: number;
  from: ActorId;
  to: ActorId;
  label: string;
  sublabel?: string;
  kind: MsgKind;
}

// Phase breakpoints (y coordinates)
const PHASE_1_TOP = 140;
const PHASE_1_BOT = 370;
const PHASE_2_TOP = 410;
const PHASE_2_BOT = 780;

const MESSAGES: Message[] = [
  // ── PHASE 1: TOOL DISCOVERY (once, on first call) ──
  { y: 170, from: 'client', to: 'stdio',  kind: 'spawn',    label: 'spawn subprocess',     sublabel: 'StdioServerParameters(command="python3", args=[mcp_server.py])' },
  { y: 215, from: 'client', to: 'server', kind: 'jsonrpc',  label: 'initialize()',          sublabel: 'JSON-RPC 2.0 handshake' },
  { y: 260, from: 'server', to: 'client', kind: 'response', label: 'ServerCapabilities',    sublabel: '{ tools: {}, prompts: {}, ... }' },
  { y: 305, from: 'client', to: 'server', kind: 'jsonrpc',  label: 'list_tools()',          sublabel: 'method: "tools/list"' },
  { y: 350, from: 'server', to: 'client', kind: 'response', label: 'ToolSchemas[3]',        sublabel: '[pubmed_search, drugbank_lookup, icd11_lookup] + JSON Schema for each' },

  // ── PHASE 2: TOOL INVOCATION (per LLM decision) ──
  { y: 440, from: 'agent',  to: 'client', kind: 'local',    label: 'call_mcp_tool("pubmed_search", {query})', sublabel: 'in-process Python call' },
  { y: 490, from: 'client', to: 'server', kind: 'jsonrpc',  label: 'tools/call',            sublabel: '{ name: "pubmed_search", arguments: { query: "headache fever" } }' },
  { y: 540, from: 'server', to: 'api',    kind: 'http',     label: 'GET /esearch.fcgi',     sublabel: 'https://eutils.ncbi.nlm.nih.gov/?term=headache+fever&retmax=5' },
  { y: 585, from: 'api',    to: 'server', kind: 'response', label: 'id_list: [pmid, ...]',  sublabel: 'HTTP 200 + JSON' },
  { y: 630, from: 'server', to: 'api',    kind: 'http',     label: 'GET /esummary.fcgi',    sublabel: '?id=38451234,38451235,...' },
  { y: 675, from: 'api',    to: 'server', kind: 'response', label: 'article metadata',      sublabel: 'title · authors · journal · year · url' },
  { y: 720, from: 'server', to: 'client', kind: 'response', label: 'CallToolResult',        sublabel: 'content: [{ type: "text", text: "{\\"results\\": [...]}" }]' },
  { y: 765, from: 'client', to: 'agent',  kind: 'response', label: 'parsed dict',           sublabel: 'json.loads(result.content[0].text)' },
];

const KIND_COLORS: Record<MsgKind, { stroke: string; fill: string; label: string }> = {
  spawn:    { stroke: 'hsl(280 70% 60%)',  fill: 'rgba(168, 85, 247, 0.15)',  label: 'text-purple-300' },
  jsonrpc:  { stroke: 'hsl(210 90% 60%)',  fill: 'rgba(59, 130, 246, 0.15)',  label: 'text-blue-300' },
  response: { stroke: 'hsl(150 60% 55%)',  fill: 'rgba(16, 185, 129, 0.12)',  label: 'text-emerald-300' },
  http:     { stroke: 'hsl(38 90% 58%)',   fill: 'rgba(245, 158, 11, 0.12)',  label: 'text-amber-300' },
  local:    { stroke: 'hsl(215 15% 60%)',  fill: 'rgba(148, 163, 184, 0.12)', label: 'text-slate-300' },
};

const CANVAS_WIDTH = 1330;
const CANVAS_HEIGHT = 820;
const ACTOR_BOX_WIDTH = 180;

function ActorHeader({ actor }: { actor: Actor }) {
  const Icon = actor.icon;
  return (
    <div
      className={`absolute rounded-lg border-2 ${actor.border} ${actor.bg} px-3 py-2 shadow-lg`}
      style={{ left: actor.x - ACTOR_BOX_WIDTH / 2, top: 20, width: ACTOR_BOX_WIDTH }}
    >
      <div className="flex items-center gap-1.5 mb-0.5">
        <Icon className={`w-4 h-4 ${actor.color}`} />
        <span className={`text-xs font-bold ${actor.color}`}>{actor.label}</span>
      </div>
      <p className="text-[10px] text-muted-foreground font-mono">{actor.subtitle}</p>
    </div>
  );
}

function Lifeline({ actor }: { actor: Actor }) {
  return (
    <div
      className="absolute border-l border-dashed border-border/50 pointer-events-none"
      style={{ left: actor.x, top: 90, height: CANVAS_HEIGHT - 110 }}
    />
  );
}

function PhaseBand({ label, sublabel, top, bottom, color, bgColor }: { label: string; sublabel: string; top: number; bottom: number; color: string; bgColor: string }) {
  return (
    <>
      <div
        className={`absolute rounded-md border border-dashed ${bgColor} pointer-events-none`}
        style={{ left: 10, top, width: CANVAS_WIDTH - 20, height: bottom - top }}
      />
      <div
        className={`absolute text-[10px] font-bold uppercase tracking-widest ${color} px-2 py-0.5 rounded bg-background/80 border ${color.replace('text-', 'border-')}/40 whitespace-nowrap`}
        style={{ left: 20, top: top + 8 }}
      >
        {label}
      </div>
      <div
        className="absolute text-[10px] text-muted-foreground italic whitespace-nowrap bg-background/80 px-1 rounded"
        style={{ left: 430, top: top + 10 }}
      >
        {sublabel}
      </div>
    </>
  );
}

function MessageArrow({ msg }: { msg: Message }) {
  const fromActor = ACTORS.find((a) => a.id === msg.from)!;
  const toActor = ACTORS.find((a) => a.id === msg.to)!;
  const kindStyle = KIND_COLORS[msg.kind];

  const leftX = Math.min(fromActor.x, toActor.x);
  const rightX = Math.max(fromActor.x, toActor.x);
  const width = rightX - leftX;
  const isReverse = toActor.x < fromActor.x;

  const arrowId = `arrow-${msg.kind}-${msg.y}`;

  return (
    <div className="absolute" style={{ left: leftX, top: msg.y, width, height: 40 }}>
      <svg width={width} height={40} className="absolute top-0 left-0 overflow-visible">
        <defs>
          <marker id={arrowId} markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto">
            <polygon points="0 0, 10 5, 0 10" fill={kindStyle.stroke} />
          </marker>
        </defs>
        {msg.kind === 'spawn' ? (
          <line x1={isReverse ? width : 0} y1="20" x2={isReverse ? 0 : width} y2="20" stroke={kindStyle.stroke} strokeWidth="2" strokeDasharray="6 4" markerEnd={`url(#${arrowId})`} />
        ) : (
          <line x1={isReverse ? width : 0} y1="20" x2={isReverse ? 0 : width} y2="20" stroke={kindStyle.stroke} strokeWidth={msg.kind === 'jsonrpc' ? 2 : 1.5} strokeDasharray={msg.kind === 'response' ? '4 3' : msg.kind === 'http' ? '8 3' : undefined} markerEnd={`url(#${arrowId})`} />
        )}
      </svg>
      {/* Kind badge (left side) */}
      <div
        className={`absolute text-[8px] font-mono uppercase px-1 rounded ${kindStyle.label}`}
        style={{ left: isReverse ? width - 60 : 4, top: 0, background: kindStyle.fill }}
      >
        {msg.kind === 'spawn' ? 'OS.spawn' : msg.kind === 'jsonrpc' ? 'JSON-RPC →' : msg.kind === 'response' ? '← return' : msg.kind === 'http' ? 'HTTP →' : 'in-process'}
      </div>
      {/* Main label */}
      <div
        className={`absolute text-[11px] font-bold ${kindStyle.label} px-2 rounded bg-background/90`}
        style={{ left: width / 2 - 120, top: 5, width: 240, textAlign: 'center' }}
      >
        {msg.label}
      </div>
      {/* Sublabel (params / payload) */}
      {msg.sublabel && (
        <div
          className="absolute text-[9px] text-muted-foreground font-mono truncate px-2"
          style={{ left: width / 2 - 180, top: 24, width: 360, textAlign: 'center' }}
          title={msg.sublabel}
        >
          {msg.sublabel}
        </div>
      )}
    </div>
  );
}

function Legend() {
  return (
    <div className="bg-card/95 backdrop-blur border border-border rounded-lg p-3 text-[10px] space-y-2">
      <div className="font-bold text-xs flex items-center gap-1.5">
        <Layers className="w-3.5 h-3.5" />
        Message Legend
      </div>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <svg width="40" height="8"><line x1="0" y1="4" x2="38" y2="4" stroke="hsl(280 70% 60%)" strokeWidth="2" strokeDasharray="6 4" markerEnd="" /></svg>
          <span className="text-muted-foreground"><span className="text-purple-300 font-mono">OS.spawn</span> — process creation</span>
        </div>
        <div className="flex items-center gap-2">
          <svg width="40" height="8"><line x1="0" y1="4" x2="38" y2="4" stroke="hsl(210 90% 60%)" strokeWidth="2" /></svg>
          <span className="text-muted-foreground"><span className="text-blue-300 font-mono">JSON-RPC</span> — MCP protocol request</span>
        </div>
        <div className="flex items-center gap-2">
          <svg width="40" height="8"><line x1="0" y1="4" x2="38" y2="4" stroke="hsl(150 60% 55%)" strokeWidth="1.5" strokeDasharray="4 3" /></svg>
          <span className="text-muted-foreground"><span className="text-emerald-300 font-mono">return</span> — response / result</span>
        </div>
        <div className="flex items-center gap-2">
          <svg width="40" height="8"><line x1="0" y1="4" x2="38" y2="4" stroke="hsl(38 90% 58%)" strokeWidth="1.5" strokeDasharray="8 3" /></svg>
          <span className="text-muted-foreground"><span className="text-amber-300 font-mono">HTTP</span> — external API call</span>
        </div>
        <div className="flex items-center gap-2">
          <svg width="40" height="8"><line x1="0" y1="4" x2="38" y2="4" stroke="hsl(215 15% 60%)" strokeWidth="1.5" /></svg>
          <span className="text-muted-foreground"><span className="text-slate-300 font-mono">in-process</span> — same Python VM</span>
        </div>
      </div>
    </div>
  );
}

function ProtocolNotes() {
  return (
    <div className="bg-card/95 backdrop-blur border border-border rounded-lg p-3 text-[10px] space-y-2">
      <div className="font-bold text-xs flex items-center gap-1.5">
        <Zap className="w-3.5 h-3.5" />
        Protocol Facts
      </div>
      <div className="space-y-1 text-muted-foreground">
        <div>
          <span className="text-foreground font-semibold">Transport</span>: stdio (subprocess pipes).<br />
          Alternatives: HTTP/SSE, WebSocket.
        </div>
        <div>
          <span className="text-foreground font-semibold">Message format</span>: JSON-RPC 2.0.<br />
          All messages have <code className="bg-background/50 px-1 rounded">id</code>, <code className="bg-background/50 px-1 rounded">method</code>, <code className="bg-background/50 px-1 rounded">params</code>.
        </div>
        <div>
          <span className="text-foreground font-semibold">Tool schema</span>: auto-generated from<br />
          <code className="bg-background/50 px-1 rounded">@mcp.tool()</code> Python type hints.
        </div>
        <div>
          <span className="text-foreground font-semibold">Current impl</span>: <span className="text-amber-300">⚠ new subprocess per call</span> — correct but wasteful. Production: keep session alive.
        </div>
      </div>
    </div>
  );
}

export default function McpSequenceView() {
  return (
    <div className="flex-1 min-h-0 flex flex-col gap-4 overflow-auto">
      <div className="flex gap-3">
        <div className="flex-1 bg-card border border-border rounded-lg p-4 relative" style={{ minWidth: CANVAS_WIDTH + 32 }}>
          <div className="relative" style={{ width: CANVAS_WIDTH, height: CANVAS_HEIGHT }}>
            {/* Phase bands (behind everything) */}
            <PhaseBand
              label="PHASE 1 · Tool Discovery (once, on startup or first call)"
              sublabel="Client learns which tools exist and their schemas"
              top={PHASE_1_TOP}
              bottom={PHASE_1_BOT}
              color="text-blue-400"
              bgColor="border-blue-500/20 bg-blue-500/5"
            />
            <PhaseBand
              label="PHASE 2 · Tool Invocation (per LLM tool-use decision)"
              sublabel="Agent calls a specific tool with arguments, gets result back"
              top={PHASE_2_TOP}
              bottom={PHASE_2_BOT}
              color="text-emerald-400"
              bgColor="border-emerald-500/20 bg-emerald-500/5"
            />

            {/* Lifelines */}
            {ACTORS.map((a) => <Lifeline key={a.id} actor={a} />)}

            {/* Actor headers */}
            {ACTORS.map((a) => <ActorHeader key={a.id} actor={a} />)}

            {/* Message arrows */}
            {MESSAGES.map((m, i) => <MessageArrow key={i} msg={m} />)}
          </div>
        </div>

        {/* Side panel */}
        <div className="w-72 flex flex-col gap-3">
          <Legend />
          <ProtocolNotes />
        </div>
      </div>
    </div>
  );
}
