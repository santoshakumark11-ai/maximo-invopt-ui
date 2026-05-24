/**
 * TopItemsByReleaseTable — ranked list of items with the highest
 * estimated release / savings value.
 */
import {
  DataTable,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  TableContainer,
  DataTableSkeleton,
  Tag,
} from '@carbon/react';

import { useTopItems } from '@api/queries';
import { EmptyState } from '@components/EmptyState';
import { ErrorState } from '@components/ErrorState';
import { formatCurrencyFull } from '@/lib/formatters';
import styles from './TopItemsByReleaseTable.module.scss';

const HEADERS = [
  { key: 'itemId', header: 'Item ID' },
  { key: 'description', header: 'Description' },
  { key: 'releaseValue', header: 'Release Value' },
  { key: 'site', header: 'Site' },
  { key: 'criticality', header: 'Criticality' },
];

const CRITICALITY_TAG: Record<string, 'red' | 'warm-gray' | 'green'> = {
  high: 'red',
  med: 'warm-gray',
  low: 'green',
};

const CRITICALITY_LABEL: Record<string, string> = {
  high: 'High',
  med: 'Medium',
  low: 'Low',
};

export function TopItemsByReleaseTable() {
  const { data, isLoading, isError, refetch } = useTopItems();

  if (isLoading) {
    return <DataTableSkeleton headers={HEADERS} rowCount={5} />;
  }

  if (isError) {
    return <ErrorState title="Failed to load top items" onRetry={() => void refetch()} />;
  }

  if (!data || data.length === 0) {
    return <EmptyState />;
  }

  const rows = [...data]
    .sort((a, b) => b.releaseValue - a.releaseValue)
    .map((item) => ({ ...item, id: item.itemId }));

  return (
    <div className={styles.wrapper} data-testid="top-items-table">
      <DataTable rows={rows} headers={HEADERS} isSortable size="sm">
        {({
          rows: tableRows,
          headers,
          getHeaderProps,
          getRowProps,
          getTableProps,
          getTableContainerProps,
        }) => (
          <TableContainer title="Top Items by Release Value" {...getTableContainerProps()}>
            <Table {...getTableProps()} useZebraStyles>
              <TableHead>
                <TableRow>
                  {headers.map((header) => (
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    <TableHeader {...(getHeaderProps({ header }) as any)} key={header.key}>
                      {header.header}
                    </TableHeader>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {tableRows.map((row) => {
                  const original = data.find((d) => d.itemId === row.id)!;
                  return (
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    <TableRow {...(getRowProps({ row }) as any)} key={row.id}>
                      <TableCell>{original.itemId}</TableCell>
                      <TableCell>{original.description}</TableCell>
                      <TableCell>{formatCurrencyFull(original.releaseValue)}</TableCell>
                      <TableCell>{original.site}</TableCell>
                      <TableCell>
                        <Tag type={CRITICALITY_TAG[original.criticality]} size="sm">
                          {CRITICALITY_LABEL[original.criticality]}
                        </Tag>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DataTable>
    </div>
  );
}
