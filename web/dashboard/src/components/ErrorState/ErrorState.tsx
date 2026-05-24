import { Warning } from '@carbon/icons-react';
import { Button } from '@carbon/react';
import styles from './ErrorState.module.scss';

interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
}

export function ErrorState({
  title = 'Failed to load data',
  description = 'An error occurred while fetching data from the server.',
  onRetry,
}: ErrorStateProps) {
  return (
    <div className={styles.wrapper} data-testid="error-state">
      <Warning size={48} className={styles.icon} />
      <p className={styles.title}>{title}</p>
      <p className={styles.description}>{description}</p>
      {onRetry && (
        <Button kind="ghost" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
