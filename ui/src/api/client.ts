import type {
  ApiErrorBody,
  Call,
  CallsQuery,
  Contact,
  ContactInput,
  ContactPatch,
  DndRequest,
  Feature,
  FeatureInput,
  FeaturePreview,
  Recording,
  RecordingsQuery,
  Settings,
  SettingsPatch,
  SystemStatus,
} from './types';

export const API_BASE = '/api';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export const UNAUTHORIZED_EVENT = 'tincan:unauthorized';

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: 'same-origin',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!res.ok) {
    let code = 'http_error';
    let message = `${res.status} ${res.statusText}`;
    try {
      const parsed = (await res.json()) as Partial<ApiErrorBody>;
      if (parsed.error) {
        code = parsed.error.code ?? code;
        message = parsed.error.message ?? message;
      }
    } catch {
      // body wasn't JSON; keep the HTTP status message
    }
    if (res.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    throw new ApiError(res.status, code, message);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function qs(params: object): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params) as [string, string | number | undefined][]) {
    if (v !== undefined && v !== '') sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : '';
}

export const api = {
  auth: {
    login: (password: string) => request<unknown>('POST', '/auth/login', { password }),
  },
  contacts: {
    list: () => request<Contact[]>('GET', '/contacts'),
    create: (input: ContactInput) => request<Contact>('POST', '/contacts', input),
    update: (id: number, patch: ContactPatch) => request<Contact>('PATCH', `/contacts/${id}`, patch),
    remove: (id: number) => request<void>('DELETE', `/contacts/${id}`),
    dnd: (id: number, body: DndRequest) => request<Contact>('POST', `/contacts/${id}/dnd`, body),
  },
  features: {
    list: () => request<Feature[]>('GET', '/features'),
    put: (digit: number, input: FeatureInput) => request<Feature>('PUT', `/features/${digit}`, input),
    preview: (digit: number) => request<FeaturePreview>('POST', `/features/${digit}/preview`),
  },
  settings: {
    get: () => request<Settings>('GET', '/settings'),
    patch: (patch: SettingsPatch) => request<Settings>('PATCH', '/settings', patch),
  },
  calls: {
    list: (q: CallsQuery = {}) => request<Call[]>('GET', `/calls${qs(q)}`),
    active: () => request<Call | null>('GET', '/calls/active'),
    hangup: () => request<void>('POST', '/calls/active/hangup'),
  },
  recordings: {
    list: (q: RecordingsQuery = {}) => request<Recording[]>('GET', `/recordings${qs(q)}`),
    markListened: (id: number, listened = true) =>
      request<Recording>('PATCH', `/recordings/${id}`, { listened }),
    audioUrl: (id: number) => `${API_BASE}/recordings/${id}/audio`,
  },
  system: {
    status: () => request<SystemStatus>('GET', '/system/status'),
    testCall: (contactId: number) =>
      request<unknown>('POST', '/system/test-call', { contact_id: contactId }),
  },
};
