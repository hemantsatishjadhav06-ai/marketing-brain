import clsx from "clsx";
import { ReactNode } from "react";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={clsx("rounded-2xl border border-line bg-panel", className)}>
      {children}
    </div>
  );
}

export function Button({
  children, onClick, type = "button", variant = "primary", disabled, className,
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "ghost" | "outline";
  disabled?: boolean;
  className?: string;
}) {
  const base = "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed focus-ring";
  const v = {
    primary: "bg-tennis text-black hover:opacity-90",
    ghost: "bg-transparent text-ink hover:bg-panel2",
    outline: "border border-line text-ink hover:bg-panel2",
  }[variant];
  return (
    <button type={type} disabled={disabled} onClick={onClick} className={clsx(base, v, className)}>
      {children}
    </button>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={clsx(
        "w-full rounded-xl border border-line bg-panel2 px-3 py-2 text-ink placeholder-mute outline-none focus-ring",
        props.className
      )}
    />
  );
}

export function PageHeader({
  title, description, action,
}: { title: string; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-end justify-between mb-6">
      <div>
        <h1 className="font-serif text-3xl md:text-4xl tracking-tight">{title}</h1>
        {description && <div className="text-mute text-sm mt-1">{description}</div>}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({ title, hint, cta }: { title: string; hint?: string; cta?: ReactNode }) {
  return (
    <Card className="p-10 text-center">
      <div className="font-serif text-2xl">{title}</div>
      {hint && <div className="text-mute text-sm mt-2">{hint}</div>}
      {cta && <div className="mt-5">{cta}</div>}
    </Card>
  );
}

export function StatusPill({ status }: { status: string }) {
  const tone: Record<string, string> = {
    queued: "bg-panel2 text-mute",
    running: "bg-tennis/15 text-tennis",
    done: "bg-emerald-500/15 text-emerald-300",
    completed: "bg-emerald-500/15 text-emerald-300",
    failed: "bg-red-500/15 text-red-300",
    cancelled: "bg-panel2 text-mute",
    idea: "bg-panel2 text-mute",
    drafted: "bg-sky-500/15 text-sky-300",
    under_review: "bg-amber-500/15 text-amber-300",
    approved: "bg-emerald-500/15 text-emerald-300",
    scheduled: "bg-violet-500/15 text-violet-300",
    published: "bg-tennis/15 text-tennis",
  };
  return (
    <span className={clsx("inline-flex rounded-full px-2 py-0.5 text-xs font-mono", tone[status] || "bg-panel2 text-mute")}>
      {status}
    </span>
  );
}
