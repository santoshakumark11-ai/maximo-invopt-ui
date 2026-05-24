/**
 * KpiStrip — renders the four Phase 1 KPI cards in a horizontal row.
 * Fetches data via useDashboardKpis and delegates formatting + layout
 * to KpiCard.
 */
import { KpiCard } from '@components/KpiCard';
import { useDashboardKpis } from '@api/queries';
import { formatCurrency, formatPercent, formatInteger } from '@/lib/formatters';
import styles from './KpiStrip.module.scss';

export function KpiStrip() {
  const { data, isLoading, isError } = useDashboardKpis();

  const errorMsg = isError ? 'Unable to load' : undefined;

  return (
    <div className={styles.strip} data-testid="kpi-strip">
      <KpiCard
        label="Inventory Value"
        value={data ? formatCurrency(data.inventoryValue) : undefined}
        description="Total on-hand inventory"
        accent="navy"
        loading={isLoading}
        error={errorMsg}
      />
      <KpiCard
        label="Working Capital"
        value={data ? formatCurrency(data.workingCapital) : undefined}
        description="Capital tied up in stock"
        accent="gold"
        loading={isLoading}
        error={errorMsg}
      />
      <KpiCard
        label="Service Level"
        value={data ? formatPercent(data.serviceLevel) : undefined}
        description="Demand met from stock"
        accent="teal"
        loading={isLoading}
        error={errorMsg}
      />
      <KpiCard
        label="Open Recommendations"
        value={data ? formatInteger(data.openRecommendations) : undefined}
        description="Pending optimisation actions"
        accent={data && data.openRecommendations > 20 ? 'red' : 'teal'}
        loading={isLoading}
        error={errorMsg}
      />
    </div>
  );
}
