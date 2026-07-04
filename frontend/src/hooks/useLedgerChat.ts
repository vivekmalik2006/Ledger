// src/hooks/useLedgerChat.ts

import { useCallback, useEffect, useRef, useState } from "react";
import {
  sendChatMessage,
  sendApproval,
  startSession,
  type ChatContext,
  type ApprovalPayload,
} from "../lib/api";

export interface DisplayMessage {
  id: string;
  speaker: "user" | "ai";
  text: string;
  // Present only on the AI message currently awaiting a yes/no from the
  // customer — set whenever requires_approval comes back true, regardless
  // of whether the block came from the Reviewer or the customer's own
  // boundary. Cleared once they respond either way.
  pendingApproval?: ChatContext;
}

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function useLedgerChat(userId: number) {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [isNudging, setIsNudging] = useState(true);

  const appendMessage = useCallback((msg: DisplayMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const hasNudged = useRef(false);

  useEffect(() => {
    if (hasNudged.current) return;
    hasNudged.current = true;

    setIsNudging(true);
    startSession(userId)
      .then((response) => {
        appendMessage({
          id: makeId(),
          speaker: "ai",
          text: response.text,
          pendingApproval: response.requires_approval ? response.context : undefined,
        });
      })
      .catch((err) => console.error("Session start failed:", err))
      .finally(() => setIsNudging(false));
  }, [userId, appendMessage]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isSending) return;
      appendMessage({ id: makeId(), speaker: "user", text });
      setIsSending(true);

      try {
        const response = await sendChatMessage(userId, text);
        appendMessage({
          id: makeId(),
          speaker: "ai",
          text: response.text,
          pendingApproval: response.requires_approval ? response.context : undefined,
        });
      } catch (err) {
        appendMessage({ id: makeId(), speaker: "ai", text: "Something went wrong reaching Ledger. Please try again." });
        console.error(err);
      } finally {
        setIsSending(false);
      }
    },
    [userId, isSending, appendMessage]
  );

  const respondToApproval = useCallback(
    async (messageId: string, approved: boolean, context: ChatContext) => {
      setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, pendingApproval: undefined } : m)));
      setIsSending(true);

      const payload: ApprovalPayload = {
        user_id: userId,
        approved,
        action: context.action,
        amount: context.amount,
        product: context.product,
      };

      try {
        const response = await sendApproval(payload);
        appendMessage({ id: makeId(), speaker: "ai", text: response.text });
      } catch (err) {
        appendMessage({ id: makeId(), speaker: "ai", text: "Couldn't process that response — please try again." });
        console.error(err);
      } finally {
        setIsSending(false);
      }
    },
    [userId, appendMessage]
  );

  return { messages, isSending, isNudging, sendMessage, respondToApproval };
}
