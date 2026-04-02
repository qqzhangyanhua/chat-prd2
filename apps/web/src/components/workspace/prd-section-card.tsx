interface PrdSectionCardProps {
  description: string;
  status: "confirmed" | "inferred" | "missing";
  title: string;
}


const statusMap = {
  confirmed: {
    badge: "已确认",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
  },
  inferred: {
    badge: "AI 推测",
    className: "border-amber-200 bg-amber-50 text-amber-700",
  },
  missing: {
    badge: "未定义",
    className: "border-stone-200 bg-stone-100 text-stone-500",
  },
};


export function PrdSectionCard({
  description,
  status,
  title,
}: PrdSectionCardProps) {
  const statusConfig = statusMap[status];

  return (
    <article className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-stone-900">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-stone-600">{description}</p>
        </div>
        <span
          className={`rounded-full border px-3 py-1 text-[11px] font-medium ${statusConfig.className}`}
        >
          {statusConfig.badge}
        </span>
      </div>
    </article>
  );
}
