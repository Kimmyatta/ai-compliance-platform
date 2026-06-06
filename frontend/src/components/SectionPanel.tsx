import type { ReactNode } from "react";

type SectionPanelProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
};

export function SectionPanel({ title, description, actions, children }: SectionPanelProps) {
  return (
    <section className="section-panel">
      <div className="section-panel__header">
        <div>
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
        {actions ? <div className="section-panel__actions">{actions}</div> : null}
      </div>
      <div className="section-panel__body">{children}</div>
    </section>
  );
}
