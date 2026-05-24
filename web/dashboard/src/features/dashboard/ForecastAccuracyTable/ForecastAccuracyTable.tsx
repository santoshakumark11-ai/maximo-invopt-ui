/**
 * ForecastAccuracyTable — Carbon DataTable showing WAPE and Bias per item.
 * Rows are sorted by WAPE descending so worst performers appear at the top.
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

import { useForecastAccuracy } from '@api/queries';
import { EmptyState } from '@components/EmptyState';
import { ErrorState } from '@components/ErrorState';
import { formatWape, formatBias } from '@/lib/formatters';
import styles from './ForecastAccuracyTable.module.scss';

const HEADERS = [
  { key: 'itemId', header: 'Item ID' },
  { key: 'description', header: 'Description' },
  { key: 'wape', header: 'WAPE' },
  { key: 'bias', header: 'Bias' },
];

function wapeTagType(wape: number): 'green' | 'warm-gray' | 'red' {
  if (wape <= 10) return 'green';
  if (wape <= 15) return 'warm-gray';
  return 'red';
}

export function ForecastAccuracyTable() {
  const { data, isLoading, isError, refetch } = useForecastAccuracy();

  if (isLoading) {
    return <DataTableSkeleton headers={HEADERS} rowCount={6} />;
  }

  if (isError) {
    return <ErrorState title="Failed to load forecast accuracy" onRetry={() => void refetch()} />;
  }

  if (!data || data.length === 0) {
    return <EmptyState />;
  }

  const rows = [...data].sort((a, b) => b.wape - a.wape).map((row) => ({ ...row, id: row.itemId }));

  return (
    <div className={styles.wrapper} data-testid="forecast-accuracy-table">
      <DataTable rows={rows} headers={HEADERS} isSortable size="sm">
        {({
          rows: tableRows,
          headers,
          getHeaderProps,
          getRowProps,
          getTableProps,
          getTableContainerProps,
        }) => (
          <TableContainer title="Forecast Accuracy" {...getTableContainerProps()}>
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
                      <TableCell>
                        <Tag type={wapeTagType(original.wape)} size="sm">
                          {formatWape(original.wape)}
                        </Tag>
                      </TableCell>
                      <TableCell>{formatBias(original.bias)}</TableCell>
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
