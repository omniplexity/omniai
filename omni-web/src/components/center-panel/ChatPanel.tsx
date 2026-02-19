import { useRef, useEffect, useState } from "react";
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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [hoveredMessageSeq, setHoveredMessageSeq] = useState<number | null>(null);

  const chatEvents = events
    .filter((e) => ["user_message", "assistant_message", "system_event"].includes(e.kind))
    .sort((a, b) => a.seq - b.seq);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatEvents.length]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [chatText]);

  const getMessageText = (event: EventEnvelope): string => {
    const p = event.payload as Record<string, unknown>;
    if (event.kind === "system_event") {
      return String(p?.details || p?.message || "System event");
    }
    return String(p?.text || p?.content || "");
  };

  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  // Empty state — branded welcome
  if (!selectedRunId) {
    return (
      <div className="chat-welcome">
        <div className="chat-welcome-inner">
          <div className="chat-welcome-logo">
            <img src="/favicon.svg" alt="OmniAI" className="chat-welcome-logo-img" />
          </div>
          <h1 className="chat-welcome-title">OmniAI</h1>
          <p className="chat-welcome-subtitle">
            Your multi-model AI workspace. Select a conversation or start a new one.
          </p>
          <div className="chat-welcome-capabilities">
            <div className="chat-welcome-cap">
              <div className="chat-welcome-cap-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <span>Multi-turn conversations</span>
            </div>
            <div className="chat-welcome-cap">
              <div className="chat-welcome-cap-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </div>
              <span>Tool & plugin integration</span>
            </div>
            <div className="chat-welcome-cap">
              <div className="chat-welcome-cap-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
              </div>
              <span>Artifact generation</span>
            </div>
            <div className="chat-welcome-cap">
              <div className="chat-welcome-cap-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <polygon points="12 2 2 7 12 12 22 7 12 2" />
                  <polyline points="2 17 12 22 22 17" />
                  <polyline points="2 12 12 17 22 12" />
                </svg>
              </div>
              <span>Workflow automation</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-v2">
      {/* Conversation thread */}
      <div className="chat-v2-thread">
        {chatEvents.length === 0 ? (
          <div className="chat-v2-empty">
            <div className="chat-v2-empty-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <p>Send a message to begin the conversation</p>
          </div>
        ) : (
          chatEvents.map((event) => {
            const isUser = event.actor === "user" && event.kind !== "system_event";
            const isSystem = event.kind === "system_event";
            const isAssistant = !isUser && !isSystem;

            if (isSystem) {
              return (
                <div key={event.seq} className="chat-v2-system">
                  <div className="chat-v2-system-line" />
                  <span className="chat-v2-system-text">
                    {getMessageText(event)}
                  </span>
                  <div className="chat-v2-system-line" />
                </div>
              );
            }

            return (
              <div
                key={event.seq}
                className={`chat-v2-msg ${isUser ? "chat-v2-msg-user" : "chat-v2-msg-ai"}`}
                onMouseEnter={() => setHoveredMessageSeq(event.seq)}
                onMouseLeave={() => setHoveredMessageSeq(null)}
              >
                <div className="chat-v2-msg-inner">
                  {/* Avatar */}
                  <div className={`chat-v2-avatar ${isUser ? "chat-v2-avatar-user" : "chat-v2-avatar-ai"}`}>
                    {isUser ? (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                        <circle cx="12" cy="7" r="4" />
                      </svg>
                    ) : (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M12 2L2 7l10 5 10-5-10-5z" />
                        <path d="M2 17l10 5 10-5" />
                        <path d="M2 12l10 5 10-5" />
                      </svg>
                    )}
                  </div>

                  {/* Content */}
                  <div className="chat-v2-msg-body">
                    <div className="chat-v2-msg-header">
                      <span className="chat-v2-msg-role">
                        {isUser ? "You" : "OmniAI"}
                      </span>
                      <span className="chat-v2-msg-time">{formatTime(event.ts)}</span>
                    </div>
                    <div className="chat-v2-msg-text">
                      {getMessageText(event)}
                    </div>

                    {/* Hover actions */}
                    {hoveredMessageSeq === event.seq && (
                      <div className="chat-v2-msg-actions">
                        <button
                          className="chat-v2-action-btn"
                          onClick={() => navigator.clipboard.writeText(getMessageText(event))}
                          title="Copy"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                          </svg>
                        </button>
                        <button
                          className="chat-v2-action-btn"
                          onClick={() => onPromoteToMemory(event.event_id)}
                          title="Save to memory"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
                          </svg>
                        </button>
                        <button
                          className="chat-v2-action-btn"
                          onClick={() => onAddComment(event.event_id)}
                          title="Comment"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                          </svg>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <div className="chat-v2-composer">
        <div className="chat-v2-composer-inner">
          <div className="chat-v2-composer-row">
            <textarea
              ref={textareaRef}
              className="chat-v2-textarea"
              value={chatText}
              onChange={(e) => onTextChange(e.target.value)}
              placeholder="Message OmniAI..."
              rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSendMessage(e);
                }
              }}
            />
          </div>
          <div className="chat-v2-composer-footer">
            <div className="chat-v2-composer-left">
              {/* Attachment button */}
              <button className="chat-v2-composer-btn" title="Attach file">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                </svg>
              </button>

              {/* Mode toggle */}
              <button
                className={`chat-v2-mode-btn ${agentMode ? "active" : ""}`}
                onClick={() => onModeChange(!agentMode)}
                title={agentMode ? "Agent mode (tools enabled)" : "Simple mode"}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" />
                  <path d="M2 17l10 5 10-5" />
                  <path d="M2 12l10 5 10-5" />
                </svg>
                <span>{agentMode ? "Agent" : "Simple"}</span>
              </button>
            </div>

            <div className="chat-v2-composer-right">
              {/* Send button */}
              <button
                className="chat-v2-send-btn"
                onClick={(e) => onSendMessage(e)}
                disabled={!chatText.trim()}
                title="Send message"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
