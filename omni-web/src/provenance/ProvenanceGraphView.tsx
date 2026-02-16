import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, { Background, Controls, MiniMap, useReactFlow, type Node } from "reactflow";
import "reactflow/dist/style.css";
import { toFlowGraph, type ProvEdge, type ProvNode } from "./layout";

type WhyPath = { nodes: string[]; edges: ProvEdge[] };
type WhyPayload = { paths: WhyPath[]; truncated: boolean };

type Props = {
  graph: {
    run_id: string;
    generated_at: string;
    truncated?: boolean;
    truncation?: { node_cap_hit?: boolean; edge_cap_hit?: boolean; depth_cap_hit?: boolean };
    nodes: ProvNode[];
    edges: ProvEdge[];
  };
  why?: WhyPayload;
  onArtifactSelect: (artifactNodeId: string) => void;
};

const TYPE_LABELS: Array<{ key: string; label: string }> = [
  { key: "event", label: "Events" },
  { key: "artifact", label: "Artifacts" },
  { key: "research_source", label: "Sources" },
  { key: "workflow_node", label: "Workflow" },
  { key: "tool", label: "Tools" },
];

export function ProvenanceGraphView({ graph, why, onArtifactSelect }: Props) {
  const [search, setSearch] = useState("");
  const [showTypes, setShowTypes] = useState<Record<string, boolean>>({
    event: true,
    artifact: true,
    research_source: true,
    workflow_node: true,
    tool: true,
  });
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [layoutMode, setLayoutMode] = useState<"columns" | "compact">("columns");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const nodes = graph.nodes.filter((n) => {
      if (showTypes[n.type] === false) return false;
      if (!q) return true;
      return n.id.toLowerCase().includes(q) || String(n.label || "").toLowerCase().includes(q);
    });
    const nodeIds = new Set(nodes.map((n) => n.id));
    const edges = graph.edges.filter((e) => nodeIds.has(e.from) && nodeIds.has(e.to));
    return { nodes, edges };
  }, [graph.nodes, graph.edges, search, showTypes]);

  const { nodes: flowNodes, edges: flowEdges } = useMemo(() => toFlowGraph(filtered.nodes, filtered.edges, layoutMode), [filtered.nodes, filtered.edges, layoutMode]);

  const selectedNode = useMemo(() => filtered.nodes.find((n) => n.id === selectedNodeId) || null, [filtered.nodes, selectedNodeId]);
  const incoming = useMemo(() => filtered.edges.filter((e) => e.to === selectedNodeId), [filtered.edges, selectedNodeId]);
  const outgoing = useMemo(() => filtered.edges.filter((e) => e.from === selectedNodeId), [filtered.edges, selectedNodeId]);

  function onNodeClick(nodeId: string) {
    setSelectedNodeId(nodeId);
    if (nodeId.startsWith("artifact:")) onArtifactSelect(nodeId);
  }

  const onFlowNodeClick = (_: React.MouseEvent, node: Node) => onNodeClick(node.id);
  const nodeList = filtered.nodes.slice(0, 300);
  const caps = graph.truncation || {};

  const copyText = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // no-op fallback
    }
  }, []);

  function AutoFit({ depKey }: { depKey: string }) {
    const rf = useReactFlow();
    useEffect(() => {
      const t = window.setTimeout(() => {
        void rf.fitView({ padding: 0.2, duration: 150 });
      }, 0);
      return () => window.clearTimeout(t);
    }, [rf, depKey]);
    return null;
  }

  const depKey = `${flowNodes.length}-${flowEdges.length}-${search}-${JSON.stringify(showTypes)}-${layoutMode}`;

  return (
    <div>
      {graph.truncated && (
        <div role="status" aria-live="polite" style={{ background: "#fef3c7", border: "1px solid #f59e0b", borderRadius: 8, padding: 8, marginBottom: 8 }}>
          Graph truncated. Consider increasing `max_depth`, `node_cap`, or `edge_cap`.
          <div>node_cap_hit={String(!!caps.node_cap_hit)} edge_cap_hit={String(!!caps.edge_cap_hit)} depth_cap_hit={String(!!caps.depth_cap_hit)}</div>
        </div>
      )}
      <div className="prov-controls">
        <input aria-label="Search provenance nodes" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search node id/label" />
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            Layout
            <select aria-label="Graph layout mode" value={layoutMode} onChange={(e) => setLayoutMode(e.target.value as "columns" | "compact")}>
              <option value="columns">columns</option>
              <option value="compact">compact</option>
            </select>
          </label>
          {TYPE_LABELS.map((t) => (
            <label key={t.key} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <input
                aria-label={`Toggle ${t.label}`}
                type="checkbox"
                checked={showTypes[t.key] !== false}
                onChange={(e) => setShowTypes((prev) => ({ ...prev, [t.key]: e.target.checked }))}
              />
              {t.label}
            </label>
          ))}
        </div>
      </div>
      <div className="prov-grid">
        <div className="prov-canvas" aria-label="Provenance graph canvas">
          {flowNodes.length === 0 ? (
            <div>No graph nodes match current filters.</div>
          ) : (
            <ReactFlow nodes={flowNodes} edges={flowEdges} fitView onNodeClick={onFlowNodeClick}>
              <AutoFit depKey={depKey} />
              <MiniMap />
              <Controls />
              <Background />
            </ReactFlow>
          )}
        </div>
        <div className="prov-side">
          <h4>Node List</h4>
          <ul role="listbox" aria-label="Provenance node list" className="prov-list">
            {nodeList.map((n) => (
              <li key={n.id}>
                <button
                  aria-label={`Select node ${n.id}`}
                  className={n.id === selectedNodeId ? "sel" : ""}
                  onClick={() => onNodeClick(n.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") onNodeClick(n.id);
                  }}
                >
                  {n.type}: {n.label}
                </button>
                <button aria-label={`Copy node id ${n.id}`} onClick={() => void copyText(n.id)}>Copy ID</button>
              </li>
            ))}
          </ul>
          <h4>Node Details</h4>
          {!selectedNode ? (
            <div>Select a node.</div>
          ) : (
            <>
              <div className="row">
                <button onClick={() => void copyText(selectedNode.id)}>Copy Node ID</button>
              </div>
              <pre>{JSON.stringify({ id: selectedNode.id, type: selectedNode.type, label: selectedNode.label }, null, 2)}</pre>
              <div>Meta</div>
              <pre>{JSON.stringify(selectedNode.meta || {}, null, 2)}</pre>
              <div>Incoming: {incoming.length}</div>
              <ul>{incoming.map((e) => <li key={`${e.from}-${e.to}-${e.kind}`}>{e.from} --{e.kind}--&gt; {e.to} <button onClick={() => void copyText(`${e.from}|${e.kind}|${e.to}`)}>Copy Edge</button></li>)}</ul>
              <div>Outgoing: {outgoing.length}</div>
              <ul>{outgoing.map((e) => <li key={`${e.from}-${e.to}-${e.kind}`}>{e.from} --{e.kind}--&gt; {e.to} <button onClick={() => void copyText(`${e.from}|${e.kind}|${e.to}`)}>Copy Edge</button></li>)}</ul>
            </>
          )}
          {selectedNode?.id.startsWith("artifact:") && (
            <>
              <h4>Why Is This Here?</h4>
              {why?.truncated && <div>Path results truncated.</div>}
              {why?.paths?.length ? (
                <ol>
                  {why.paths.map((p, idx) => (
                    <li key={`why-${idx}`}>
                      <div>Path {idx + 1}</div>
                      <ol>{p.nodes.map((pn) => <li key={`${idx}-${pn}`}>{pn}</li>)}</ol>
                    </li>
                  ))}
                </ol>
              ) : (
                <div>No upstream paths for selected artifact.</div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
