import vestigeService from "@/api/services/vestigeService";
import type { RunSource } from "@/types/vestige";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Descriptions, Empty, Progress, Steps, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
	ArrowLeft,
	Building2,
	CheckCircle2,
	ExternalLink,
	Globe,
	Layers,
	Play,
	RefreshCw,
	RotateCcw,
	XCircle,
} from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { ConfidenceBadge, RunStatusBadge, formatDateTime } from "../components/run-status";

const PIPELINE_STAGES = ["created", "queued", "searching", "crawling", "disambiguation", "persisted"];

function getStageStepIndex(stage: string, status: string): number {
	if (status === "succeeded") return PIPELINE_STAGES.length - 1;
	const normalized = (stage || "").toLowerCase();
	const idx = PIPELINE_STAGES.findIndex((s) => normalized.includes(s));
	return idx >= 0 ? idx : 1;
}

export default function RunDetailPage() {
	const { id = "" } = useParams();
	const navigate = useNavigate();
	const queryClient = useQueryClient();

	const runQuery = useQuery({
		queryKey: ["run", id],
		queryFn: () => vestigeService.getRun(id),
		enabled: Boolean(id),
		refetchInterval: 5_000,
	});

	const sourcesQuery = useQuery({
		queryKey: ["run-sources", id],
		queryFn: () => vestigeService.listRunSources(id),
		enabled: Boolean(id),
		refetchInterval: 5_000,
	});

	const cancelMutation = useMutation({
		mutationFn: vestigeService.cancelRun,
		onSuccess: async () => {
			message.success("Cancellation requested");
			await queryClient.invalidateQueries({ queryKey: ["run", id] });
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to cancel run"),
	});

	const retryMutation = useMutation({
		mutationFn: vestigeService.retryRun,
		onSuccess: async (run) => {
			message.success("Run re-queued");
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
			navigate(`/runs/${run.id}`);
		},
		onError: (error: Error) => message.error(error.message || "Failed to retry run"),
	});

	if (runQuery.isLoading) {
		return (
			<Card className="p-12 text-center border-slate-200 dark:border-slate-800">
				<CardContent>
					<div className="flex flex-col items-center gap-3">
						<RefreshCw className="h-8 w-8 text-blue-600 animate-spin" />
						<span className="text-sm font-medium text-slate-600">Loading run details...</span>
					</div>
				</CardContent>
			</Card>
		);
	}

	if (runQuery.isError || !runQuery.data) {
		return (
			<Card className="p-12 text-center border-slate-200 dark:border-slate-800">
				<CardContent>
					<Empty description="Run detail not found" image={Empty.PRESENTED_IMAGE_SIMPLE}>
						<Button onClick={() => navigate("/runs")}>Return to Runs Center</Button>
					</Empty>
				</CardContent>
			</Card>
		);
	}

	const run = runQuery.data;
	const canCancel = run.status === "queued" || run.status === "running";
	const canRetry = run.status === "failed" || run.status === "cancelled";
	const currentStepIndex = getStageStepIndex(run.stage, run.status);
	const laneResults = run.settings_snapshot?.lane_results || {};
	const configuredLanes =
		(run.settings_snapshot?.lanes as string[] | undefined) ||
		Object.keys(laneResults);
	const laneNames =
		configuredLanes.length > 0
			? configuredLanes
			: Object.keys(laneResults).length > 0
				? Object.keys(laneResults)
				: ["footprint", "channels", "owned"];
	const failedLanes = laneNames.filter((lane) => {
		const status = laneResults[lane]?.status;
		return status === "error" || status === "empty";
	});
	const laneFailureSummary =
		failedLanes.length > 0
			? failedLanes
					.map((lane) => {
						const info = laneResults[lane];
						const detail = info?.error?.trim();
						return detail ? `${lane}: ${detail}` : `${lane} (${info?.status || "failed"})`;
					})
					.join(" · ")
			: null;
	const runWarning =
		typeof run.settings_snapshot?.warning === "string"
			? run.settings_snapshot.warning
			: null;

	const sourceColumns: ColumnsType<RunSource> = [
		{
			title: "Source URL / Page",
			dataIndex: "url",
			key: "url",
			render: (url: string, record) => (
				<div className="flex flex-col max-w-lg">
					<a
						href={url}
						target="_blank"
						rel="noreferrer"
						className="font-medium text-slate-900 hover:text-blue-600 dark:text-slate-100 dark:hover:text-blue-400 truncate flex items-center gap-1.5"
					>
						<Globe className="h-3.5 w-3.5 shrink-0 text-slate-400" />
						<span className="truncate">{record.title || url}</span>
						<ExternalLink className="h-3 w-3 shrink-0 text-slate-400 opacity-60" />
					</a>
					<span className="text-xs text-slate-400 font-mono truncate">{url}</span>
				</div>
			),
		},
		{
			title: "Domain",
			dataIndex: "domain",
			key: "domain",
			width: 150,
			render: (d: string) => (
				<span className="text-xs font-mono font-medium text-slate-600 dark:text-slate-300">
					{d || "—"}
				</span>
			),
		},
		{
			title: "Type",
			dataIndex: "source_type",
			key: "source_type",
			width: 150,
			render: (st: string) => <Tag color="blue">{st || "unknown"}</Tag>,
		},
		{
			title: "Ownership",
			dataIndex: "ownership",
			key: "ownership",
			width: 130,
			render: (o: string) => (
				<Badge variant={o === "first_party" ? "success" : "info"}>
					{o === "first_party" ? "First Party" : "Third Party"}
				</Badge>
			),
		},
		{
			title: "Confidence",
			dataIndex: "confidence",
			key: "confidence",
			width: 120,
			render: (val: number) => <ConfidenceBadge value={val ?? 0} />,
		},
		{
			title: "Discovery Path",
			dataIndex: "discovery_path",
			key: "discovery_path",
			width: 200,
			render: (value: string) => (
				<span className="truncate text-xs font-mono text-slate-400 block max-w-[180px]">
					{value || "direct"}
				</span>
			),
		},
	];

	return (
		<div className="flex w-full flex-col gap-6">
			{/* Back Link */}
			<div>
				<button
					type="button"
					className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-blue-600 transition-colors"
					onClick={() => navigate("/runs")}
				>
					<ArrowLeft className="mr-1 h-3.5 w-3.5" />
					Back to Execution Queue
				</button>
			</div>

			{/* Hero Header */}
			<Card className="border-slate-200 dark:border-slate-800 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white shadow-sm overflow-hidden">
				<CardContent className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
					<div className="flex items-center gap-4">
						<div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600/20 border border-blue-400/30 text-xl font-bold text-blue-400 shrink-0">
							{run.company?.name?.[0]?.toUpperCase() ?? "C"}
						</div>
						<div>
							<div className="flex items-center gap-3">
								<h1 className="text-2xl font-bold tracking-tight text-white">{run.company?.name}</h1>
								<RunStatusBadge status={run.status} />
							</div>
							<div className="mt-1 flex items-center gap-3 text-xs text-slate-300 font-mono">
								<span>Run ID: {run.id}</span>
								<span>•</span>
								<span>Domain: {run.company?.official_domain || "N/A"}</span>
							</div>
						</div>
					</div>

					{/* Action Buttons */}
					<div className="flex items-center gap-3">
						<Button
							variant="outline"
							className="bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700"
							onClick={() => navigate(`/companies/${run.company_id}`)}
						>
							<Building2 className="mr-1.5 h-4 w-4" />
							View Target Console
						</Button>

						{canCancel && (
							<Button
								variant="outline"
								className="border-amber-600 text-amber-500 hover:bg-amber-950/30"
								disabled={cancelMutation.isPending}
								onClick={() => cancelMutation.mutate(run.id)}
							>
								<XCircle className="mr-1.5 h-4 w-4" />
								Cancel Execution
							</Button>
						)}

						{canRetry && (
							<Button
								className="bg-blue-600 hover:bg-blue-500 text-white font-semibold"
								disabled={retryMutation.isPending}
								onClick={() => retryMutation.mutate(run.id)}
							>
								<RotateCcw className="mr-1.5 h-4 w-4" />
								Retry Run
							</Button>
						)}
					</div>
				</CardContent>
			</Card>

			{/* Pipeline Stepper Progress */}
			<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
				<CardHeader className="p-4 border-b border-slate-100 dark:border-slate-800">
					<CardTitle className="text-sm font-semibold">Discovery Pipeline Stepper</CardTitle>
				</CardHeader>
				<CardContent className="p-6">
					<Steps
						current={currentStepIndex}
						status={
							run.status === "failed"
								? "error"
								: run.status === "succeeded"
									? "finish"
									: "process"
						}
						items={[
							{ title: "Created", description: "Job enqueued" },
							{ title: "Queued", description: "Worker pickup" },
							{ title: "Searching", description: "Multi-lane discovery" },
							{ title: "Crawling", description: "HTML extraction" },
							{ title: "Disambiguation", description: "LLM scoring" },
							{ title: "Persisted", description: "Saved to DB" },
						]}
					/>
				</CardContent>
			</Card>

			{/* Lane status */}
			{(configuredLanes.length > 0 || Object.keys(laneResults).length > 0) && (
				<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
					<CardHeader className="p-4 border-b border-slate-100 dark:border-slate-800 flex flex-row items-center justify-between">
						<div>
							<CardTitle className="text-sm font-semibold flex items-center gap-2">
								<Layers className="h-4 w-4 text-slate-500" />
								Discovery Lanes
								{failedLanes.length > 0 ? (
									<Badge variant="destructive" className="ml-1 font-normal">
										{failedLanes.length} issue{failedLanes.length > 1 ? "s" : ""}
									</Badge>
								) : null}
							</CardTitle>
							<p className="text-xs text-slate-400 mt-0.5">
								Footprint SERP, channel site: search, and owned-domain seed
							</p>
						</div>
					</CardHeader>
					<CardContent className="p-4 space-y-3">
						{laneFailureSummary ? (
							<Alert
								type="error"
								showIcon
								message="Lane failures"
								description={
									<span className="text-xs leading-relaxed">{laneFailureSummary}</span>
								}
								className="border-rose-200 dark:border-rose-900 bg-rose-50/80 dark:bg-rose-950/30"
							/>
						) : null}
						<div className="grid gap-3 sm:grid-cols-3">
							{laneNames.map((lane) => {
								const info = laneResults[lane];
								const status =
									info?.status ||
									(run.status === "queued" || run.status === "running" ? "pending" : "—");
								const isError = status === "error";
								const isEmpty = status === "empty";
								const isOk = status === "ok" || status === "seeded";
								const color = isOk
									? "success"
									: isError
										? "error"
										: isEmpty
											? "warning"
											: status === "warning"
												? "warning"
												: "default";
								const cardTone = isError
									? "border-rose-300 dark:border-rose-800 bg-rose-50/70 dark:bg-rose-950/40"
									: isEmpty
										? "border-amber-300 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-950/30"
										: isOk
											? "border-emerald-200 dark:border-emerald-900 bg-emerald-50/40 dark:bg-emerald-950/20"
											: "border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/40";
								return (
									<div key={lane} className={`rounded-lg border p-3 ${cardTone}`}>
										<div className="flex items-center justify-between gap-2">
											<span className="text-sm font-semibold capitalize text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
												{isError ? (
													<XCircle className="h-3.5 w-3.5 text-rose-600 shrink-0" />
												) : isOk ? (
													<CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
												) : null}
												{lane}
											</span>
											<Tag color={color}>{status}</Tag>
										</div>
										<div className="mt-2 text-xs text-slate-500 font-mono">
											{info?.source_count ?? 0} sources
										</div>
										{info?.error ? (
											<p
												className={`mt-2 text-xs whitespace-pre-wrap break-words ${
													isError
														? "text-rose-700 dark:text-rose-300"
														: "text-amber-800 dark:text-amber-300"
												}`}
											>
												{info.error}
											</p>
										) : isEmpty ? (
											<p className="mt-2 text-xs text-amber-700 dark:text-amber-400">
												No sources returned for this lane
											</p>
										) : null}
									</div>
								);
							})}
						</div>
					</CardContent>
				</Card>
			)}

			{/* Error / warning banners */}
			{run.error && (
				<Alert
					type="error"
					showIcon
					message="Execution Error"
					description={run.error}
					className="border-rose-200 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/30"
				/>
			)}
			{runWarning && !run.error && (
				<Alert
					type="warning"
					showIcon
					message="Lane warning"
					description={runWarning}
				/>
			)}
			{laneFailureSummary && !run.error && !runWarning && failedLanes.some((l) => laneResults[l]?.status === "error") && (
				<Alert
					type="warning"
					showIcon
					message="Partial discovery"
					description="One or more lanes failed; other lanes may still have contributed sources. Check Discovery Lanes above."
				/>
			)}
			{run.status === "queued" && (
				<Alert
					type="info"
					showIcon
					message="Waiting for worker"
					description="Run is queued. Ensure `make worker` is running to consume the queue."
				/>
			)}

			{/* Meta Information & Progress */}
			<div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
				<Card className="lg:col-span-2 border-slate-200 dark:border-slate-800 shadow-xs">
					<CardHeader className="p-4 border-b border-slate-100 dark:border-slate-800">
						<CardTitle className="text-sm font-semibold">Run Parameters & Metadata</CardTitle>
					</CardHeader>
					<CardContent className="p-4">
						<Descriptions column={2} size="small" bordered className="vestige-descriptions">
							<Descriptions.Item label="Target Company">{run.company?.name}</Descriptions.Item>
							<Descriptions.Item label="Official Domain">{run.company?.official_domain || "—"}</Descriptions.Item>
							<Descriptions.Item label="Pipeline Stage">
								<span className="font-mono font-semibold text-blue-600">{run.stage}</span>
							</Descriptions.Item>
							<Descriptions.Item label="Search Backend">
								<span className="font-mono">{run.settings_snapshot?.search_backend || "default"}</span>
							</Descriptions.Item>
							<Descriptions.Item label="Lanes">
								<span className="font-mono">
									{(run.settings_snapshot?.lanes as string[] | undefined)?.join(", ") ||
										"footprint, channels, owned"}
								</span>
							</Descriptions.Item>
							<Descriptions.Item label="Created At">{formatDateTime(run.created_at)}</Descriptions.Item>
							<Descriptions.Item label="Finished At">{formatDateTime(run.finished_at)}</Descriptions.Item>
						</Descriptions>
					</CardContent>
				</Card>

				<Card className="border-slate-200 dark:border-slate-800 shadow-xs flex flex-col justify-center items-center p-6 text-center">
					<Progress
						type="dashboard"
						percent={run.progress}
						status={
							run.status === "failed"
								? "exception"
								: run.status === "succeeded"
									? "success"
									: "active"
						}
						width={140}
					/>
					<div className="mt-3 font-semibold text-slate-900 dark:text-slate-100 text-sm">
						{run.stage ? `Stage: ${run.stage}` : "Processing..."}
					</div>
					<div className="text-xs text-slate-400 mt-1">
						{sourcesQuery.data?.length ?? 0} sources persisted
					</div>
				</Card>
			</div>

			{/* Discovered Sources Table */}
			<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
				<CardHeader className="p-4 border-b border-slate-100 dark:border-slate-800 flex flex-row items-center justify-between">
					<div>
						<CardTitle className="text-base font-semibold">Discovered Footprint Sources</CardTitle>
						<p className="text-xs text-slate-400 mt-0.5">Persisted URLs and digital assets for this run</p>
					</div>
					<Badge variant="secondary" className="font-mono">
						{sourcesQuery.data?.length ?? 0} Sources
					</Badge>
				</CardHeader>
				<CardContent className="p-0">
					{sourcesQuery.isError ? (
						<div className="p-12 text-center">
							<Empty description="Failed to load run sources" image={Empty.PRESENTED_IMAGE_SIMPLE}>
								<Button variant="outline" onClick={() => sourcesQuery.refetch()}>
									Retry
								</Button>
							</Empty>
						</div>
					) : (
						<Table
							rowKey="id"
							size="middle"
							loading={sourcesQuery.isLoading}
							columns={sourceColumns}
							dataSource={sourcesQuery.data ?? []}
							pagination={{ pageSize: 15, showSizeChanger: true }}
							locale={{
								emptyText: (
									<Empty
										image={Empty.PRESENTED_IMAGE_SIMPLE}
										description={
											run.status === "queued" || run.status === "running"
												? "Worker is actively searching and crawling..."
												: "No sources persisted for this run."
										}
									/>
								),
							}}
							scroll={{ x: 960 }}
						/>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
