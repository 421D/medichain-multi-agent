import type { Session, Message, DashboardStats, AgentLog } from '@/types/medichain';

export const mockSessions: Session[] = [
  {
    id: 'sess-001',
    title: 'Acute Chest Pain Evaluation',
    status: 'completed',
    llm_model: 'gpt-4',
    created_at: '2026-03-15T14:30:00Z',
    preliminary_diagnosis: 'Acute Coronary Syndrome vs. Costochondritis',
    confidence_score: 0.82,
    safety_flags: ['cardiac_emergency'],
    agent_participation: ['interviewer', 'diagnostician', 'critic', 'coordinator'],
  },
  {
    id: 'sess-002',
    title: 'Persistent Headache Workup',
    status: 'active',
    llm_model: 'gpt-4',
    created_at: '2026-03-16T09:15:00Z',
    preliminary_diagnosis: 'Migraine with Aura vs. Tension-type Headache',
    confidence_score: 0.74,
    agent_participation: ['interviewer', 'diagnostician', 'coordinator'],
  },
  {
    id: 'sess-003',
    title: 'Pediatric Fever Assessment',
    status: 'active',
    llm_model: 'gpt-4',
    created_at: '2026-03-17T08:00:00Z',
    agent_participation: ['interviewer'],
  },
  {
    id: 'sess-004',
    title: 'Lower Back Pain - Chronic',
    status: 'completed',
    llm_model: 'gpt-4',
    created_at: '2026-03-14T11:45:00Z',
    preliminary_diagnosis: 'Lumbar Disc Herniation',
    confidence_score: 0.88,
    agent_participation: ['interviewer', 'diagnostician', 'critic', 'coordinator'],
  },
  {
    id: 'sess-005',
    title: 'Shortness of Breath Triage',
    status: 'completed',
    llm_model: 'gpt-4',
    created_at: '2026-03-13T16:20:00Z',
    preliminary_diagnosis: 'Asthma Exacerbation',
    confidence_score: 0.91,
    safety_flags: ['respiratory_distress'],
    agent_participation: ['interviewer', 'diagnostician', 'critic', 'coordinator'],
  },
];

export const mockMessages: Message[] = [
  {
    id: 'msg-001', session_id: 'sess-001', role: 'user',
    content: "I've been having chest pain for the last 3 hours. It's a sharp pain on the left side that gets worse when I breathe deeply.",
    timestamp: '2026-03-15T14:31:00Z',
  },
  {
    id: 'msg-002', session_id: 'sess-001', role: 'assistant', agent: 'coordinator',
    content: "Thank you for sharing that. I understand you're experiencing chest pain, and I want to help evaluate this carefully.\n\nBased on our clinical assessment, I'd like to ask you a few more questions to better understand your symptoms:\n\n• **When did the pain start exactly?** Was it sudden or gradual?\n• **Can you rate the pain** on a scale of 1-10?\n• **Does the pain radiate** to your arm, jaw, or back?\n• **Have you experienced** any shortness of breath, nausea, or sweating?",
    timestamp: '2026-03-15T14:31:45Z',
    citations: [
      { id: 'cit-1', title: 'Chest Pain Evaluation in the Emergency Department', source: 'NEJM', doi: '10.1056/NEJMra1514050' },
      { id: 'cit-2', title: 'ACS Guidelines 2025', source: 'AHA/ACC', doi: '10.1161/CIR.0000000000001123' },
    ],
  },
  {
    id: 'msg-003', session_id: 'sess-001', role: 'user',
    content: "It started suddenly about 3 hours ago. I'd say it's a 7 out of 10. It doesn't radiate anywhere. No nausea but I feel a bit short of breath.",
    timestamp: '2026-03-15T14:33:00Z',
  },
  {
    id: 'msg-004', session_id: 'sess-001', role: 'assistant', agent: 'coordinator',
    content: "Thank you for those details. The combination of **sudden-onset, sharp chest pain** with **pleuritic character** (worsens with breathing) and mild **dyspnea** is noted.\n\n⚠️ **Safety Note:** Given the acute nature of your symptoms, if you haven't already, please consider seeking immediate medical attention.\n\nOur differential assessment suggests:\n1. **Costochondritis** — musculoskeletal chest wall pain\n2. **Pleuritis** — inflammation of the lung lining\n3. **Pulmonary embolism** — requires ruling out given acute onset\n\nA few more questions:\n• Do you have any **history of blood clots** or recent surgery/travel?\n• Is the pain reproducible by **pressing on your chest**?",
    timestamp: '2026-03-15T14:34:00Z',
  },
];

export const mockDashboardStats: DashboardStats = {
  total_sessions: 47,
  active_sessions: 3,
  total_messages: 312,
  latest_session_date: '2026-03-17T08:00:00Z',
};

export const mockAgentLogs: AgentLog[] = [
  { id: 'log-1', session_id: 'sess-001', agent: 'interviewer', event_type: 'transition', content: 'Initiating SOCRATES framework assessment for chest pain presentation', timestamp: '2026-03-15T14:31:05Z', completed: true },
  { id: 'log-2', session_id: 'sess-001', agent: 'interviewer', event_type: 'reasoning', content: 'Identified key symptoms: acute onset, pleuritic character, left-sided. Prioritizing cardiac vs. musculoskeletal differential.', timestamp: '2026-03-15T14:31:10Z', completed: true },
  { id: 'log-3', session_id: 'sess-001', agent: 'diagnostician', event_type: 'transition', content: 'Generating differential diagnosis with RAG evidence retrieval', timestamp: '2026-03-15T14:31:15Z', completed: true },
  { id: 'log-4', session_id: 'sess-001', agent: 'diagnostician', event_type: 'reasoning', content: 'Retrieved 12 relevant articles. Top differentials: ACS (Wells score pending), Costochondritis, PE, Pleuritis. Confidence: moderate — need more history.', timestamp: '2026-03-15T14:31:22Z', completed: true },
  { id: 'log-5', session_id: 'sess-001', agent: 'critic', event_type: 'transition', content: 'Safety review initiated — screening for red-flag conditions', timestamp: '2026-03-15T14:31:25Z', completed: true },
  { id: 'log-6', session_id: 'sess-001', agent: 'critic', event_type: 'reasoning', content: '⚠️ RED FLAG: Acute chest pain with dyspnea requires urgent cardiac workup. Recommending immediate medical attention advisory. PE cannot be excluded without D-dimer/CTPA.', timestamp: '2026-03-15T14:31:30Z', completed: true },
  { id: 'log-7', session_id: 'sess-001', agent: 'coordinator', event_type: 'transition', content: 'Synthesizing agent outputs into patient-facing response', timestamp: '2026-03-15T14:31:35Z', completed: true },
  { id: 'log-8', session_id: 'sess-001', agent: 'coordinator', event_type: 'message', content: 'Final response generated with safety advisory, differential list, and follow-up questions', timestamp: '2026-03-15T14:31:45Z', completed: true },
];
