import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  CallsQuery,
  ContactInput,
  ContactPatch,
  DndRequest,
  FeatureInput,
  RecordingsQuery,
  SettingsPatch,
} from './types';

export const keys = {
  contacts: ['contacts'] as const,
  features: ['features'] as const,
  settings: ['settings'] as const,
  calls: (q: CallsQuery = {}) => ['calls', q] as const,
  activeCall: ['calls', 'active'] as const,
  recordings: (q: RecordingsQuery = {}) => ['recordings', q] as const,
  ringtones: ['ringtones'] as const,
  status: ['status'] as const,
};

export function useContacts() {
  return useQuery({ queryKey: keys.contacts, queryFn: api.contacts.list });
}

export function useContactMutations() {
  const qc = useQueryClient();
  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: keys.contacts });
    void qc.invalidateQueries({ queryKey: keys.features });
  };
  const create = useMutation({
    mutationFn: (input: ContactInput) => api.contacts.create(input),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: ContactPatch }) => api.contacts.update(id, patch),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.contacts.remove(id),
    onSuccess: invalidate,
  });
  const dnd = useMutation({
    mutationFn: ({ id, body }: { id: number; body: DndRequest }) => api.contacts.dnd(id, body),
    onSuccess: invalidate,
  });
  return { create, update, remove, dnd };
}

export function useFeatures() {
  return useQuery({ queryKey: keys.features, queryFn: api.features.list });
}

export function useFeatureMutations() {
  const qc = useQueryClient();
  const put = useMutation({
    mutationFn: ({ digit, input }: { digit: number; input: FeatureInput }) =>
      api.features.put(digit, input),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.features }),
  });
  const preview = useMutation({ mutationFn: (digit: number) => api.features.preview(digit) });
  return { put, preview };
}

export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: api.settings.get });
}

export function useSettingsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: SettingsPatch) => api.settings.patch(patch),
    onSuccess: (data) => qc.setQueryData(keys.settings, data),
  });
}

export function useCalls(q: CallsQuery = {}) {
  return useQuery({ queryKey: keys.calls(q), queryFn: () => api.calls.list(q) });
}

export function useActiveCall() {
  return useQuery({ queryKey: keys.activeCall, queryFn: api.calls.active });
}

export function useHangup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.calls.hangup,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.activeCall });
      void qc.invalidateQueries({ queryKey: ['calls'] });
    },
  });
}

export function useRecordings(q: RecordingsQuery = {}) {
  return useQuery({ queryKey: keys.recordings(q), queryFn: () => api.recordings.list(q) });
}

export function useMarkListened() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, listened = true }: { id: number; listened?: boolean }) =>
      api.recordings.markListened(id, listened),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['recordings'] }),
  });
}

export function useRingtones() {
  return useQuery({ queryKey: keys.ringtones, queryFn: api.ringtones.list });
}

export function useRingtoneMutations() {
  const qc = useQueryClient();
  const upload = useMutation({
    mutationFn: (file: File) => api.ringtones.upload(file),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.ringtones }),
  });
  const remove = useMutation({
    mutationFn: (name: string) => api.ringtones.remove(name),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.ringtones });
      // Deleting the active ringtone resets settings.ringtone on the backend.
      void qc.invalidateQueries({ queryKey: keys.settings });
    },
  });
  return { upload, remove };
}

export function useStatus() {
  return useQuery({ queryKey: keys.status, queryFn: api.system.status, refetchInterval: 30_000 });
}

export function useTestCall() {
  return useMutation({ mutationFn: (contactId: number) => api.system.testCall(contactId) });
}
