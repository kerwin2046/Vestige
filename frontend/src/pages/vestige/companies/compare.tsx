import vestigeService from "@/api/services/vestigeService";
import type { DiscoveryRun } from "@/types/vestige";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader } from "@/ui/card";
import { useQuery } from "@tanstack/react-query";
import { Alert, Empty, Select, Space, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { RunStatusBadge, formatDateTime } from "../components/run-status";

function runOptionLabel(run: DiscoveryRun) {
	return `${formatDateTime(run.created_at)} · ${run.status} · ${run.id.slice(0, 8)}`;
}

export default function ComparePage() {
	const { id = "" } = useParams();
	const navigate = useNavigate();
	const [baseRunId, setBaseRunId] = useState<string>();
	const [targetRunId, setTargetRunId] = useState<string>();

	const companyQuery = useQuery({
		queryKey: ["companies"],
		queryFn: vestigeService.listCompanies,
	});

	const runsQuery = useQuery({
		queryKey: ["runs", id],
		queryFn: () => vestigeService.listRuns({ company_id: id }),
		enabled: Boolean(id),
	});

	const company = companyQuery.data?.find((item) => item.id === id);
	const succeeded = useMemo(
		() => (runsQuery.data ?? []).filter((run) => run.status === "succeeded"),
		[runsQuery.data],
	);

	useEffect(() => {
		if (succeeded.length >= 2) {
			setTargetRunId((current) => current ?? succeeded[0].id);
			setBaseRunId((current) => current ?? succeeded[1].id);
		}
	}, [succeeded]);

	const baseRun = succeeded.find((run) => run.id === baseRunId);
	const targetRun = succeeded.find((run) => run.id === targetRunId);
	const canCompare = Boolean(baseRun && targetRun && baseRun.id !== targetRun.id);

	return (
		<div className="flex w-full flex-col gap-4">
			<div className="flex flex-wrap items-start justify-between gap-4">
				<div>
					<Typography.Title level={4} className="!mb-1">
						Run comparison
					</Typography.Title>
					<Typography.Text type="secondary">
						{company?.name
							? `Compare successful discovery runs for ${company.name}.`
							: "Compare added, removed, and reclassified sources across two successful runs."}
					</Typography.Text>
				</div>
				<Button variant="outline" onClick={() => navigate("/companies")}>
					Back to companies
				</Button>
			</div>

			<Card>
				<CardHeader>
					<div className="font-medium">Select runs</div>
				</CardHeader>
				<CardContent className="grid gap-4">
					{runsQuery.isError ? (
						<Empty description="Failed to load runs" image={Empty.PRESENTED_IMAGE_SIMPLE}>
							<Button variant="outline" onClick={() => runsQuery.refetch()}>
								Retry
							</Button>
						</Empty>
					) : succeeded.length < 2 ? (
						<Empty
							image={Empty.PRESENTED_IMAGE_SIMPLE}
							description="At least two successful runs are required to compare."
						>
							<Button onClick={() => navigate("/companies")}>Start another discovery</Button>
						</Empty>
					) : (
						<>
							<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
								<div className="grid gap-2">
									<Typography.Text type="secondary">Base run</Typography.Text>
									<Select
										value={baseRunId}
										options={succeeded.map((run) => ({
											value: run.id,
											label: runOptionLabel(run),
										}))}
										onChange={setBaseRunId}
									/>
									{baseRun ? (
										<Space>
											<RunStatusBadge status={baseRun.status} />
											<Typography.Text type="secondary">
												{formatDateTime(baseRun.finished_at ?? baseRun.created_at)}
											</Typography.Text>
										</Space>
									) : null}
								</div>
								<div className="grid gap-2">
									<Typography.Text type="secondary">Target run</Typography.Text>
									<Select
										value={targetRunId}
										options={succeeded.map((run) => ({
											value: run.id,
											label: runOptionLabel(run),
										}))}
										onChange={setTargetRunId}
									/>
									{targetRun ? (
										<Space>
											<RunStatusBadge status={targetRun.status} />
											<Typography.Text type="secondary">
												{formatDateTime(targetRun.finished_at ?? targetRun.created_at)}
											</Typography.Text>
										</Space>
									) : null}
								</div>
							</div>

							{canCompare ? (
								<Alert
									type="info"
									showIcon
									message="Comparison API is not connected yet"
									description="Run selection and empty states are ready. Diff results will appear here once the compare endpoint and worker persistence are available."
								/>
							) : (
								<Alert
									type="warning"
									showIcon
									message="Select two different successful runs to compare."
								/>
							)}
						</>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
