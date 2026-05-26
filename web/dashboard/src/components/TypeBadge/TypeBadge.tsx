import type { RecType } from '@/types';
import styles from './TypeBadge.module.scss';

const LABELS: Record<RecType, string> = {
  ROP: 'ROP',
  SS: 'SS',
  EOQ: 'EOQ',
  SUB: 'Sub',
  WRITEOFF: 'Write-off',
};

interface Props {
  type: RecType;
}

export function TypeBadge({ type }: Props) {
  return <span className={`${styles.badge} ${styles[type]}`}>{LABELS[type] ?? type}</span>;
}
