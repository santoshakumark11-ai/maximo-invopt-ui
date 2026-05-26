/**
 * TanStack Query v5 mutation hooks for Phase 2 recommendation actions.
 *
 * All mutations invalidate the affected detail + list keys on success so the
 * UI stays consistent without manual cache surgery.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import { queryKeys } from './queries';
import type {
  ApprovePayload,
  RejectPayload,
  EditPayload,
  BulkApprovePayload,
  BulkRejectPayload,
  BulkResultSummary,
  RecDetail,
} from '@/types';

// ─── helpers ─────────────────────────────────────────────────────────────────

function useInvalidateRec() {
  const qc = useQueryClient();
  return (recId?: string) => {
    if (recId) qc.invalidateQueries({ queryKey: queryKeys.recDetail(recId) });
    qc.invalidateQueries({ queryKey: ['recommendations', 'list'] });
    qc.invalidateQueries({ queryKey: ['metrics', 'dashboard'] });
    qc.invalidateQueries({ queryKey: ['metrics', 'recommendations-by-status'] });
  };
}

// ─── Approve ─────────────────────────────────────────────────────────────────

export function useApproveRec() {
  const invalidate = useInvalidateRec();
  return useMutation({
    mutationFn: ({ recId, payload }: { recId: string; payload: ApprovePayload }) =>
      apiClient.post<RecDetail>(`/recommendations/${recId}/approve`, payload),
    onSuccess: (_data, { recId }) => invalidate(recId),
  });
}

// ─── Reject ──────────────────────────────────────────────────────────────────

export function useRejectRec() {
  const invalidate = useInvalidateRec();
  return useMutation({
    mutationFn: ({ recId, payload }: { recId: string; payload: RejectPayload }) =>
      apiClient.post<RecDetail>(`/recommendations/${recId}/reject`, payload),
    onSuccess: (_data, { recId }) => invalidate(recId),
  });
}

// ─── Edit recommended value ───────────────────────────────────────────────────

export function useEditRec() {
  const invalidate = useInvalidateRec();
  return useMutation({
    mutationFn: ({ recId, payload }: { recId: string; payload: EditPayload }) =>
      apiClient.patch<RecDetail>(`/recommendations/${recId}`, payload),
    onSuccess: (_data, { recId }) => invalidate(recId),
  });
}

// ─── Bulk approve ─────────────────────────────────────────────────────────────

export function useBulkApprove() {
  const invalidate = useInvalidateRec();
  return useMutation({
    mutationFn: (payload: BulkApprovePayload) =>
      apiClient.post<BulkResultSummary>('/recommendations:bulk-approve', payload),
    onSuccess: (_data, payload) => {
      payload.recIds.forEach((id) => invalidate(id));
    },
  });
}

// ─── Bulk reject ──────────────────────────────────────────────────────────────

export function useBulkReject() {
  const invalidate = useInvalidateRec();
  return useMutation({
    mutationFn: (payload: BulkRejectPayload) =>
      apiClient.post<BulkResultSummary>('/recommendations:bulk-reject', payload),
    onSuccess: (_data, payload) => {
      payload.recIds.forEach((id) => invalidate(id));
    },
  });
}
