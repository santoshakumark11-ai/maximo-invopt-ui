/**
 * MSW v2 request handlers — realistic fixture data for Phase 1–3 endpoints.
 *
 * The recommendations store is kept mutable so approve/reject/edit mutations
 * are reflected immediately in subsequent GET calls within the same MSW session.
 */
import { http, HttpResponse } from 'msw';
import type {
  DashboardKpis,
  WorkingCapitalSeries,
  StatusMix,
  ForecastAccuracyRow,
  TopItem,
  RecDetail,
  RecListResponse,
  BulkResultSummary,
  ForecastSeries,
  ApprovePayload,
  RejectPayload,
  EditPayload,
  BulkApprovePayload,
  BulkRejectPayload,
} from '@/types';

const BASE = '/v1';

// ─────────────────────────────────────────────────────────────────────────────
// Phase 1 — metrics fixtures
// ─────────────────────────────────────────────────────────────────────────────

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
  { status: 'NEW', count: 12 },
  { status: 'PENDING', count: 9 },
  { status: 'APPROVED', count: 7 },
  { status: 'APPLIED', count: 45 },
  { status: 'REJECTED', count: 3 },
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

// ─────────────────────────────────────────────────────────────────────────────
// Phase 2 — mutable recommendations store
// ─────────────────────────────────────────────────────────────────────────────

const REC_STORE = new Map<string, RecDetail>([
  [
    'REC-0001',
    {
      recId: 'REC-0001',
      itemId: 'PUMP-001',
      itemDescription: 'Centrifugal Pump 3" 15HP',
      warehouseId: 'WH-PERTH',
      type: 'ROP',
      criticality: 'HIGH',
      currentValue: 2,
      recommendedValue: 4,
      deltaWorkingCapital: -12_400,
      confidence: 0.91,
      status: 'NEW',
      version: 1,
      createdAt: '2024-05-01T08:00:00Z',
      wcRelease: 12_400,
      stockOutRiskChangePct: -18.5,
      modelVersion: 'v2.3.1',
      expiresAt: '2024-06-01T08:00:00Z',
      rationale: {
        demandPattern: 'smooth',
        adi: 1.12,
        cvSquared: 0.08,
        twelveMonthMeanQty: 1.8,
        leadTimeDaysMean: 14,
        leadTimeDaysStd: 2.5,
        serviceLevelTarget: 0.97,
        summaryText:
          'Smooth demand with low variability. ROP increase recommended due to extended lead time variance.',
      },
      featureContributions: [
        { name: 'Lead time std dev', value: 2.5, contribution: 0.42 },
        { name: 'Service level target', value: '97%', contribution: 0.31 },
        { name: '12-month mean demand', value: 1.8, contribution: 0.18 },
        { name: 'Holding cost rate', value: '22%', contribution: 0.09 },
      ],
      vendor: {
        vendorId: 'VEN-0042',
        name: 'Weir Minerals Australia',
        meanLeadDays: 14,
        stdLeadDays: 2.5,
        onTimePct: 0.88,
        unitCost: 6_200,
        holdingCostPct: 0.22,
        orderCost: 180,
      },
      linkedAssets: [
        { assetId: 'AST-1014', description: 'Slurry Pump Station A', criticality: 'HIGH' },
        { assetId: 'AST-1031', description: 'Tailings Transfer Pump', criticality: 'HIGH' },
      ],
      audit: [
        {
          ts: '2024-05-01T08:00:00Z',
          actor: 'system',
          event: 'CREATED',
          detail: 'Generated by model run 2024-W18',
        },
      ],
    },
  ],
  [
    'REC-0002',
    {
      recId: 'REC-0002',
      itemId: 'MOTOR-022',
      itemDescription: 'Electric Motor 75kW TEFC',
      warehouseId: 'WH-PERTH',
      type: 'SS',
      criticality: 'HIGH',
      currentValue: 1,
      recommendedValue: 2,
      deltaWorkingCapital: -8_900,
      confidence: 0.87,
      status: 'PENDING',
      version: 1,
      createdAt: '2024-05-01T08:00:00Z',
      wcRelease: 8_900,
      stockOutRiskChangePct: -22.1,
      modelVersion: 'v2.3.1',
      expiresAt: '2024-06-01T08:00:00Z',
      rationale: {
        demandPattern: 'intermittent',
        adi: 1.74,
        cvSquared: 0.38,
        twelveMonthMeanQty: 0.9,
        leadTimeDaysMean: 21,
        leadTimeDaysStd: 4.2,
        serviceLevelTarget: 0.97,
        summaryText:
          'Intermittent demand. Higher safety stock advised given long and variable lead time.',
      },
      featureContributions: [
        { name: 'Lead time mean', value: 21, contribution: 0.51 },
        { name: 'Demand variability', value: 0.38, contribution: 0.29 },
        { name: 'Service level target', value: '97%', contribution: 0.2 },
      ],
      vendor: {
        vendorId: 'VEN-0017',
        name: 'ABB Motors and Drives',
        meanLeadDays: 21,
        stdLeadDays: 4.2,
        onTimePct: 0.82,
        unitCost: 8_900,
        holdingCostPct: 0.22,
        orderCost: 250,
      },
      linkedAssets: [
        { assetId: 'AST-2205', description: 'Conveyor Drive #3', criticality: 'HIGH' },
      ],
      audit: [
        {
          ts: '2024-05-01T08:00:00Z',
          actor: 'system',
          event: 'CREATED',
          detail: 'Generated by model run 2024-W18',
        },
        { ts: '2024-05-03T09:15:00Z', actor: 'j.smith@acme.com', event: 'VIEWED', detail: null },
      ],
    },
  ],
  [
    'REC-0003',
    {
      recId: 'REC-0003',
      itemId: 'VALVE-042',
      itemDescription: 'Gate Valve 4" Class 150',
      warehouseId: 'WH-KALGOOR',
      type: 'EOQ',
      criticality: 'MED',
      currentValue: 8,
      recommendedValue: 12,
      deltaWorkingCapital: 3_200,
      confidence: 0.78,
      status: 'APPROVED',
      version: 2,
      createdAt: '2024-04-15T08:00:00Z',
      wcRelease: -3_200,
      stockOutRiskChangePct: -8.3,
      modelVersion: 'v2.3.0',
      expiresAt: '2024-05-15T08:00:00Z',
      rationale: {
        demandPattern: 'smooth',
        adi: 1.05,
        cvSquared: 0.04,
        twelveMonthMeanQty: 9.2,
        leadTimeDaysMean: 7,
        leadTimeDaysStd: 1.0,
        serviceLevelTarget: 0.95,
        summaryText:
          'Smooth high-frequency demand. EOQ increase reduces ordering frequency and unit cost.',
      },
      featureContributions: [
        { name: 'Annual demand', value: '110 units', contribution: 0.55 },
        { name: 'Order cost', value: '$95', contribution: 0.25 },
        { name: 'Unit cost', value: '$680', contribution: 0.2 },
      ],
      vendor: {
        vendorId: 'VEN-0091',
        name: 'Bray International',
        meanLeadDays: 7,
        stdLeadDays: 1.0,
        onTimePct: 0.95,
        unitCost: 680,
        holdingCostPct: 0.2,
        orderCost: 95,
      },
      linkedAssets: [],
      audit: [
        {
          ts: '2024-04-15T08:00:00Z',
          actor: 'system',
          event: 'CREATED',
          detail: 'Generated by model run 2024-W16',
        },
        {
          ts: '2024-04-18T11:30:00Z',
          actor: 'p.jones@acme.com',
          event: 'APPROVED',
          detail: 'Agreed with EOQ analysis',
        },
      ],
    },
  ],
  [
    'REC-0004',
    {
      recId: 'REC-0004',
      itemId: 'BEAR-117',
      itemDescription: 'Roller Bearing 6205-2RS',
      warehouseId: 'WH-PERTH',
      type: 'ROP',
      criticality: 'MED',
      currentValue: 10,
      recommendedValue: 6,
      deltaWorkingCapital: 2_720,
      confidence: 0.83,
      status: 'NEW',
      version: 1,
      createdAt: '2024-05-01T08:00:00Z',
      wcRelease: 2_720,
      stockOutRiskChangePct: 5.1,
      modelVersion: 'v2.3.1',
      expiresAt: '2024-06-01T08:00:00Z',
      rationale: {
        demandPattern: 'smooth',
        adi: 1.02,
        cvSquared: 0.06,
        twelveMonthMeanQty: 4.8,
        leadTimeDaysMean: 5,
        leadTimeDaysStd: 0.8,
        serviceLevelTarget: 0.95,
        summaryText:
          'Demand is smooth and lead time is short. ROP can be safely reduced to release working capital.',
      },
      featureContributions: [
        { name: 'Current stock level', value: 10, contribution: 0.6 },
        { name: 'Lead time mean', value: 5, contribution: 0.25 },
        { name: 'Demand variability', value: 0.06, contribution: 0.15 },
      ],
      vendor: {
        vendorId: 'VEN-0055',
        name: 'SKF Australia',
        meanLeadDays: 5,
        stdLeadDays: 0.8,
        onTimePct: 0.97,
        unitCost: 68,
        holdingCostPct: 0.2,
        orderCost: 45,
      },
      linkedAssets: [{ assetId: 'AST-0872', description: 'Ball Mill Pinion', criticality: 'MED' }],
      audit: [
        {
          ts: '2024-05-01T08:00:00Z',
          actor: 'system',
          event: 'CREATED',
          detail: 'Generated by model run 2024-W18',
        },
      ],
    },
  ],
  [
    'REC-0005',
    {
      recId: 'REC-0005',
      itemId: 'SEAL-009',
      itemDescription: 'Mechanical Seal Type A',
      warehouseId: 'WH-PERTH',
      type: 'SS',
      criticality: 'HIGH',
      currentValue: 3,
      recommendedValue: 5,
      deltaWorkingCapital: -9_600,
      confidence: 0.94,
      status: 'NEW',
      version: 1,
      createdAt: '2024-05-01T08:00:00Z',
      wcRelease: 9_600,
      stockOutRiskChangePct: -29.4,
      modelVersion: 'v2.3.1',
      expiresAt: '2024-06-01T08:00:00Z',
      rationale: {
        demandPattern: 'intermittent',
        adi: 1.89,
        cvSquared: 0.62,
        twelveMonthMeanQty: 1.2,
        leadTimeDaysMean: 28,
        leadTimeDaysStd: 7.0,
        serviceLevelTarget: 0.99,
        summaryText:
          'High-criticality item with long, erratic lead time. Safety stock increase strongly recommended.',
      },
      featureContributions: [
        { name: 'Lead time variability', value: 7.0, contribution: 0.48 },
        { name: 'Criticality override', value: 'HIGH', contribution: 0.3 },
        { name: 'Demand CV2', value: 0.62, contribution: 0.22 },
      ],
      vendor: {
        vendorId: 'VEN-0033',
        name: 'John Crane Pty Ltd',
        meanLeadDays: 28,
        stdLeadDays: 7.0,
        onTimePct: 0.74,
        unitCost: 1_200,
        holdingCostPct: 0.22,
        orderCost: 150,
      },
      linkedAssets: [
        { assetId: 'AST-1014', description: 'Slurry Pump Station A', criticality: 'HIGH' },
      ],
      audit: [
        {
          ts: '2024-05-01T08:00:00Z',
          actor: 'system',
          event: 'CREATED',
          detail: 'Generated by model run 2024-W18',
        },
      ],
    },
  ],
  [
    'REC-0006',
    {
      recId: 'REC-0006',
      itemId: 'BELT-203',
      itemDescription: 'V-Belt B55 Industrial',
      warehouseId: 'WH-BEDFORD',
      type: 'EOQ',
      criticality: 'LOW',
      currentValue: 20,
      recommendedValue: 30,
      deltaWorkingCapital: 1_800,
      confidence: 0.72,
      status: 'REJECTED',
      version: 2,
      createdAt: '2024-04-10T08:00:00Z',
      wcRelease: -1_800,
      stockOutRiskChangePct: -3.2,
      modelVersion: 'v2.3.0',
      expiresAt: '2024-05-10T08:00:00Z',
      rationale: {
        demandPattern: 'smooth',
        adi: 1.01,
        cvSquared: 0.02,
        twelveMonthMeanQty: 22.0,
        leadTimeDaysMean: 3,
        leadTimeDaysStd: 0.5,
        serviceLevelTarget: 0.9,
        summaryText: 'Low-criticality item. EOQ increase rejected as current stock is sufficient.',
      },
      featureContributions: [
        { name: 'Annual demand', value: '264 units', contribution: 0.6 },
        { name: 'Order cost', value: '$35', contribution: 0.25 },
        { name: 'Holding cost', value: '20%', contribution: 0.15 },
      ],
      vendor: {
        vendorId: 'VEN-0112',
        name: 'Gates Australia',
        meanLeadDays: 3,
        stdLeadDays: 0.5,
        onTimePct: 0.99,
        unitCost: 18,
        holdingCostPct: 0.18,
        orderCost: 35,
      },
      linkedAssets: [],
      audit: [
        {
          ts: '2024-04-10T08:00:00Z',
          actor: 'system',
          event: 'CREATED',
          detail: 'Generated by model run 2024-W15',
        },
        {
          ts: '2024-04-12T14:00:00Z',
          actor: 'p.jones@acme.com',
          event: 'REJECTED',
          detail: 'Sufficient stock on hand until contract renegotiation',
        },
      ],
    },
  ],
  [
    'REC-0007',
    {
      recId: 'REC-0007',
      itemId: 'FILT-088',
      itemDescription: 'Oil Filter Cartridge HF35',
      warehouseId: 'WH-BEDFORD',
      type: 'ROP',
      criticality: 'LOW',
      currentValue: 12,
      recommendedValue: 8,
      deltaWorkingCapital: 1_240,
      confidence: 0.8,
      status: 'APPLIED',
      version: 3,
      createdAt: '2024-03-20T08:00:00Z',
      wcRelease: 1_240,
      stockOutRiskChangePct: 2.8,
      modelVersion: 'v2.2.5',
      expiresAt: '2024-04-20T08:00:00Z',
      rationale: {
        demandPattern: 'smooth',
        adi: 1.0,
        cvSquared: 0.01,
        twelveMonthMeanQty: 7.5,
        leadTimeDaysMean: 2,
        leadTimeDaysStd: 0.3,
        serviceLevelTarget: 0.9,
        summaryText: 'Very smooth demand, near-instant replenishment. ROP safely lowered.',
      },
      featureContributions: [
        { name: 'Demand variability', value: 0.01, contribution: 0.7 },
        { name: 'Lead time mean', value: 2, contribution: 0.2 },
        { name: 'Service level', value: '90%', contribution: 0.1 },
      ],
      vendor: {
        vendorId: 'VEN-0078',
        name: 'Donaldson Filtration',
        meanLeadDays: 2,
        stdLeadDays: 0.3,
        onTimePct: 0.99,
        unitCost: 31,
        holdingCostPct: 0.18,
        orderCost: 25,
      },
      linkedAssets: [],
      audit: [
        {
          ts: '2024-03-20T08:00:00Z',
          actor: 'system',
          event: 'CREATED',
          detail: 'Generated by model run 2024-W12',
        },
        {
          ts: '2024-03-22T10:00:00Z',
          actor: 'p.jones@acme.com',
          event: 'APPROVED',
          detail: 'Low-risk reduction',
        },
        {
          ts: '2024-03-25T06:00:00Z',
          actor: 'system',
          event: 'APPLIED',
          detail: 'Written to Maximo INVBALANCES',
        },
      ],
    },
  ],
  [
    'REC-0008',
    {
      recId: 'REC-0008',
      itemId: 'COUP-014',
      itemDescription: 'Flexible Coupling 50mm',
      warehouseId: 'WH-KALGOOR',
      type: 'SS',
      criticality: 'MED',
      currentValue: 4,
      recommendedValue: 2,
      deltaWorkingCapital: 3_600,
      confidence: 0.76,
      status: 'PENDING',
      version: 1,
      createdAt: '2024-05-02T08:00:00Z',
      wcRelease: 3_600,
      stockOutRiskChangePct: 6.5,
      modelVersion: 'v2.3.1',
      expiresAt: '2024-06-02T08:00:00Z',
      rationale: {
        demandPattern: 'intermittent',
        adi: 2.1,
        cvSquared: 0.55,
        twelveMonthMeanQty: 0.6,
        leadTimeDaysMean: 10,
        leadTimeDaysStd: 2.0,
        serviceLevelTarget: 0.95,
        summaryText: 'Very low and intermittent demand. Current safety stock is excessive.',
      },
      featureContributions: [
        { name: 'ADI', value: 2.1, contribution: 0.55 },
        { name: 'Annual demand', value: '0.6 units', contribution: 0.3 },
        { name: 'Lead time std dev', value: 2.0, contribution: 0.15 },
      ],
      vendor: {
        vendorId: 'VEN-0064',
        name: 'Rexnord Pacific',
        meanLeadDays: 10,
        stdLeadDays: 2.0,
        onTimePct: 0.91,
        unitCost: 450,
        holdingCostPct: 0.22,
        orderCost: 80,
      },
      linkedAssets: [
        { assetId: 'AST-3301', description: 'Crusher Motor Coupling', criticality: 'MED' },
      ],
      audit: [
        {
          ts: '2024-05-02T08:00:00Z',
          actor: 'system',
          event: 'CREATED',
          detail: 'Generated by model run 2024-W18',
        },
      ],
    },
  ],
]);

// ─────────────────────────────────────────────────────────────────────────────
// Phase 3 — forecast fixtures
// ─────────────────────────────────────────────────────────────────────────────

const FORECASTS = new Map<string, ForecastSeries>([
  [
    'PUMP-001|WH-PERTH',
    {
      itemId: 'PUMP-001',
      warehouseId: 'WH-PERTH',
      history: [
        { month: '2023-06', qty: 2 },
        { month: '2023-07', qty: 1 },
        { month: '2023-08', qty: 2 },
        { month: '2023-09', qty: 2 },
        { month: '2023-10', qty: 1 },
        { month: '2023-11', qty: 2 },
        { month: '2023-12', qty: 2 },
        { month: '2024-01', qty: 1 },
        { month: '2024-02', qty: 2 },
        { month: '2024-03', qty: 2 },
        { month: '2024-04', qty: 2 },
        { month: '2024-05', qty: 1 },
      ],
      forecast: [
        { month: '2024-06', mean: 1.8, p10: 1.0, p90: 3.0 },
        { month: '2024-07', mean: 1.8, p10: 1.0, p90: 3.0 },
        { month: '2024-08', mean: 1.9, p10: 1.0, p90: 3.0 },
        { month: '2024-09', mean: 1.8, p10: 1.0, p90: 3.0 },
        { month: '2024-10', mean: 1.8, p10: 1.0, p90: 3.0 },
        { month: '2024-11', mean: 1.9, p10: 1.0, p90: 3.0 },
      ],
      recommendedReorderPoint: 4,
      recommendedSafetyStock: 2,
      modelVersion: 'v2.3.1',
      asOf: '2024-05-15T00:00:00Z',
    },
  ],
  [
    'MOTOR-022|WH-PERTH',
    {
      itemId: 'MOTOR-022',
      warehouseId: 'WH-PERTH',
      history: [
        { month: '2023-06', qty: 0 },
        { month: '2023-07', qty: 1 },
        { month: '2023-08', qty: 0 },
        { month: '2023-09', qty: 1 },
        { month: '2023-10', qty: 0 },
        { month: '2023-11', qty: 0 },
        { month: '2023-12', qty: 1 },
        { month: '2024-01', qty: 0 },
        { month: '2024-02', qty: 1 },
        { month: '2024-03', qty: 0 },
        { month: '2024-04', qty: 0 },
        { month: '2024-05', qty: 1 },
      ],
      forecast: [
        { month: '2024-06', mean: 0.7, p10: 0.0, p90: 2.0 },
        { month: '2024-07', mean: 0.8, p10: 0.0, p90: 2.0 },
        { month: '2024-08', mean: 0.7, p10: 0.0, p90: 2.0 },
        { month: '2024-09', mean: 0.8, p10: 0.0, p90: 2.0 },
        { month: '2024-10', mean: 0.7, p10: 0.0, p90: 2.0 },
        { month: '2024-11', mean: 0.8, p10: 0.0, p90: 2.0 },
      ],
      recommendedReorderPoint: 2,
      recommendedSafetyStock: 1,
      modelVersion: 'v2.3.1',
      asOf: '2024-05-15T00:00:00Z',
    },
  ],
  [
    'SEAL-009|WH-PERTH',
    {
      itemId: 'SEAL-009',
      warehouseId: 'WH-PERTH',
      history: [
        { month: '2023-06', qty: 1 },
        { month: '2023-07', qty: 0 },
        { month: '2023-08', qty: 1 },
        { month: '2023-09', qty: 2 },
        { month: '2023-10', qty: 0 },
        { month: '2023-11', qty: 1 },
        { month: '2023-12', qty: 0 },
        { month: '2024-01', qty: 2 },
        { month: '2024-02', qty: 0 },
        { month: '2024-03', qty: 1 },
        { month: '2024-04', qty: 1 },
        { month: '2024-05', qty: 0 },
      ],
      forecast: [
        { month: '2024-06', mean: 1.0, p10: 0.0, p90: 3.0 },
        { month: '2024-07', mean: 1.1, p10: 0.0, p90: 3.0 },
        { month: '2024-08', mean: 1.0, p10: 0.0, p90: 3.0 },
        { month: '2024-09', mean: 1.2, p10: 0.0, p90: 3.0 },
        { month: '2024-10', mean: 1.0, p10: 0.0, p90: 3.0 },
        { month: '2024-11', mean: 1.1, p10: 0.0, p90: 3.0 },
      ],
      recommendedReorderPoint: 5,
      recommendedSafetyStock: 3,
      modelVersion: 'v2.3.1',
      asOf: '2024-05-15T00:00:00Z',
    },
  ],
  [
    'BEAR-117|WH-PERTH',
    {
      itemId: 'BEAR-117',
      warehouseId: 'WH-PERTH',
      history: [
        { month: '2023-06', qty: 5 },
        { month: '2023-07', qty: 4 },
        { month: '2023-08', qty: 6 },
        { month: '2023-09', qty: 5 },
        { month: '2023-10', qty: 4 },
        { month: '2023-11', qty: 5 },
        { month: '2023-12', qty: 5 },
        { month: '2024-01', qty: 4 },
        { month: '2024-02', qty: 5 },
        { month: '2024-03', qty: 5 },
        { month: '2024-04', qty: 6 },
        { month: '2024-05', qty: 4 },
      ],
      forecast: [
        { month: '2024-06', mean: 4.9, p10: 3.0, p90: 7.0 },
        { month: '2024-07', mean: 4.9, p10: 3.0, p90: 7.0 },
        { month: '2024-08', mean: 5.0, p10: 3.0, p90: 7.0 },
        { month: '2024-09', mean: 4.8, p10: 3.0, p90: 7.0 },
        { month: '2024-10', mean: 5.0, p10: 3.0, p90: 7.0 },
        { month: '2024-11', mean: 5.1, p10: 3.0, p90: 7.0 },
      ],
      recommendedReorderPoint: 6,
      recommendedSafetyStock: 2,
      modelVersion: 'v2.3.1',
      asOf: '2024-05-15T00:00:00Z',
    },
  ],
  [
    'VALVE-042|WH-KALGOOR',
    {
      itemId: 'VALVE-042',
      warehouseId: 'WH-KALGOOR',
      history: [
        { month: '2023-06', qty: 8 },
        { month: '2023-07', qty: 9 },
        { month: '2023-08', qty: 10 },
        { month: '2023-09', qty: 9 },
        { month: '2023-10', qty: 8 },
        { month: '2023-11', qty: 11 },
        { month: '2023-12', qty: 9 },
        { month: '2024-01', qty: 8 },
        { month: '2024-02', qty: 10 },
        { month: '2024-03', qty: 9 },
        { month: '2024-04', qty: 9 },
        { month: '2024-05', qty: 10 },
      ],
      forecast: [
        { month: '2024-06', mean: 9.2, p10: 7.0, p90: 12.0 },
        { month: '2024-07', mean: 9.2, p10: 7.0, p90: 12.0 },
        { month: '2024-08', mean: 9.3, p10: 7.0, p90: 12.0 },
        { month: '2024-09', mean: 9.1, p10: 7.0, p90: 12.0 },
        { month: '2024-10', mean: 9.2, p10: 7.0, p90: 12.0 },
        { month: '2024-11', mean: 9.4, p10: 7.0, p90: 12.0 },
      ],
      recommendedReorderPoint: 12,
      recommendedSafetyStock: 3,
      modelVersion: 'v2.3.1',
      asOf: '2024-05-15T00:00:00Z',
    },
  ],
]);

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function allRecs(): RecDetail[] {
  return Array.from(REC_STORE.values());
}

function toListItem(r: RecDetail) {
  return {
    recId: r.recId,
    itemId: r.itemId,
    itemDescription: r.itemDescription,
    warehouseId: r.warehouseId,
    type: r.type,
    criticality: r.criticality,
    currentValue: r.currentValue,
    recommendedValue: r.recommendedValue,
    deltaWorkingCapital: r.deltaWorkingCapital,
    confidence: r.confidence,
    status: r.status,
    version: r.version,
    createdAt: r.createdAt,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Handlers
// ─────────────────────────────────────────────────────────────────────────────

export const handlers = [
  // ── Phase 1 — metrics ───────────────────────────────────────────────────────

  http.get(`${BASE}/metrics/dashboard`, () => HttpResponse.json(kpis)),

  http.get(`${BASE}/metrics/working-capital-trend`, () => HttpResponse.json(workingCapitalTrend)),

  http.get(`${BASE}/metrics/recommendations-by-status`, () =>
    HttpResponse.json(recommendationsByStatus)
  ),

  http.get(`${BASE}/metrics/forecast-accuracy`, () => HttpResponse.json(forecastAccuracy)),

  http.get(`${BASE}/metrics/top-items`, () => HttpResponse.json(topItems)),

  // ── Phase 2 — recommendations list ─────────────────────────────────────────

  http.get(`${BASE}/recommendations`, ({ request }) => {
    const url = new URL(request.url);
    const statusFilter = url.searchParams.get('status')?.split(',') ?? [];
    const typeFilter = url.searchParams.get('type')?.split(',') ?? [];
    const critFilter = url.searchParams.get('criticality')?.split(',') ?? [];
    const q = url.searchParams.get('q')?.toLowerCase() ?? '';
    const page = Number(url.searchParams.get('page') ?? '1');
    const pageSize = Number(url.searchParams.get('pageSize') ?? '20');
    const sort = url.searchParams.get('sort') ?? '';

    let items = allRecs();

    if (statusFilter.length) items = items.filter((r) => statusFilter.includes(r.status));
    if (typeFilter.length) items = items.filter((r) => typeFilter.includes(r.type));
    if (critFilter.length) items = items.filter((r) => critFilter.includes(r.criticality));
    if (q) {
      items = items.filter(
        (r) =>
          r.itemId.toLowerCase().includes(q) ||
          r.itemDescription.toLowerCase().includes(q) ||
          r.warehouseId.toLowerCase().includes(q)
      );
    }

    if (sort) {
      const [field, dir] = sort.split(':');
      const asc = dir !== 'desc';
      items = [...items].sort((a, b) => {
        const av = (a as unknown as Record<string, unknown>)[field ?? ''] ?? 0;
        const bv = (b as unknown as Record<string, unknown>)[field ?? ''] ?? 0;
        const cmp = av < bv ? -1 : av > bv ? 1 : 0;
        return asc ? cmp : -cmp;
      });
    }

    const total = items.length;
    const start = (page - 1) * pageSize;
    const sliced = items.slice(start, start + pageSize);

    const response: RecListResponse = {
      items: sliced.map(toListItem),
      page,
      pageSize,
      totalItems: total,
      totalPages: Math.ceil(total / pageSize),
      asOf: new Date().toISOString(),
    };

    return HttpResponse.json(response);
  }),

  // ── Phase 2 — recommendation detail ────────────────────────────────────────

  http.get(`${BASE}/recommendations/:recId`, ({ params }) => {
    const rec = REC_STORE.get(params.recId as string);
    if (!rec) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json(rec);
  }),

  // ── Phase 2 — approve ───────────────────────────────────────────────────────

  http.post(`${BASE}/recommendations/:recId/approve`, async ({ params, request }) => {
    const rec = REC_STORE.get(params.recId as string);
    if (!rec) return new HttpResponse(null, { status: 404 });
    const body = (await request.json()) as ApprovePayload;
    const updated: RecDetail = {
      ...rec,
      status: 'APPROVED',
      version: rec.version + 1,
      audit: [
        ...rec.audit,
        {
          ts: new Date().toISOString(),
          actor: 'planner@acme.com',
          event: 'APPROVED',
          detail: body.justification ?? null,
        },
      ],
    };
    REC_STORE.set(rec.recId, updated);
    return HttpResponse.json(updated);
  }),

  // ── Phase 2 — reject ────────────────────────────────────────────────────────

  http.post(`${BASE}/recommendations/:recId/reject`, async ({ params, request }) => {
    const rec = REC_STORE.get(params.recId as string);
    if (!rec) return new HttpResponse(null, { status: 404 });
    const body = (await request.json()) as RejectPayload;
    const updated: RecDetail = {
      ...rec,
      status: 'REJECTED',
      version: rec.version + 1,
      audit: [
        ...rec.audit,
        {
          ts: new Date().toISOString(),
          actor: 'planner@acme.com',
          event: 'REJECTED',
          detail: body.reason,
        },
      ],
    };
    REC_STORE.set(rec.recId, updated);
    return HttpResponse.json(updated);
  }),

  // ── Phase 2 — edit value ────────────────────────────────────────────────────

  http.patch(`${BASE}/recommendations/:recId`, async ({ params, request }) => {
    const rec = REC_STORE.get(params.recId as string);
    if (!rec) return new HttpResponse(null, { status: 404 });
    const body = (await request.json()) as EditPayload;
    if (body.expectedVersion !== rec.version) {
      return HttpResponse.json(
        { code: 'VERSION_CONFLICT', message: 'Version conflict - please reload.' },
        { status: 409 }
      );
    }
    const updated: RecDetail = {
      ...rec,
      recommendedValue: body.recommendedValue,
      version: rec.version + 1,
      audit: [
        ...rec.audit,
        {
          ts: new Date().toISOString(),
          actor: 'planner@acme.com',
          event: 'EDITED',
          detail: body.justification,
        },
      ],
    };
    REC_STORE.set(rec.recId, updated);
    return HttpResponse.json(updated);
  }),

  // ── Phase 2 — bulk approve ──────────────────────────────────────────────────

  http.post(`${BASE}/recommendations:bulk-approve`, async ({ request }) => {
    const body = (await request.json()) as BulkApprovePayload;
    const succeeded: string[] = [];
    const failed: Array<{ recId: string; error?: string | null }> = [];
    for (const id of body.recIds) {
      const rec = REC_STORE.get(id);
      if (!rec) {
        failed.push({ recId: id, error: 'Not found' });
        continue;
      }
      REC_STORE.set(id, {
        ...rec,
        status: 'APPROVED',
        version: rec.version + 1,
        audit: [
          ...rec.audit,
          {
            ts: new Date().toISOString(),
            actor: 'planner@acme.com',
            event: 'APPROVED',
            detail: body.justification ?? null,
          },
        ],
      });
      succeeded.push(id);
    }
    const result: BulkResultSummary = { succeeded, failed };
    return HttpResponse.json(result);
  }),

  // ── Phase 2 — bulk reject ───────────────────────────────────────────────────

  http.post(`${BASE}/recommendations:bulk-reject`, async ({ request }) => {
    const body = (await request.json()) as BulkRejectPayload;
    const succeeded: string[] = [];
    const failed: Array<{ recId: string; error?: string | null }> = [];
    for (const id of body.recIds) {
      const rec = REC_STORE.get(id);
      if (!rec) {
        failed.push({ recId: id, error: 'Not found' });
        continue;
      }
      REC_STORE.set(id, {
        ...rec,
        status: 'REJECTED',
        version: rec.version + 1,
        audit: [
          ...rec.audit,
          {
            ts: new Date().toISOString(),
            actor: 'planner@acme.com',
            event: 'REJECTED',
            detail: body.reason,
          },
        ],
      });
      succeeded.push(id);
    }
    const result: BulkResultSummary = { succeeded, failed };
    return HttpResponse.json(result);
  }),

  // ── Phase 3 — forecast series ───────────────────────────────────────────────

  http.get(`${BASE}/forecasts/:itemId/:warehouseId`, ({ params }) => {
    const key = `${(params.itemId as string).toUpperCase()}|${(params.warehouseId as string).toUpperCase()}`;
    const series = FORECASTS.get(key);
    if (!series) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json(series);
  }),
];
