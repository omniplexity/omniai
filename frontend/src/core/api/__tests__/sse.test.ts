import { describe, it, expect } from 'vitest';
import { parseSseResponse } from '../sse';

describe('SSE Parser', () => {
  describe('parseSseResponse', () => {
    it('should parse single message event', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('id: 1\nevent: message\ndata: {"content":"hello"}\n\n'));
          controller.close();
        }
      });

      const res = new Response(body, { status: 200 });
      const signal = new AbortController().signal;

      const frames: any[] = [];
      for await (const frame of parseSseResponse(res, signal)) {
        frames.push(frame);
      }

      expect(frames).toHaveLength(1);
      expect(frames[0]).toEqual({ event: 'message', data: '{"content":"hello"}' });
    });

    it('should parse multiple events', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('id: 1\nevent: message\ndata: first\n\n'));
          controller.enqueue(new TextEncoder().encode('id: 2\nevent: message\ndata: second\n\n'));
          controller.close();
        }
      });

      const res = new Response(body, { status: 200 });
      const signal = new AbortController().signal;

      const frames: any[] = [];
      for await (const frame of parseSseResponse(res, signal)) {
        frames.push(frame);
      }

      expect(frames).toHaveLength(2);
      expect(frames[0].data).toBe('first');
      expect(frames[1].data).toBe('second');
    });

    it('should parse multi-line data events', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('id: 1\nevent: message\ndata: line1\ndata: line2\ndata: line3\n\n'));
          controller.close();
        }
      });

      const res = new Response(body, { status: 200 });
      const signal = new AbortController().signal;

      const frames: any[] = [];
      for await (const frame of parseSseResponse(res, signal)) {
        frames.push(frame);
      }

      expect(frames).toHaveLength(1);
      expect(frames[0].data).toBe('line1\nline2\nline3');
    });

    it('should parse different event types', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('id: 1\nevent: message\ndata: msg1\n\n'));
          controller.enqueue(new TextEncoder().encode('id: 2\nevent: done\ndata: complete\n\n'));
          controller.enqueue(new TextEncoder().encode('id: 3\nevent: error\ndata: error_msg\n\n'));
          controller.close();
        }
      });

      const res = new Response(body, { status: 200 });
      const signal = new AbortController().signal;

      const frames: any[] = [];
      for await (const frame of parseSseResponse(res, signal)) {
        frames.push(frame);
      }

      expect(frames).toHaveLength(3);
      expect(frames[0].event).toBe('message');
      expect(frames[1].event).toBe('done');
      expect(frames[2].event).toBe('error');
    });

    it('should ignore comment lines starting with :', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(': this is a comment\nid: 1\nevent: message\ndata: test\n\n'));
          controller.close();
        }
      });

      const res = new Response(body, { status: 200 });
      const signal = new AbortController().signal;

      const frames: any[] = [];
      for await (const frame of parseSseResponse(res, signal)) {
        frames.push(frame);
      }

      expect(frames).toHaveLength(1);
      expect(frames[0].data).toBe('test');
    });

    it('should ignore ping comments', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(': ping\n\n'));
          controller.enqueue(new TextEncoder().encode('id: 1\nevent: message\ndata: test\n\n'));
          controller.close();
        }
      });

      const res = new Response(body, { status: 200 });
      const signal = new AbortController().signal;

      const frames: any[] = [];
      for await (const frame of parseSseResponse(res, signal)) {
        frames.push(frame);
      }

      expect(frames).toHaveLength(1);
    });

    it('should throw on HTTP error', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.close();
        }
      });

      const res = new Response(body, { status: 500, statusText: 'Server Error' });
      const signal = new AbortController().signal;

      await expect(parseSseResponse(res, signal)).rejects.toThrow('SSE HTTP 500');
    });

    it('should throw on abort', async () => {
      const body = new ReadableStream({
        start(controller) {
          // Never close - would hang without abort
          setTimeout(() => controller.close(), 5000);
        }
      });

      const res = new Response(body, { status: 200 });
      const abortController = new AbortController();
      
      setTimeout(() => abortController.abort(), 100);

      await expect(parseSseResponse(res, abortController.signal)).rejects.toThrow('AbortError');
    });

    it('should handle chunked input correctly', async () => {
      // Simulate chunked reading where data spans multiple chunks
      const body = new ReadableStream({
        start(controller) {
          // First chunk: partial event
          controller.enqueue(new TextEncoder().encode('id: 1\nevent: mess'));
          // Second chunk: rest of event
          controller.enqueue(new TextEncoder().encode('age\ndata: chunked\n\n'));
          controller.close();
        }
      });

      const res = new Response(body, { status: 200 });
      const signal = new AbortController().signal;

      const frames: any[] = [];
      for await (const frame of parseSseResponse(res, signal)) {
        frames.push(frame);
      }

      expect(frames).toHaveLength(1);
      expect(frames[0].data).toBe('chunked');
    });

    it('should default to message event type', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('id: 1\ndata: no event type\n\n'));
          controller.close();
        }
      });

      const res = new Response(body, { status: 200 });
      const signal = new AbortController().signal;

      const frames: any[] = [];
      for await (const frame of parseSseResponse(res, signal)) {
        frames.push(frame);
      }

      expect(frames).toHaveLength(1);
      expect(frames[0].event).toBe('message');
    });

    it('should strip trailing newline from data', async () => {
      const body = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('id: 1\nevent: message\ndata: test\n\n'));
          controller.close();
        }
      });

      const res = new Response(body, { status: 200 });
      const signal = new AbortController().signal;

      const frames: any[] = [];
      for await (const frame of parseSseResponse(res, signal)) {
        frames.push(frame);
      }

      expect(frames[0].data).toBe('test');
    });
  });
});
