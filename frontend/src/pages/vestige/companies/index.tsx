import vestigeService from "@/api/services/vestigeService";
import type { Company, CompanyTier } from "@/types/vestige";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import { Card, CardContent } from "@/ui/card";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	Empty,
	Input,
	Modal,
	Popconfirm,
	Select,
	Space,
	Table,
	Tag,
	Tooltip,
	message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
	Activity,
	Building2,
	ExternalLink,
	Globe,
	MapPin,
	Play,
	Plus,
	Radio,
	Save,
	Search,
	Trash2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { ActivitySparkCard } from "../components/activity-spark-card";
import { RunStatusBadge, formatDateTime } from "../components/run-status";
import CompanyForm from "./company-form";

const TABS: Array<{ key: CompanyTier | "all"; label: string }> = [
	{ key: "candidate", label: "Candidates" },
	{ key: "target", label: "Targets" },
	{ key: "monitoring", label: "Monitoring" },
	{ key: "all", label: "All" },
];

const ROLE_OPTIONS = [
	{ value: "ALL", label: "All Roles" },
	{ value: "prospect", label: "Prospect" },
	{ value: "competitor", label: "Competitor" },
	{ value: "manufacturer", label: "Manufacturer" },
	{ value: "partner", label: "Partner" },
	{ value: "noise", label: "Noise" },
];

function roleColor(role: string) {
	switch (role) {
		case "competitor":
			return "magenta";
		case "prospect":
			return "green";
		case "manufacturer":
			return "blue";
		case "partner":
			return "cyan";
		case "noise":
			return "default";
		default:
			return "default";
	}
}

function relativeTime(value: string | null | undefined) {
	if (!value) return null;
	const ts = Date.parse(value);
	if (Number.isNaN(ts)) return null;
	const delta = Date.now() - ts;
	const minutes = Math.floor(delta / 60_000);
	if (minutes < 1) return "just now";
	if (minutes < 60) return `${minutes}m ago`;
	const hours = Math.floor(minutes / 60);
	if (hours < 24) return `${hours}h ago`;
	const days = Math.floor(hours / 24);
	if (days < 14) return `${days}d ago`;
	return formatDateTime(value);
}

function ActivityCell({ company }: { company: Company }) {
	const activity = company.activity;
	const total = activity?.signal_count ?? 0;
	const today = activity?.signals_today ?? 0;
	const live = Boolean(activity?.active_24h);
	const level = !live ? "quiet" : today >= 10 ? "high" : today >= 4 ? "medium" : today >= 1 ? "low" : "quiet";

	return (
		<ActivitySparkCard
			total={total}
			newCount24h={today}
			lastSignalAt={activity?.last_signal_at}
			active24h={live}
			level={level}
			runStatus={
				activity?.last_run_status ? (
					<Tooltip
						title={activity.last_run_at ? `Run ${formatDateTime(activity.last_run_at)}` : "Latest run"}
					>
						<span className="inline-flex">
							<RunStatusBadge status={activity.last_run_status as never} />
						</span>
					</Tooltip>
				) : undefined
			}
		/>
	);
}

export default function CompaniesPage() {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [createOpen, setCreateOpen] = useState(false);
	const [tierTab, setTierTab] = useState<CompanyTier | "all">("target");
	const [searchText, setSearchText] = useState("");
	const [selectedRole, setSelectedRole] = useState("ALL");
	const [selectedSource, setSelectedSource] = useState("ALL");
	const [sortLiveFirst, setSortLiveFirst] = useState(true);

	const { data = [], isLoading, isError, refetch, isRefetching, dataUpdatedAt } = useQuery({
		queryKey: ["companies", tierTab],
		queryFn: () =>
			vestigeService.listCompanies({
				tier: tierTab === "all" ? undefined : tierTab,
			}),
		refetchOnWindowFocus: true,
	});

	const revisionQuery = useQuery({
		queryKey: ["companies", "activity-revision"],
		queryFn: vestigeService.getCompanyActivityRevision,
		refetchInterval: 15_000,
		refetchOnWindowFocus: true,
	});

	const lastRevision = useRef<string | null>(null);
	useEffect(() => {
		const revision = revisionQuery.data?.revision;
		if (!revision) return;
		if (lastRevision.current === null) {
			lastRevision.current = revision;
			return;
		}
		if (lastRevision.current === revision) return;
		lastRevision.current = revision;
		void queryClient.invalidateQueries({ queryKey: ["companies", tierTab] });
		void queryClient.invalidateQueries({ queryKey: ["companies", "all-for-counts"] });
	}, [revisionQuery.data?.revision, queryClient, tierTab]);

	const countsQuery = useQuery({
		queryKey: ["companies", "all-for-counts"],
		queryFn: () => vestigeService.listCompanies({ include_activity: false }),
		refetchOnWindowFocus: true,
	});
	const allCompanies = countsQuery.data ?? [];

	const tierCounts = useMemo(() => {
		const map: Record<string, number> = { all: allCompanies.length };
		for (const company of allCompanies) {
			const tier = company.tier || "target";
			map[tier] = (map[tier] ?? 0) + 1;
		}
		return map;
	}, [allCompanies]);

	const sources = useMemo(() => {
		const set = new Set<string>();
		data.forEach((c) => {
			if (c.source) set.add(c.source);
		});
		return Array.from(set).sort();
	}, [data]);

	const filteredCompanies = useMemo(() => {
		const rows = data.filter((company) => {
			const q = searchText.trim().toLowerCase();
			const matchesSearch =
				!q ||
				company.name.toLowerCase().includes(q) ||
				(company.official_domain || "").toLowerCase().includes(q);
			const matchesRole =
				selectedRole === "ALL" ||
				(company.roles || []).map((r) => r.toLowerCase()).includes(selectedRole);
			const matchesSource =
				selectedSource === "ALL" || company.source === selectedSource;
			return matchesSearch && matchesRole && matchesSource;
		});
		if (!sortLiveFirst) return rows;
		return [...rows].sort((a, b) => {
			const aLive = a.activity?.active_24h ? 1 : 0;
			const bLive = b.activity?.active_24h ? 1 : 0;
			if (aLive !== bLive) return bLive - aLive;
			const aToday = a.activity?.signals_today ?? 0;
			const bToday = b.activity?.signals_today ?? 0;
			if (aToday !== bToday) return bToday - aToday;
			const aTotal = a.activity?.signal_count ?? 0;
			const bTotal = b.activity?.signal_count ?? 0;
			return bTotal - aTotal;
		});
	}, [data, searchText, selectedRole, selectedSource, sortLiveFirst]);

	const pulseSummary = useMemo(() => {
		const live = filteredCompanies.filter((c) => c.activity?.active_24h).length;
		const withSignals = filteredCompanies.filter((c) => (c.activity?.signal_count ?? 0) > 0).length;
		const today = filteredCompanies.reduce((sum, c) => sum + (c.activity?.signals_today ?? 0), 0);
		return { live, withSignals, today };
	}, [filteredCompanies]);

	const createMutation = useMutation({
		mutationFn: vestigeService.createCompany,
		onSuccess: async (company) => {
			const agentHint = company.agent_path ? ` · agent: ${company.agent_path}` : "";
			message.success(`Company created${agentHint}`);
			setCreateOpen(false);
			await queryClient.invalidateQueries({ queryKey: ["companies"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to create company"),
	});

	const deleteMutation = useMutation({
		mutationFn: vestigeService.deleteCompany,
		onSuccess: async () => {
			message.success("Company removed");
			await queryClient.invalidateQueries({ queryKey: ["companies"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to delete company"),
	});

	const promoteMutation = useMutation({
		mutationFn: ({ id, tier }: { id: string; tier: CompanyTier }) =>
			vestigeService.promoteCompany(id, tier),
		onSuccess: async (_company, vars) => {
			message.success(
				vars.tier === "target" ? "Saved as Target" : `Moved to ${vars.tier}`,
			);
			await queryClient.invalidateQueries({ queryKey: ["companies"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to promote"),
	});

	const runMutation = useMutation({
		mutationFn: async (companyId: string) => {
			await vestigeService.promoteCompany(companyId, "monitoring");
			return vestigeService.createRun(companyId, {
				lanes: ["footprint", "channels", "owned"],
			});
		},
		onSuccess: async () => {
			message.success("Footprint discovery queued");
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
			await queryClient.invalidateQueries({ queryKey: ["companies"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
			navigate("/runs");
		},
		onError: (error: Error) => message.error(error.message || "Failed to start discovery"),
	});

	const columns: ColumnsType<Company> = [
		{
			title: "Company",
			dataIndex: "name",
			key: "name",
			render: (_, record) => (
				<div className="flex items-center gap-3">
					<div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-blue-200 bg-blue-600/10 text-base font-bold text-blue-600 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
						{record.name?.[0]?.toUpperCase() ?? "C"}
						{record.activity?.active_24h ? (
							<span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-emerald-500 dark:border-slate-900" />
						) : null}
					</div>
					<div className="flex min-w-0 flex-col">
						<button
							type="button"
							className="w-fit text-left font-semibold text-slate-900 transition-colors hover:text-blue-600 dark:text-slate-100 dark:hover:text-blue-400"
							onClick={() => navigate(`/companies/${record.id}`)}
						>
							{record.name}
						</button>
						{record.official_domain ? (
							<a
								href={`https://${record.official_domain.replace(/^https?:\/\//, "")}`}
								target="_blank"
								rel="noreferrer"
								className="inline-flex items-center gap-1 font-mono text-xs text-slate-500 hover:text-blue-500"
							>
								<Globe className="h-3 w-3" />
								{record.official_domain}
								<ExternalLink className="h-2.5 w-2.5 opacity-60" />
							</a>
						) : (
							<span className="font-mono text-xs text-slate-400">No official domain</span>
						)}
					</div>
				</div>
			),
		},
		{
			title: (
				<span className="inline-flex items-center gap-1">
					<Radio className="h-3.5 w-3.5" /> Activity
				</span>
			),
			key: "activity",
			width: 220,
			render: (_, record) => <ActivityCell company={record} />,
		},
		{
			title: "Roles",
			key: "roles",
			width: 150,
			render: (_, record) => (
				<div className="flex flex-wrap gap-1">
					{(record.roles || []).length ? (
						record.roles.map((role) => (
							<Tag key={role} color={roleColor(role)} className="m-0 text-xs">
								{role}
							</Tag>
						))
					) : (
						<span className="text-xs text-slate-400">—</span>
					)}
				</div>
			),
		},
		{
			title: "Industry / Location",
			key: "meta",
			width: 180,
			render: (_, record) => (
				<div className="flex flex-col gap-1">
					{record.industry ? (
						<span className="text-xs text-slate-700 dark:text-slate-300">{record.industry}</span>
					) : (
						<span className="text-xs text-slate-400">—</span>
					)}
					{record.location && (
						<span className="inline-flex items-center gap-1 text-xs text-slate-500">
							<MapPin className="h-3 w-3 text-slate-400" />
							{record.location}
						</span>
					)}
				</div>
			),
		},
		{
			title: "Source",
			dataIndex: "source",
			width: 120,
			render: (value: string, record) => (
				<div className="flex flex-col gap-1">
					<Badge variant="secondary" className="w-fit text-xs">
						{value || "manual"}
					</Badge>
					{record.priority ? (
						<span className="text-[11px] text-slate-500">Priority: {record.priority}</span>
					) : null}
				</div>
			),
		},
		{
			title: "Actions",
			key: "actions",
			align: "right",
			width: 260,
			render: (_, record) => (
				<Space size={6} className="justify-end">
					{(record.tier || "target") === "candidate" && (
						<Button
							size="sm"
							className="bg-emerald-600 font-medium text-white hover:bg-emerald-500"
							disabled={promoteMutation.isPending}
							onClick={() => promoteMutation.mutate({ id: record.id, tier: "target" })}
						>
							<Save className="mr-1 h-3.5 w-3.5" />
							Save
						</Button>
					)}
					{((record.tier || "target") === "target" ||
						(record.tier || "target") === "monitoring") && (
						<Button
							size="sm"
							className="bg-blue-600 font-medium text-white hover:bg-blue-500"
							disabled={runMutation.isPending}
							onClick={() => runMutation.mutate(record.id)}
						>
							<Play className="mr-1 h-3.5 w-3.5" />
							Start discovery
						</Button>
					)}
					<Button size="sm" variant="outline" onClick={() => navigate(`/companies/${record.id}`)}>
						Console
					</Button>
					<Popconfirm
						title="Delete this company?"
						description="Related runs and sources will be removed."
						okText="Delete"
						okButtonProps={{ danger: true }}
						onConfirm={() => deleteMutation.mutate(record.id)}
					>
						<Button size="sm" variant="ghost" className="px-2 text-slate-400 hover:text-rose-600">
							<Trash2 className="h-4 w-4" />
						</Button>
					</Popconfirm>
				</Space>
			),
		},
	];

	return (
		<div className="flex w-full flex-col gap-4">
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
						<Building2 className="h-6 w-6 text-blue-600" />
						Company Directory
					</h1>
					<p className="mt-1 text-sm text-slate-500">
						Candidates are a sorting pool. Save promotes them to Targets. Monitoring means active
						footprint tracking.
					</p>
				</div>
				<Button
					size="lg"
					className="bg-blue-600 font-semibold text-white shadow-xs hover:bg-blue-500"
					onClick={() => setCreateOpen(true)}
				>
					<Plus className="mr-1.5 h-5 w-5" />
					New company
				</Button>
			</div>

			<div className="flex flex-wrap gap-2">
				{TABS.map((tab) => {
					const active = tierTab === tab.key;
					const count = tab.key === "all" ? (tierCounts.all ?? 0) : (tierCounts[tab.key] ?? 0);
					return (
						<button
							key={tab.key}
							type="button"
							onClick={() => setTierTab(tab.key)}
							className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
								active
									? "border-blue-600 bg-blue-600 text-white"
									: "border-slate-200 bg-white text-slate-600 hover:border-blue-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
							}`}
						>
							{tab.label}
							<span className={`ml-2 text-xs ${active ? "text-blue-100" : "text-slate-400"}`}>
								{count}
							</span>
						</button>
					);
				})}
			</div>

			<div className="grid grid-cols-2 gap-3 md:grid-cols-4">
				<div className="rounded-xl border border-emerald-200/80 bg-emerald-50/60 px-4 py-3 dark:border-emerald-900 dark:bg-emerald-950/20">
					<div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
						<span className="relative flex h-2 w-2">
							<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" />
							<span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
						</span>
						Live now
					</div>
					<div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900 dark:text-slate-50">
						{pulseSummary.live}
					</div>
					<div className="text-xs text-slate-500">active in last 24h</div>
				</div>
				<div className="rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950">
					<div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
						<Activity className="h-3.5 w-3.5" /> Today
					</div>
					<div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900 dark:text-slate-50">
						{pulseSummary.today}
					</div>
					<div className="text-xs text-slate-500">new signals in view</div>
				</div>
				<div className="rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950">
					<div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Covered</div>
					<div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900 dark:text-slate-50">
						{pulseSummary.withSignals}
					</div>
					<div className="text-xs text-slate-500">companies with signals</div>
				</div>
				<div className="rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950">
					<div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Shown</div>
					<div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900 dark:text-slate-50">
						{filteredCompanies.length}
					</div>
					<div className="text-xs text-slate-500">
						{dataUpdatedAt ? `synced ${relativeTime(new Date(dataUpdatedAt).toISOString())}` : "loading"}
					</div>
				</div>
			</div>

			<div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_1fr]">
				<Card className="h-fit border-slate-200 shadow-xs dark:border-slate-800">
					<CardContent className="flex flex-col gap-4 p-4">
						<div>
							<div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
								Search
							</div>
							<Input
								placeholder="Name or domain"
								prefix={<Search className="mr-1 h-4 w-4 text-slate-400" />}
								value={searchText}
								onChange={(e) => setSearchText(e.target.value)}
								allowClear
							/>
						</div>
						<div>
							<div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
								Role
							</div>
							<Select
								value={selectedRole}
								onChange={setSelectedRole}
								className="w-full"
								options={ROLE_OPTIONS}
							/>
						</div>
						<div>
							<div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
								Source
							</div>
							<Select
								value={selectedSource}
								onChange={setSelectedSource}
								className="w-full"
								options={[
									{ value: "ALL", label: "All Sources" },
									...sources.map((s) => ({ value: s, label: s })),
								]}
							/>
						</div>
						<label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
							<input
								type="checkbox"
								checked={sortLiveFirst}
								onChange={(e) => setSortLiveFirst(e.target.checked)}
								className="rounded border-slate-300"
							/>
							Sort live activity first
						</label>
						<Button
							variant="outline"
							size="sm"
							onClick={() => {
								setSearchText("");
								setSelectedRole("ALL");
								setSelectedSource("ALL");
							}}
						>
							Clear filters
						</Button>
					</CardContent>
				</Card>

				<Card className="overflow-hidden border-slate-200 shadow-xs dark:border-slate-800">
					<CardContent className="p-0">
						<div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-800">
							<span className="text-sm font-medium text-slate-700 dark:text-slate-200">
								{tierTab === "candidate"
									? "Candidate pool"
									: tierTab === "target"
										? "Saved targets"
										: tierTab === "monitoring"
											? "Active monitoring"
											: "All companies"}
							</span>
							<div className="flex items-center gap-3 text-xs text-slate-500">
								<span className="inline-flex items-center gap-1">
									<span
										className={`h-1.5 w-1.5 rounded-full ${isRefetching ? "animate-pulse bg-emerald-500" : "bg-slate-300"}`}
									/>
									refresh on change
								</span>
								<span>{filteredCompanies.length} shown</span>
							</div>
						</div>
						{isError ? (
							<div className="p-12 text-center">
								<Empty description="Failed to load companies" image={Empty.PRESENTED_IMAGE_SIMPLE}>
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
								dataSource={filteredCompanies}
								pagination={{ pageSize: 12, showSizeChanger: true }}
								locale={{
									emptyText: (
										<Empty
											image={Empty.PRESENTED_IMAGE_SIMPLE}
											description={
												tierTab === "candidate"
													? "No candidates yet. Run: make sync-expomind"
													: "No companies in this tier."
											}
										/>
									),
								}}
								scroll={{ x: 1100 }}
							/>
						)}
					</CardContent>
				</Card>
			</div>

			<Modal
				title={
					<div className="flex items-center gap-2 text-base font-bold text-slate-900">
						<Building2 className="h-5 w-5 text-blue-600" />
						Create Target Company
					</div>
				}
				open={createOpen}
				onCancel={() => setCreateOpen(false)}
				okText="Save company"
				okButtonProps={{
					htmlType: "submit",
					form: "company-form",
					loading: createMutation.isPending,
					className: "bg-blue-600 hover:bg-blue-500",
				}}
				destroyOnClose
				width={580}
			>
				<p className="mb-4 text-xs text-slate-500">
					Manual creates are saved directly as Targets (L2) and scaffold an OpenClaw agent.
				</p>
				<CompanyForm
					onSubmit={(company) =>
						createMutation.mutate({
							...company,
							tier: "target",
							roles: company.roles?.length ? company.roles : [],
							source: "manual",
						})
					}
				/>
			</Modal>
		</div>
	);
}
