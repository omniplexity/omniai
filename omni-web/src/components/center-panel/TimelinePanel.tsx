interface TimelinePanelProps {
  traceKind: string;
  traceToolId: string;
  traceErrorsOnly: boolean;
  traceSearch: string;
  filteredEvents: Array<{ seq: number; kind: string }>;
  onTraceKindChange: (kind: string) => void;
  onTraceToolIdChange: (toolId: string) => void;
  onTraceErrorsOnlyChange: (errorsOnly: boolean) => void;
  onTraceSearchChange: (search: string) => void;
}

export function TimelinePanel({
  traceKind,
  traceToolId,
  traceErrorsOnly,
  traceSearch,
  filteredEvents,
  onTraceKindChange,
  onTraceToolIdChange,
  onTraceErrorsOnlyChange,
  onTraceSearchChange,
}: TimelinePanelProps) {
  return (
    <div className="dashboard-container">
      <div className="section-header">
        <span className="section-title">Timeline</span>
      </div>
      <div className="section-content">
        <div className="flex gap-xs mb-sm">
          <input type="text" className="input" placeholder="Kind filter" value={traceKind} onChange={(e) => onTraceKindChange(e.target.value)} />
          <input type="text" className="input" placeholder="Tool filter" value={traceToolId} onChange={(e) => onTraceToolIdChange(e.target.value)} />
        </div>
        <label className="checkbox-label mb-sm">
          <input type="checkbox" checked={traceErrorsOnly} onChange={(e) => onTraceErrorsOnlyChange(e.target.checked)} />
          Errors only
        </label>
        <input type="text" className="input mb-sm" placeholder="Search payload..." value={traceSearch} onChange={(e) => onTraceSearchChange(e.target.value)} />
        <div className="list" style={{ maxHeight: "360px", overflowY: "auto" }}>
          {filteredEvents.slice(0, 200).map((e) => (
            <div key={e.seq} className="list-item">
              <div className="list-item-content">
                <div className="list-item-title">
                  <span className="badge badge-default">#{e.seq}</span> {e.kind}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
