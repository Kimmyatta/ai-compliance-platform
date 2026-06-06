import type { JobStatus } from "../types/audit";

type StatusBadgeProps = {
  status: JobStatus | string;
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = status.toLowerCase();

  return <span className={`status-badge status-badge--${normalized}`}>{status}</span>;
}
