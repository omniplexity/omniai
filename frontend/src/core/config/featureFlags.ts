type Flags = {
  memoryPanel: boolean;
  knowledgePanel: boolean;
  voice: boolean;
  tools: boolean;
  adminOps: boolean;
};

const DEFAULT_FLAGS: Flags = {
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
    memoryPanel: Boolean(f.memoryPanel),
    knowledgePanel: Boolean(f.knowledgePanel),
    voice: Boolean(f.voice),
    tools: Boolean(f.tools),
    adminOps: Boolean(f.adminOps)
  };
}

export function getFlags(): Flags {
  return _flags;
}
