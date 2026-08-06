import type { ReactNode } from "react";

type ActivityLevel = "quiet" | "low" | "medium" | "high";

export function relativeTimeShort(value: string | null | undefined) {
	if (!value) return null;
	const ts = Date.parse(value);
	if (Number.isNaN(ts)) return null;
	const delta = Date.now() - ts;
	const minutes = Math.floor(delta / 60_000);
	if (minutes < 1) return "just now";
	if (minutes < 60) return `${minutes}m ago`;
	const hours = Math.floor(minutes / 60);
	if (hours < 24) return `${hours}h ago`;
	const days = Math.floor(hours / 24);
	return `${days}d ago`;
}

function resolveLevel(newCount24h: number, active24h: boolean, level?: string): ActivityLevel {
	const normalized = (level || "").toLowerCase();
	if (normalized === "high" || normalized === "medium" || normalized === "low" || normalized === "quiet") {
		return normalized;
	}
	if (!active24h) return "quiet";
	if (newCount24h >= 10) return "high";
	if (newCount24h >= 4) return "medium";
	if (newCount24h >= 1) return "low";
	return "quiet";
}

function levelBadgeClass(level: ActivityLevel): string {
	if (level === "high") {
		return "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-900";
	}
	if (level === "medium") {
		return "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900";
	}
	if (level === "low") {
		return "bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:ring-sky-900";
	}
	return "bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-900 dark:text-slate-300 dark:ring-slate-700";
}

export function ActivitySparkCard({
	total,
	newCount24h,
	lastSignalAt,
	active24h,
	level,
	runStatus,
}: {
	total: number;
	newCount24h: number;
	lastSignalAt: string | null | undefined;
	active24h: boolean;
	level?: string;
	runStatus?: ReactNode;
}) {
	const resolvedLevel = resolveLevel(newCount24h, active24h, level);
	const lastSeen = relativeTimeShort(lastSignalAt);
	const levelCls = levelBadgeClass(resolvedLevel);

	return (
		<div className="min-w-[210px] rounded-xl border border-slate-200/80 bg-white/70 px-2.5 py-1.5 dark:border-slate-800 dark:bg-slate-900/30">
			<div className="flex items-center gap-2">
				<span className="relative flex h-2.5 w-2.5">
					{active24h ? (
						<>
							<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
							<span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
						</>
					) : (
						<span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-slate-300 dark:bg-slate-600" />
					)}
				</span>
				<span className="text-sm font-semibold tabular-nums text-slate-900 dark:text-slate-100">{total}</span>
				<span className="text-[11px] text-slate-400">signals</span>
				{newCount24h > 0 ? (
					<span className="rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-900">
						+{newCount24h} today
					</span>
				) : null}
				<span
					className={`ml-auto rounded-full px-1.5 py-0.5 text-[10px] font-semibold capitalize ring-1 ring-inset ${levelCls}`}
				>
					{resolvedLevel}
				</span>
			</div>
			<div className="mt-1.5 flex items-center justify-between gap-2 text-[11px] text-slate-500">
				<span>{lastSeen ? `Last signal ${lastSeen}` : "No signals yet"}</span>
				{runStatus ? <span className="inline-flex">{runStatus}</span> : null}
			</div>
		</div>
	);
}

