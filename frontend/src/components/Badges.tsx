import type { Category, Priority, Status } from "../api/client";
import { CATEGORY_LABELS, PRIORITY_LABELS, STATUS_LABELS } from "../labels";

export function PriorityBadge({ value }: { value: Priority }) {
  return <span className={`badge badge--${value}`}>{PRIORITY_LABELS[value]}</span>;
}

export function StatusBadge({ value }: { value: Status }) {
  return <span className={`badge badge--status-${value}`}>{STATUS_LABELS[value]}</span>;
}

export function CategoryTag({ value }: { value: Category }) {
  return <span className="tag">{CATEGORY_LABELS[value]}</span>;
}
