import { describe, it, expect, beforeEach } from 'vitest';
import {
  __resetRuntimeConfigForTest,
  setRuntimeConfig,
  getRuntimeConfig,
  loadRuntimeConfig,
  normalizeBaseUrl
} from '../runtimeConfig';

describe('Runtime Config', () => {
  beforeEach(() => {
    __resetRuntimeConfigForTest();
  });

  describe('normalizeBaseUrl', () => {
    it('should remove trailing slash', () => {
      expect(normalizeBaseUrl('https://example.com/')).toBe('https://example.com');
    });

    it('should keep URL without trailing slash', () => {
      expect(normalizeBaseUrl('https://example.com')).toBe('https://example.com');
    });

    it('should trim whitespace', () => {
      expect(normalizeBaseUrl('  https://example.com  ')).toBe('https://example.com');
    });

    it('should throw on empty string', () => {
      expect(() => normalizeBaseUrl('')).toThrow('BACKEND_BASE_URL is empty');
    });

    it('should throw on null/undefined', () => {
      expect(() => normalizeBaseUrl(null as any)).toThrow('BACKEND_BASE_URL is empty');
      expect(() => normalizeBaseUrl(undefined as any)).toThrow('BACKEND_BASE_URL is empty');
    });
  });

  describe('setRuntimeConfig', () => {
    it('should set config with normalized URL', () => {
      setRuntimeConfig({ BACKEND_BASE_URL: 'https://example.com/' });
      const cfg = getRuntimeConfig();
      expect(cfg.BACKEND_BASE_URL).toBe('https://example.com');
    });

    it('should preserve feature flags', () => {
      setRuntimeConfig({ 
        BACKEND_BASE_URL: 'https://example.com',
        FEATURE_FLAGS: { memoryPanel: true }
      });
      const cfg = getRuntimeConfig();
      expect(cfg.FEATURE_FLAGS?.memoryPanel).toBe(true);
    });
  });

  describe('getRuntimeConfig', () => {
    it('should throw if config not set', () => {
      expect(() => getRuntimeConfig()).toThrow('Runtime config not set');
    });

    it('should return config after setting', () => {
      setRuntimeConfig({ BACKEND_BASE_URL: 'https://test.com' });
      const cfg = getRuntimeConfig();
      expect(cfg.BACKEND_BASE_URL).toBe('https://test.com');
    });
  });

  describe('loadRuntimeConfig', () => {
    it('should fetch runtime-config.json', async () => {
      // Mock fetch
      const mockJson = { BACKEND_BASE_URL: 'https://api.example.com' };
      (globalThis as any).fetch = async (url: string) => {
        if (url.includes('runtime-config.json')) {
          return new Response(JSON.stringify(mockJson), { status: 200 });
        }
        return new Response('Not Found', { status: 404 });
      };

      const cfg = await loadRuntimeConfig();
      expect(cfg.BACKEND_BASE_URL).toBe('https://api.example.com');
    });

    it('should throw if file not found', async () => {
      (globalThis as any).fetch = async () => new Response('Not Found', { status: 404 });

      await expect(loadRuntimeConfig()).rejects.toThrow('Missing runtime-config.json');
    });

    it('should throw if BACKEND_BASE_URL missing', async () => {
      (globalThis as any).fetch = async () => new Response('{}', { status: 200 });

      await expect(loadRuntimeConfig()).rejects.toThrow('runtime-config.json missing BACKEND_BASE_URL');
    });

    it('should use cache: no-store for fetch', async () => {
      let fetchOptions: any;
      (globalThis as any).fetch = async (_url: string, options: any) => {
        fetchOptions = options;
        return new Response('{"BACKEND_BASE_URL":"https://api.example.test"}', { status: 200 });
      };

      await loadRuntimeConfig();
      expect(fetchOptions.cache).toBe('no-store');
    });
  });
});
