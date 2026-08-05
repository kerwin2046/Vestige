import vestigeService from "@/api/services/vestigeService";
import { Chart, useChart } from "@/components/chart";
import { Icon } from "@/components/icon";
import type { DiscoveryRun, RunSource } from "@/types/vestige";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader } from "@/ui/card";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Empty, Progress, Table, Tabs, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { RunStatusBadge, formatConfidence, formatDateTime } from "../components/run-status";
import CompanyForm from "./company-form";

const SOURCE_TYPE_LABELS: Record<string, string> = {
	owned: "Owned",
	social: "Social",
	news_media: "News / Media",
	community_ugc: "Community / UGC",
	marketplace_directory: "Marketplace",
	reference: "Reference",
	public_record: "Public record",
	recruitment: "Recruitment",
	academic_technical: "Academic / Tech",
	other: "Other",
	irrelevant: "Irrelevant",
};

const OWNERSHIP_LABELS: Record<string, string> = {
	first_party: "First party",
	third_party: "Third party",
	unknown: "Unknown",
};

const OWNERSHIP_COLORS: Record<string, string> = {
	first_party: "#22c55e",
	third_party: "#2563eb",
	unknown: "#cbd5e1",
};

function labelSourceType(value: string) {
	return SOURCE_TYPE_LABELS[value] ?? value;
}

function labelOwnership(value: string) {
	return OWNERSHIP_LABELS[value] ?? value;
}

function countBy(items: string[]) {
	const map = new Map<string, number>();
	for (const item of items) {
		const key = item || "unknown";
		map.set(key, (map.get(key) ?? 0) + 1);
	}
	return [...map.entries()]
		.map(([key, count]) => ({ key, count }))
		.sort((a, b) => b.count - a.count);
}

function StatCard({
	label,
	value,
	icon,
	tone = "primary",
	footnote,
}: {
	label: string;
	value: string;
	icon: string;
	tone?: "primary" | "success" | "error" | "warning";
	footnote?: string;
}) {
	const toneClass = {
		primary: "bg-primary/10 text-primary",
		success: "bg-success/10 text-success",
		error: "bg-error/10 text-error",
		warning: "bg-warning/10 text-warning",
	}[tone];
	return (
		<Card className="gap-0 py-0">
			<CardContent className="flex flex-col gap-1 px-4 py-3">
				<div className="flex items-center justify-between">
					<span className="truncate text-xs text-text-secondary">{label}</span>
					<span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md ${toneClass}`}>
						<Icon icon={icon} size={14} />
					</span>
				</div>
				<div className="text-xl font-semibold tracking-tight">{value}</div>
				{footnote ? <span className="text-xs text-text-secondary">{footnote}</span> : null}
			</CardContent>
		</Card>
	);
}

function OwnershipDonut({
	items,
}: {
	items: { key: string; count: number }[];
}) {
	const total = items.reduce((sum, item) => sum + item.count, 0);
	const options = useChart({
		labels: items.map((item) => labelOwnership(item.key)),
		colors: items.map((item) => OWNERSHIP_COLORS[item.key] ?? "#94a3b8"),
		stroke: { show: false },
		legend: { show: false },
		dataLabels: { enabled: false },
		plotOptions: {
			pie: {
				donut: {
					size: "78%",
					labels: {
						show: true,
						total: {
							show: true,
							label: "Sources",
							formatter: () => String(total),
						},
					},
				},
			},
		},
	});

	if (!total) {
		return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No sources yet" />;
	}

	return (
		<>
			<Chart type="donut" series={items.map((item) => item.count)} options={options} height={170} />
			<div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs">
				{items.map((item) => (
					<span key={item.key} className="flex items-center gap-1.5">
						<span
							className="h-2 w-2 rounded-full"
							style={{ backgroundColor: OWNERSHIP_COLORS[item.key] ?? "#94a3b8" }}
						/>
						{labelOwnership(item.key)} {Math.round((item.count / total) * 100)}%
					</span>
				))}
			</div>
		</>
	);
}

function SourceTypeBars({
	items,
	total,
}: {
	items: { key: string; count: number }[];
	total: number;
}) {
	if (!total) {
		return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No sources yet" />;
	}

	return (
		<div className="flex flex-col gap-3">
			{items.slice(0, 6).map((item) => {
				const pct = Math.round((item.count / total) * 100);
				return (
					<div key={item.key} className="flex items-center gap-3">
						<span className="w-36 truncate text-sm">{labelSourceType(item.key)}</span>
						<div className="flex-1">
							<Progress percent={pct} showInfo={false} size="small" />
						</div>
						<span className="w-16 text-right text-xs text-text-secondary">
							{item.count} ({pct}%)
						</span>
					</div>
				);
			})}
		</div>
	);
}

export default function CompanyDetailPage() {
	const { id = "" } = useParams();
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [activeTab, setActiveTab] = useState("overview");

	const companyQuery = useQuery({
		queryKey: ["company", id],
		queryFn: () => vestigeService.getCompany(id),
		enabled: Boolean(id),
	});

	const runsQuery = useQuery({
		queryKey: ["runs", id],
		queryFn: () => vestigeService.listRuns({ company_id: id }),
		enabled: Boolean(id),
		refetchInterval: 5_000,
	});

	const runs = runsQuery.data ?? [];
	const currentRun = runs[0];

	const runKind = (run: DiscoveryRun) => {
		const snap = run.settings_snapshot || {};
		if (snap.kind) return String(snap.kind);
		if (snap.source === "competitive-intel") return "signals";
		if (snap.imported) return "imported";
		return "footprint";
	};

	const latestFootprint = runs.find(
		(run) => run.status === "succeeded" && runKind(run) !== "signals",
	);
	const latestSignals = runs.find(
		(run) => run.status === "succeeded" && runKind(run) === "signals",
	);

	const sourcesQuery = useQuery({
		queryKey: ["run-sources", latestFootprint?.id],
		queryFn: () => vestigeService.listRunSources(latestFootprint?.id ?? ""),
		enabled: Boolean(latestFootprint?.id),
	});

	const signalsQuery = useQuery({
		queryKey: ["run-sources-signals", latestSignals?.id],
		queryFn: () => vestigeService.listRunSources(latestSignals?.id ?? ""),
		enabled: Boolean(latestSignals?.id),
	});

	const sources = sourcesQuery.data ?? [];
	const signalSources = signalsQuery.data ?? [];

	const runMutation = useMutation({
		mutationFn: () => vestigeService.createRun(id, {}),
		onSuccess: async () => {
			message.success("Discovery run queued");
			await queryClient.invalidateQueries({ queryKey: ["runs", id] });
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to start discovery"),
	});

	const updateMutation = useMutation({
		mutationFn: (values: Parameters<typeof vestigeService.updateCompany>[1]) =>
			vestigeService.updateCompany(id, values),
		onSuccess: async () => {
			message.success("Company updated");
			await queryClient.invalidateQueries({ queryKey: ["company", id] });
			await queryClient.invalidateQueries({ queryKey: ["companies"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to update company"),
	});

	const stats = useMemo(() => {
		const ownership = countBy(sources.map((source) => source.ownership));
		const sourceTypes = countBy(sources.map((source) => source.source_type));
		const domains = countBy(sources.map((source) => source.domain));
		const firstParty = ownership.find((item) => item.key === "first_party")?.count ?? 0;
		const thirdParty = ownership.find((item) => item.key === "third_party")?.count ?? 0;
		const avgConfidence =
			sources.length > 0
				? sources.reduce((sum, source) => sum + (source.confidence ?? 0), 0) / sources.length
				: 0;

		return {
			ownership,
			sourceTypes,
			domains,
			firstParty,
			thirdParty,
			avgConfidence,
			recentSources: sources.slice(0, 8),
		};
	}, [sources]);

	const metrics = useMemo(
		() => [
			{
				label: "Sources",
				value: String(sources.length),
				icon: "solar:database-bold-duotone",
				footnote: latestFootprint ? `Run ${latestFootprint.id.slice(0, 8)}` : "No footprint run",
			},
			{
				label: "Domains",
				value: String(stats.domains.length),
				icon: "solar:global-bold-duotone",
			},
			{
				label: "First party",
				value: String(stats.firstParty),
				icon: "solar:shield-check-bold-duotone",
				tone: "success" as const,
			},
			{
				label: "Third party",
				value: String(stats.thirdParty),
				icon: "solar:users-group-rounded-bold-duotone",
			},
			{
				label: "Avg confidence",
				value: sources.length ? formatConfidence(stats.avgConfidence) : "—",
				icon: "solar:graph-up-bold-duotone",
			},
			{
				label: "Daily signals",
				value: String(signalSources.length),
				icon: "solar:bell-bold-duotone",
				footnote: latestSignals ? `Run ${latestSignals.id.slice(0, 8)}` : "No signals yet",
			},
		],
		[sources.length, signalSources.length, stats, runs.length, latestFootprint, latestSignals, currentRun],
	);

	if (companyQuery.isLoading) {
		return (
			<Card>
				<CardContent className="py-16">
					<Empty description="Loading company…" image={Empty.PRESENTED_IMAGE_SIMPLE} />
				</CardContent>
			</Card>
		);
	}

	if (companyQuery.isError || !companyQuery.data) {
		return (
			<Card>
				<CardContent className="py-16">
					<Empty description="Company not found" image={Empty.PRESENTED_IMAGE_SIMPLE}>
						<Button variant="outline" onClick={() => navigate("/companies")}>
							Back to companies
						</Button>
					</Empty>
				</CardContent>
			</Card>
		);
	}

	const company = companyQuery.data;
	const meta = [company.industry, company.location].filter(Boolean).join(" · ");

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
						<div className="mt-1 text-xs text-text-secondary line-clamp-1">{record.title}</div>
					) : null}
				</div>
			),
		},
		{
			title: "Type",
			dataIndex: "source_type",
			width: 150,
			render: (value: string) => labelSourceType(value),
		},
		{
			title: "Ownership",
			dataIndex: "ownership",
			width: 120,
			render: (value: string) => labelOwnership(value),
		},
		{ title: "Confidence", dataIndex: "confidence", width: 110, render: formatConfidence },
	];

	const runColumns: ColumnsType<DiscoveryRun> = [
		{
			title: "Run",
			dataIndex: "id",
			render: (value: string) => <span className="font-mono text-xs">{value.slice(0, 8)}</span>,
			width: 110,
		},
		{ title: "Status", dataIndex: "status", width: 150, render: (s) => <RunStatusBadge status={s} /> },
		{ title: "Stage", dataIndex: "stage", width: 140 },
		{ title: "Progress", dataIndex: "progress", width: 100, render: (p: number) => `${p}%` },
		{ title: "Created", dataIndex: "created_at", width: 180, render: formatDateTime },
		{
			title: "",
			key: "actions",
			align: "right",
			render: (_, record) => (
				<Button size="sm" variant="outline" onClick={() => navigate(`/runs/${record.id}`)}>
					Details
				</Button>
			),
		},
	];

	const overviewTab = (
		<div className="flex flex-col gap-3">
			<div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
				{metrics.map((m) => (
					<StatCard key={m.label} {...m} />
				))}
			</div>

			<div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
				<Card className="gap-3 py-4">
					<CardHeader className="flex-row items-center justify-between space-y-0">
						<div className="font-medium">Top domains</div>
					</CardHeader>
					<CardContent className="flex flex-col gap-3">
						{stats.domains.length ? (
							stats.domains.slice(0, 6).map((item) => (
								<div key={item.key} className="flex items-center justify-between">
									<span className="truncate text-sm">{item.key}</span>
									<span className="text-sm text-text-secondary">{item.count}</span>
								</div>
							))
						) : (
							<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No sources yet" />
						)}
						{stats.domains.length ? (
							<Button variant="outline" size="sm" className="mt-1" onClick={() => setActiveTab("sources")}>
								View all sources
							</Button>
						) : null}
					</CardContent>
				</Card>

				<Card className="gap-3 py-4">
					<CardHeader className="flex-row items-center justify-between space-y-0">
						<div className="font-medium">Ownership</div>
					</CardHeader>
					<CardContent className="flex flex-col items-center gap-2">
						<OwnershipDonut items={stats.ownership} />
					</CardContent>
				</Card>

				<Card className="gap-3 py-4">
					<CardHeader className="flex-row items-center justify-between space-y-0">
						<div className="font-medium">Source types</div>
					</CardHeader>
					<CardContent>
						<SourceTypeBars items={stats.sourceTypes} total={sources.length} />
					</CardContent>
				</Card>
			</div>

			<Card className="gap-3 py-4">
				<CardHeader className="flex-row items-center justify-between space-y-0">
					<div className="font-medium">Recent sources</div>
					{latestFootprint ? (
						<Typography.Text type="secondary">From run {latestFootprint.id.slice(0, 8)}</Typography.Text>
					) : null}
				</CardHeader>
				<CardContent className="flex flex-col gap-3">
					{stats.recentSources.length ? (
						stats.recentSources.map((source) => (
							<div key={source.id} className="flex items-start gap-2 border-b pb-3 last:border-0">
								<div className="min-w-0 flex-1">
									<div className="truncate text-sm" title={source.title || source.url}>
										{source.title || source.url}
									</div>
									<div className="text-xs text-text-secondary">
										{source.domain} · {labelSourceType(source.source_type)}
									</div>
								</div>
								<Badge variant={source.ownership === "first_party" ? "success" : "secondary"}>
									{labelOwnership(source.ownership)}
								</Badge>
							</div>
						))
					) : (
						<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Run discovery to populate sources." />
					)}
				</CardContent>
			</Card>
		</div>
	);

	const sourcesTab = (
		<Card className="gap-3 py-4">
			<CardHeader className="flex-row items-center justify-between space-y-0">
				<div className="font-medium">All sources</div>
				<Typography.Text type="secondary">
					{latestFootprint ? `From run ${latestFootprint.id.slice(0, 8)}` : "No footprint run"}
				</Typography.Text>
			</CardHeader>
			<CardContent>
				<Table
					rowKey="id"
					size="middle"
					loading={sourcesQuery.isLoading}
					columns={sourceColumns}
					dataSource={sources}
					pagination={{ pageSize: 20, showSizeChanger: true, hideOnSinglePage: true }}
					locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No sources yet." /> }}
					scroll={{ x: 800 }}
				/>
			</CardContent>
		</Card>
	);

	const signalsTab = (
		<Card className="gap-3 py-4">
			<CardHeader className="flex-row items-center justify-between space-y-0">
				<div className="font-medium">Daily signals</div>
				<Typography.Text type="secondary">
					{latestSignals ? `From run ${latestSignals.id.slice(0, 8)}` : "No signal run"}
				</Typography.Text>
			</CardHeader>
			<CardContent>
				<Table
					rowKey="id"
					size="middle"
					loading={signalsQuery.isLoading}
					columns={sourceColumns}
					dataSource={signalSources}
					pagination={{ pageSize: 20, showSizeChanger: true, hideOnSinglePage: true }}
					locale={{
						emptyText: (
							<Empty
								image={Empty.PRESENTED_IMAGE_SIMPLE}
								description="No daily signals yet. OpenClaw agents POST to /ingest."
							/>
						),
					}}
					scroll={{ x: 800 }}
				/>
			</CardContent>
		</Card>
	);

	const historyTab = (
		<Card className="gap-3 py-4">
			<CardHeader>
				<div className="font-medium">Run history</div>
			</CardHeader>
			<CardContent>
				<Table
					rowKey="id"
					size="middle"
					loading={runsQuery.isLoading}
					columns={runColumns}
					dataSource={runs}
					pagination={{ pageSize: 10, hideOnSinglePage: true }}
					locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No runs yet." /> }}
					scroll={{ x: 760 }}
				/>
			</CardContent>
		</Card>
	);

	const settingsTab = (
		<Card className="gap-3 py-4">
			<CardHeader>
				<div className="font-medium">Company settings</div>
			</CardHeader>
			<CardContent className="max-w-xl">
				<CompanyForm
					formId="company-settings-form"
					initialValues={company}
					onSubmit={(values) => updateMutation.mutate(values)}
				/>
				<div className="mt-2 flex justify-end">
					<Button type="submit" form="company-settings-form" disabled={updateMutation.isPending}>
						Save changes
					</Button>
				</div>
			</CardContent>
		</Card>
	);

	return (
		<div className="grid w-full grid-cols-1 gap-3 xl:grid-cols-[1fr_280px]">
			<div className="flex min-w-0 flex-col gap-3">
				<Card className="gap-0 py-0">
					<CardContent className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
						<div className="flex items-center gap-4">
							<div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 text-xl font-semibold text-primary">
								{company.name.slice(0, 1).toUpperCase()}
							</div>
							<div>
								<div className="flex items-center gap-2">
									<Typography.Title level={4} className="!mb-0">
										{company.name}
									</Typography.Title>
									{currentRun ? <RunStatusBadge status={currentRun.status} /> : <Badge variant="secondary">Idle</Badge>}
								</div>
								<div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-secondary">
									{meta ? <span>{meta}</span> : null}
									{company.official_domain ? (
										<a
											href={`https://${company.official_domain}`}
											target="_blank"
											rel="noreferrer"
											className="inline-flex items-center gap-1 text-primary"
										>
											{company.official_domain}
											<Icon icon="solar:square-top-down-linear" size={14} />
										</a>
									) : null}
								</div>
							</div>
						</div>
						<div className="flex gap-2">
							<Button disabled={runMutation.isPending} onClick={() => runMutation.mutate()}>
								Start discovery
							</Button>
						</div>
					</CardContent>
				</Card>

				<Tabs
					activeKey={activeTab}
					onChange={setActiveTab}
					items={[
						{ key: "overview", label: "Overview", children: overviewTab },
						{ key: "sources", label: `Sources (${sources.length})`, children: sourcesTab },
						{ key: "signals", label: `Signals (${signalSources.length})`, children: signalsTab },
						{ key: "history", label: `History (${runs.length})`, children: historyTab },
						{ key: "settings", label: "Settings", children: settingsTab },
					]}
				/>
			</div>

			<div className="flex flex-col gap-3">
				<Card className="gap-3 py-4">
					<CardHeader>
						<div className="font-medium">Current Run</div>
					</CardHeader>
					<CardContent className="flex flex-col gap-3">
						{currentRun ? (
							<>
								<div className="flex items-center justify-between">
									<RunStatusBadge status={currentRun.status} />
									<span className="font-mono text-xs text-text-secondary">{currentRun.id.slice(0, 8)}</span>
								</div>
								<Progress
									percent={currentRun.progress}
									size="small"
									status={
										currentRun.status === "failed"
											? "exception"
											: currentRun.status === "succeeded"
												? "success"
												: "active"
									}
								/>
								<div className="grid grid-cols-2 gap-2 text-sm">
									<div>
										<div className="text-xs text-text-secondary">Stage</div>
										<div>{currentRun.stage}</div>
									</div>
									<div>
										<div className="text-xs text-text-secondary">Created</div>
										<div>{formatDateTime(currentRun.created_at)}</div>
									</div>
								</div>
								{currentRun.error ? (
									<div className="rounded-md bg-error/10 px-3 py-2 text-xs text-error">{currentRun.error}</div>
								) : null}
								<Button variant="outline" className="w-full" onClick={() => navigate(`/runs/${currentRun.id}`)}>
									View Run Details
								</Button>
							</>
						) : (
							<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No runs yet">
								<Button size="sm" onClick={() => runMutation.mutate()}>
									Start discovery
								</Button>
							</Empty>
						)}
					</CardContent>
				</Card>

				<Card className="gap-3 py-4">
					<CardHeader>
						<div className="font-medium">Breakdown</div>
					</CardHeader>
					<CardContent className="flex flex-col gap-2 text-sm">
						{stats.sourceTypes.length ? (
							stats.sourceTypes.map((item) => (
								<div key={item.key} className="flex items-center justify-between">
									<span className="text-text-secondary">{labelSourceType(item.key)}</span>
									<span>{item.count}</span>
								</div>
							))
						) : (
							<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No source types yet" />
						)}
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
