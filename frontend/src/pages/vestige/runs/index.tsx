import vestigeService from "@/api/services/vestigeService";
import type { DiscoveryRun, RunStatus } from "@/types/vestige";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Empty, Progress, Radio, Select, Space, Table, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
	Activity,
	Building2,
	CheckCircle2,
	Play,
	RefreshCw,
	RotateCcw,
	XCircle,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { RunStatusBadge, formatDateTime } from "../components/run-status";

export default function RunsPage() {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [statusFilter, setStatusFilter] = useState<RunStatus | "all">("all");

	const { data = [], isLoading, isError, refetch, isRefetching } = useQuery({
		queryKey: ["runs"],
		queryFn: () => vestigeService.listRuns(),
		refetchInterval: 5_000,
	});

	const filteredRuns = useMemo(() => {
		if (statusFilter === "all") return data;
		return data.filter((run) => run.status === statusFilter);
	}, [data, statusFilter]);

	const cancelMutation = useMutation({
		mutationFn: vestigeService.cancelRun,
		onSuccess: async () => {
			message.success("Cancellation requested");
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to cancel run"),
	});

	const retryMutation = useMutation({
		mutationFn: vestigeService.retryRun,
		onSuccess: async () => {
			message.success("Discovery run re-queued");
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to retry run"),
	});

	const statusCounts = useMemo(() => {
		const map: Record<string, number> = { all: data.length };
		data.forEach((r) => {
			map[r.status] = (map[r.status] ?? 0) + 1;
		});
		return map;
	}, [data]);

	const columns: ColumnsType<DiscoveryRun> = [
		{
			title: "Target Company",
			dataIndex: ["company", "name"],
			key: "company",
			render: (_, record) => (
				<div className="flex items-center gap-3">
					<div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400 font-bold text-sm border border-blue-100 dark:border-blue-900">
						{record.company?.name?.[0]?.toUpperCase() ?? "C"}
					</div>
					<div className="flex flex-col">
						<button
							type="button"
							className="text-left font-semibold text-slate-900 hover:text-blue-600 dark:text-slate-100 dark:hover:text-blue-400 transition-colors"
							onClick={() => navigate(`/companies/${record.company_id}`)}
						>
							{record.company?.name}
						</button>
						<span className="font-mono text-xs text-slate-400">ID: {record.id.slice(0, 8)}</span>
					</div>
				</div>
			),
		},
		{
			title: "Execution Status",
			dataIndex: "status",
			key: "status",
			width: 160,
			render: (status: RunStatus) => <RunStatusBadge status={status} />,
		},
		{
			title: "Pipeline Stage",
			dataIndex: "stage",
			key: "stage",
			width: 180,
			render: (stage: string) => (
				<span className="font-mono text-xs text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700">
					{stage || "init"}
				</span>
			),
		},
		{
			title: "Progress",
			dataIndex: "progress",
			key: "progress",
			width: 160,
			render: (progress: number, record) => (
				<div className="w-full min-w-[120px]">
					<div className="flex justify-between text-xs text-slate-500 mb-1">
						<span>{progress}%</span>
					</div>
					<Progress
						percent={progress}
						size="small"
						showInfo={false}
						status={
							record.status === "failed"
								? "exception"
								: record.status === "succeeded"
									? "success"
									: "active"
						}
					/>
				</div>
			),
		},
		{
			title: "Triggered At",
			dataIndex: "created_at",
			key: "created_at",
			width: 180,
			render: (val) => (
				<span className="text-xs text-slate-500 font-mono">{formatDateTime(val)}</span>
			),
		},
		{
			title: "Actions",
			key: "actions",
			align: "right",
			width: 220,
			render: (_, record) => (
				<Space size={6} className="justify-end">
					<Button
						size="sm"
						variant="outline"
						onClick={() => navigate(`/runs/${record.id}`)}
					>
						Console
					</Button>
					{(record.status === "queued" || record.status === "running") && (
						<Button
							size="sm"
							variant="ghost"
							className="text-amber-600 hover:text-amber-700"
							disabled={cancelMutation.isPending}
							onClick={() => cancelMutation.mutate(record.id)}
						>
							<XCircle className="mr-1 h-3.5 w-3.5" />
							Cancel
						</Button>
					)}
					{(record.status === "failed" || record.status === "cancelled") && (
						<Button
							size="sm"
							className="bg-blue-600 hover:bg-blue-500 text-white"
							disabled={retryMutation.isPending}
							onClick={() => retryMutation.mutate(record.id)}
						>
							<RotateCcw className="mr-1 h-3.5 w-3.5" />
							Retry
						</Button>
					)}
				</Space>
			),
		},
	];

	return (
		<div className="flex w-full flex-col gap-6">
			{/* Page Header */}
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
						<Activity className="h-6 w-6 text-blue-600" />
						Execution Center & Job Queue
					</h1>
					<p className="mt-1 text-sm text-slate-500">
						Monitor active discovery workers, pipeline stages, and execution logs in real time.
					</p>
				</div>
				<div className="flex items-center gap-3">
					<Button
						variant="outline"
						size="sm"
						onClick={() => refetch()}
					>
						<RefreshCw className={`mr-2 h-3.5 w-3.5 ${isRefetching ? "animate-spin" : ""}`} />
						Sync Jobs
					</Button>
				</div>
			</div>

			{(statusCounts.queued ?? 0) > 0 && (statusCounts.running ?? 0) === 0 && (
				<Alert
					type="info"
					showIcon
					message={`${statusCounts.queued} run(s) queued`}
					description="Ensure `make worker` is running — the API only enqueues jobs; the worker consumes them."
				/>
			)}

			{/* Filter Radio Group */}
			<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
				<CardContent className="p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
					<Radio.Group
						value={statusFilter}
						onChange={(e) => setStatusFilter(e.target.value)}
						buttonStyle="solid"
						size="middle"
					>
						<Radio.Button value="all">
							All <span className="ml-1 text-xs opacity-80">({statusCounts.all ?? 0})</span>
						</Radio.Button>
						<Radio.Button value="running">
							Running <span className="ml-1 text-xs opacity-80">({statusCounts.running ?? 0})</span>
						</Radio.Button>
						<Radio.Button value="queued">
							Queued <span className="ml-1 text-xs opacity-80">({statusCounts.queued ?? 0})</span>
						</Radio.Button>
						<Radio.Button value="succeeded">
							Succeeded <span className="ml-1 text-xs opacity-80">({statusCounts.succeeded ?? 0})</span>
						</Radio.Button>
						<Radio.Button value="failed">
							Failed <span className="ml-1 text-xs opacity-80">({statusCounts.failed ?? 0})</span>
						</Radio.Button>
						<Radio.Button value="cancelled">
							Cancelled <span className="ml-1 text-xs opacity-80">({statusCounts.cancelled ?? 0})</span>
						</Radio.Button>
					</Radio.Group>

					<div className="text-xs text-slate-400 font-mono flex items-center gap-1.5">
						<span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
						Auto-refresh 5s
					</div>
				</CardContent>
			</Card>

			{/* Table */}
			<Card className="border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
				<CardContent className="p-0">
					{isError ? (
						<div className="p-12 text-center">
							<Empty description="Failed to load runs" image={Empty.PRESENTED_IMAGE_SIMPLE}>
								<Button variant="outline" onClick={() => refetch()}>
									Retry
								</Button>
							</Empty>
						</div>
					) : (
						<Table
							rowKey="id"
							size="middle"
							loading={isLoading}
							columns={columns}
							dataSource={filteredRuns}
							pagination={{ pageSize: 12, showSizeChanger: true }}
							locale={{
								emptyText: (
									<Empty
										image={Empty.PRESENTED_IMAGE_SIMPLE}
										description="No discovery runs matching current filter."
									/>
								),
							}}
							scroll={{ x: 1000 }}
						/>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
