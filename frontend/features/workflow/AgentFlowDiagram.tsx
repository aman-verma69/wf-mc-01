const AGENTS = ["buyer", "catalog", "customer", "analytics", "growth", "campaign"];
const SERVICES = ["checkout", "payment", "dispute", "notification"];

export function AgentFlowDiagram() {
  return (
    <svg viewBox="0 0 720 400" className="w-full h-auto">
      <rect x="20" y="20" width="680" height="360" rx="10" fill="none" stroke="#232C40" strokeWidth="1" />
      <text x="40" y="46" fill="#8993A8" fontSize="11" fontFamily="var(--font-plex-mono)" letterSpacing="0.05em">
        LLAMAINDEX WORKFLOW
      </text>

      {/* agentic layer */}
      <rect x="40" y="64" width="640" height="90" rx="8" fill="#182238" stroke="#2E3A54" />
      <text x="360" y="88" textAnchor="middle" fill="#EDEFF3" fontSize="13" fontFamily="var(--font-fraunces)" fontStyle="italic">
        Agentic layer · gpt-oss-20b
      </text>
      {AGENTS.map((name, i) => {
        const w = 90;
        const gap = 12;
        const totalW = AGENTS.length * w + (AGENTS.length - 1) * gap;
        const startX = 360 - totalW / 2;
        const x = startX + i * (w + gap);
        return (
          <g key={name}>
            <rect x={x} y={106} width={w} height={32} rx="5" fill="#0B1120" stroke="#2E3A54" />
            <text x={x + w / 2} y={126} textAnchor="middle" fill="#C7CDDA" fontSize="10.5" fontFamily="var(--font-plex-mono)">
              {name}
            </text>
          </g>
        );
      })}

      {/* arrow to gate */}
      <line x1="360" y1="154" x2="360" y2="178" stroke="#B8923A" strokeWidth="1.5" markerEnd="url(#arrow)" />

      {/* guardrail gate */}
      <rect x="270" y="180" width="180" height="52" rx="6" fill="#5C4319" fillOpacity="0.25" stroke="#E0A030" />
      <text x="360" y="202" textAnchor="middle" fill="#E0A030" fontSize="12.5" fontFamily="var(--font-fraunces)" fontStyle="italic">
        Guardrail gate
      </text>
      <text x="360" y="219" textAnchor="middle" fill="#EDEFF3" fontSize="9.5" fontFamily="var(--font-plex-mono)">
        delegation scope · spend limit
      </text>

      {/* arrow to services */}
      <line x1="360" y1="232" x2="360" y2="256" stroke="#B8923A" strokeWidth="1.5" markerEnd="url(#arrow)" />

      {/* deterministic layer */}
      <rect x="40" y="258" width="640" height="90" rx="8" fill="#182238" stroke="#1B4F47" />
      <text x="360" y="282" textAnchor="middle" fill="#EDEFF3" fontSize="13" fontFamily="var(--font-fraunces)" fontStyle="italic">
        Deterministic services · no LLM calls
      </text>
      {["policy", ...SERVICES, "order", "audit"].map((name, i, arr) => {
        const w = 78;
        const gap = 10;
        const totalW = arr.length * w + (arr.length - 1) * gap;
        const startX = 360 - totalW / 2;
        const x = startX + i * (w + gap);
        return (
          <g key={name}>
            <rect x={x} y={300} width={w} height={32} rx="5" fill="#0B1120" stroke="#1B4F47" />
            <text x={x + w / 2} y={320} textAnchor="middle" fill="#7FC7BB" fontSize="10" fontFamily="var(--font-plex-mono)">
              {name}
            </text>
          </g>
        );
      })}

      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M2 1L8 5L2 9" fill="none" stroke="#B8923A" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </marker>
      </defs>
    </svg>
  );
}
