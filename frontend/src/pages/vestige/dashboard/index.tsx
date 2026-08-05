import vestigeService from "@/api/services/vestigeService";
import { Icon } from "@/components/icon";
import type { DiscoveryRun } from "@/types/vestige";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { useQuery } from "@tanstack/react-query";
import { Alert, Empty, Progress, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ArrowRight, Building2, Globe, Play, RefreshCw, Zap } from "lucide-react";
import { useNavigate } from "react-router";
import { RunStatusBadge, formatDateTime } from "../components/run-status";

export default function DashboardPage() {
	const navigate = useNavigate();
	const { data, isLoading, isError, refetch, isRefetching } = useQuery({
		queryKey: ["dashboard"],
		queryFn: vestigeService.getDashboard,
		refetchInterval: 8_000,
	});

	const activeRuns = data?.recent_runs?.filter(
		(r) => r.status === "running" || r.status === "queued",
	) ?? [];

	const columns: ColumnsType<DiscoveryRun> = [
		{
			title: "Company Target",
			dataIndex: ["company", "name"],
			key: "company",
			render: (_, record) => (
				<div className="flex items-center gap-2">
					<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400 font-semibold text-xs border border-blue-100 dark:border-blue-900">
						{record.company?.name?.[0]?.toUpperCase() ?? "C"}
					</div>
					<div>
						<button
							type="button"
							className="text-left font-medium text-slate-900 hover:text-blue-600 dark:text-slate-100 dark:hover:text-blue-400 transition-colors"
							onClick={() => navigate(`/companies/${record.company_id}`)}
						>
							{record.company?.name}
						</button>
						{record.company?.domain && (
							<div className="text-xs text-slate-400 font-mono">{record.company.domain}</div>
						)}
					</div>
				</div>
			),
		},
		{
			title: "Execution Status",
			dataIndex: "status",
			key: "status",
			width: 160,
			render: (status) => <RunStatusBadge status={status} />,
		},
		{
			title: "Current Pipeline Stage",
			dataIndex: "stage",
			key: "stage",
			width: 180,
			render: (stage) => (
				<span className="font-mono text-xs text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700">
					{stage || "init"}
				</span>
			),
		},
		{
			title: "Progress",
			dataIndex: "progress",
			key: "progress",
			width: 140,
			render: (progress: number, record) => (
				<div className="w-full">
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
				<span className="text-xs text-slate-500 dark:text-slate-400 font-mono">
					{formatDateTime(val)}
				</span>
			),
		},
		{
			title: "Action",
			key: "action",
			width: 100,
			align: "right",
			render: (_, record) => (
				<Button
					variant="ghost"
					size="sm"
					className="h-8 px-2 text-xs"
					onClick={() => navigate(`/runs/${record.id}`)}
				>
					Details
				</Button>
			),
		},
	];

	return (
		<div className="flex w-full flex-col gap-6">
			{/* Header Console Banner */}
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-slate-200 dark:border-slate-800 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 p-6 text-white shadow-sm">
				<div>
					<div className="flex items-center gap-2">
						<span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
						<h1 className="text-2xl font-bold tracking-tight text-white">Footprint Intelligence Console</h1>
					</div>
					<p className="mt-1 text-sm text-slate-300 max-w-2xl">
						Autonomous multi-source web discovery engine. Continuous monitoring, footprint resolution, and signal ingestion for company targets.
					</p>
				</div>
				<div className="flex items-center gap-3">
					<Button
						variant="outline"
						size="sm"
						className="bg-slate-800/80 border-slate-700 text-slate-200 hover:bg-slate-700 hover:text-white"
						onClick={() => refetch()}
					>
						<RefreshCw className={`mr-2 h-3.5 w-3.5 ${isRefetching ? "animate-spin" : ""}`} />
						Refresh
					</Button>
					<Button
						size="sm"
						className="bg-blue-600 hover:bg-blue-500 text-white font-medium"
						onClick={() => navigate("/companies")}
					>
						<Building2 className="mr-2 h-4 w-4" />
						Manage Targets
					</Button>
				</div>
			</div>

			{/* Active Running Job Alert */}
			{activeRuns.length > 0 && (
				<Alert
					type="info"
					showIcon
					icon={<Zap className="h-4 w-4 text-blue-500 animate-bounce" />}
					message={
						<div className="flex items-center justify-between font-medium">
							<span>
								{activeRuns.length} discovery run{activeRuns.length > 1 ? "s" : ""} currently in queue or processing.
							</span>
							<Button
								variant="link"
								size="sm"
								className="p-0 text-blue-600 dark:text-blue-400 font-semibold"
								onClick={() => navigate("/runs")}
							>
								Monitor Queue <ArrowRight className="ml-1 h-3.5 w-3.5" />
							</Button>
						</div>
					}
					className="border-blue-200 bg-blue-50/80 dark:bg-blue-950/30 dark:border-blue-900"
				/>
			)}

			{/* Metric KPI Grid */}
			<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
				<Card className="relative overflow-hidden border-slate-200 dark:border-slate-800 shadow-xs hover:border-blue-300 transition-colors">
					<CardContent className="p-5">
						<div className="flex items-center justify-between">
							<span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tracked Companies</span>
							<div className="rounded-lg bg-blue-50 p-2 text-blue-600 dark:bg-blue-950/60 dark:text-blue-400">
								<Building2 className="h-5 w-5" />
							</div>
						</div>
						<div className="mt-3 text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
							{isLoading ? "—" : (data?.company_count ?? 0)}
						</div>
						<div className="mt-2 flex items-center text-xs text-slate-500">
							<span className="text-emerald-600 font-medium mr-1">Active</span> targets in workspace
						</div>
					</CardContent>
				</Card>

				<Card className="relative overflow-hidden border-slate-200 dark:border-slate-800 shadow-xs hover:border-blue-300 transition-colors">
					<CardContent className="p-5">
						<div className="flex items-center justify-between">
							<span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Runs</span>
							<div className="rounded-lg bg-purple-50 p-2 text-purple-600 dark:bg-purple-950/60 dark:text-purple-400">
								<Play className="h-5 w-5" />
							</div>
						</div>
						<div className="mt-3 text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
							{isLoading ? "—" : (data?.run_count ?? 0)}
						</div>
						<div className="mt-2 flex items-center text-xs text-slate-500">
							Footprint executions executed
						</div>
					</CardContent>
				</Card>

				<Card className="relative overflow-hidden border-slate-200 dark:border-slate-800 shadow-xs hover:border-blue-300 transition-colors">
					<CardContent className="p-5">
						<div className="flex items-center justify-between">
							<span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Worker Queue</span>
							<div className="rounded-lg bg-amber-50 p-2 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400">
								<Zap className="h-5 w-5" />
							</div>
						</div>
						<div className="mt-3 flex items-baseline gap-2">
							<span className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
								{isLoading ? "—" : (data?.queued_count ?? 0)}
							</span>
							{data?.queued_count && data.queued_count > 0 ? (
								<Badge variant="warning" className="text-xs">Processing</Badge>
							) : (
								<Badge variant="secondary" className="text-xs">Idle</Badge>
							)}
						</div>
						<div className="mt-2 flex items-center text-xs text-slate-500">
							Pending / executing runs
						</div>
					</CardContent>
				</Card>

				<Card className="relative overflow-hidden border-slate-200 dark:border-slate-800 shadow-xs hover:border-blue-300 transition-colors">
					<CardContent className="p-5">
						<div className="flex items-center justify-between">
							<span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Discovered Sources</span>
							<div className="rounded-lg bg-emerald-50 p-2 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400">
								<Globe className="h-5 w-5" />
							</div>
						</div>
						<div className="mt-3 text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
							{isLoading ? "—" : (data?.source_count ?? 0)}
						</div>
						<div className="mt-2 flex items-center text-xs text-slate-500">
							Persisted digital footprints
						</div>
					</CardContent>
				</Card>
			</div>

			{/* Recent Executions & Quick Actions Grid */}
			<div className="grid grid-cols-1 gap-6">
				<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
					<CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-4">
						<div>
							<CardTitle className="text-base font-semibold text-slate-900 dark:text-slate-100">
								Recent Discovery Runs
							</CardTitle>
							<p className="text-xs text-slate-500 mt-0.5">
								Live stream of recent crawling and disambiguation tasks
							</p>
						</div>
						<Space>
							<Button variant="outline" size="sm" onClick={() => navigate("/runs")}>
								View All Runs
							</Button>
						</Space>
					</CardHeader>
					<CardContent className="p-0">
						<Table
							rowKey="id"
							size="middle"
							loading={isLoading}
							columns={columns}
							dataSource={data?.recent_runs ?? []}
							pagination={false}
							className="vestige-table"
							locale={{
								emptyText: (
									<Empty
										image={Empty.PRESENTED_IMAGE_SIMPLE}
										description="No discovery runs yet."
									>
										<Button size="sm" onClick={() => navigate("/companies")}>
											Create Target Company
										</Button>
									</Empty>
								),
							}}
						/>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
