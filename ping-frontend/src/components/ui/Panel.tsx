import { useId } from "react";

export function Panel({
  title,
  aside,
  children,
  className = "",
  style,
}: {
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  const id = useId();
  return (
    <section aria-labelledby={id} className={`panel ${className}`} style={style}>
      <div className="panel-header">
        <h2 id={id}>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
