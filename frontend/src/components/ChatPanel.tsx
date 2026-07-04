// src/components/ChatPanel.tsx

import { useState, type FormEvent } from "react";
import { useLedgerChat } from "../hooks/useLedgerChat";

interface ChatPanelProps {
  userId: number;
  customerName: string;
}

export function ChatPanel({ userId, customerName }: ChatPanelProps) {
  const { messages, isSending, isNudging, sendMessage, respondToApproval } = useLedgerChat(userId);
  const [draft, setDraft] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    sendMessage(draft);
    setDraft("");
  };

  return (
    <div className="flex h-full flex-col bg-background text-on-background font-sans">
      <header className="border-b border-outline-variant px-7 py-5">
        <h1 className="font-serif text-2xl font-semibold">
          Ledger<span className="text-secondary">.</span>
        </h1>
        <p className="mt-1 font-mono text-xs text-on-background/60">session — {customerName}</p>
      </header>

      <div className="flex-1 overflow-y-auto px-7 py-6 space-y-4">
        {isNudging && messages.length === 0 && (
          <p className="font-mono text-xs text-on-background/40 animate-pulse">Ledger is reviewing the account...</p>
        )}
        {!isNudging && messages.length === 0 && (
          <p className="font-mono text-xs text-on-background/50">
            Say hello, ask about your idle savings, or try "start an equity SIP of 5000".
          </p>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={msg.speaker === "user" ? "flex justify-end" : "flex justify-start"}>
            <div className="max-w-[85%]">
              <div className="mb-1 font-mono text-[10px] uppercase tracking-wide text-on-background/50">
                {msg.speaker === "user" ? "You" : "Ledger"}
              </div>
              <div
                className={
                  msg.speaker === "user"
                    ? "rounded-xl rounded-br-sm bg-on-background px-4 py-3 text-sm text-background"
                    : "rounded-xl rounded-bl-sm border border-outline-variant bg-surface-container px-4 py-3 text-sm leading-relaxed"
                }
              >
                {msg.text}
              </div>
              {msg.pendingApproval && (
                <ApprovalPrompt
                  context={msg.pendingApproval}
                  disabled={isSending}
                  onRespond={(approved) => respondToApproval(msg.id, approved, msg.pendingApproval!)}
                />
              )}
            </div>
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-outline-variant px-7 py-5">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={isSending}
          placeholder="Ask Ledger about your finances..."
          className="flex-1 rounded-lg border border-outline-variant bg-surface-container px-4 py-3 text-sm outline-none focus:border-secondary disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isSending || !draft.trim()}
          className="rounded-lg bg-secondary px-5 text-sm font-semibold text-background disabled:opacity-40"
        >
          {isSending ? "..." : "Send"}
        </button>
      </form>
    </div>
  );
}

interface ApprovalPromptProps {
  context: { action: string; amount: number; product: string };
  disabled: boolean;
  onRespond: (approved: boolean) => void;
}

function ApprovalPrompt({ context, disabled, onRespond }: ApprovalPromptProps) {
  return (
    <div className="mt-2 rounded-lg border border-secondary/40 bg-secondary/10 px-4 py-3">
      <p className="font-mono text-[11px] text-secondary">
        awaiting confirmation — ₹{context.amount.toLocaleString("en-IN")} {context.product}
      </p>
      <div className="mt-2 flex gap-2">
        <button
          onClick={() => onRespond(true)}
          disabled={disabled}
          className="rounded-md bg-secondary px-3 py-1.5 text-xs font-semibold text-background disabled:opacity-40"
        >
          Approve anyway
        </button>
        <button
          onClick={() => onRespond(false)}
          disabled={disabled}
          className="rounded-md border border-outline-variant px-3 py-1.5 text-xs font-semibold text-on-background/80 disabled:opacity-40"
        >
          Decline
        </button>
      </div>
    </div>
  );
}
