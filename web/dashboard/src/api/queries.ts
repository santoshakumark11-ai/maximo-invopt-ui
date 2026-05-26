/**
 * TanStack Query v5 hooks for all Phase 1-3 API endpoints.
 */
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import type {
  DashboardKpis,
  WorkingCapitalSeries,
  StatusMix,
  ForecastAccuracyRow,
  TopItem,
  RecListParams,
  RecListResponse,
  RecDetail,
  ForecastSeries,
} from '@/types';

// ─── Query key factory ───────────────────────────────────────────────────────

export const queryKeys = {
  dashboardKpis: () => ['metrics', 'dashboard'] as const,
  workingCapitalTrend: () => ['metrics', 'working-capital-trend'] as const,
  recommendationsByStatus: () => ['metrics', 'recommendations-by-status'] as const,
  forecastAccuracy: () => ['metrics', 'forecast-accuracy'] as const,
  topItems: () => ['metrics', 'top-items'] as const,
  recList: (params: RecListParams) => ['recommendations', 'list', params] as const,
  recDetail: (recId: string) => ['recommendations', 'detail', recId] as const,
  forecast: (itemId: string, warehouseId: string) => ['forecasts', itemId, warehouseId] as const,
} as const;

// ─── Phase 1 ─────────────────────────────────────────────────────────────────

export function useDashboardKpis() {
  return useQuery({
    queryKey: queryKeys.dashboardKpis(),
    queryFn: () => apiClient.get<DashboardKpis>('/metrics/dashboard'),
    staleTime: 5 * 60 * 1_000,
  });
}

export function useWorkingCapitalTrend() {
  return useQuery({
    queryKey: queryKeys.workingCapitalTrend(),
    queryFn: () => apiClient.get<WorkingCapitalSeries>('/metrics/working-capital-trend'),
    staleTime: 5 * 60 * 1_000,
  });
}

export function useRecommendationsByStatus() {
  return useQuery({
    queryKey: queryKeys.recommendationsByStatus(),
    queryFn: () => apiClient.get<StatusMix>('/metrics/recommendations-by-status'),
    staleTime: 5 * 60 * 1_000,
  });
}

export function useForecastAccuracy() {
  return useQuery({
    queryKey: queryKeys.forecastAccuracy(),
    queryFn: () => apiClient.get<ForecastAccuracyRow[]>('/metrics/forecast-accuracy'),
    staleTime: 10 * 60 * 1_000,
  });
}

export function useTopItems() {
  return useQuery({
    queryKey: queryKeys.topItems(),
    queryFn: () => apiClient.get<TopItem[]>('/metrics/top-items'),
    staleTime: 10 * 60 * 1_000,
  });
}

// ─── Phase 2 — Recommendations ───────────────────────────────────────────────

function buildRecListQs(params: RecListParams): string {
  const qs = new URLSearchParams();
  if (params.status?.length) qs.set('status', params.status.join(','));
  if (params.type?.length) qs.set('type', params.type.join(','));
  if (params.criticality?.length) qs.set('criticality', params.criticality.join(','));
  if (params.item) qs.set('item', params.item);
  if (params.q) qs.set('q', params.q);
  if (params.page != null) qs.set('page', String(params.page));
  if (params.pageSize != null) qs.set('pageSize', String(params.pageSize));
  if (params.sort) qs.set('sort', params.sort);
  const str = qs.toString();
  return str ? `?${str}` : '';
}

export function useRecList(params: RecListParams) {
  return useQuery({
    queryKey: queryKeys.recList(params),
    queryFn: () => apiClient.get<RecListResponse>(`/recommendations${buildRecListQs(params)}`),
    placeholderData: (prev) => prev,
    staleTime: 60 * 1_000,
  });
}

export function useRecDetail(recId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.recDetail(recId ?? ''),
    queryFn: () => apiClient.get<RecDetail>(`/recommendations/${recId}`),
    enabled: Boolean(recId),
    staleTime: 60 * 1_000,
  });
}

export function usePrefetchRecDetail() {
  const qc = useQueryClient();
  return (recId: string) =>
    qc.prefetchQuery({
      queryKey: queryKeys.recDetail(recId),
      queryFn: () => apiClient.get<RecDetail>(`/recommendations/${recId}`),
      staleTime: 60 * 1_000,
    });
}

// ─── Phase 3 — Forecasts ─────────────────────────────────────────────────────

export function useForecastSeries(itemId?: string, warehouseId?: string) {
  return useQuery({
    queryKey: queryKeys.forecast(itemId ?? '', warehouseId ?? ''),
    queryFn: () => apiClient.get<ForecastSeries>(`/forecasts/${itemId}/${warehouseId}`),
    enabled: Boolean(itemId && warehouseId),
    staleTime: 10 * 60 * 1_000,
  });
}
