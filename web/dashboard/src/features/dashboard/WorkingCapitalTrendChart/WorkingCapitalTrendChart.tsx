/**
 * WorkingCapitalTrendChart — 12-month line chart rendered with @carbon/charts-react.
 */
import { LineChart } from '@carbon/charts-react';
import type { LineChartOptions } from '@carbon/charts';
import '@carbon/charts-react/styles.css';

import { useWorkingCapitalTrend } from '@api/queries';
import { EmptyState } from '@components/EmptyState';
import { ErrorState } from '@components/ErrorState';
import { formatCurrency, formatPeriodLabel } from '@/lib/formatters';
import { SkeletonPlaceholder } from '@carbon/react';
import styles from './WorkingCapitalTrendChart.module.scss';

export function WorkingCapitalTrendChart() {
  const { data, isLoading, isError, refetch } = useWorkingCapitalTrend();

  if (isLoading) {
    return <SkeletonPlaceholder className={styles.skeleton} />;
  }

  if (isError) {
    return <ErrorState title="Failed to load trend data" onRetry={() => void refetch()} />;
  }

  if (!data || data.length === 0) {
    return <EmptyState />;
  }

  // Transform to Carbon Charts dataset format
  const chartData = data.map((point) => ({
    group: 'Working Capital',
    key: formatPeriodLabel(point.period),
    value: point.value,
  }));

  const options: LineChartOptions = {
    title: 'Working Capital Trend',
    axes: {
      bottom: { title: '', mapsTo: 'key', scaleType: 'labels' },
      left: {
        title: 'Working Capital (USD)',
        mapsTo: 'value',
        formatter: (v: number) => formatCurrency(v),
      },
    },
    height: '300px',
    legend: { enabled: false },
    tooltip: {
      valueFormatter: (v: number) => formatCurrency(v),
    },
  };

  return (
    <div className={styles.wrapper} data-testid="working-capital-chart">
      <LineChart data={chartData} options={options} />
    </div>
  );
}
