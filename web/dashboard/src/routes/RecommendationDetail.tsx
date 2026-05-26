/**
 * RecommendationDetail route — Phase 3
 *
 * Sections:
 *  - KPI stat boxes (delta WC, WC release, stockout risk delta, confidence)
 *  - Demand history + forecast ComboChart
 *  - Model rationale card
 *  - Feature contributions horizontal bar card
 *  - Vendor & lead-time card
 *  - Linked assets card
 *  - Audit trail card
 *
 * Actions (header): Edit Value, Reject, Approve — gated by current status.
 */
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button, InlineLoading, InlineNotification, Tag } from '@carbon/react';
import { ArrowLeft, CheckmarkFilled, CloseFilled, Edit } from '@carbon/icons-react';
import { ComboChart } from '@carbon/charts-react';
import type { ComboChartOptions } from '@carbon/charts';
import { ScaleTypes } from '@carbon/charts';
import { useRecDetail, useForecastSeries } from '@/api/queries';
import { useApproveRec } from '@/api/mutations';
import { StatusBadge } from '@/components/StatusBadge';
import { TypeBadge } from '@/components/TypeBadge';
import { CriticalityBadge } from '@/components/CriticalityBadge';
import { EditValueDialog } from '@/features/detail/EditValueDialog';
import { RejectDialog } from '@/features/recommendations/RejectDialog';
import type { RecDetail, ForecastSeries } from '@/types';
import styles from './RecommendationDetail.module.scss';
import '@carbon/charts/styles.css';

// ─── currency / number formatters ────────────────────────────────────────────

const fmtCcy = (v: number) =>
  v.toLocaleString('en-AU', { style: 'currency', currency: 'AUD', maximumFractionDigits: 0 });

const fmtPct = (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

// ─── Sub-components ───────────────────────────────────────────────────────────

interface StatBoxProps {
  label: string;
  value: string;
  positive?: boolean;
  negative?: boolean;
}

function StatBox({ label, value, positive, negative }: StatBoxProps) {
  const cls = positive ? styles.positive : negative ? styles.negative : undefined;
  return (
    <div>
      <div className={styles.statLabel}>{label}</div>
      <div className={`${styles.statValueLarge} ${cls ?? ''}`}>{value}</div>
    </div>
  );
}

interface CardProps {
  title: string;
  children: React.ReactNode;
  fullWidth?: boolean;
}

function Card({ title, children, fullWidth }: CardProps) {
  return (
    <div className={fullWidth ? styles.chartCard : styles.card}>
      <div className={styles.cardTitle}>{title}</div>
      {children}
    </div>
  );
}

// ─── Forecast ComboChart ──────────────────────────────────────────────────────

function ForecastChart({ series }: { series: ForecastSeries }) {
  const chartData: { group: string; key: string; value: number }[] = [
    ...series.history.map((h) => ({ group: 'History', key: h.month, value: h.qty })),
    ...series.forecast.map((f) => ({ group: 'Forecast', key: f.month, value: f.mean })),
    ...series.forecast.map((f) => ({ group: 'Upper (P90)', key: f.month, value: f.p90 })),
    ...series.forecast.map((f) => ({ group: 'Lower (P10)', key: f.month, value: f.p10 })),
  ];

  const options: ComboChartOptions = {
    title: 'Demand History & Forecast',
    height: '300px',
    comboChartTypes: [
      { type: 'simple-bar', correspondingDatasets: ['History'] },
      { type: 'line', correspondingDatasets: ['Forecast'] },
      { type: 'area', correspondingDatasets: ['Upper (P90)', 'Lower (P10)'] },
    ],
    axes: {
      left: { mapsTo: 'value', scaleType: ScaleTypes.LINEAR, title: 'Units' },
      bottom: { mapsTo: 'key', scaleType: ScaleTypes.LABELS, title: 'Month' },
    },
    legend: { enabled: true },
    toolbar: { enabled: false },
  };

  return <ComboChart data={chartData} options={options} />;
}

// ─── Feature contributions ────────────────────────────────────────────────────

function FeatureContributionsCard({ rec }: { rec: RecDetail }) {
  const max = Math.max(...rec.featureContributions.map((f) => f.contribution), 0.01);
  return (
    <Card title="Feature Contributions">
      {rec.featureContributions.map((f) => (
        <div key={f.name} className={styles.contribRow}>
          <span className={styles.contribLabel}>{f.name}</span>
          <span className={styles.contribValue}>{(f.contribution * 100).toFixed(0)}%</span>
          <div className={styles.contribBarTrack}>
            <div
              className={styles.contribBarFill}
              style={{ width: `${(f.contribution / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </Card>
  );
}

// ─── Rationale card ───────────────────────────────────────────────────────────

function RationaleCard({ rec }: { rec: RecDetail }) {
  const r = rec.rationale;
  return (
    <Card title="Model Rationale">
      <p style={{ marginBottom: '0.75rem', fontSize: '0.875rem' }}>{r.summaryText}</p>
      <div className={styles.statGrid}>
        <div>
          <div className={styles.statLabel}>Demand Pattern</div>
          <div className={styles.statValue}>{r.demandPattern}</div>
        </div>
        <div>
          <div className={styles.statLabel}>ADI</div>
          <div className={styles.statValue}>{r.adi.toFixed(2)}</div>
        </div>
        <div>
          <div className={styles.statLabel}>CV²</div>
          <div className={styles.statValue}>{r.cvSquared.toFixed(2)}</div>
        </div>
        <div>
          <div className={styles.statLabel}>12-mo Mean Qty</div>
          <div className={styles.statValue}>{r.twelveMonthMeanQty.toFixed(1)}</div>
        </div>
        <div>
          <div className={styles.statLabel}>Lead Time (days)</div>
          <div className={styles.statValue}>
            {r.leadTimeDaysMean} ± {r.leadTimeDaysStd}
          </div>
        </div>
        <div>
          <div className={styles.statLabel}>Service Level Target</div>
          <div className={styles.statValue}>{(r.serviceLevelTarget * 100).toFixed(0)}%</div>
        </div>
      </div>
    </Card>
  );
}

// ─── Vendor card ──────────────────────────────────────────────────────────────

function VendorCard({ rec }: { rec: RecDetail }) {
  const v = rec.vendor;
  return (
    <Card title="Vendor & Lead Time">
      <div className={styles.statGrid}>
        <div>
          <div className={styles.statLabel}>Vendor</div>
          <div className={styles.statValue}>{v.name}</div>
        </div>
        <div>
          <div className={styles.statLabel}>Vendor ID</div>
          <div className={styles.statValue}>{v.vendorId}</div>
        </div>
        <div>
          <div className={styles.statLabel}>Mean Lead Time</div>
          <div className={styles.statValue}>{v.meanLeadDays} days</div>
        </div>
        <div>
          <div className={styles.statLabel}>Std Dev Lead Time</div>
          <div className={styles.statValue}>{v.stdLeadDays} days</div>
        </div>
        <div>
          <div className={styles.statLabel}>On-Time Delivery</div>
          <div className={styles.statValue}>{(v.onTimePct * 100).toFixed(0)}%</div>
        </div>
        <div>
          <div className={styles.statLabel}>Unit Cost</div>
          <div className={styles.statValue}>{fmtCcy(v.unitCost)}</div>
        </div>
        <div>
          <div className={styles.statLabel}>Holding Cost Rate</div>
          <div className={styles.statValue}>{(v.holdingCostPct * 100).toFixed(0)}%</div>
        </div>
        <div>
          <div className={styles.statLabel}>Order Cost</div>
          <div className={styles.statValue}>{fmtCcy(v.orderCost)}</div>
        </div>
      </div>
    </Card>
  );
}

// ─── Linked assets card ───────────────────────────────────────────────────────

function LinkedAssetsCard({ rec }: { rec: RecDetail }) {
  if (!rec.linkedAssets.length) {
    return (
      <Card title="Linked Assets">
        <p style={{ fontSize: '0.875rem', color: 'var(--cds-text-helper)' }}>No linked assets.</p>
      </Card>
    );
  }
  return (
    <Card title="Linked Assets">
      {rec.linkedAssets.map((a) => (
        <div
          key={a.assetId}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '0.375rem 0',
            borderBottom: '1px solid var(--cds-border-subtle, #e0e0e0)',
            fontSize: '0.875rem',
          }}
        >
          <span>
            <strong>{a.assetId}</strong> — {a.description}
          </span>
          <CriticalityBadge criticality={a.criticality} />
        </div>
      ))}
    </Card>
  );
}

// ─── Audit trail card ─────────────────────────────────────────────────────────

function AuditTrailCard({ rec }: { rec: RecDetail }) {
  return (
    <Card title="Audit Trail" fullWidth>
      {rec.audit.map((e, i) => (
        <div key={i} className={styles.auditEntry}>
          <span className={styles.auditTs}>{new Date(e.ts).toLocaleString('en-AU')}</span>
          <span className={styles.auditActor}>{e.actor}</span>
          <span className={styles.auditEvent}>{e.event}</span>
          {e.detail && <span className={styles.auditDetail}>{e.detail}</span>}
        </div>
      ))}
    </Card>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function RecommendationDetail() {
  const { recId } = useParams<{ recId: string }>();
  const navigate = useNavigate();

  const { data: rec, isLoading, isError, error } = useRecDetail(recId);
  const { data: forecast } = useForecastSeries(rec?.itemId, rec?.warehouseId);

  const { mutate: approve, isPending: isApproving } = useApproveRec();

  const [showEdit, setShowEdit] = useState(false);
  const [rejectId, setRejectId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className={styles.page}>
        <InlineLoading description="Loading recommendation…" />
      </div>
    );
  }

  if (isError || !rec) {
    return (
      <div className={styles.page}>
        <InlineNotification
          kind="error"
          title="Failed to load recommendation"
          subtitle={(error as Error)?.message ?? 'Not found'}
        />
      </div>
    );
  }

  const canApprove = rec.status === 'NEW' || rec.status === 'PENDING';
  const canReject = rec.status === 'NEW' || rec.status === 'PENDING' || rec.status === 'APPROVED';
  const canEdit = rec.status === 'NEW' || rec.status === 'PENDING';

  const deltaPositive = rec.deltaWorkingCapital < 0; // negative delta = WC release = good
  const deltaNegative = rec.deltaWorkingCapital > 0;

  return (
    <div className={styles.page}>
      {/* Breadcrumb */}
      <button className={styles.breadcrumb} onClick={() => navigate('/recommendations')}>
        <ArrowLeft size={14} />
        Recommendations
      </button>

      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerMeta}>
          <div className={styles.eyebrow}>Recommendation Detail</div>
          <div className={styles.pageTitle}>
            {rec.itemId} — {rec.itemDescription}
          </div>
          <div className={styles.badgeRow}>
            <StatusBadge status={rec.status} />
            <TypeBadge type={rec.type} />
            <CriticalityBadge criticality={rec.criticality} />
            <Tag type="outline" size="sm">
              {rec.warehouseId}
            </Tag>
            <Tag type="outline" size="sm">
              v{rec.version}
            </Tag>
            <span style={{ fontSize: '0.75rem', color: 'var(--cds-text-helper)' }}>
              Expires {new Date(rec.expiresAt).toLocaleDateString('en-AU')}
            </span>
          </div>
        </div>

        <div className={styles.headerActions}>
          {canEdit && (
            <Button kind="tertiary" size="sm" renderIcon={Edit} onClick={() => setShowEdit(true)}>
              Edit Value
            </Button>
          )}
          {canReject && (
            <Button
              kind="danger--tertiary"
              size="sm"
              renderIcon={CloseFilled}
              onClick={() => setRejectId(rec.recId)}
            >
              Reject
            </Button>
          )}
          {canApprove && (
            <Button
              kind="primary"
              size="sm"
              renderIcon={CheckmarkFilled}
              disabled={isApproving}
              onClick={() =>
                approve(
                  { recId: rec.recId, payload: {} },
                  { onSuccess: () => navigate('/recommendations') }
                )
              }
            >
              {isApproving ? 'Approving…' : 'Approve'}
            </Button>
          )}
        </div>
      </div>

      {/* KPI stat boxes */}
      <div className={styles.grid}>
        <div className={styles.card}>
          <div className={styles.cardTitle}>Key Metrics</div>
          <div className={styles.statGrid}>
            <StatBox
              label="Working Capital Δ"
              value={fmtCcy(rec.deltaWorkingCapital)}
              positive={deltaPositive}
              negative={deltaNegative}
            />
            <StatBox
              label="WC Release"
              value={fmtCcy(rec.wcRelease)}
              positive={rec.wcRelease > 0}
            />
            <StatBox
              label="Stockout Risk Δ"
              value={fmtPct(rec.stockOutRiskChangePct)}
              positive={rec.stockOutRiskChangePct < 0}
              negative={rec.stockOutRiskChangePct > 0}
            />
            <StatBox label="Model Confidence" value={`${Math.round(rec.confidence * 100)}%`} />
          </div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardTitle}>Recommendation</div>
          <div className={styles.statGrid}>
            <StatBox label="Current Value" value={String(rec.currentValue)} />
            <StatBox label="Recommended Value" value={String(rec.recommendedValue)} />
            <div>
              <div className={styles.statLabel}>Model</div>
              <div className={styles.statValue}>{rec.modelVersion}</div>
            </div>
            <div>
              <div className={styles.statLabel}>Created</div>
              <div className={styles.statValue}>
                {new Date(rec.createdAt).toLocaleDateString('en-AU')}
              </div>
            </div>
          </div>
        </div>

        {/* Forecast chart — spans full width */}
        {forecast ? (
          <ForecastChart series={forecast} />
        ) : (
          <div className={styles.chartCard}>
            <div className={styles.cardTitle}>Demand History &amp; Forecast</div>
            <p style={{ fontSize: '0.875rem', color: 'var(--cds-text-helper)' }}>
              Forecast data not available.
            </p>
          </div>
        )}

        <RationaleCard rec={rec} />
        <FeatureContributionsCard rec={rec} />
        <VendorCard rec={rec} />
        <LinkedAssetsCard rec={rec} />
        <AuditTrailCard rec={rec} />
      </div>

      {/* Dialogs */}
      <EditValueDialog
        key={rec?.recId ?? 'none'}
        rec={showEdit ? rec : null}
        onClose={() => setShowEdit(false)}
      />

      <RejectDialog recId={rejectId} onClose={() => setRejectId(null)} />
    </div>
  );
}
