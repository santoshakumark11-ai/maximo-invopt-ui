/**
 * Recommendations route — Phase 2
 *
 * Features:
 *  - Paginated Carbon DataTable with batch approve/reject
 *  - URL-driven filters (status, type, criticality, search, sort, page)
 *  - Row hover prefetch for instant detail navigation
 *  - Delegates to RejectDialog, BulkApproveDialog, BulkRejectDialog
 */
import { useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  DataTable,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  TableBatchActions,
  TableBatchAction,
  TableSelectAll,
  TableSelectRow,
  TableToolbar,
  TableToolbarContent,
  Pagination,
  InlineLoading,
  InlineNotification,
  Button,
} from '@carbon/react';
import { CheckmarkFilled, CloseFilled } from '@carbon/icons-react';
import { useRecList, usePrefetchRecDetail } from '@/api/queries';
import { StatusBadge } from '@/components/StatusBadge';
import { TypeBadge } from '@/components/TypeBadge';
import { CriticalityBadge } from '@/components/CriticalityBadge';
import { FilterBar } from '@/features/recommendations/FilterBar';
import { RejectDialog } from '@/features/recommendations/RejectDialog';
import { BulkApproveDialog, BulkRejectDialog } from '@/features/recommendations/BulkDialogs';
import type { RecListParams, RecStatus, RecType, Criticality } from '@/types';
import styles from './Recommendations.module.scss';

// ── URL param helpers ─────────────────────────────────────────────────────────

function splitCSV<T extends string>(val: string | null): T[] {
  if (!val) return [];
  return val.split(',').filter(Boolean) as T[];
}

function buildParams(sp: URLSearchParams): RecListParams {
  const params: RecListParams = {
    status: splitCSV<RecStatus>(sp.get('status')),
    type: splitCSV<RecType>(sp.get('type')),
    criticality: splitCSV<Criticality>(sp.get('criticality')),
    page: sp.get('page') ? Number(sp.get('page')) : 1,
    pageSize: 20,
  };
  const q = sp.get('q');
  const sort = sp.get('sort');
  if (q) params.q = q;
  if (sort) params.sort = sort;
  return params;
}

// ── Column definitions ────────────────────────────────────────────────────────

const HEADERS = [
  { key: 'recId', header: 'Rec ID' },
  { key: 'itemId', header: 'Item' },
  { key: 'warehouseId', header: 'Warehouse' },
  { key: 'type', header: 'Type' },
  { key: 'criticality', header: 'Criticality' },
  { key: 'currentValue', header: 'Current' },
  { key: 'recommendedValue', header: 'Recommended' },
  { key: 'deltaWorkingCapital', header: 'Δ WC' },
  { key: 'confidence', header: 'Confidence' },
  { key: 'status', header: 'Status' },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function Recommendations() {
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const prefetch = usePrefetchRecDetail();
  const params = buildParams(sp);

  const { data, isLoading, isError, error } = useRecList(params);

  // Dialogs
  const [rejectId, setRejectId] = useState<string | null>(null);
  const [bulkApproveIds, setBulkApproveIds] = useState<string[] | null>(null);
  const [bulkRejectIds, setBulkRejectIds] = useState<string[] | null>(null);

  const handlePrefetch = useCallback(
    (recId: string) => {
      void prefetch(recId);
    },
    [prefetch]
  );

  const rows = (data?.items ?? []).map((r) => ({
    id: r.recId,
    recId: r.recId,
    itemId: `${r.itemId} — ${r.itemDescription}`,
    warehouseId: r.warehouseId,
    type: r.type,
    criticality: r.criticality,
    currentValue: String(r.currentValue),
    recommendedValue: String(r.recommendedValue),
    deltaWorkingCapital: r.deltaWorkingCapital.toLocaleString('en-AU', {
      style: 'currency',
      currency: 'AUD',
      maximumFractionDigits: 0,
    }),
    confidence: `${Math.round(r.confidence * 100)}%`,
    status: r.status,
  }));

  if (isError) {
    return (
      <div className={styles.page}>
        <InlineNotification
          kind="error"
          title="Failed to load recommendations"
          subtitle={(error as Error)?.message}
        />
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <FilterBar />
      </div>

      {isLoading && (
        <InlineLoading description="Loading recommendations…" className={styles.loading ?? ''} />
      )}

      <DataTable rows={rows} headers={HEADERS} isSortable>
        {({
          rows: tableRows,
          headers,
          getTableProps,
          getHeaderProps,
          getRowProps,
          getSelectionProps,
          getBatchActionProps,
          selectedRows,
        }) => {
          const batchProps = getBatchActionProps();
          return (
            <>
              <TableToolbar>
                <TableBatchActions {...batchProps}>
                  <TableBatchAction
                    tabIndex={batchProps.shouldShowBatchActions ? 0 : -1}
                    renderIcon={CheckmarkFilled}
                    onClick={() => setBulkApproveIds(selectedRows.map((r) => r.id))}
                  >
                    Approve
                  </TableBatchAction>
                  <TableBatchAction
                    tabIndex={batchProps.shouldShowBatchActions ? 0 : -1}
                    renderIcon={CloseFilled}
                    onClick={() => setBulkRejectIds(selectedRows.map((r) => r.id))}
                  >
                    Reject
                  </TableBatchAction>
                </TableBatchActions>
                <TableToolbarContent aria-hidden={batchProps.shouldShowBatchActions} />
              </TableToolbar>

              <Table {...getTableProps()} className={styles.table ?? ''}>
                <TableHead>
                  <TableRow>
                    <TableSelectAll {...getSelectionProps()} />
                    {headers.map((h) => (
                      <TableHeader {...getHeaderProps({ header: h })}>{h.header}</TableHeader>
                    ))}
                    <TableHeader>Actions</TableHeader>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tableRows.map((row) => (
                    <TableRow
                      {...getRowProps({ row })}
                      className={styles.dataRow ?? ''}
                      onClick={(e: React.MouseEvent) => {
                        if ((e.target as HTMLElement).closest('input[type="checkbox"]')) return;
                        navigate(`/recommendations/${row.id}`);
                      }}
                      onMouseEnter={() => handlePrefetch(row.id)}
                      onFocus={() => handlePrefetch(row.id)}
                    >
                      <TableSelectRow {...getSelectionProps({ row })} />
                      {row.cells.map((cell) => (
                        <TableCell key={cell.id}>
                          {cell.info.header === 'status' ? (
                            <StatusBadge status={cell.value as RecStatus} />
                          ) : cell.info.header === 'type' ? (
                            <TypeBadge type={cell.value as RecType} />
                          ) : cell.info.header === 'criticality' ? (
                            <CriticalityBadge criticality={cell.value as Criticality} />
                          ) : (
                            cell.value
                          )}
                        </TableCell>
                      ))}
                      <TableCell onClick={(e: React.MouseEvent) => e.stopPropagation()}>
                        <Button
                          kind="ghost"
                          size="sm"
                          renderIcon={CloseFilled}
                          iconDescription="Reject"
                          hasIconOnly
                          onClick={() => setRejectId(row.id)}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          );
        }}
      </DataTable>

      {data && (
        <Pagination
          totalItems={data.totalItems}
          pageSize={20}
          page={params.page ?? 1}
          pageSizes={[20]}
          onChange={({ page: p }) => {
            const next = new URLSearchParams(sp);
            next.set('page', String(p));
            navigate(`?${next.toString()}`, { replace: true });
          }}
        />
      )}

      <RejectDialog recId={rejectId} onClose={() => setRejectId(null)} />

      <BulkApproveDialog recIds={bulkApproveIds} onClose={() => setBulkApproveIds(null)} />

      <BulkRejectDialog recIds={bulkRejectIds} onClose={() => setBulkRejectIds(null)} />
    </div>
  );
}
