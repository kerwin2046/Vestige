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
	message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
	Building2,
	ExternalLink,
	Globe,
	MapPin,
	Play,
	Plus,
	Save,
	Search,
	Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { formatDateTime } from "../components/run-status";
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

export default function CompaniesPage() {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [createOpen, setCreateOpen] = useState(false);
	const [tierTab, setTierTab] = useState<CompanyTier | "all">("target");
	const [searchText, setSearchText] = useState("");
	const [selectedRole, setSelectedRole] = useState("ALL");
	const [selectedSource, setSelectedSource] = useState("ALL");

	const { data = [], isLoading, isError, refetch } = useQuery({
		queryKey: ["companies", tierTab],
		queryFn: () =>
			vestigeService.listCompanies({
				tier: tierTab === "all" ? undefined : tierTab,
			}),
	});

	const countsQuery = useQuery({
		queryKey: ["companies", "all-for-counts"],
		queryFn: () => vestigeService.listCompanies(),
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
		return data.filter((company) => {
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
	}, [data, searchText, selectedRole, selectedSource]);

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
					<div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-600/10 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 font-bold text-base border border-blue-200 dark:border-blue-800">
						{record.name?.[0]?.toUpperCase() ?? "C"}
					</div>
					<div className="flex flex-col min-w-0">
						<button
							type="button"
							className="w-fit text-left font-semibold text-slate-900 hover:text-blue-600 dark:text-slate-100 dark:hover:text-blue-400 transition-colors"
							onClick={() => navigate(`/companies/${record.id}`)}
						>
							{record.name}
						</button>
						{record.official_domain ? (
							<a
								href={`https://${record.official_domain.replace(/^https?:\/\//, "")}`}
								target="_blank"
								rel="noreferrer"
								className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-blue-500 font-mono"
							>
								<Globe className="h-3 w-3" />
								{record.official_domain}
								<ExternalLink className="h-2.5 w-2.5 opacity-60" />
							</a>
						) : (
							<span className="text-xs text-slate-400 font-mono">No official domain</span>
						)}
					</div>
				</div>
			),
		},
		{
			title: "Roles",
			key: "roles",
			width: 200,
			render: (_, record) => (
				<div className="flex flex-wrap gap-1">
					{(record.roles || []).length ? (
						record.roles.map((role) => (
							<Tag key={role} color={roleColor(role)} className="text-xs m-0">
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
			width: 200,
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
			title: "Updated",
			dataIndex: "updated_at",
			width: 160,
			render: (val) => (
				<span className="text-xs text-slate-500 font-mono">{formatDateTime(val)}</span>
			),
		},
		{
			title: "Actions",
			key: "actions",
			align: "right",
			width: 280,
			render: (_, record) => (
				<Space size={6} className="justify-end">
					{(record.tier || "target") === "candidate" && (
						<Button
							size="sm"
							className="bg-emerald-600 hover:bg-emerald-500 text-white font-medium"
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
							className="bg-blue-600 hover:bg-blue-500 text-white font-medium"
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
						<Button size="sm" variant="ghost" className="text-slate-400 hover:text-rose-600 px-2">
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
					<h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
						<Building2 className="h-6 w-6 text-blue-600" />
						Company Directory
					</h1>
					<p className="mt-1 text-sm text-slate-500">
						Candidates are a sorting pool. Save promotes them to Targets. Monitoring means active footprint tracking.
					</p>
				</div>
				<Button
					size="lg"
					className="bg-blue-600 hover:bg-blue-500 text-white shadow-xs font-semibold"
					onClick={() => setCreateOpen(true)}
				>
					<Plus className="mr-1.5 h-5 w-5" />
					New company
				</Button>
			</div>

			{/* Tier tabs like Apollo Total / Saved */}
			<div className="flex flex-wrap gap-2">
				{TABS.map((tab) => {
					const active = tierTab === tab.key;
					const count = tab.key === "all" ? tierCounts.all ?? 0 : tierCounts[tab.key] ?? 0;
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

			<div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_1fr]">
				{/* Left filters */}
				<Card className="border-slate-200 dark:border-slate-800 shadow-xs h-fit">
					<CardContent className="p-4 flex flex-col gap-4">
						<div>
							<div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
								Search
							</div>
							<Input
								placeholder="Name or domain"
								prefix={<Search className="h-4 w-4 text-slate-400 mr-1" />}
								value={searchText}
								onChange={(e) => setSearchText(e.target.value)}
								allowClear
							/>
						</div>
						<div>
							<div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
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
							<div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
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

				{/* Table */}
				<Card className="border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
					<CardContent className="p-0">
						<div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 px-4 py-3">
							<span className="text-sm font-medium text-slate-700 dark:text-slate-200">
								{tierTab === "candidate"
									? "Candidate pool"
									: tierTab === "target"
										? "Saved targets"
										: tierTab === "monitoring"
											? "Active monitoring"
											: "All companies"}
							</span>
							<span className="text-xs text-slate-500">
								{filteredCompanies.length} shown
							</span>
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
								scroll={{ x: 1000 }}
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
				<p className="text-xs text-slate-500 mb-4">
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
