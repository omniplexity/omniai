import type { Edge, Node } from "reactflow";

export type ProvNode = { id: string; type: string; label: string; meta: Record<string, unknown> };
export type ProvEdge = { from: string; to: string; kind: string; meta: Record<string, unknown> };

const TYPE_ORDER = ["event", "workflow_node", "artifact", "research_source", "tool"];
const TYPE_X: Record<string, number> = {
  event: 0,
  workflow_node: 280,
  artifact: 560,
  research_source: 840,
  tool: 1120,
};

function xForType(t: string): number {
  if (t in TYPE_X) return TYPE_X[t];
  return 1120 + Math.max(0, TYPE_ORDER.indexOf(t)) * 280;
}

function toFlowGraphColumns(nodes: ProvNode[], edges: ProvEdge[]): { nodes: Node[]; edges: Edge[] } {
  const grouped = new Map<string, ProvNode[]>();
  for (const n of nodes) {
    const arr = grouped.get(n.type) || [];
    arr.push(n);
    grouped.set(n.type, arr);
  }
  const flowNodes: Node[] = [];
  for (const [type, arr] of grouped.entries()) {
    const sorted = [...arr].sort((a, b) => a.id.localeCompare(b.id));
    sorted.forEach((n, idx) => {
      flowNodes.push({
        id: n.id,
        data: { label: n.label || n.id, type: n.type, meta: n.meta },
        position: { x: xForType(type), y: idx * 90 },
        style: { width: 220, border: "1px solid #cbd5e1", borderRadius: 8, background: "#fff" },
      });
    });
  }
  const flowEdges: Edge[] = edges.map((e, idx) => ({
    id: `${e.from}->${e.to}:${e.kind}:${idx}`,
    source: e.from,
    target: e.to,
    label: e.kind,
    animated: false,
    style: { stroke: "#64748b" },
    labelStyle: { fontSize: 10, fill: "#334155" },
  }));
  return { nodes: flowNodes, edges: flowEdges };
}

function toFlowGraphCompact(nodes: ProvNode[], edges: ProvEdge[]): { nodes: Node[]; edges: Edge[] } {
  const incoming = new Map<string, number>();
  const outgoing = new Map<string, string[]>();
  for (const n of nodes) {
    incoming.set(n.id, 0);
    outgoing.set(n.id, []);
  }
  for (const e of edges) {
    if (incoming.has(e.to)) incoming.set(e.to, (incoming.get(e.to) || 0) + 1);
    const out = outgoing.get(e.from);
    if (out) out.push(e.to);
  }
  const roots = [...nodes].filter((n) => (incoming.get(n.id) || 0) === 0).sort((a, b) => a.id.localeCompare(b.id));
  const layer = new Map<string, number>();
  const queue = [...roots];
  for (const r of roots) layer.set(r.id, 0);
  while (queue.length) {
    const cur = queue.shift()!;
    const base = layer.get(cur.id) || 0;
    for (const nxt of (outgoing.get(cur.id) || []).sort()) {
      const nextLayer = base + 1;
      if (!layer.has(nxt) || (layer.get(nxt) || 0) < nextLayer) layer.set(nxt, nextLayer);
      queue.push(nodes.find((n) => n.id === nxt)!);
    }
  }
  for (const n of nodes) if (!layer.has(n.id)) layer.set(n.id, 0);
  const byLayer = new Map<number, ProvNode[]>();
  for (const n of nodes) {
    const l = layer.get(n.id) || 0;
    const arr = byLayer.get(l) || [];
    arr.push(n);
    byLayer.set(l, arr);
  }
  const flowNodes: Node[] = [];
  for (const [l, arr] of [...byLayer.entries()].sort((a, b) => a[0] - b[0])) {
    arr.sort((a, b) => a.id.localeCompare(b.id)).forEach((n, idx) => {
      flowNodes.push({
        id: n.id,
        data: { label: n.label || n.id, type: n.type, meta: n.meta },
        position: { x: l * 280, y: idx * 90 },
        style: { width: 220, border: "1px solid #cbd5e1", borderRadius: 8, background: "#fff" },
      });
    });
  }
  const flowEdges: Edge[] = edges.map((e, idx) => ({
    id: `${e.from}->${e.to}:${e.kind}:${idx}`,
    source: e.from,
    target: e.to,
    label: e.kind,
    style: { stroke: "#64748b" },
    labelStyle: { fontSize: 10, fill: "#334155" },
  }));
  return { nodes: flowNodes, edges: flowEdges };
}

export function toFlowGraph(nodes: ProvNode[], edges: ProvEdge[], mode: "columns" | "compact" = "columns"): { nodes: Node[]; edges: Edge[] } {
  return mode === "compact" ? toFlowGraphCompact(nodes, edges) : toFlowGraphColumns(nodes, edges);
}
