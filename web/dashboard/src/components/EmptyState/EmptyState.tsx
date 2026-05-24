import { DataViewAlt } from '@carbon/icons-react';
import styles from './EmptyState.module.scss';

interface EmptyStateProps {
  title?: string;
  description?: string;
}

export function EmptyState({
  title = 'No data available',
  description = 'There is nothing to display for the selected period.',
}: EmptyStateProps) {
  return (
    <div className={styles.wrapper} data-testid="empty-state">
      <DataViewAlt size={48} className={styles.icon} />
      <p className={styles.title}>{title}</p>
      <p className={styles.description}>{description}</p>
    </div>
  );
}
