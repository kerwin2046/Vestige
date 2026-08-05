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
	cancelled: "warning",
};

const STATUS_LABEL: Record<RunStatus, string> = {
	queued: "Queued",
	running: "Running",
	succeeded: "Succeeded",
	failed: "Failed",
	cancel_requested: "Cancel requested",
	cancelled: "Cancelled",
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
	return <Badge variant={STATUS_VARIANT[status]}>{STATUS_LABEL[status]}</Badge>;
}

export function formatDateTime(value: string | null | undefined) {
	if (!value) return "—";
	return new Date(value).toLocaleString();
}

export function formatConfidence(value: number) {
	return `${(value * 100).toFixed(0)}%`;
}
