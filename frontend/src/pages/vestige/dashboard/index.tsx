import vestigeService from "@/api/services/vestigeService";
import type { DiscoveryRun } from "@/types/vestige";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader } from "@/ui/card";
import { useQuery } from "@tanstack/react-query";
import { Empty, Space, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useNavigate } from "react-router";
import { RunStatusBadge, formatDateTime } from "../components/run-status";

export default function DashboardPage() {
	const navigate = useNavigate();
	const { data, isLoading, isError, refetch } = useQuery({
		queryKey: ["dashboard"],
		queryFn: vestigeService.getDashboard,
		refetchInterval: 10_000,
	});

	const metrics = [
		{ key: "company_count" as const, label: "Companies", hint: "Tracked targets" },
		{ key: "run_count" as const, label: "Total runs", hint: "All discovery jobs" },
		{ key: "queued_count" as const, label: "Queued runs", hint: "Waiting for worker" },
		{ key: "source_count" as const, label: "Discovered sources", hint: "Persisted URLs" },
	];

	const columns: ColumnsType<DiscoveryRun> = [
		{
			title: "Company",
			dataIndex: ["company", "name"],
			render: (_, record) => (
				<button
					type="button"
					className="text-left font-medium text-primary hover:underline"
					onClick={() => navigate(`/companies/${record.company_id}`)}
				>
					{record.company.name}
				</button>
			),
		},
		{
			title: "Status",
			dataIndex: "status",
			width: 150,
			render: (status) => <RunStatusBadge status={status} />,
		},
		{
			title: "Stage",
			dataIndex: "stage",
			width: 140,
		},
		{
			title: "Progress",
			dataIndex: "progress",
			width: 100,
			render: (progress: number) => `${progress}%`,
		},
		{
			title: "Created",
			dataIndex: "created_at",
			width: 180,
			render: formatDateTime,
		},
	];

	return (
		<div className="flex w-full flex-col gap-4">
			<div className="flex flex-wrap items-start justify-between gap-4">
				<div>
					<Typography.Title level={4} className="!mb-1">
						Overview
					</Typography.Title>
					<Typography.Text type="secondary">
						Discover, verify, and continuously track a company's public web footprint.
					</Typography.Text>
				</div>
				<Space>
					<Button variant="outline" onClick={() => navigate("/runs")}>
						View runs
					</Button>
					<Button onClick={() => navigate("/companies")}>Manage companies</Button>
				</Space>
			</div>

			{isError ? (
				<Card>
					<CardContent className="py-16">
						<Empty description="Failed to load overview" image={Empty.PRESENTED_IMAGE_SIMPLE}>
							<Button variant="outline" onClick={() => refetch()}>
								Retry
							</Button>
						</Empty>
					</CardContent>
				</Card>
			) : (
				<>
					<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
						{metrics.map((metric) => (
							<Card key={metric.key} className="gap-2">
								<CardHeader className="pb-0">
									<div className="text-sm text-text-secondary">{metric.label}</div>
								</CardHeader>
								<CardContent>
									<div className="text-3xl font-semibold tracking-tight">
										{isLoading ? "—" : data?.[metric.key] ?? 0}
									</div>
									<div className="mt-1 text-xs text-text-secondary">{metric.hint}</div>
								</CardContent>
							</Card>
						))}
					</div>

					<Card>
						<CardHeader className="flex-row items-center justify-between space-y-0">
							<div className="font-medium">Recent runs</div>
							<Typography.Text type="secondary">Auto-refresh 10s</Typography.Text>
						</CardHeader>
						<CardContent>
							<Table
								rowKey="id"
								size="middle"
								loading={isLoading}
								columns={columns}
								dataSource={data?.recent_runs ?? []}
								pagination={false}
								locale={{
									emptyText: (
										<Empty
											image={Empty.PRESENTED_IMAGE_SIMPLE}
											description="No runs yet. Create a company and start a discovery."
										>
											<Button onClick={() => navigate("/companies")}>Go to companies</Button>
										</Empty>
									),
								}}
							/>
						</CardContent>
					</Card>
				</>
			)}
		</div>
	);
}
