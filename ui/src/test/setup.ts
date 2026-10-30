import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll, vi } from 'vitest';
import { server } from '../mocks/server';
import { resetDb } from '../mocks/handlers';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  resetDb();
});
afterAll(() => server.close());

// jsdom's Blob has no arrayBuffer/text/stream, which Node's fetch and MSW need to read a multipart
// upload (without them the request hangs). Back-fill them with FileReader, which jsdom does have.
function readBlob(blob: Blob, as: 'arrayBuffer' | 'text'): Promise<ArrayBuffer | string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer | string);
    reader.onerror = () => reject(reader.error);
    if (as === 'arrayBuffer') reader.readAsArrayBuffer(blob);
    else reader.readAsText(blob);
  });
}
const blobProto = Blob.prototype as Blob & Record<string, unknown>;
if (typeof blobProto.arrayBuffer !== 'function') {
  blobProto.arrayBuffer = function (this: Blob) {
    return readBlob(this, 'arrayBuffer') as Promise<ArrayBuffer>;
  };
}
if (typeof blobProto.text !== 'function') {
  blobProto.text = function (this: Blob) {
    return readBlob(this, 'text') as Promise<string>;
  };
}
if (typeof blobProto.stream !== 'function') {
  blobProto.stream = function (this: Blob) {
    const bytes = this.arrayBuffer();
    return new ReadableStream<Uint8Array>({
      async start(controller) {
        controller.enqueue(new Uint8Array(await bytes));
        controller.close();
      },
    });
  };
}

// jsdom has no media playback.
Object.defineProperty(HTMLMediaElement.prototype, 'play', { configurable: true, value: vi.fn().mockResolvedValue(undefined) });
Object.defineProperty(HTMLMediaElement.prototype, 'pause', { configurable: true, value: vi.fn() });
Object.defineProperty(HTMLMediaElement.prototype, 'load', { configurable: true, value: vi.fn() });
