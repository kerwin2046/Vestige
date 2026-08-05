import vestigeService from "@/api/services/vestigeService";
import type { RunSource } from "@/types/vestige";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader } from "@/ui/card";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Descriptions, Empty, Progress, Space, Table, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useNavigate, useParams } from "react-router";
import { RunStatusBadge, formatConfidence, formatDateTime } from "../components/run-status";

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
			message.success("Cancel requested");
			await queryClient.invalidateQueries({ queryKey: ["run", id] });
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to cancel run"),
	});

	const retryMutation = useMutation({
		mutationFn: vestigeService.retryRun,
		onSuccess: async (run) => {
			message.success("Retry queued");
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
			navigate(`/runs/${run.id}`);
		},
		onError: (error: Error) => message.error(error.message || "Failed to retry run"),
	});

	if (runQuery.isLoading) {
		return (
			<Card>
				<CardContent className="py-16">
					<Empty description="Loading run details…" image={Empty.PRESENTED_IMAGE_SIMPLE} />
				</CardContent>
			</Card>
		);
	}

	if (runQuery.isError || !runQuery.data) {
		return (
			<Card>
				<CardContent className="py-16">
					<Empty description="Failed to load run details" image={Empty.PRESENTED_IMAGE_SIMPLE}>
						<Button variant="outline" onClick={() => runQuery.refetch()}>
							Retry
						</Button>
					</Empty>
				</CardContent>
			</Card>
		);
	}

	const run = runQuery.data;
	const canCancel = run.status === "queued" || run.status === "running";
	const canRetry = run.status === "failed" || run.status === "cancelled";

	const sourceColumns: ColumnsType<RunSource> = [
		{
			title: "URL",
			dataIndex: "url",
			render: (url: string, record) => (
				<div className="max-w-xl">
					<a href={url} target="_blank" rel="noreferrer" className="break-all text-primary">
						{url}
					</a>
					{record.title ? (
						<div className="mt-1 text-xs text-text-secondary line-clamp-2">{record.title}</div>
					) : null}
				</div>
			),
		},
		{
			title: "Type",
			dataIndex: "source_type",
			width: 140,
		},
		{
			title: "Ownership",
			dataIndex: "ownership",
			width: 120,
		},
		{
			title: "Confidence",
			dataIndex: "confidence",
			width: 110,
			render: formatConfidence,
		},
		{
			title: "Discovery path",
			dataIndex: "discovery_path",
			width: 220,
			render: (value: string) => (
				<span className="break-all text-xs text-text-secondary">{value || "—"}</span>
			),
		},
	];

	return (
		<div className="flex w-full flex-col gap-4">
			<div className="flex flex-wrap items-start justify-between gap-4">
				<div>
					<Typography.Title level={4} className="!mb-1">
						{run.company.name}
					</Typography.Title>
					<Space size="middle" wrap>
						<RunStatusBadge status={run.status} />
						<Typography.Text type="secondary">Stage · {run.stage}</Typography.Text>
						<Typography.Text type="secondary" className="font-mono">
							{run.id}
						</Typography.Text>
					</Space>
				</div>
				<Space>
					<Button variant="outline" onClick={() => navigate("/runs")}>
						Back to runs
					</Button>
					{canCancel && (
						<Button
							variant="outline"
							disabled={cancelMutation.isPending}
							onClick={() => cancelMutation.mutate(run.id)}
						>
							Cancel
						</Button>
					)}
					{canRetry && (
						<Button disabled={retryMutation.isPending} onClick={() => retryMutation.mutate(run.id)}>
							Retry
						</Button>
					)}
				</Space>
			</div>

			{run.error ? <Alert type="error" showIcon message="Run failed" description={run.error} /> : null}

			<div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
				<Card className="xl:col-span-2">
					<CardHeader>
						<div className="font-medium">Run info</div>
					</CardHeader>
					<CardContent>
						<Descriptions column={1} size="small" bordered>
							<Descriptions.Item label="Company">{run.company.name}</Descriptions.Item>
							<Descriptions.Item label="Official domain">
								{run.company.official_domain || "—"}
							</Descriptions.Item>
							<Descriptions.Item label="Search backend">
								{run.settings_snapshot.search_backend || "default"}
							</Descriptions.Item>
							<Descriptions.Item label="Created">{formatDateTime(run.created_at)}</Descriptions.Item>
							<Descriptions.Item label="Started">{formatDateTime(run.started_at)}</Descriptions.Item>
							<Descriptions.Item label="Finished">{formatDateTime(run.finished_at)}</Descriptions.Item>
						</Descriptions>
					</CardContent>
				</Card>

				<Card>
					<CardHeader>
						<div className="font-medium">Progress</div>
					</CardHeader>
					<CardContent className="flex flex-col items-center justify-center gap-4 py-8">
						<Progress
							type="circle"
							percent={run.progress}
							status={
								run.status === "failed"
									? "exception"
									: run.status === "succeeded"
										? "success"
										: "active"
							}
						/>
						<Typography.Text type="secondary">{run.stage}</Typography.Text>
					</CardContent>
				</Card>
			</div>

			<Card>
				<CardHeader className="flex-row items-center justify-between space-y-0">
					<div className="font-medium">Sources</div>
					<Typography.Text type="secondary">{sourcesQuery.data?.length ?? 0} rows</Typography.Text>
				</CardHeader>
				<CardContent>
					{sourcesQuery.isError ? (
						<Empty description="Failed to load sources" image={Empty.PRESENTED_IMAGE_SIMPLE}>
							<Button variant="outline" onClick={() => sourcesQuery.refetch()}>
								Retry
							</Button>
						</Empty>
					) : (
						<Table
							rowKey="id"
							size="middle"
							loading={sourcesQuery.isLoading}
							columns={sourceColumns}
							dataSource={sourcesQuery.data ?? []}
							pagination={{ pageSize: 20, showSizeChanger: true, hideOnSinglePage: true }}
							locale={{
								emptyText: (
									<Empty
										image={Empty.PRESENTED_IMAGE_SIMPLE}
										description={
											run.status === "queued" || run.status === "running"
												? "Waiting for the worker to produce sources."
												: "No sources were persisted for this run."
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
