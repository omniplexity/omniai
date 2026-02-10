export type ModelInfo = {
  id: string;
  name: string;
  contextLength?: number;
};

export type ProviderInfo = {
  id: string;
  name: string;
  models: ModelInfo[];
};
