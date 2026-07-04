// src/lib/api.ts
//
// Thin fetch wrappers around the backend. Kept framework-agnostic so it's
// easy to test or swap transport later.

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface ChatContext {
  action: string;
  amount: number;
  product: string;
}

export interface ChatResponse {
  speaker: "ai";
  text: string;
  requires_approval: boolean;
  context?: ChatContext;
}

export interface ApprovalPayload {
  user_id: number;
  approved: boolean;
  action: string;
  amount: number;
  product: string;
}

async function handleResponse(res: Response): Promise<ChatResponse> {
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function sendChatMessage(userId: number, message: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, message }),
  });
  return handleResponse(res);
}

export async function startSession(userId: number): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/session/start/${userId}`);
  return handleResponse(res);
}

export async function sendApproval(payload: ApprovalPayload): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/api/chat/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export interface AuditLogEntry {
  id: number;
  action: string;
  reason: string;
  rule_checked: string;
  status:
    | "ACTED"
    | "BLOCKED"
    | "DECLINED"
    | "NEGOTIATED"
    | "SUCCESS_MANUAL_OVERRIDE"
    | "REAUTH_REQUIRED"
    | "LIMIT_ADJUSTED";
  amount: number | null;
  timestamp: string;
}

export async function fetchAuditLog(userId: number): Promise<AuditLogEntry[]> {
  const res = await fetch(`${API_BASE}/api/audit/${userId}`);
  if (!res.ok) throw new Error(`Audit log request failed: ${res.status}`);
  return res.json();
}

export interface AuditVerifyResult {
  intact: boolean;
  broken_at_id: number | null;
}

export async function verifyAuditIntegrity(userId: number): Promise<AuditVerifyResult> {
  const res = await fetch(`${API_BASE}/api/audit/${userId}/verify`);
  if (!res.ok) throw new Error(`Audit verify request failed: ${res.status}`);
  return res.json();
}
