/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DashboardKpis } from '../models/DashboardKpis';
import type { ForecastAccuracyRow } from '../models/ForecastAccuracyRow';
import type { StatusMix } from '../models/StatusMix';
import type { TopItem } from '../models/TopItem';
import type { WorkingCapitalTrend } from '../models/WorkingCapitalTrend';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DefaultService {
  /**
   * Get executive dashboard KPI metrics
   * @returns DashboardKpis Dashboard KPI metrics
   * @throws ApiError
   */
  public static getDashboardMetrics(): CancelablePromise<DashboardKpis> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/v1/metrics/dashboard',
    });
  }
  /**
   * Get working capital trend over time
   * @returns WorkingCapitalTrend Working capital trend data
   * @throws ApiError
   */
  public static getWorkingCapitalTrend(): CancelablePromise<WorkingCapitalTrend> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/v1/metrics/working-capital-trend',
    });
  }
  /**
   * Get recommendation counts grouped by status
   * @returns StatusMix Recommendation status mix
   * @throws ApiError
   */
  public static getRecommendationsByStatus(): CancelablePromise<StatusMix> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/v1/metrics/recommendations-by-status',
    });
  }
  /**
   * Get forecast accuracy by demand pattern
   * @returns ForecastAccuracyRow Forecast accuracy breakdown
   * @throws ApiError
   */
  public static getForecastAccuracy(): CancelablePromise<Array<ForecastAccuracyRow>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/v1/metrics/forecast-accuracy',
    });
  }
  /**
   * Get top items by working capital released
   * @returns TopItem Top items list
   * @throws ApiError
   */
  public static getTopItems(): CancelablePromise<Array<TopItem>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/v1/metrics/top-items',
    });
  }
}
