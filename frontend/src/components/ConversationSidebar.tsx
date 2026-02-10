import { useEffect, useState } from "preact/hooks";
import { navigate } from "../core/router/hashRouter";
import * as conversationApi from "../core/conversation/conversationApi";
import {
  conversationStore,
  loadConversations,
  createNewConversation,
  renameCurrentConversation
} from "../core/conversation/conversationStore";

export function ConversationSidebar() {
  const [store, setStore] = useState(conversationStore.get());
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const unsub = conversationStore.subscribe(() => {
      setStore(conversationStore.get());
    });
    return unsub;
  }, []);

  useEffect(() => {
    void loadConversations();
  }, []);

  const filtered = store.conversations.filter(c =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  async function onNewChat() {
    setCreating(true);
    try {
      const conv = await createNewConversation();
      navigate(`/chat/${conv.id}`);
    } catch (e) {
      console.error("Failed to create conversation:", e);
    } finally {
      setCreating(false);
    }
  }

  async function onSelect(id: string) {
    conversationStore.setCurrentConversation(id);
    navigate(`/chat/${id}`);
  }

  function startEdit(e: Event, id: string, title: string) {
    e.preventDefault();
    e.stopPropagation();
    setEditingId(id);
    setEditTitle(title);
  }

  async function submitEdit(id: string) {
    if (editTitle.trim()) {
      try {
        await renameCurrentConversation(editTitle.trim());
      } catch (e) {
        console.error("Failed to rename:", e);
      }
    }
    setEditingId(null);
    setEditTitle("");
  }

  async function onDelete(e: Event, id: string) {
    e.preventDefault();
    e.stopPropagation();
    if (confirm("Delete this conversation?")) {
      try {
        await deleteConversationById(id);
        if (store.currentId === id) {
          navigate("/chat");
        }
      } catch (e) {
        console.error("Failed to delete:", e);
      }
    }
  }

  async function deleteConversationById(id: string) {
    await conversationApi.deleteConversation(id);
    const { currentId, conversations } = conversationStore.get();
    const newConversations = conversations.filter(c => c.id !== id);
    conversationStore.patch({
      conversations: newConversations,
      currentId: currentId === id ? null : currentId,
      loading: false
    });
  }

  function formatDate(iso: string): string {
    const d = new Date(iso);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  }

  return (
    <div class="conversation-sidebar">
      <div class="sidebar-header">
        <button
          class="btn new-chat-btn"
          onClick={onNewChat}
          disabled={creating || store.loading}
        >
          {creating ? "..." : "+ New chat"}
        </button>
      </div>

      <div class="sidebar-search">
        <input
          class="input search-input"
          placeholder="Search conversations..."
          value={search}
          onInput={(e) => setSearch((e.target as HTMLInputElement).value)}
        />
      </div>

      <div class="conversation-list">
        {store.loading && store.conversations.length === 0 ? (
          <div class="muted empty-state">Loading...</div>
        ) : filtered.length === 0 ? (
          <div class="muted empty-state">
            {search ? "No matching conversations" : "No conversations yet"}
          </div>
        ) : (
          filtered.map((conv) => (
            <div
              key={conv.id}
              class={`conversation-item ${store.currentId === conv.id ? "active" : ""}`}
              onClick={() => onSelect(conv.id)}
            >
              {editingId === conv.id ? (
                <input
                  class="input edit-input"
                  value={editTitle}
                  autoFocus
                  onInput={(e) => setEditTitle((e.target as HTMLInputElement).value)}
                  onBlur={() => submitEdit(conv.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") submitEdit(conv.id);
                    if (e.key === "Escape") {
                      setEditingId(null);
                      setEditTitle("");
                    }
                  }}
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <>
                  <div class="conversation-title">{conv.title}</div>
                  <div class="conversation-meta">
                    <span class="conversation-date">{formatDate(conv.updated_at)}</span>
                    <div class="conversation-actions">
                      <button
                        class="action-btn"
                        title="Rename"
                        onClick={(e) => startEdit(e, conv.id, conv.title)}
                      >
                        ✎
                      </button>
                      <button
                        class="action-btn delete"
                        title="Delete"
                        onClick={(e) => onDelete(e, conv.id)}
                      >
                        ×
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>

      {store.error ? (
        <div class="sidebar-error muted">{store.error}</div>
      ) : null}
    </div>
  );
}
