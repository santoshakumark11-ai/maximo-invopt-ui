/**
 * MSW v2 request handlers — realistic fixture data for Phase 1 endpoints.
 */
import { http, HttpResponse } from 'msw';
import type {
  DashboardKpis,
  WorkingCapitalSeries,
  StatusMix,
  ForecastAccuracyRow,
  TopItem,
} from '@/types';

const BASE = '/v1';

// ─── Fixture data ─────────────────────────────────────────────────────────────

const kpis: DashboardKpis = {
  inventoryValue: 4_820_000,
  workingCapital: 1_250_000,
  serviceLevel: 97.4,
  openRecommendations: 38,
};

const workingCapitalTrend: WorkingCapitalSeries = [
  { period: '2023-06', value: 1_680_000 },
  { period: '2023-07', value: 1_640_000 },
  { period: '2023-08', value: 1_590_000 },
  { period: '2023-09', value: 1_520_000 },
  { period: '2023-10', value: 1_490_000 },
  { period: '2023-11', value: 1_430_000 },
  { period: '2023-12', value: 1_380_000 },
  { period: '2024-01', value: 1_360_000 },
  { period: '2024-02', value: 1_330_000 },
  { period: '2024-03', value: 1_290_000 },
  { period: '2024-04', value: 1_270_000 },
  { period: '2024-05', value: 1_250_000 },
];

const recommendationsByStatus: StatusMix = [
  { status: 'new', count: 12 },
  { status: 'pending', count: 9 },
  { status: 'approved', count: 7 },
  { status: 'applied', count: 45 },
  { status: 'rejected', count: 3 },
];

const forecastAccuracy: ForecastAccuracyRow[] = [
  { itemId: 'PUMP-001', description: 'Centrifugal Pump 3" 15HP', wape: 8.2, bias: 2.1 },
  { itemId: 'VALVE-042', description: 'Gate Valve 4" Class 150', wape: 12.5, bias: -3.4 },
  { itemId: 'BEAR-117', description: 'Roller Bearing 6205-2RS', wape: 6.8, bias: 1.0 },
  { itemId: 'SEAL-009', description: 'Mechanical Seal Type A', wape: 15.3, bias: -6.2 },
  { itemId: 'BELT-203', description: 'V-Belt B55 Industrial', wape: 9.1, bias: 0.5 },
  { itemId: 'FILT-088', description: 'Oil Filter Cartridge HF35', wape: 11.0, bias: 3.8 },
  { itemId: 'COUP-014', description: 'Flexible Coupling 50mm', wape: 7.4, bias: -1.2 },
  { itemId: 'GAGE-055', description: 'Pressure Gauge 0-100 PSI', wape: 18.6, bias: 5.9 },
];

const topItems: TopItem[] = [
  {
    itemId: 'PUMP-001',
    description: 'Centrifugal Pump 3" 15HP',
    releaseValue: 148_000,
    site: 'BEDFORD',
    criticality: 'high',
  },
  {
    itemId: 'MOTOR-022',
    description: 'Electric Motor 75kW TEFC',
    releaseValue: 112_000,
    site: 'PERTH',
    criticality: 'high',
  },
  {
    itemId: 'XFMR-007',
    description: 'Distribution Transformer 500kVA',
    releaseValue: 96_500,
    site: 'BEDFORD',
    criticality: 'med',
  },
  {
    itemId: 'VALVE-042',
    description: 'Gate Valve 4" Class 150',
    releaseValue: 74_200,
    site: 'KALGOOR',
    criticality: 'med',
  },
  {
    itemId: 'CRANE-003',
    description: 'Overhead Crane Hook Block 5T',
    releaseValue: 61_800,
    site: 'PERTH',
    criticality: 'low',
  },
];

// ─── Handlers ────────────────────────────────────────────────────────────────

export const handlers = [
  http.get(`${BASE}/metrics/dashboard`, () => HttpResponse.json(kpis)),

  http.get(`${BASE}/metrics/working-capital-trend`, () => HttpResponse.json(workingCapitalTrend)),

  http.get(`${BASE}/metrics/recommendations-by-status`, () =>
    HttpResponse.json(recommendationsByStatus)
  ),

  http.get(`${BASE}/metrics/forecast-accuracy`, () => HttpResponse.json(forecastAccuracy)),

  http.get(`${BASE}/metrics/top-items`, () => HttpResponse.json(topItems)),
];
