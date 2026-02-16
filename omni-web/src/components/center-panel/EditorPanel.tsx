import { ArtifactRef } from "../../types";

interface EditorPanelProps {
  docTitle: string;
  docText: string;
  artifacts: ArtifactRef[];
  loadArtifactId: string;
  selectedRunId: string;
  onTitleChange: (title: string) => void;
  onTextChange: (text: string) => void;
  onSave: () => void;
  onLoadArtifact: (artifactId: string) => void;
  onFileUpload: (file: File) => void;
  onPromoteToMemory: (artifactId: string) => void;
}

export function EditorPanel({
  docTitle,
  docText,
  artifacts,
  loadArtifactId,
  selectedRunId,
  onTitleChange,
  onTextChange,
  onSave,
  onLoadArtifact,
  onFileUpload,
  onPromoteToMemory,
}: EditorPanelProps) {
  return (
    <div className="editor-container">
      {/* Header */}
      <div className="section-header">
        <div className="flex items-center gap-md">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
          </svg>
          <span className="section-title">Editor</span>
        </div>
      </div>

      {/* Document Title */}
      <div className="input-group">
        <label className="input-label">Document Title</label>
        <input
          type="text"
          className="input"
          value={docTitle}
          onChange={(e) => onTitleChange(e.target.value)}
          placeholder="Enter document title..."
        />
      </div>

      {/* Editor Textarea */}
      <div className="input-group" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <label className="input-label">Content</label>
        <textarea
          className="input editor-textarea"
          value={docText}
          onChange={(e) => onTextChange(e.target.value)}
          placeholder="Start writing..."
          style={{ flex: 1, minHeight: "200px" }}
        />
      </div>

      {/* Actions */}
      <div className="editor-toolbar">
        <button 
          className="btn btn-primary"
          onClick={onSave}
          disabled={!selectedRunId}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
            <polyline points="17 21 17 13 7 13 7 21" />
            <polyline points="7 3 7 8 15 8" />
          </svg>
          Save
        </button>
        
        <div style={{ flex: 1 }} />
        
        <input
          type="file"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onFileUpload(file);
          }}
          style={{ width: "auto" }}
        />
        
        <select
          className="input"
          value={loadArtifactId}
          onChange={(e) => onLoadArtifact(e.target.value)}
          style={{ width: "200px" }}
        >
          <option value="">Load artifact...</option>
          {artifacts.map((a) => (
            <option key={a.artifact_id} value={a.artifact_id}>
              {a.title || a.artifact_id.slice(0, 16)}
            </option>
          ))}
        </select>
        
        <button
          className="btn btn-secondary"
          onClick={() => loadArtifactId && onPromoteToMemory(loadArtifactId)}
          disabled={!loadArtifactId}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 3v18M3 12h18" />
          </svg>
          Promote to Memory
        </button>
      </div>
    </div>
  );
}
