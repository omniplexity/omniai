import { MemoryItem } from "../../types";

interface MemoryPanelProps {
  memoryItems: MemoryItem[];
  memoryType: string;
  memoryTitle: string;
  memoryContent: string;
  memoryQuery: string;
  memoryBudget: number;
  memoryPreview: string;
  onCreateMemory: () => void;
  onDeleteMemory: (id: string) => void;
  onSearchMemory: () => void;
  onMemoryTypeChange: (type: string) => void;
  onMemoryTitleChange: (title: string) => void;
  onMemoryContentChange: (content: string) => void;
  onMemoryQueryChange: (query: string) => void;
  onMemoryBudgetChange: (budget: number) => void;
}

export function MemoryPanel({
  memoryItems,
  memoryType,
  memoryTitle,
  memoryContent,
  memoryQuery,
  memoryBudget,
  memoryPreview,
  onCreateMemory,
  onDeleteMemory,
  onSearchMemory,
  onMemoryTypeChange,
  onMemoryTitleChange,
  onMemoryContentChange,
  onMemoryQueryChange,
  onMemoryBudgetChange,
}: MemoryPanelProps) {
  return (
    <div className="dashboard-container">
      <div className="section-header"><span className="section-title">Memory</span></div>
      <div className="section-content">
        <select className="input mb-sm" value={memoryType} onChange={(e) => onMemoryTypeChange(e.target.value)}>
          <option value="episodic">Episodic</option><option value="semantic">Semantic</option><option value="procedural">Procedural</option>
        </select>
        <input type="text" className="input mb-sm" placeholder="Title" value={memoryTitle} onChange={(e) => onMemoryTitleChange(e.target.value)} />
        <textarea className="input mb-sm" rows={2} placeholder="Content..." value={memoryContent} onChange={(e) => onMemoryContentChange(e.target.value)} />
        <button className="btn btn-primary btn-sm mb-sm" onClick={onCreateMemory}>Create</button>
        <input type="text" className="input mb-sm" placeholder="Search..." value={memoryQuery} onChange={(e) => onMemoryQueryChange(e.target.value)} />
        <div className="flex gap-xs items-center mb-sm">
          <span className="text-sm text-secondary">Budget:</span>
          <input type="number" className="input" value={memoryBudget} onChange={(e) => onMemoryBudgetChange(Number(e.target.value))} style={{ width: "80px" }} />
          <button className="btn btn-ghost btn-sm" onClick={onSearchMemory}>Search</button>
        </div>
        {memoryPreview && <pre className="text-xs mb-sm" style={{ whiteSpace: "pre-wrap", maxHeight: "120px", overflowY: "auto" }}>{memoryPreview}</pre>}
        <div className="list" style={{ maxHeight: "320px", overflowY: "auto" }}>
          {memoryItems.map((m) => (
            <div key={m.memory_id} className="list-item">
              <div className="list-item-content"><div className="list-item-title"><span className="badge badge-default">{m.type}</span> {m.title || m.content.slice(0, 20)}</div></div>
              <button className="btn btn-ghost btn-sm" onClick={() => onDeleteMemory(m.memory_id)}>×</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
