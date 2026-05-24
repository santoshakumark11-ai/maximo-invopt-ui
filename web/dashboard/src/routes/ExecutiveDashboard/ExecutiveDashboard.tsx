/**
 * ExecutiveDashboard — the main Phase 1 view.
 *
 * Layout (vertical stack within a Carbon Grid):
 *   1. KpiStrip (four KPI cards)
 *   2. WorkingCapitalTrendChart | RecommendationsByStatusDonut
 *   3. ForecastAccuracyTable    | TopItemsByReleaseTable
 */
import { Grid, Column } from '@carbon/react';
import { KpiStrip } from '@features/dashboard/KpiStrip';
import { WorkingCapitalTrendChart } from '@features/dashboard/WorkingCapitalTrendChart';
import { RecommendationsByStatusDonut } from '@features/dashboard/RecommendationsByStatusDonut';
import { ForecastAccuracyTable } from '@features/dashboard/ForecastAccuracyTable';
import { TopItemsByReleaseTable } from '@features/dashboard/TopItemsByReleaseTable';
import styles from './ExecutiveDashboard.module.scss';

export function ExecutiveDashboard() {
  return (
    <div className={styles.page} data-testid="executive-dashboard">
      <Grid fullWidth>
        {/* KPI strip — full width */}
        <Column sm={4} md={8} lg={16}>
          <KpiStrip />
        </Column>

        {/* Charts row */}
        <Column sm={4} md={5} lg={10}>
          <WorkingCapitalTrendChart />
        </Column>
        <Column sm={4} md={3} lg={6}>
          <RecommendationsByStatusDonut />
        </Column>

        {/* Tables row */}
        <Column sm={4} md={4} lg={8}>
          <ForecastAccuracyTable />
        </Column>
        <Column sm={4} md={4} lg={8}>
          <TopItemsByReleaseTable />
        </Column>
      </Grid>
    </div>
  );
}
