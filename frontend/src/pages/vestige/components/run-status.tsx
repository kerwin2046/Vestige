import type { RunStatus } from "@/types/vestige";
import { Badge } from "@/ui/badge";

const STATUS_VARIANT: Record<
	RunStatus,
	"default" | "info" | "success" | "warning" | "error" | "secondary"
> = {
	queued: "secondary",
	running: "info",
	succeeded: "success",
	failed: "error",
	cancel_requested: "warning",
	cancelled: "secondary",
};

const STATUS_LABEL: Record<RunStatus, string> = {
	queued: "Queued",
	running: "Running",
	succeeded: "Succeeded",
	failed: "Failed",
	cancel_requested: "Cancelling",
	cancelled: "Cancelled",
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
	const label = STATUS_LABEL[status] ?? status;
	const variant = STATUS_VARIANT[status] ?? "secondary";

	if (status === "running") {
		return (
			<Badge variant={variant} className="inline-flex items-center gap-1.5 font-semibold">
				<span className="relative flex h-2 w-2">
					<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
					<span className="relative inline-flex h-2 w-2 rounded-full bg-blue-600" />
				</span>
				{label}
			</Badge>
		);
	}

	if (status === "queued") {
		return (
			<Badge variant={variant} className="inline-flex items-center gap-1.5 font-medium">
				<span className="h-2 w-2 rounded-full bg-slate-400" />
				{label}
			</Badge>
		);
	}

	if (status === "succeeded") {
		return (
			<Badge variant={variant} className="inline-flex items-center gap-1.5 font-medium">
				<span className="h-2 w-2 rounded-full bg-emerald-500" />
				{label}
			</Badge>
		);
	}

	if (status === "failed") {
		return (
			<Badge variant={variant} className="inline-flex items-center gap-1.5 font-medium">
				<span className="h-2 w-2 rounded-full bg-rose-500" />
				{label}
			</Badge>
		);
	}

	return <Badge variant={variant}>{label}</Badge>;
}

export function ConfidenceBadge({ value }: { value: number }) {
	const percent = Math.round((value ?? 0) * 100);
	let colorClass = "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20";
	if (percent < 50) {
		colorClass = "bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/20";
	} else if (percent < 80) {
		colorClass = "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20";
	}

	return (
		<span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${colorClass}`}>
			{percent}%
		</span>
	);
}

export function formatDateTime(value: string | null | undefined) {
	if (!value) return "—";
	try {
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return value;
		return date.toLocaleString(undefined, {
			year: "numeric",
			month: "short",
			day: "numeric",
			hour: "2-digit",
			minute: "2-digit",
			second: "2-digit",
		});
	} catch {
		return value;
	}
}

export function formatConfidence(value: number) {
	return `${((value ?? 0) * 100).toFixed(0)}%`;
}
