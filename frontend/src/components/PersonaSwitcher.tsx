// src/components/PersonaSwitcher.tsx
//
// Matches backend/scripts/populate_demo.py exactly. If personas change
// there, update this list to match — there's no /api/personas endpoint,
// this is intentionally hardcoded for demo speed.

export interface Persona {
  id: number;
  name: string;
  note: string;
}

// NOTE: ids here assume a fresh DB where autoincrement starts at 1 in
// insertion order (priya, vivek, arjun). Confirm against your actual DB if
// you've reseeded multiple times — steward_id is the stable identifier,
// these numeric ids are a demo convenience.
export const PERSONAS: Persona[] = [
  { id: 1, name: "Priya", note: "clears both checks — acts" },
  { id: 2, name: "Vivek", note: "over his limit — negotiates" },
  { id: 3, name: "Arjun", note: "ask for an equity SIP — hard reject" },
];

interface PersonaSwitcherProps {
  activeId: number;
  onChange: (id: number) => void;
}

export function PersonaSwitcher({ activeId, onChange }: PersonaSwitcherProps) {
  return (
    <div className="flex items-center gap-2 px-7 py-3 border-b border-outline-variant flex-wrap">
      <span className="font-mono text-[10px] uppercase tracking-wide text-on-background/50 mr-1">
        Demo as
      </span>
      {PERSONAS.map((p) => (
        <button
          key={p.id}
          onClick={() => onChange(p.id)}
          title={p.note}
          className={
            p.id === activeId
              ? "rounded-full bg-secondary px-4 py-1.5 text-xs font-semibold text-background"
              : "rounded-full border border-outline-variant px-4 py-1.5 text-xs text-on-background/70 hover:border-secondary hover:text-on-background"
          }
        >
          {p.name}
        </button>
      ))}
    </div>
  );
}
