/**
 * TanStack Query v5 hooks for all Phase 1 API endpoints.
 *
 * Each hook returns the standard useQuery result shape.
 * Query keys are exported so tests and invalidation calls can reference them.
 */
import { useQuery } from '@tanstack/react-query';
import { apiClient } from './client';
import type {
  DashboardKpis,
  WorkingCapitalSeries,
  StatusMix,
  ForecastAccuracyRow,
  TopItem,
} from '@/types';

// ─── Query key factory ───────────────────────────────────────────────────────

export const queryKeys = {
  dashboardKpis: () => ['metrics', 'dashboard'] as const,
  workingCapitalTrend: () => ['metrics', 'working-capital-trend'] as const,
  recommendationsByStatus: () => ['metrics', 'recommendations-by-status'] as const,
  forecastAccuracy: () => ['metrics', 'forecast-accuracy'] as const,
  topItems: () => ['metrics', 'top-items'] as const,
} as const;

// ─── Hooks ───────────────────────────────────────────────────────────────────

/** Dashboard KPI summary — inventory value, working capital, service level, open recs */
export function useDashboardKpis() {
  return useQuery({
    queryKey: queryKeys.dashboardKpis(),
    queryFn: () => apiClient.get<DashboardKpis>('/metrics/dashboard'),
    staleTime: 5 * 60 * 1_000, // 5 min
  });
}

/** 12-month working-capital trend series */
export function useWorkingCapitalTrend() {
  return useQuery({
    queryKey: queryKeys.workingCapitalTrend(),
    queryFn: () => apiClient.get<WorkingCapitalSeries>('/metrics/working-capital-trend'),
    staleTime: 5 * 60 * 1_000,
  });
}

/** Recommendation counts grouped by status (donut chart) */
export function useRecommendationsByStatus() {
  return useQuery({
    queryKey: queryKeys.recommendationsByStatus(),
    queryFn: () => apiClient.get<StatusMix>('/metrics/recommendations-by-status'),
    staleTime: 5 * 60 * 1_000,
  });
}

/** Per-item forecast accuracy rows (WAPE + bias) */
export function useForecastAccuracy() {
  return useQuery({
    queryKey: queryKeys.forecastAccuracy(),
    queryFn: () => apiClient.get<ForecastAccuracyRow[]>('/metrics/forecast-accuracy'),
    staleTime: 10 * 60 * 1_000,
  });
}

/** Top items ranked by release / savings value */
export function useTopItems() {
  return useQuery({
    queryKey: queryKeys.topItems(),
    queryFn: () => apiClient.get<TopItem[]>('/metrics/top-items'),
    staleTime: 10 * 60 * 1_000,
  });
}
