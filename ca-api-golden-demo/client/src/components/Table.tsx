import React from "react";
import {
  useReactTable,
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
} from "@tanstack/react-table";

interface TableProps {
  data: any[];
  shouldSort: boolean;
  variant?: "default" | "branded";
}

export const parseCsv = (csvString: string): any[] => {
  // Trim whitespace/newlines and split into lines
  const rows = csvString.trim().split("\n");
  if (rows.length < 2) return [];

  // Assume first row is header row and replace any empty header with "label"
  const headers = rows[0].split(",").map((header) => {
    const trimmed = header.trim();
    return trimmed === "" ? "label" : trimmed;
  });

  // Map each subsequent row to an object using headers
  return rows.slice(1).map((row) => {
    const values = row.split(",").map((val) => val.trim());
    return headers.reduce((acc, header, i) => {
      acc[header] = values[i];
      return acc;
    }, {} as any);
  });
};

const Table: React.FC<TableProps> = ({
  data,
  shouldSort,
  variant = "default",
}) => {
  let tableClass = "data-table";
  let outerTableClass = "rounded-outer-table";
  if (variant === "branded") {
    tableClass = "data-table branded";
    outerTableClass = "rounded-outer-table branded";
  }

  const slicedData = React.useMemo(() => data.slice(0, 200), [data]); // Only render first 200 rows

  const columns = React.useMemo<ColumnDef<any>[]>(() => {
    if (slicedData.length === 0) return [];

    return Object.keys(slicedData[0]).map((key) => {
      /* IDs */
      // If the column name contains "_id", treat as string without formatting
      if (key.toLowerCase().includes("_id")) {
        return {
          header: key,
          accessorFn: (row: any) => row[key],
          cell: (info: any) => info.getValue(),
        };
      }

      // Compute numeric values for the column across all rows
      const numericValues = slicedData
        .map((row) => parseFloat(row[key]))
        .filter((v) => !isNaN(v));
      // Determine if all numbers in this column are small (<1 in absolute value)
      const isSmall =
        numericValues.length > 0 &&
        numericValues.every((val) => Math.abs(val) < 1);
      // Determine if some numbers in this column contain decimals
      const containsFloat =
        numericValues.length > 0 &&
        numericValues.some((val) => !Number.isInteger(val));

      return {
        header: key,
        accessorFn: (row: any) => row[key],
        cell: (info: any) => {
          const value = info.getValue();

          /* Dates */
          // Check if value looks like a date string
          const isDatePattern =
            typeof value === "string" &&
            /^\d{4}-\d{1,2}(-\d{1,2})?$/.test(value);
          if (isDatePattern) {
            return value;
          }

          /* Numbers */
          // Try parsing the value as a number
          const num = typeof value === "number" ? value : parseFloat(value);
          if (!isNaN(num)) {
            if (/sale/i.test(key)) {
              // Always format sale as currency
              return `$${num.toLocaleString("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}`;
            } else if (/year/i.test(key)) {
              // Do not format years
              return value;
            } else if (/percentage/i.test(key)) {
              // Always format percentage with two decimals
              return `${num.toFixed(2)}%`;
            } else if (containsFloat) {
              // For numbers with decimals, retain exactly 2 decimal places
              return num.toLocaleString("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              });
            } else if (isSmall) {
              // For small numbers, preserve decimals (up to 4 places)
              return num.toLocaleString("en-US", {
                maximumFractionDigits: 4,
              });
            } else {
              // Format as integer with commas by default
              return Math.round(num).toLocaleString();
            }
          }

          // Default case just return value
          return value;
        },
      };
    });
  }, [slicedData]);

  // Conditionally apply initial sorting based on shouldSort flag, otherwise sort ascending by the first column
  const initialSortingState: SortingState =
    shouldSort && columns.length > 0
      ? [{ id: Object.keys(slicedData[0])[0] as string, desc: false }]
      : [];

  const [sorting, setSorting] =
    React.useState<SortingState>(initialSortingState);

  const table = useReactTable({
    data: slicedData,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className={outerTableClass}>
      <div className="scrollable-inner-table">
        <table className={tableClass}>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id}>
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext()
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Table;
