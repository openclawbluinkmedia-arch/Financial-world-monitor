interface Column {
  key: string;
  label: string;
  render?: (row: any) => React.ReactNode;
  className?: string;
  onClick?: (row: any) => void;
}

interface DataTableProps {
  columns: Column[];
  data: any[];
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: any) => void;
  rowKey?: string;
}

function LoadingRows() {
  return (
    <>
      {[1, 2, 3, 4, 5].map((i) => (
        <tr key={i}>
          {[1, 2, 3, 4, 5].map((j) => (
            <td key={j} className="px-3 py-3">
              <div className="h-4 bg-surface-hover rounded animate-pulse w-3/4" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <tr>
      <td colSpan={99} className="px-3 py-12 text-center">
        <p className="text-sm text-fg-dim">{message}</p>
      </td>
    </tr>
  );
}

export default function DataTable({
  columns,
  data,
  loading = false,
  emptyMessage = "No data found",
  onRowClick,
  rowKey = "id",
}: DataTableProps) {
  return (
    <div className="overflow-x-auto">
      <table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} className={col.className}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <LoadingRows />
          ) : data.length === 0 ? (
            <EmptyState message={emptyMessage} />
          ) : (
            data.map((row) => (
              <tr
                key={row[rowKey] || row.id}
                className={onRowClick ? "cursor-pointer" : ""}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((col) => (
                  <td key={col.key} className={col.className}>
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
