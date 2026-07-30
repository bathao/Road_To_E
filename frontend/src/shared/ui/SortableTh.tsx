// Clickable table-header cell for client-side sorting: click to sort by the
// column, click again to reverse. The active column shows ▲/▼; inactive ones
// a faint ↕ hint. Shared by the Database table and the Match Stats ELO table.
export interface Sort<K extends string> {
  key: K;
  dir: 1 | -1;
}

export default function SortableTh<K extends string>({
  label,
  k,
  sort,
  onSort,
  title,
}: {
  label: string;
  k: K;
  sort: Sort<K> | null;
  onSort: (k: K) => void;
  title?: string;
}) {
  const active = sort?.key === k;
  return (
    <th
      className={`th-sort${active ? " active" : ""}`}
      title={title}
      onClick={() => onSort(k)}
    >
      {label}
      <span className="sort-arrow">
        {active ? (sort!.dir === 1 ? "▲" : "▼") : "↕"}
      </span>
    </th>
  );
}

// Toggle helper implementing the shared click behaviour: first click sorts by
// the column's most useful direction (per `defaults`), second click reverses.
export function toggleSort<K extends string>(
  sort: Sort<K> | null,
  key: K,
  defaults: Record<K, 1 | -1>
): Sort<K> {
  return sort?.key === key
    ? { key, dir: -sort.dir as 1 | -1 }
    : { key, dir: defaults[key] };
}
