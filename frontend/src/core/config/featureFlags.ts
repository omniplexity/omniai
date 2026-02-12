type Flags = {
  workspace: boolean;
  memoryPanel: boolean;
  knowledgePanel: boolean;
  voice: boolean;
  tools: boolean;
  adminOps: boolean;
};

const DEFAULT_FLAGS: Flags = {
  workspace: false,
  memoryPanel: false,
  knowledgePanel: false,
  voice: false,
  tools: false,
  adminOps: false
};

let _flags: Flags = { ...DEFAULT_FLAGS };

export function setFlagsFromRuntime(cfg: { FEATURE_FLAGS?: Record<string, boolean> }) {
  const f = cfg.FEATURE_FLAGS ?? {};
  _flags = {
    workspace: Boolean(f.workspace),
    memoryPanel: Boolean(f.memoryPanel),
    knowledgePanel: Boolean(f.knowledgePanel),
    voice: Boolean(f.voice),
    tools: Boolean(f.tools),
    adminOps: Boolean(f.adminOps)
  };
}

export function setFlagsFromMeta(meta: { flags?: Record<string, unknown> } | undefined): void {
  const flags = meta?.flags ?? {};
  const effective = (flags.effective as Record<string, unknown> | undefined) ?? flags;
  const nextWorkspace = effective.workspace;
  if (typeof nextWorkspace === "boolean") {
    _flags = { ..._flags, workspace: nextWorkspace };
  }
}

export function getFlags(): Flags {
  return _flags;
}
