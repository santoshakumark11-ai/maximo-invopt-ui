/**
 * Cross-cutting TypeScript interfaces for Phase 1.
 * All shapes mirror the OpenAPI spec in src/test/openapi-fixture.json.
 */

// ─── KPI / Dashboard ────────────────────────────────────────────────────────

export interface DashboardKpis {
  /** Total value of on-hand inventory (USD) */
  inventoryValue: number;
  /** Working capital tied up in inventory (USD) */
  workingCapital: number;
  /** Percentage of demand met from stock (0-100) */
  serviceLevel: number;
  /** Number of open optimisation recommendations */
  openRecommendations: number;
}

// ─── Working-Capital Trend ───────────────────────────────────────────────────

export interface WorkingCapitalPoint {
  /** ISO-8601 date string, e.g. "2024-01" */
  period: string;
  /** Working capital value in USD */
  value: number;
}

export type WorkingCapitalSeries = WorkingCapitalPoint[];

// ─── Recommendations by Status ───────────────────────────────────────────────

export type RecommendationStatus = 'new' | 'pending' | 'approved' | 'applied' | 'rejected';

export interface StatusMixItem {
  status: RecommendationStatus;
  count: number;
}

export type StatusMix = StatusMixItem[];

// ─── Forecast Accuracy ───────────────────────────────────────────────────────

export interface ForecastAccuracyRow {
  /** Item / SKU identifier */
  itemId: string;
  /** Human-readable description */
  description: string;
  /** Weighted Absolute Percentage Error (0-100) */
  wape: number;
  /** Bias percentage — positive = over-forecast, negative = under-forecast */
  bias: number;
}

// ─── Top Items ───────────────────────────────────────────────────────────────

export interface TopItem {
  itemId: string;
  description: string;
  /** Estimated release / savings value in USD */
  releaseValue: number;
  /** Asset / storeroom site code */
  site: string;
  criticality: 'high' | 'med' | 'low';
}

// ─── Recommendations (full entity used in detail views) ──────────────────────

export interface Recommendation {
  id: string;
  itemId: string;
  description: string;
  status: RecommendationStatus;
  /** Recommended stock level */
  recommendedQty: number;
  /** Current on-hand quantity */
  currentQty: number;
  releaseValue: number;
  site: string;
  criticality: 'high' | 'med' | 'low';
  createdAt: string;
  updatedAt: string;
}

// ─── API helpers ─────────────────────────────────────────────────────────────

/** Generic paginated envelope used by list endpoints */
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

/** Standard error body returned by the API */
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}
