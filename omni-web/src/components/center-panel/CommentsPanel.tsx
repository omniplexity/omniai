import { CommentRow } from "../../types";

interface CommentsPanelProps {
  comments: CommentRow[];
  commentTargetType: "run" | "event" | "artifact";
  commentTargetId: string;
  commentBody: string;
  selectedProjectId: string;
  onCreateComment: () => void;
  onDeleteComment: (id: string) => void;
  onCommentTargetTypeChange: (type: "run" | "event" | "artifact") => void;
  onCommentTargetIdChange: (id: string) => void;
  onCommentBodyChange: (body: string) => void;
}

export function CommentsPanel({
  comments,
  commentTargetType,
  commentTargetId,
  commentBody,
  selectedProjectId,
  onCreateComment,
  onDeleteComment,
  onCommentTargetTypeChange,
  onCommentTargetIdChange,
  onCommentBodyChange,
}: CommentsPanelProps) {
  return (
    <div className="dashboard-container">
      <div className="section-header"><span className="section-title">Comments</span></div>
      <div className="section-content">
        <div className="flex gap-xs mb-sm">
          <select className="input" value={commentTargetType} onChange={(e) => onCommentTargetTypeChange(e.target.value as "run" | "event" | "artifact")}>
            <option value="run">run</option><option value="event">event</option><option value="artifact">artifact</option>
          </select>
          <input type="text" className="input" placeholder="target id" value={commentTargetId} onChange={(e) => onCommentTargetIdChange(e.target.value)} />
        </div>
        <textarea className="input mb-sm" rows={2} placeholder="Comment..." value={commentBody} onChange={(e) => onCommentBodyChange(e.target.value)} />
        <button className="btn btn-primary btn-sm mb-sm" onClick={onCreateComment} disabled={!selectedProjectId}>Add Comment</button>
        <div className="list">
          {comments.map((c) => (
            <div key={c.comment_id} className="list-item">
              <div className="list-item-content"><div className="list-item-title">{c.author_id}: {c.body}</div></div>
              <button className="btn btn-ghost btn-sm" onClick={() => onDeleteComment(c.comment_id)}>×</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
