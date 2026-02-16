import { EventEnvelope } from "../../types";

interface ChatPanelProps {
  events: EventEnvelope[];
  chatText: string;
  agentMode: boolean;
  selectedRunId: string;
  onSendMessage: (e: React.FormEvent) => void;
  onTextChange: (text: string) => void;
  onModeChange: (mode: boolean) => void;
  onPromoteToMemory: (eventId: string) => void;
  onAddComment: (eventId: string) => void;
}

export function ChatPanel({
  events,
  chatText,
  agentMode,
  selectedRunId,
  onSendMessage,
  onTextChange,
  onModeChange,
  onPromoteToMemory,
  onAddComment,
}: ChatPanelProps) {
  const chatEvents = events
    .filter((e) => ["user_message", "assistant_message", "system_event"].includes(e.kind))
    .sort((a, b) => a.seq - b.seq);

  return (
    <div className="chat-container">
      {/* Header */}
      <div className="section-header">
        <div className="flex items-center gap-md">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          <span className="section-title">Chat</span>
        </div>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={agentMode}
            onChange={(e) => onModeChange(e.target.checked)}
          />
          <span>Agent Mode</span>
        </label>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {chatEvents.length === 0 ? (
          <div className="empty-state">
            <svg className="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <div className="empty-state-title">No messages yet</div>
            <div className="empty-state-description">
              Start a conversation by sending a message below
            </div>
          </div>
        ) : (
          chatEvents.map((event) => (
            <div key={event.seq} className={`message ${event.kind === "system_event" ? "system" : event.actor}`}>
              <div className="message-avatar">
                {event.kind === "system_event" ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 16v-4M12 8h.01" />
                  </svg>
                ) : event.actor === "user" ? (
                  "U"
                ) : (
                  "AI"
                )}
              </div>
              <div className="message-content">
                {event.kind === "system_event" 
                  ? String((event.payload as Record<string, unknown>)?.details as Record<string, unknown> || (event.payload as Record<string, unknown>)?.message || "system")
                  : String((event.payload as Record<string, unknown>)?.text || (event.payload as Record<string, unknown>)?.content || "")
                }
                {event.kind !== "system_event" && (
                  <div className="message-actions">
                    <button 
                      className="btn btn-ghost btn-sm"
                      onClick={() => onPromoteToMemory(event.event_id)}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 3v18M3 12h18" />
                      </svg>
                      Memory
                    </button>
                    <button 
                      className="btn btn-ghost btn-sm"
                      onClick={() => onAddComment(event.event_id)}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                      </svg>
                      Comment
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Input */}
      <div className="chat-input-container">
        <form className="chat-input-form" onSubmit={onSendMessage}>
          <textarea
            className="input chat-input"
            value={chatText}
            onChange={(e) => onTextChange(e.target.value)}
            placeholder={selectedRunId ? "Type your message..." : "Select a run to start chatting"}
            disabled={!selectedRunId}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSendMessage(e);
              }
            }}
          />
          <button 
            type="submit" 
            className="btn btn-primary"
            disabled={!selectedRunId || !chatText.trim()}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
