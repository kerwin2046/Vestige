import vestigeService from "@/api/services/vestigeService";
import type { DiscoveryRun, RunStatus } from "@/types/vestige";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader } from "@/ui/card";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Empty, Progress, Select, Space, Table, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { RunStatusBadge, formatDateTime } from "../components/run-status";

const STATUS_FILTERS: Array<{ label: string; value: RunStatus | "all" }> = [
	{ label: "All statuses", value: "all" },
	{ label: "Queued", value: "queued" },
	{ label: "Running", value: "running" },
	{ label: "Succeeded", value: "succeeded" },
	{ label: "Failed", value: "failed" },
	{ label: "Cancelled", value: "cancelled" },
];

export default function RunsPage() {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [statusFilter, setStatusFilter] = useState<RunStatus | "all">("all");

	const { data = [], isLoading, isError, refetch } = useQuery({
		queryKey: ["runs"],
		queryFn: () => vestigeService.listRuns(),
		refetchInterval: 5_000,
	});

	const filtered = useMemo(() => {
		if (statusFilter === "all") return data;
		return data.filter((run) => run.status === statusFilter);
	}, [data, statusFilter]);

	const cancelMutation = useMutation({
		mutationFn: vestigeService.cancelRun,
		onSuccess: async () => {
			message.success("Cancel requested");
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to cancel run"),
	});

	const retryMutation = useMutation({
		mutationFn: vestigeService.retryRun,
		onSuccess: async () => {
			message.success("Retry queued");
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to retry run"),
	});

	const columns: ColumnsType<DiscoveryRun> = [
		{
			title: "Company",
			dataIndex: ["company", "name"],
			render: (_, record) => (
				<div className="flex flex-col">
					<span className="font-medium">{record.company.name}</span>
					<span className="font-mono text-xs text-text-secondary">{record.id.slice(0, 8)}</span>
				</div>
			),
		},
		{
			title: "Status",
			dataIndex: "status",
			width: 150,
			render: (status: RunStatus) => <RunStatusBadge status={status} />,
		},
		{
			title: "Stage",
			dataIndex: "stage",
			width: 140,
			render: (stage: string) => <span className="text-text-secondary">{stage}</span>,
		},
		{
			title: "Progress",
			dataIndex: "progress",
			width: 160,
			render: (progress: number, record) => (
				<div className="min-w-[120px]">
					<Progress
						percent={progress}
						size="small"
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
			title: "Created",
			dataIndex: "created_at",
			width: 180,
			render: formatDateTime,
		},
		{
			title: "Actions",
			key: "actions",
			align: "right",
			width: 220,
			render: (_, record) => (
				<Space size={4}>
					<Button size="sm" variant="outline" onClick={() => navigate(`/runs/${record.id}`)}>
						Details
					</Button>
					{(record.status === "queued" || record.status === "running") && (
						<Button
							size="sm"
							variant="ghost"
							disabled={cancelMutation.isPending}
							onClick={() => cancelMutation.mutate(record.id)}
						>
							Cancel
						</Button>
					)}
					{(record.status === "failed" || record.status === "cancelled") && (
						<Button
							size="sm"
							disabled={retryMutation.isPending}
							onClick={() => retryMutation.mutate(record.id)}
						>
							Retry
						</Button>
					)}
				</Space>
			),
		},
	];

	return (
		<div className="flex w-full flex-col gap-4">
			<div className="flex items-start justify-between gap-4">
				<div>
					<Typography.Title level={4} className="!mb-1">
						Runs
					</Typography.Title>
					<Typography.Text type="secondary">
						Track discovery status, cancel queued work, or retry failed runs.
					</Typography.Text>
				</div>
				<Select
					value={statusFilter}
					style={{ width: 180 }}
					options={STATUS_FILTERS}
					onChange={setStatusFilter}
				/>
			</div>

			<Card>
				<CardHeader className="flex-row items-center justify-between space-y-0">
					<div className="font-medium">Run list</div>
					<Typography.Text type="secondary">
						{filtered.length} shown · auto-refresh 5s
					</Typography.Text>
				</CardHeader>
				<CardContent>
					{isError ? (
						<Empty description="Failed to load runs" image={Empty.PRESENTED_IMAGE_SIMPLE}>
							<Button variant="outline" onClick={() => refetch()}>
								Retry
							</Button>
						</Empty>
					) : (
						<Table
							rowKey="id"
							size="middle"
							loading={isLoading}
							columns={columns}
							dataSource={filtered}
							pagination={{ pageSize: 10, showSizeChanger: true, hideOnSinglePage: true }}
							locale={{
								emptyText: (
									<Empty
										image={Empty.PRESENTED_IMAGE_SIMPLE}
										description="No runs yet. Start a discovery from Companies."
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
