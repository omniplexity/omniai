export type Unsubscribe = () => void;

export type Store<T> = {
  get: () => T;
  set: (next: T) => void;
  patch: (partial: Partial<T>) => void;
  subscribe: (fn: () => void) => Unsubscribe;
};

export function createStore<T extends object>(initial: T): Store<T> {
  let value = initial;
  const subs = new Set<() => void>();

  function emit() {
    for (const fn of subs) fn();
  }

  return {
    get: () => value,
    set: (next: T) => {
      value = next;
      emit();
    },
    patch: (partial: Partial<T>) => {
      value = { ...value, ...partial };
      emit();
    },
    subscribe: (fn: () => void) => {
      subs.add(fn);
      return () => subs.delete(fn);
    }
  };
}
