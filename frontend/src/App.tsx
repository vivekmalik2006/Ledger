// src/App.tsx

import { useState } from "react";
import { PersonaSwitcher, PERSONAS } from "./components/PersonaSwitcher";
import { ChatPanel } from "./components/ChatPanel";
import { AuditTrail } from "./components/AuditTrail";

export default function App() {
  const [activeUserId, setActiveUserId] = useState<number>(PERSONAS[0].id);
  const activePersona = PERSONAS.find((p) => p.id === activeUserId)!;

  return (
    <div className="flex h-screen flex-col bg-background">
      <PersonaSwitcher activeId={activeUserId} onChange={setActiveUserId} />
      <div className="grid flex-1 min-h-0 grid-cols-[1.1fr_0.9fr]">
        <div className="border-r border-outline-variant min-h-0">
          <ChatPanel key={activeUserId} userId={activeUserId} customerName={activePersona.name} />
        </div>
        <div className="min-h-0">
          <AuditTrail userId={activeUserId} />
        </div>
      </div>
    </div>
  );
}
