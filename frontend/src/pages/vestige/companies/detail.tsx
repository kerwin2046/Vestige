import vestigeService from "@/api/services/vestigeService";
import { Chart, useChart } from "@/components/chart";
import type { CompanySignal, DiscoveryRun, RunSource } from "@/types/vestige";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	Alert,
	Empty,
	Input,
	Progress,
	Select,
	Space,
	Table,
	Tabs,
	Tag,
	Tooltip,
	Typography,
	message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
	ArrowLeft,
	Bell,
	Bot,
	Building2,
	CheckCircle2,
	ExternalLink,
	Globe,
	Layers,
	MapPin,
	Play,
	RefreshCw,
	Search,
	ShieldCheck,
	Sparkles,
	TrendingUp,
	Users,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import {
	ConfidenceBadge,
	RunStatusBadge,
	formatConfidence,
	formatDateTime,
} from "../components/run-status";
import CompanyForm from "./company-form";

const SOURCE_TYPE_LABELS: Record<string, string> = {
	owned: "Owned Site",
	social: "Social Media",
	news_media: "News & Media",
	community_ugc: "Community / Forum",
	marketplace_directory: "Marketplace / Directory",
	reference: "Reference",
	public_record: "Public Record",
	recruitment: "Jobs & Careers",
	academic_technical: "Academic / Technical",
	other: "Other Source",
	irrelevant: "Irrelevant",
};

const OWNERSHIP_LABELS: Record<string, string> = {
	first_party: "First Party",
	third_party: "Third Party",
	unknown: "Unclassified",
};

const OWNERSHIP_COLORS: Record<string, string> = {
	first_party: "#10b981", // emerald
	third_party: "#3b82f6", // blue
	unknown: "#94a3b8", // slate
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
	icon: IconComponent,
	accentColor = "blue",
	footnote,
}: {
	label: string;
	value: string;
	icon: React.ElementType;
	accentColor?: "blue" | "emerald" | "purple" | "amber" | "rose";
	footnote?: string;
}) {
	const colorMap = {
		blue: "bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-400",
		emerald: "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400",
		purple: "bg-purple-50 text-purple-600 dark:bg-purple-950/50 dark:text-purple-400",
		amber: "bg-amber-50 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400",
		rose: "bg-rose-50 text-rose-600 dark:bg-rose-950/50 dark:text-rose-400",
	}[accentColor];

	return (
		<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
			<CardContent className="p-4 flex flex-col justify-between h-full">
				<div className="flex items-center justify-between">
					<span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
					<div className={`p-2 rounded-lg ${colorMap}`}>
						<IconComponent className="h-4 w-4" />
					</div>
				</div>
				<div className="mt-2">
					<div className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">{value}</div>
					{footnote && <div className="mt-1 text-xs text-slate-400 truncate">{footnote}</div>}
				</div>
			</CardContent>
		</Card>
	);
}

function OwnershipDonut({ items }: { items: { key: string; count: number }[] }) {
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
					size: "75%",
					labels: {
						show: true,
						total: {
							show: true,
							label: "Total Sources",
							formatter: () => String(total),
						},
					},
				},
			},
		},
	});

	if (!total) {
		return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No sources available" />;
	}

	return (
		<div className="flex flex-col items-center">
			<Chart type="donut" series={items.map((item) => item.count)} options={options} height={180} />
			<div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-xs mt-2">
				{items.map((item) => (
					<span key={item.key} className="flex items-center gap-1.5 font-medium text-slate-600 dark:text-slate-300">
						<span
							className="h-2.5 w-2.5 rounded-full"
							style={{ backgroundColor: OWNERSHIP_COLORS[item.key] ?? "#94a3b8" }}
						/>
						{labelOwnership(item.key)}: <span className="font-semibold">{item.count}</span> ({Math.round((item.count / total) * 100)}%)
					</span>
				))}
			</div>
		</div>
	);
}

function SourceTypeBars({ items, total }: { items: { key: string; count: number }[]; total: number }) {
	if (!total) {
		return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No source types categorized" />;
	}

	return (
		<div className="flex flex-col gap-3">
			{items.slice(0, 6).map((item) => {
				const pct = Math.round((item.count / total) * 100);
				return (
					<div key={item.key} className="flex items-center gap-3">
						<span className="w-32 truncate text-xs font-medium text-slate-700 dark:text-slate-300">
							{labelSourceType(item.key)}
						</span>
						<div className="flex-1">
							<Progress percent={pct} showInfo={false} size="small" strokeColor="#2563eb" />
						</div>
						<span className="w-16 text-right text-xs font-mono text-slate-500">
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

	// Search and filters for Sources tab
	const [sourceSearch, setSourceSearch] = useState("");
	const [sourceTypeFilter, setSourceTypeFilter] = useState("ALL");
	const [ownershipFilter, setOwnershipFilter] = useState("ALL");
	const [lastAgentRun, setLastAgentRun] = useState<{
		status: string;
		pid?: number | null;
		log_path: string;
		agent_path: string;
	} | null>(null);

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

	const sourcesQuery = useQuery({
		queryKey: ["run-sources", latestFootprint?.id],
		queryFn: () => vestigeService.listRunSources(latestFootprint?.id ?? ""),
		enabled: Boolean(latestFootprint?.id),
	});

	const signalsQuery = useQuery({
		queryKey: ["company-signals", id],
		queryFn: () => vestigeService.listCompanySignals(id),
		enabled: Boolean(id),
	});

	const sources = sourcesQuery.data ?? [];
	const signalSources = signalsQuery.data?.items ?? [];
	const signalTotal = signalsQuery.data?.total ?? signalSources.length;

	const runMutation = useMutation({
		mutationFn: () =>
			vestigeService.createRun(id, {
				lanes: ["footprint", "channels", "owned"],
			}),
		onSuccess: async () => {
			message.success("Multi-lane discovery run queued");
			await queryClient.invalidateQueries({ queryKey: ["runs", id] });
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to start discovery"),
	});

	const scaffoldAgentMutation = useMutation({
		mutationFn: () => vestigeService.scaffoldCompanyAgent(id),
		onSuccess: async (data) => {
			message.success(`Agent scaffolded at ${data.agent_path}`);
			await queryClient.invalidateQueries({ queryKey: ["company", id] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to scaffold agent"),
	});

	const runAgentMutation = useMutation({
		mutationFn: () => vestigeService.runCompanyAgent(id, { wait: false }),
		onSuccess: async (data) => {
			setLastAgentRun({
				status: data.status,
				pid: data.pid,
				log_path: data.log_path,
				agent_path: data.agent_path,
			});
			message.success(
				data.pid
					? `OpenClaw started (pid ${data.pid}). Log: ${data.log_path}`
					: `OpenClaw ${data.status}. Log: ${data.log_path}`,
				5,
			);
			await queryClient.invalidateQueries({ queryKey: ["company", id] });
			await queryClient.invalidateQueries({ queryKey: ["runs", id] });
			await queryClient.invalidateQueries({ queryKey: ["company-signals", id] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to run OpenClaw agent"),
	});

	const updateMutation = useMutation({
		mutationFn: (values: Parameters<typeof vestigeService.updateCompany>[1]) =>
			vestigeService.updateCompany(id, values),
		onSuccess: async () => {
			message.success("Company anchors updated");
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

	// Filter sources in Sources Tab
	const filteredSources = useMemo(() => {
		return sources.filter((s) => {
			const matchesSearch =
				!sourceSearch ||
				s.url.toLowerCase().includes(sourceSearch.toLowerCase()) ||
				(s.title && s.title.toLowerCase().includes(sourceSearch.toLowerCase())) ||
				(s.domain && s.domain.toLowerCase().includes(sourceSearch.toLowerCase()));

			const matchesType = sourceTypeFilter === "ALL" || s.source_type === sourceTypeFilter;
			const matchesOwnership = ownershipFilter === "ALL" || s.ownership === ownershipFilter;

			return matchesSearch && matchesType && matchesOwnership;
		});
	}, [sources, sourceSearch, sourceTypeFilter, ownershipFilter]);

	if (companyQuery.isLoading) {
		return (
			<Card className="p-12 text-center border-slate-200 dark:border-slate-800">
				<CardContent>
					<div className="flex flex-col items-center gap-3">
						<RefreshCw className="h-8 w-8 text-blue-600 animate-spin" />
						<span className="text-sm font-medium text-slate-600">Loading target console...</span>
					</div>
				</CardContent>
			</Card>
		);
	}

	if (companyQuery.isError || !companyQuery.data) {
		return (
			<Card className="p-12 text-center border-slate-200 dark:border-slate-800">
				<CardContent>
					<Empty description="Target company not found" image={Empty.PRESENTED_IMAGE_SIMPLE}>
						<Button onClick={() => navigate("/companies")}>Return to Companies Directory</Button>
					</Empty>
				</CardContent>
			</Card>
		);
	}

	const company = companyQuery.data;

	const sourceColumns: ColumnsType<RunSource> = [
		{
			title: "Source Document / URL",
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
			render: (domain: string) => (
				<span className="text-xs font-mono font-medium text-slate-600 dark:text-slate-300">
					{domain || "—"}
				</span>
			),
		},
		{
			title: "Category",
			dataIndex: "source_type",
			key: "source_type",
			width: 160,
			render: (value: string) => <Tag color="blue">{labelSourceType(value)}</Tag>,
		},
		{
			title: "Ownership",
			dataIndex: "ownership",
			key: "ownership",
			width: 130,
			render: (value: string) => (
				<Badge
					variant={
						value === "first_party"
							? "success"
							: value === "third_party"
								? "info"
								: "secondary"
					}
				>
					{labelOwnership(value)}
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
	];

	const signalColumns: ColumnsType<CompanySignal> = [
		{
			title: "Signal / URL",
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
			width: 140,
			render: (domain: string) => (
				<span className="text-xs font-mono font-medium text-slate-600 dark:text-slate-300">
					{domain || "—"}
				</span>
			),
		},
		{
			title: "Category",
			dataIndex: "source_type",
			key: "source_type",
			width: 150,
			render: (value: string) => <Tag color="blue">{labelSourceType(value)}</Tag>,
		},
		{
			title: "Collector",
			dataIndex: "collector",
			key: "collector",
			width: 120,
			render: (value: string) => (
				<span className="text-xs text-slate-500">{value || "—"}</span>
			),
		},
		{
			title: "Confidence",
			dataIndex: "confidence",
			key: "confidence",
			width: 110,
			render: (val: number) => <ConfidenceBadge value={val ?? 0} />,
		},
		{
			title: "Last Seen",
			dataIndex: "last_seen_at",
			key: "last_seen_at",
			width: 160,
			render: (value: string) => (
				<span className="text-xs text-slate-500">{formatDateTime(value)}</span>
			),
		},
	];

	const runColumns: ColumnsType<DiscoveryRun> = [
		{
			title: "Run ID",
			dataIndex: "id",
			key: "id",
			width: 120,
			render: (value: string) => (
				<span className="font-mono text-xs font-semibold text-slate-700 dark:text-slate-300">
					{value.slice(0, 8)}
				</span>
			),
		},
		{
			title: "Kind",
			key: "kind",
			width: 120,
			render: (_, record) => {
				const k = runKind(record);
				return (
					<Tag color={k === "signals" ? "purple" : "cyan"} className="text-xs font-medium">
						{k.toUpperCase()}
					</Tag>
				);
			},
		},
		{
			title: "Status",
			dataIndex: "status",
			key: "status",
			width: 150,
			render: (s) => <RunStatusBadge status={s} />,
		},
		{
			title: "Stage",
			dataIndex: "stage",
			key: "stage",
			width: 150,
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
			width: 100,
			render: (p: number) => `${p}%`,
		},
		{
			title: "Created At",
			dataIndex: "created_at",
			key: "created_at",
			width: 180,
			render: (val) => (
				<span className="text-xs text-slate-500 font-mono">{formatDateTime(val)}</span>
			),
		},
		{
			title: "Action",
			key: "actions",
			align: "right",
			width: 100,
			render: (_, record) => (
				<Button
					size="sm"
					variant="outline"
					onClick={() => navigate(`/runs/${record.id}`)}
				>
					Details
				</Button>
			),
		},
	];

	// Overview Tab Component
	const overviewTab = (
		<div className="flex flex-col gap-6">
			{/* Metric Stat Grid */}
			<div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
				<StatCard
					label="Total Sources"
					value={String(sources.length)}
					icon={Layers}
					accentColor="blue"
					footnote={
						latestFootprint
							? (() => {
									const merge = (latestFootprint.settings_snapshot as { merge?: { total?: number; added?: number; kept?: number } })
										?.merge;
									const short = `Footprint ${latestFootprint.id.slice(0, 8)}`;
									if (!merge) return short;
									return `${short} · inventory ${merge.total ?? sources.length} (+${merge.added ?? 0} / kept ${merge.kept ?? 0})`;
								})()
							: "No run yet"
					}
				/>
				<StatCard
					label="Unique Domains"
					value={String(stats.domains.length)}
					icon={Globe}
					accentColor="purple"
				/>
				<StatCard
					label="First Party"
					value={String(stats.firstParty)}
					icon={ShieldCheck}
					accentColor="emerald"
				/>
				<StatCard
					label="Third Party"
					value={String(stats.thirdParty)}
					icon={Users}
					accentColor="blue"
				/>
				<StatCard
					label="Avg Confidence"
					value={sources.length ? formatConfidence(stats.avgConfidence) : "—"}
					icon={TrendingUp}
					accentColor="amber"
				/>
				<StatCard
					label="Daily Signals"
					value={String(signalTotal)}
					icon={Bell}
					accentColor="rose"
					footnote={signalTotal ? "Company signal ledger" : "No signals yet"}
				/>
			</div>

			{/* Distribution Charts */}
			<div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
				<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
					<CardHeader className="pb-3 border-b border-slate-100 dark:border-slate-800">
						<CardTitle className="text-sm font-semibold">Domain Footprint Breakdown</CardTitle>
					</CardHeader>
					<CardContent className="p-4 flex flex-col gap-3">
						{stats.domains.length ? (
							stats.domains.slice(0, 6).map((item) => (
								<div key={item.key} className="flex items-center justify-between text-xs">
									<span className="font-mono text-slate-700 dark:text-slate-300 truncate max-w-[180px]">
										{item.key}
									</span>
									<span className="font-semibold text-slate-900 dark:text-slate-100 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
										{item.count} sources
									</span>
								</div>
							))
						) : (
							<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No domains discovered" />
						)}
						{stats.domains.length > 0 && (
							<Button
								variant="outline"
								size="sm"
								className="mt-2 w-full text-xs"
								onClick={() => setActiveTab("sources")}
							>
								View All Discovered Sources
							</Button>
						)}
					</CardContent>
				</Card>

				<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
					<CardHeader className="pb-3 border-b border-slate-100 dark:border-slate-800">
						<CardTitle className="text-sm font-semibold">Ownership Classification</CardTitle>
					</CardHeader>
					<CardContent className="p-4">
						<OwnershipDonut items={stats.ownership} />
					</CardContent>
				</Card>

				<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
					<CardHeader className="pb-3 border-b border-slate-100 dark:border-slate-800">
						<CardTitle className="text-sm font-semibold">Source Categories</CardTitle>
					</CardHeader>
					<CardContent className="p-4">
						<SourceTypeBars items={stats.sourceTypes} total={sources.length} />
					</CardContent>
				</Card>
			</div>

			{/* Recent Discovered Sources List */}
			<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
				<CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
					<div>
						<CardTitle className="text-sm font-semibold">Recent Footprint Discoveries</CardTitle>
						<p className="text-xs text-slate-400 mt-0.5">Top high-confidence pages verified for {company.name}</p>
					</div>
					{latestFootprint && (
						<Tag color="blue" className="text-xs font-mono">
							Run #{latestFootprint.id.slice(0, 8)}
						</Tag>
					)}
				</CardHeader>
				<CardContent className="p-4 flex flex-col gap-3">
					{stats.recentSources.length ? (
						stats.recentSources.map((source) => (
							<div
								key={source.id}
								className="flex items-center justify-between gap-4 border-b border-slate-100 dark:border-slate-800 pb-3 last:border-0 last:pb-0"
							>
								<div className="min-w-0 flex-1">
									<a
										href={source.url}
										target="_blank"
										rel="noreferrer"
										className="truncate text-sm font-medium text-slate-900 hover:text-blue-600 dark:text-slate-100 dark:hover:text-blue-400 block"
									>
										{source.title || source.url}
									</a>
									<div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5 font-mono">
										<span>{source.domain}</span>
										<span>•</span>
										<span>{labelSourceType(source.source_type)}</span>
									</div>
								</div>
								<div className="flex items-center gap-3 shrink-0">
									<ConfidenceBadge value={source.confidence ?? 0} />
									<Badge variant={source.ownership === "first_party" ? "success" : "info"}>
										{labelOwnership(source.ownership)}
									</Badge>
								</div>
							</div>
						))
					) : (
						<Empty
							image={Empty.PRESENTED_IMAGE_SIMPLE}
							description="No sources yet. Start a footprint discovery run to analyze."
						/>
					)}
				</CardContent>
			</Card>
		</div>
	);

	// Sources Tab Component
	const sourcesTab = (
		<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
			<CardHeader className="p-4 border-b border-slate-100 dark:border-slate-800">
				<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
					<div className="flex flex-1 items-center gap-3">
						<Input
							placeholder="Search by title, domain, or URL..."
							prefix={<Search className="h-4 w-4 text-slate-400 mr-1" />}
							value={sourceSearch}
							onChange={(e) => setSourceSearch(e.target.value)}
							allowClear
							className="max-w-md h-9"
						/>
						<Select
							value={sourceTypeFilter}
							onChange={setSourceTypeFilter}
							className="w-44 h-9"
							options={[
								{ value: "ALL", label: "All Categories" },
								...Object.entries(SOURCE_TYPE_LABELS).map(([k, v]) => ({ value: k, label: v })),
							]}
						/>
						<Select
							value={ownershipFilter}
							onChange={setOwnershipFilter}
							className="w-36 h-9"
							options={[
								{ value: "ALL", label: "All Ownership" },
								{ value: "first_party", label: "First Party" },
								{ value: "third_party", label: "Third Party" },
							]}
						/>
					</div>
					<span className="text-xs text-slate-500 font-medium">
						Showing {filteredSources.length} of {sources.length} sources
					</span>
				</div>
			</CardHeader>
			<CardContent className="p-0">
				<Table
					rowKey="id"
					size="middle"
					loading={sourcesQuery.isLoading}
					columns={sourceColumns}
					dataSource={filteredSources}
					pagination={{ pageSize: 15, showSizeChanger: true }}
					locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No sources matching filter." /> }}
					scroll={{ x: 900 }}
				/>
			</CardContent>
		</Card>
	);

	// Signals Tab Component
	const signalsTab = (
		<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
			<CardHeader className="p-4 border-b border-slate-100 dark:border-slate-800 flex flex-row items-center justify-between">
				<div>
					<CardTitle className="text-base font-semibold">Company Signal Ledger</CardTitle>
					<p className="text-xs text-slate-500 mt-0.5">
						Upserted by canonical URL across all ingest batches (OpenClaw + competitive-intel)
					</p>
				</div>
				<Badge variant="secondary" className="font-mono">
					{signalTotal} Signals
				</Badge>
			</CardHeader>
			<CardContent className="p-0">
				<Table
					rowKey="id"
					size="middle"
					loading={signalsQuery.isLoading}
					columns={signalColumns}
					dataSource={signalSources}
					pagination={{ pageSize: 15, showSizeChanger: true }}
					locale={{
						emptyText: (
							<Empty
								image={Empty.PRESENTED_IMAGE_SIMPLE}
								description="No daily signals ingested yet for this target."
							/>
						),
					}}
					scroll={{ x: 1000 }}
				/>
			</CardContent>
		</Card>
	);

	// History Tab Component
	const historyTab = (
		<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
			<CardHeader className="p-4 border-b border-slate-100 dark:border-slate-800 flex flex-row items-center justify-between">
				<CardTitle className="text-base font-semibold">Discovery Execution History</CardTitle>
				<Button
					size="sm"
					className="bg-blue-600 hover:bg-blue-500 text-white font-medium"
					onClick={() => runMutation.mutate()}
					disabled={runMutation.isPending}
				>
					<Play className="mr-1.5 h-3.5 w-3.5" />
					Trigger New Run
				</Button>
			</CardHeader>
			<CardContent className="p-0">
				<Table
					rowKey="id"
					size="middle"
					loading={runsQuery.isLoading}
					columns={runColumns}
					dataSource={runs}
					pagination={{ pageSize: 10 }}
					locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No runs recorded yet." /> }}
					scroll={{ x: 800 }}
				/>
			</CardContent>
		</Card>
	);

	// Settings & Agent Tab Component
	const settingsTab = (
		<div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
			<Card className="lg:col-span-2 border-slate-200 dark:border-slate-800 shadow-xs">
				<CardHeader className="p-4 border-b border-slate-100 dark:border-slate-800">
					<CardTitle className="text-base font-semibold">Company Identity Anchors</CardTitle>
				</CardHeader>
				<CardContent className="p-6">
					<CompanyForm
						formId="company-settings-form"
						initialValues={company}
						onSubmit={(values) => updateMutation.mutate(values)}
					/>
					<div className="mt-4 flex justify-end">
						<Button
							type="submit"
							form="company-settings-form"
							className="bg-blue-600 hover:bg-blue-500 text-white font-medium"
							disabled={updateMutation.isPending}
						>
							Save Anchors
						</Button>
					</div>
				</CardContent>
			</Card>

			<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
				<CardHeader className="p-4 border-b border-slate-100 dark:border-slate-800 flex flex-row items-center gap-2">
					<Bot className="h-5 w-5 text-blue-600" />
					<CardTitle className="text-base font-semibold">OpenClaw Crawler Agent</CardTitle>
				</CardHeader>
				<CardContent className="p-5 flex flex-col gap-4">
					<p className="text-xs text-slate-500">
						Scaffold creates the workspace under OpenClaw. Run Agent calls{" "}
						<code className="font-mono">openclaw agent</code> with this company&apos;s TASK.md
						(results POST back via ingest).
					</p>

					{company.agent_path ? (
						<div className="rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-3 flex flex-col gap-2">
							<div className="flex items-center gap-2 text-xs font-semibold text-emerald-600">
								<CheckCircle2 className="h-4 w-4" />
								Agent Scaffolded
							</div>
							<div className="text-xs font-mono text-slate-600 dark:text-slate-300 break-all bg-white dark:bg-slate-800 p-2 rounded border border-slate-200 dark:border-slate-700">
								{company.agent_path}
							</div>
						</div>
					) : (
						<Alert
							type="warning"
							message="Agent Not Scaffolded"
							description="Create a dedicated directory with daily crawler scripts for OpenClaw."
							className="text-xs"
						/>
					)}

					<div className="flex flex-col gap-2">
						<Button
							className="w-full bg-blue-600 hover:bg-blue-500 text-white"
							disabled={runAgentMutation.isPending}
							onClick={() => runAgentMutation.mutate()}
						>
							<Play className="mr-1.5 h-4 w-4" />
							{runAgentMutation.isPending ? "Starting OpenClaw…" : "Run OpenClaw Agent"}
						</Button>
						<Button
							variant="outline"
							className="w-full"
							disabled={scaffoldAgentMutation.isPending}
							onClick={() => scaffoldAgentMutation.mutate()}
						>
							<Sparkles className="mr-1.5 h-4 w-4 text-blue-600" />
							{company.agent_path ? "Re-Scaffold Agent Directory" : "Scaffold OpenClaw Agent"}
						</Button>
						<p className="text-[11px] text-slate-400 font-mono">
							CLI: make run-agent DOMAIN={company.official_domain || "…"}
						</p>
						{lastAgentRun && (
							<Alert
								type="success"
								showIcon
								message={
									lastAgentRun.pid
										? `Agent started (pid ${lastAgentRun.pid})`
										: `Agent status: ${lastAgentRun.status}`
								}
								description={
									<div className="text-xs font-mono break-all">
										log: {lastAgentRun.log_path}
									</div>
								}
							/>
						)}
					</div>
				</CardContent>
			</Card>
		</div>
	);

	return (
		<div className="flex w-full flex-col gap-6">
			{/* Top Nav Back Link */}
			<div>
				<button
					type="button"
					className="inline-flex items-center text-xs font-medium text-slate-500 hover:text-blue-600 transition-colors"
					onClick={() => navigate("/companies")}
				>
					<ArrowLeft className="mr-1 h-3.5 w-3.5" />
					Back to Target Directory
				</button>
			</div>

			{/* Enterprise Hero Banner */}
			<Card className="border-slate-200 dark:border-slate-800 bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 text-white shadow-sm overflow-hidden">
				<CardContent className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
					<div className="flex items-center gap-4">
						<div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600/20 border border-blue-400/30 text-2xl font-bold text-blue-400 shrink-0">
							{company.name?.[0]?.toUpperCase() ?? "C"}
						</div>
						<div>
							<div className="flex items-center gap-3">
								<h1 className="text-2xl font-bold tracking-tight text-white">{company.name}</h1>
								{currentRun ? (
									<RunStatusBadge status={currentRun.status} />
								) : (
									<Badge variant="secondary" className="bg-slate-800 text-slate-300">Idle Target</Badge>
								)}
							</div>
							<div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-300">
								{company.official_domain && (
									<a
										href={`https://${company.official_domain.replace(/^https?:\/\//, "")}`}
										target="_blank"
										rel="noreferrer"
										className="inline-flex items-center gap-1 text-blue-400 hover:underline font-mono"
									>
										<Globe className="h-3.5 w-3.5" />
										{company.official_domain}
										<ExternalLink className="h-3 w-3" />
									</a>
								)}
								{company.industry && (
									<span className="inline-flex items-center gap-1 text-slate-300">
										<Building2 className="h-3.5 w-3.5 text-slate-400" />
										{company.industry}
									</span>
								)}
								{company.location && (
									<span className="inline-flex items-center gap-1 text-slate-300">
										<MapPin className="h-3.5 w-3.5 text-slate-400" />
										{company.location}
									</span>
								)}
							</div>
						</div>
					</div>

					{/* Action Buttons */}
					<div className="flex items-center gap-3 shrink-0">
						<Button
							size="lg"
							className="bg-blue-600 hover:bg-blue-500 text-white font-semibold shadow-xs"
							disabled={runMutation.isPending}
							onClick={() => runMutation.mutate()}
						>
							<Play className="mr-2 h-4 w-4" />
							Start Footprint Run
						</Button>
					</div>
				</CardContent>
			</Card>

			{/* Main Console Tabbed View */}
			<div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
				<div className="lg:col-span-3">
					<Tabs
						activeKey={activeTab}
						onChange={setActiveTab}
						className="vestige-tabs"
						items={[
							{ key: "overview", label: "Overview", children: overviewTab },
							{ key: "sources", label: `Footprint Sources (${sources.length})`, children: sourcesTab },
							{ key: "signals", label: `Daily Signals (${signalTotal})`, children: signalsTab },
							{ key: "history", label: `Run History (${runs.length})`, children: historyTab },
							{ key: "settings", label: "Settings & Agent", children: settingsTab },
						]}
					/>
				</div>

				{/* Right Monitor Panel */}
				<div className="flex flex-col gap-4">
					{/* Active / Last Run Card */}
					<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
						<CardHeader className="p-4 border-b border-slate-100 dark:border-slate-800 pb-3">
							<CardTitle className="text-sm font-semibold">Latest Execution</CardTitle>
						</CardHeader>
						<CardContent className="p-4 flex flex-col gap-3">
							{currentRun ? (
								<>
									<div className="flex items-center justify-between">
										<RunStatusBadge status={currentRun.status} />
										<span className="font-mono text-xs text-slate-500">#{currentRun.id.slice(0, 8)}</span>
									</div>
									<div className="w-full">
										<div className="flex justify-between text-xs text-slate-500 mb-1">
											<span>Pipeline Progress</span>
											<span>{currentRun.progress}%</span>
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
									</div>
									<div className="text-xs text-slate-600 dark:text-slate-300">
										<span className="text-slate-400">Current Stage:</span>{" "}
										<span className="font-mono font-semibold">{currentRun.stage}</span>
									</div>
									<Button
										variant="outline"
										size="sm"
										className="w-full mt-1"
										onClick={() => navigate(`/runs/${currentRun.id}`)}
									>
										View Execution Logs
									</Button>
								</>
							) : (
								<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No runs queued or executed yet." />
							)}
						</CardContent>
					</Card>

					{/* Agent Status Panel */}
					<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
						<CardHeader className="p-4 border-b border-slate-100 dark:border-slate-800 pb-3">
							<CardTitle className="text-sm font-semibold flex items-center gap-2">
								<Bot className="h-4 w-4 text-blue-600" />
								OpenClaw Automation
							</CardTitle>
						</CardHeader>
						<CardContent className="p-4 text-xs text-slate-600 dark:text-slate-300 flex flex-col gap-2">
							<div className="flex justify-between items-center">
								<span className="text-slate-500">Scheduled Ingest:</span>
								<span className="font-semibold text-emerald-600">Daily @ 02:00</span>
							</div>
							<div className="flex justify-between items-center">
								<span className="text-slate-500">Agent Path:</span>
								<span className="font-mono text-slate-700 dark:text-slate-300 truncate max-w-[120px]">
									{company.agent_path ? "Scaffolded" : "Not set"}
								</span>
							</div>
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	);
}
