import type { RecStatus } from '@/types';
import styles from './StatusBadge.module.scss';

const LABELS: Record<RecStatus, string> = {
  NEW: 'New',
  PENDING: 'Pending',
  APPROVED: 'Approved',
  APPLIED: 'Applied',
  REJECTED: 'Rejected',
};

interface Props {
  status: RecStatus;
}

export function StatusBadge({ status }: Props) {
  return <span className={`${styles.badge} ${styles[status]}`}>{LABELS[status] ?? status}</span>;
}
