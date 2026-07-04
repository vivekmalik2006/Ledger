// src/components/AuditTrail.tsx

import { useEffect, useState, useCallback } from "react";
import { fetchAuditLog, verifyAuditIntegrity, type AuditLogEntry } from "../lib/api";
import { PERSONAS } from "./PersonaSwitcher";

const POLL_INTERVAL_MS = 4000;

interface AuditTrailProps {
  userId: number;
}

const STATUS_STYLES: Record<AuditLogEntry["status"], { border: string; dot: string; label: string }> = {
  ACTED: { border: "border-l-secondary", dot: "bg-secondary", label: "acted" },
  SUCCESS_MANUAL_OVERRIDE: { border: "border-l-secondary", dot: "bg-secondary", label: "overridden — acted" },
  BLOCKED: { border: "border-l-reviewer", dot: "bg-reviewer", label: "paused" },
  DECLINED: { border: "border-l-declined", dot: "bg-declined", label: "declined" },
  NEGOTIATED: { border: "border-l-negotiate", dot: "bg-negotiate", label: "negotiated" },
  LIMIT_ADJUSTED: { border: "border-l-secondary", dot: "bg-secondary", label: "trust adjusted" },
  REAUTH_REQUIRED: { border: "border-l-declined", dot: "bg-declined", label: "re-auth required" },
};

export function AuditTrail({ userId }: AuditTrailProps) {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [verifyState, setVerifyState] = useState<"idle" | "checking" | "intact" | "broken">("idle");

  const persona = PERSONAS.find((p) => p.id === userId);

  const load = useCallback(async () => {
    try {
      const data = await fetchAuditLog(userId);
      setEntries(data);
    } catch (err) {
      console.error("Failed to load audit log:", err);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    setLoading(true);
    setVerifyState("idle");
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load]);

  const handleVerify = async () => {
    setVerifyState("checking");
    try {
      const result = await verifyAuditIntegrity(userId);
      setVerifyState(result.intact ? "intact" : "broken");
    } catch (err) {
      console.error("Verify failed:", err);
      setVerifyState("idle");
    }
  };

  return (
    <div className="flex h-full flex-col bg-surface-container text-on-background font-sans">
      <header className="px-7 py-5 border-b border-outline-variant flex items-start justify-between gap-3">
        <div>
          <h2 className="font-serif text-lg font-semibold">Audit Trail</h2>
          <p className="mt-1 font-mono text-xs text-on-background/50">hash-chained — tampering is detectable</p>
        </div>
        <button
          onClick={handleVerify}
          className="shrink-0 rounded-md border border-outline-variant px-3 py-1.5 text-[10px] font-mono uppercase tracking-wide text-on-background/70 hover:border-secondary"
        >
          {verifyState === "checking" ? "checking..." : "verify chain"}
        </button>
      </header>

      {verifyState === "intact" && (
        <div className="mx-7 mt-3 rounded-md bg-secondary/10 border border-secondary/40 px-3 py-2 text-xs text-secondary">
          Chain intact — no entries altered.
        </div>
      )}
      {verifyState === "broken" && (
        <div className="mx-7 mt-3 rounded-md bg-declined/10 border border-declined/40 px-3 py-2 text-xs text-declined">
          Chain broken — tampering detected.
        </div>
      )}

      {persona && (
        <div className="mx-7 mt-4 rounded-lg border border-outline-variant bg-surface-container-high px-4 py-3 text-xs">
          <div className="flex justify-between py-0.5">
            <span className="text-on-background/50">Customer</span>
            <span className="font-mono">{persona.name}</span>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-7 py-5 space-y-3">
        {loading && entries.length === 0 && <p className="font-mono text-xs text-on-background/40">Loading...</p>}
        {!loading && entries.length === 0 && (
          <p className="font-mono text-xs text-on-background/40 text-center py-8">
            No decisions logged yet.
            <br />
            Send a message to begin.
          </p>
        )}

        {entries.map((entry) => {
          const style = STATUS_STYLES[entry.status] ?? STATUS_STYLES.BLOCKED;
          return (
            <div key={entry.id} className={`border-l-2 ${style.border} pl-3 py-1 relative`}>
              <span className={`absolute -left-[5px] top-2 h-2 w-2 rounded-full ${style.dot}`} aria-hidden />
              <div className="font-mono text-[10px] uppercase tracking-wide text-on-background/50">{style.label}</div>
              <div className="text-sm leading-relaxed mt-0.5">{entry.reason}</div>
              <div className="font-mono text-[10px] text-on-background/40 mt-1">
                {new Date(entry.timestamp).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
