import { Card, CardLabel } from "@/components/Card";
import { AgentFlowDiagram } from "@/features/workflow/AgentFlowDiagram";

export default function WorkflowPage() {
  return (
    <div className="p-8 max-w-4xl">
      <p className="text-xs font-mono text-ink-300 mb-2">workflow</p>
      <h1 className="font-display text-2xl italic text-ink-50 mb-1">How a request reaches Razorpay.</h1>
      <p className="text-ink-300 text-sm mb-6 max-w-lg">
        The workflow only routes and logs. It never decides whether a payment should happen —
        that decision belongs to the guardrail gate alone.
      </p>

      <Card className="p-6 mb-6">
        <AgentFlowDiagram />
      </Card>

      <div className="grid grid-cols-2 gap-4">
        <Card className="p-4">
          <CardLabel>validate</CardLabel>
          <p className="mt-1.5 text-sm text-ink-50">Confirms the requested agent exists, logs the routing decision.</p>
        </Card>
        <Card className="p-4">
          <CardLabel>invoke_agent</CardLabel>
          <p className="mt-1.5 text-sm text-ink-50">Runs the agent's tool-calling loop; catches gpt-oss-20b failures cleanly.</p>
        </Card>
      </div>
    </div>
  );
}
