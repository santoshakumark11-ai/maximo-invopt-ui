/**
 * FilterBar — MultiSelect dropdowns + search input for the recommendations list.
 * Reads from / writes to React Router URL search params.
 */
import { useSearchParams } from 'react-router-dom';
import { MultiSelect, Search } from '@carbon/react';
import type { RecStatus, RecType, Criticality } from '@/types';
import styles from './FilterBar.module.scss';

// ── option shapes expected by Carbon MultiSelect ──────────────────────────────
interface Item<T extends string> {
  id: T;
  label: string;
}

const STATUS_OPTIONS: Item<RecStatus>[] = [
  { id: 'NEW', label: 'New' },
  { id: 'PENDING', label: 'Pending' },
  { id: 'APPROVED', label: 'Approved' },
  { id: 'APPLIED', label: 'Applied' },
  { id: 'REJECTED', label: 'Rejected' },
];

const TYPE_OPTIONS: Item<RecType>[] = [
  { id: 'ROP', label: 'Reorder Point' },
  { id: 'SS', label: 'Safety Stock' },
  { id: 'EOQ', label: 'EOQ' },
  { id: 'SUB', label: 'Substitute' },
  { id: 'WRITEOFF', label: 'Write-off' },
];

const CRIT_OPTIONS: Item<Criticality>[] = [
  { id: 'HIGH', label: 'High' },
  { id: 'MED', label: 'Medium' },
  { id: 'LOW', label: 'Low' },
];

// ── helpers ───────────────────────────────────────────────────────────────────

function splitParam<T extends string>(
  params: URLSearchParams,
  key: string,
  allowed: readonly T[]
): T[] {
  const raw = params.get(key);
  if (!raw) return [];
  return raw.split(',').filter((v): v is T => (allowed as readonly string[]).includes(v));
}

function setMultiParam(sp: URLSearchParams, key: string, values: string[]): URLSearchParams {
  const next = new URLSearchParams(sp);
  if (values.length) next.set(key, values.join(','));
  else next.delete(key);
  next.delete('page'); // reset to page 1 on filter change
  return next;
}

// ── component ─────────────────────────────────────────────────────────────────

export function FilterBar() {
  const [sp, setSp] = useSearchParams();

  const selectedStatus = splitParam(
    sp,
    'status',
    STATUS_OPTIONS.map((o) => o.id)
  );
  const selectedType = splitParam(
    sp,
    'type',
    TYPE_OPTIONS.map((o) => o.id)
  );
  const selectedCrit = splitParam(
    sp,
    'criticality',
    CRIT_OPTIONS.map((o) => o.id)
  );
  const q = sp.get('q') ?? '';

  return (
    <div className={styles.bar}>
      <div className={styles.dropdownWrap}>
        <MultiSelect
          id="filter-status"
          titleText="Status"
          label="All statuses"
          items={STATUS_OPTIONS}
          itemToString={(item) => item?.label ?? ''}
          selectedItems={STATUS_OPTIONS.filter((o) => selectedStatus.includes(o.id))}
          onChange={({ selectedItems }) =>
            setSp(
              setMultiParam(
                sp,
                'status',
                (selectedItems ?? []).map((i) => i.id)
              )
            )
          }
        />
      </div>

      <div className={styles.dropdownWrap}>
        <MultiSelect
          id="filter-type"
          titleText="Type"
          label="All types"
          items={TYPE_OPTIONS}
          itemToString={(item) => item?.label ?? ''}
          selectedItems={TYPE_OPTIONS.filter((o) => selectedType.includes(o.id))}
          onChange={({ selectedItems }) =>
            setSp(
              setMultiParam(
                sp,
                'type',
                (selectedItems ?? []).map((i) => i.id)
              )
            )
          }
        />
      </div>

      <div className={styles.dropdownWrap}>
        <MultiSelect
          id="filter-criticality"
          titleText="Criticality"
          label="All criticalities"
          items={CRIT_OPTIONS}
          itemToString={(item) => item?.label ?? ''}
          selectedItems={CRIT_OPTIONS.filter((o) => selectedCrit.includes(o.id))}
          onChange={({ selectedItems }) =>
            setSp(
              setMultiParam(
                sp,
                'criticality',
                (selectedItems ?? []).map((i) => i.id)
              )
            )
          }
        />
      </div>

      <div className={styles.searchWrap}>
        <Search
          id="filter-search"
          labelText="Search"
          placeholder="Search item, description, warehouse…"
          value={q}
          onChange={(e) => {
            const next = new URLSearchParams(sp);
            if (e.target.value) next.set('q', e.target.value);
            else next.delete('q');
            next.delete('page');
            setSp(next);
          }}
          onClear={() => {
            const next = new URLSearchParams(sp);
            next.delete('q');
            next.delete('page');
            setSp(next);
          }}
        />
      </div>
    </div>
  );
}
