type RiskBadgeProps = {
  risk: string;
};

export function RiskBadge({ risk }: RiskBadgeProps) {
  const normalized = risk.toLowerCase().replace(/\s+/g, "-") || "unknown";

  return <span className={`risk-badge risk-badge--${normalized}`}>{risk || "UNKNOWN"}</span>;
}
