import { CheckCircle, Sparkles, CircleDashed } from "lucide-react";
import type { PrdSectionStatus } from "../../lib/types";

interface PrdSectionCardProps {
  description: string;
  status: PrdSectionStatus;
  title: string;
}


const statusMap = {
  confirmed: {
    badge: "已确认",
    badgeClass: "border-emerald-200 bg-emerald-50 text-emerald-700",
    borderClass: "border-l-emerald-400",
    Icon: CheckCircle,
    iconClass: "text-emerald-500",
  },
  inferred: {
    badge: "AI 推测",
    badgeClass: "border-amber-200 bg-amber-50 text-amber-700",
    borderClass: "border-l-amber-400",
    Icon: Sparkles,
    iconClass: "text-amber-500",
  },
  missing: {
    badge: "未定义",
    badgeClass: "border-stone-200 bg-stone-100 text-stone-400",
    borderClass: "border-l-stone-200",
    Icon: CircleDashed,
    iconClass: "text-stone-400",
  },
};


export function PrdSectionCard({
  description,
  status,
  title,
}: PrdSectionCardProps) {
  const { badge, badgeClass, borderClass, Icon, iconClass } = statusMap[status];

  return (
    <article className={`rounded-xl border border-stone-200 border-l-2 ${borderClass} bg-white p-4 shadow-sm`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5 min-w-0">
          <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${iconClass}`} />
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-stone-900">{title}</h3>
            <p className="mt-1.5 text-xs leading-5 text-stone-500 empty:hidden">{description}</p>
          </div>
        </div>
        <span
          className={`shrink-0 rounded-full border px-2.5 py-0.5 text-[10px] font-medium ${badgeClass}`}
        >
          {badge}
        </span>
      </div>
    </article>
  );
}
