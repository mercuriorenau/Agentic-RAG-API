import { Explainer } from "./Explainer";
import { AGENT_PATH } from "../explainers";

type Props = {
  route: string;
  modelProvider: string;
  modelName: string;
  toolsUsed: string[];
};

const TOOL_LABELS: Record<string, string> = {
  retrieve_documents: "Search uploads",
  web_search: "Web search",
  answer_directly: "Answer directly",
};

function summarizeTools(tools: string[]): { name: string; label: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const tool of tools) {
    counts.set(tool, (counts.get(tool) || 0) + 1);
  }
  return [...counts.entries()].map(([name, count]) => ({
    name,
    label: TOOL_LABELS[name] || name,
    count,
  }));
}

function routeLabel(route: string): string {
  switch (route) {
    case "retrieve":
      return "Route: retrieve uploads";
    case "web":
      return "Route: web search";
    case "mixed":
      return "Route: retrieve + web";
    case "direct":
      return "Route: direct answer";
    default:
      return `Route: ${route}`;
  }
}

export function AgentPath({ route, modelProvider, modelName, toolsUsed }: Props) {
  const tools = summarizeTools(toolsUsed);
  const totalCalls = toolsUsed.length;

  return (
    <div className="agent-path">
      <div className="agent-path-head">
        <h3>What the agent did</h3>
        <Explainer summary="Route, model, and tools">{AGENT_PATH}</Explainer>
      </div>
      <div className="agent-path-badges meta">
        <span className="badge" title="High-level path for this answer">
          {routeLabel(route)}
        </span>
        <span className="badge" title="LLM that ran the agent loop">
          Model: {modelProvider} / {modelName}
        </span>
      </div>
      {tools.length > 0 ? (
        <div className="agent-path-tools">
          <p className="agent-path-tools-label muted">
            Tool calls this turn
            {totalCalls > 1 ? ` (${totalCalls} total)` : ""}:
          </p>
          <div className="meta">
            {tools.map((tool) => (
              <span
                key={tool.name}
                className="badge subtle"
                title={
                  tool.count > 1
                    ? `${tool.name} was called ${tool.count} times`
                    : tool.name
                }
              >
                {tool.label}
                {tool.count > 1 ? ` ×${tool.count}` : ""}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <p className="muted agent-path-tools-empty">
          No tools — the model answered without retrieve or web search.
        </p>
      )}
    </div>
  );
}
