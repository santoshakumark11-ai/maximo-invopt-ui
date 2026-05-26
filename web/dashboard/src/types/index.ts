/**
 * Cross-cutting TypeScript interfaces for Phases 1-3.
 * All shapes mirror the backend Pydantic models (camelCase aliases).
 */

// ─── Phase 1 — KPI / Dashboard ───────────────────────────────────────────────

export interface DashboardKpis {
  inventoryValue: number;
  workingCapital: number;
  serviceLevel: number;
  openRecommendations: number;
}

export interface WorkingCapitalPoint {
  period: string;
  value: number;
}

export type WorkingCapitalSeries = WorkingCapitalPoint[];

export interface StatusMixItem {
  status: string;
  count: number;
}

export type StatusMix = StatusMixItem[];

export interface ForecastAccuracyRow {
  itemId: string;
  description: string;
  wape: number;
  bias: number;
}

export interface TopItem {
  itemId: string;
  description: string;
  releaseValue: number;
  site: string;
  criticality: 'high' | 'med' | 'low';
}

// ─── Phase 2 — Recommendations enums ────────────────────────────────────────

export type RecStatus = 'NEW' | 'PENDING' | 'APPROVED' | 'APPLIED' | 'REJECTED';
export type RecType = 'ROP' | 'SS' | 'EOQ' | 'SUB' | 'WRITEOFF';
export type Criticality = 'HIGH' | 'MED' | 'LOW';
export type AuditEventType =
  | 'CREATED'
  | 'NOTIFIED'
  | 'VIEWED'
  | 'EDITED'
  | 'APPROVED'
  | 'REJECTED'
  | 'APPLIED'
  | 'FAILED';

// ─── Phase 2 — List ──────────────────────────────────────────────────────────

export interface RecListItem {
  recId: string;
  itemId: string;
  itemDescription: string;
  warehouseId: string;
  type: RecType;
  criticality: Criticality;
  currentValue: number | string;
  recommendedValue: number | string;
  deltaWorkingCapital: number;
  confidence: number;
  status: RecStatus;
  version: number;
  createdAt: string;
}

export interface RecListResponse {
  items: RecListItem[];
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
  asOf: string;
}

export interface RecListParams {
  status?: RecStatus[];
  type?: RecType[];
  criticality?: Criticality[];
  item?: string;
  q?: string;
  page?: number;
  pageSize?: number;
  sort?: string;
}

// ─── Phase 2 — Detail ────────────────────────────────────────────────────────

export interface FeatureContribution {
  name: string;
  value: number | string;
  contribution: number;
}

export interface Rationale {
  demandPattern: 'smooth' | 'intermittent' | 'erratic' | 'lumpy';
  adi: number;
  cvSquared: number;
  twelveMonthMeanQty: number;
  leadTimeDaysMean: number;
  leadTimeDaysStd: number;
  serviceLevelTarget: number;
  summaryText: string;
}

export interface VendorInfo {
  vendorId: string;
  name: string;
  meanLeadDays: number;
  stdLeadDays: number;
  onTimePct: number;
  unitCost: number;
  holdingCostPct: number;
  orderCost: number;
}

export interface LinkedAsset {
  assetId: string;
  description: string;
  criticality: Criticality;
}

export interface AuditEvent {
  ts: string;
  actor: string;
  event: AuditEventType;
  detail: string | null;
}

export interface RecDetail extends RecListItem {
  rationale: Rationale;
  featureContributions: FeatureContribution[];
  vendor: VendorInfo;
  linkedAssets: LinkedAsset[];
  audit: AuditEvent[];
  wcRelease: number;
  stockOutRiskChangePct: number;
  modelVersion: string;
  expiresAt: string;
}

// ─── Phase 2 — Payloads ──────────────────────────────────────────────────────

export interface ApprovePayload {
  justification?: string;
}

export interface RejectPayload {
  reason: string;
}

export interface EditPayload {
  recommendedValue: number;
  justification: string;
  expectedVersion: number;
}

export interface BulkApprovePayload {
  recIds: string[];
  justification?: string;
}

export interface BulkRejectPayload {
  recIds: string[];
  reason: string;
}

export interface BulkResultItem {
  recId: string;
  error?: string | null;
}

export interface BulkResultSummary {
  succeeded: string[];
  failed: BulkResultItem[];
}

// ─── Phase 3 — Forecast series ───────────────────────────────────────────────

export interface HistoryPoint {
  month: string;
  qty: number;
}

export interface ForecastPoint {
  month: string;
  mean: number;
  p10: number;
  p90: number;
}

export interface ForecastSeries {
  itemId: string;
  warehouseId: string;
  history: HistoryPoint[];
  forecast: ForecastPoint[];
  recommendedReorderPoint: number;
  recommendedSafetyStock: number;
  modelVersion: string;
  asOf: string;
}

// ─── API helpers ─────────────────────────────────────────────────────────────

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}
