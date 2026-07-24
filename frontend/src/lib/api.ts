const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchApi<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API error: ${res.status} ${res.statusText} — ${body.slice(0, 200)}`);
  }
  return res.json();
}

export async function fetchBlob(path: string, init?: RequestInit): Promise<Blob> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.blob();
}

// ─── Health ────────────────────────────────────────────────────

export interface HealthData {
  status: string;
  mode: string;
  services: Record<string, { status: string; detail: string | null }>;
}

export function getHealth(): Promise<HealthData> {
  return fetchApi("/api/health");
}

// ─── Intelligence Events ────────────────────────────────────────

export interface IntelligenceEvent {
  id: string;
  event_id: string;
  event_type: string;
  factual_summary: string;
  timestamp: string;
  geography: string;
  impact_direction: string;
  impact_horizon: string;
  confidence: number;
  uncertainty: number;
  sectors: string[];
  industries: string[];
  commodities: string[];
  currencies: string[];
  entities: any[];
  direct_impacts: any[];
  indirect_impacts: any[];
  possible_beneficiaries: any[];
  possible_negative_exposures: any[];
  causal_chain: any[];
  source_ids: string[];
  human_review_required: boolean;
  validation_flags: string[];
  lat?: number;
  lng?: number;
  source_name?: string;
  original_url?: string;
  publisher?: string;
  title?: string;
}

interface EventsResponse {
  items: IntelligenceEvent[];
  total: number;
}

interface StatsResponse {
  total_events: number;
  avg_confidence: number;
  validation_pass_rate: number;
  human_review_required: number;
  by_type: Record<string, number>;
  [key: string]: any;
}

export function getEvents(params?: Record<string, string>): Promise<EventsResponse> {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return fetchApi(`/api/intelligence/events${qs}`);
}

export function getEventDetail(id: string): Promise<IntelligenceEvent> {
  return fetchApi(`/api/intelligence/events/${id}`);
}

export function getIntelligenceStats(): Promise<StatsResponse> {
  return fetchApi("/api/intelligence/stats");
}

// ─── Evidence ───────────────────────────────────────────────────

export interface EvidenceItem {
  id: string;
  evidence_id: string;
  source_name: string;
  original_url: string | null;
  publisher: string | null;
  title: string;
  raw_content: string;
  publication_ts: string | null;
  ingestion_ts: string;
  jurisdiction: string;
  source_type: string;
  is_mock: boolean;
  duplicate_status: string;
}

interface EvidenceResponse {
  items: EvidenceItem[];
  total: number;
}

export interface SourceStat {
  source_name: string;
  source_type: string;
  total_items: number;
  mock_items: number;
  health_status: string;
  latest_ingestion?: string;
}

export function getEvidence(params?: Record<string, string>): Promise<EvidenceResponse> {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return fetchApi(`/api/evidence${qs}`);
}

export function getSourceStats(): Promise<SourceStat[]> {
  return fetchApi("/api/evidence/stats/sources");
}

// ─── Connector Health ──────────────────────────────────────────

export interface ConnectorHealthItem {
  connector: string;
  status: string;
  last_run_at: string | null;
  last_success_at: string | null;
  consecutive_failures: number;
  last_error: string | null;
}

export function getConnectorHealth(): Promise<ConnectorHealthItem[]> {
  return fetchApi("/api/evidence/health/connectors");
}

// ─── Portfolios ─────────────────────────────────────────────────

export interface Portfolio {
  id: string;
  name: string;
  description?: string;
  total_value?: number;
  holding_count?: number;
  created_at?: string;
  updated_at?: string;
  [key: string]: any;
}

export function getPortfolios(): Promise<Portfolio[]> {
  return fetchApi("/api/portfolios");
}

export function createPortfolio(data: Partial<Portfolio>): Promise<Portfolio> {
  return fetchApi("/api/portfolios", { method: "POST", body: JSON.stringify(data) });
}

// ─── Copilot ────────────────────────────────────────────────────

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

interface ChatResponse {
  response: string;
  conversation_id: string;
  citations: any[];
  sources: any[];
}

export function getConversations(): Promise<Conversation[]> {
  return fetchApi("/api/copilot/conversations");
}

export function chatSend(
  conversationId: string | null,
  message: string,
): Promise<ChatResponse> {
  return fetchApi("/api/copilot/chat", {
    method: "POST",
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
    }),
  });
}

// ─── Ingestion / Connectors ─────────────────────────────────────

export interface ConnectorListItem {
  name: string;
  display_name: string;
  type: string;
}

export function listConnectors(): Promise<{ connectors: ConnectorListItem[] }> {
  return fetchApi("/api/ingestion/connectors");
}

export function getConnectorHealthByName(name: string): Promise<any> {
  return fetchApi(`/api/ingestion/connectors/${name}/health`);
}
