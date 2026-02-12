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

const RUNTIME_FLAG_MAP: Record<string, keyof Flags> = {
  workspace: "workspace",
  memoryPanel: "memoryPanel",
  knowledgePanel: "knowledgePanel",
  voice: "voice",
  tools: "tools",
  adminOps: "adminOps",
};

const META_FLAG_MAP: Record<string, keyof Flags> = {
  workspace: "workspace",
  memory: "memoryPanel",
  knowledge: "knowledgePanel",
  voice: "voice",
  tools: "tools",
  admin_ops: "adminOps",
};

export function setFlagsFromRuntime(cfg: { FEATURE_FLAGS?: Record<string, boolean> }) {
  const f = cfg.FEATURE_FLAGS ?? {};
  const next = { ...DEFAULT_FLAGS };
  for (const [sourceKey, targetKey] of Object.entries(RUNTIME_FLAG_MAP)) {
    next[targetKey] = Boolean(f[sourceKey]);
  }
  _flags = next;
}

export function setFlagsFromMeta(meta: { flags?: Record<string, unknown> } | undefined): void {
  const flags = meta?.flags ?? {};
  const effective = (flags.effective as Record<string, unknown> | undefined) ?? flags;
  const next = { ..._flags };
  for (const [sourceKey, targetKey] of Object.entries(META_FLAG_MAP)) {
    const value = effective[sourceKey];
    if (typeof value === "boolean") {
      next[targetKey] = value;
    }
  }
  _flags = next;
}

export function getFlags(): Flags {
  return _flags;
}
