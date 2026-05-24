/**
 * RecommendationsByStatusDonut — donut chart showing recommendation counts
 * grouped by status (New, Pending, Approved, Applied, Rejected).
 */
import { DonutChart } from '@carbon/charts-react';
import type { DonutChartOptions } from '@carbon/charts';

import { useRecommendationsByStatus } from '@api/queries';
import { EmptyState } from '@components/EmptyState';
import { ErrorState } from '@components/ErrorState';
import { SkeletonPlaceholder } from '@carbon/react';
import styles from './RecommendationsByStatusDonut.module.scss';

// Status → display colour mapping (matches tokens.scss)
const STATUS_COLOURS: Record<string, string> = {
  new: '#1E2761',
  pending: '#D97706',
  approved: '#00A896',
  applied: '#1F9D55',
  rejected: '#C0392B',
};

const STATUS_LABELS: Record<string, string> = {
  new: 'New',
  pending: 'Pending',
  approved: 'Approved',
  applied: 'Applied',
  rejected: 'Rejected',
};

export function RecommendationsByStatusDonut() {
  const { data, isLoading, isError, refetch } = useRecommendationsByStatus();

  if (isLoading) {
    return <SkeletonPlaceholder className={styles.skeleton} />;
  }

  if (isError) {
    return <ErrorState title="Failed to load recommendations" onRetry={() => void refetch()} />;
  }

  if (!data || data.length === 0) {
    return <EmptyState />;
  }

  const total = data.reduce((sum, item) => sum + item.count, 0);

  const chartData = data.map((item) => ({
    group: STATUS_LABELS[item.status] ?? item.status,
    value: item.count,
  }));

  const colourScale = Object.fromEntries(
    data.map((item) => [
      STATUS_LABELS[item.status] ?? item.status,
      STATUS_COLOURS[item.status] ?? '#888',
    ])
  );

  const options: DonutChartOptions = {
    title: 'Recommendations by Status',
    donut: {
      center: {
        label: 'Total',
        number: total,
      },
    },
    height: '300px',
    color: { scale: colourScale },
  };

  return (
    <div className={styles.wrapper} data-testid="recs-by-status-chart">
      <DonutChart data={chartData} options={options} />
    </div>
  );
}
