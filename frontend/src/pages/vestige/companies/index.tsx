import vestigeService from "@/api/services/vestigeService";
import { Icon } from "@/components/icon";
import type { Company } from "@/types/vestige";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader } from "@/ui/card";
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
	Typography,
	message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import {
	Bot,
	Building2,
	ExternalLink,
	Globe,
	MapPin,
	Play,
	Plus,
	Search,
	Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { formatDateTime } from "../components/run-status";
import CompanyForm from "./company-form";

export default function CompaniesPage() {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [createOpen, setCreateOpen] = useState(false);
	const [searchText, setSearchText] = useState("");
	const [selectedIndustry, setSelectedIndustry] = useState<string>("ALL");

	const { data = [], isLoading, isError, refetch } = useQuery({
		queryKey: ["companies"],
		queryFn: vestigeService.listCompanies,
	});

	const createMutation = useMutation({
		mutationFn: vestigeService.createCompany,
		onSuccess: async (company) => {
			const agentHint = company.agent_path
				? ` · agent: ${company.agent_path}`
				: "";
			message.success(`Company created successfully${agentHint}`);
			setCreateOpen(false);
			await queryClient.invalidateQueries({ queryKey: ["companies"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to create company"),
	});

	const deleteMutation = useMutation({
		mutationFn: vestigeService.deleteCompany,
		onSuccess: async () => {
			message.success("Company target removed");
			await queryClient.invalidateQueries({ queryKey: ["companies"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to delete company"),
	});

	const runMutation = useMutation({
		mutationFn: (companyId: string) => vestigeService.createRun(companyId, {}),
		onSuccess: async () => {
			message.success("Footprint discovery run queued");
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
			navigate("/runs");
		},
		onError: (error: Error) => message.error(error.message || "Failed to start discovery"),
	});

	// Extract unique industries for filtering
	const industries = useMemo(() => {
		const set = new Set<string>();
		data.forEach((c) => {
			if (c.industry) set.add(c.industry);
		});
		return Array.from(set);
	}, [data]);

	// Filter companies by search query and industry
	const filteredCompanies = useMemo(() => {
		return data.filter((company) => {
			const matchesSearch =
				!searchText ||
				company.name.toLowerCase().includes(searchText.toLowerCase()) ||
				(company.official_domain &&
					company.official_domain.toLowerCase().includes(searchText.toLowerCase()));

			const matchesIndustry =
				selectedIndustry === "ALL" || company.industry === selectedIndustry;

			return matchesSearch && matchesIndustry;
		});
	}, [data, searchText, selectedIndustry]);

	const columns: ColumnsType<Company> = [
		{
			title: "Target Company",
			dataIndex: "name",
			key: "name",
			render: (_, record) => (
				<div className="flex items-center gap-3">
					<div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-600/10 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 font-bold text-base border border-blue-200 dark:border-blue-800">
						{record.name?.[0]?.toUpperCase() ?? "C"}
					</div>
					<div className="flex flex-col">
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
			title: "Industry & Location",
			key: "meta",
			width: 220,
			render: (_, record) => (
				<div className="flex flex-col gap-1">
					{record.industry ? (
						<Tag color="blue" className="w-fit text-xs font-medium">
							{record.industry}
						</Tag>
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
			title: "OpenClaw Agent",
			key: "agent",
			width: 180,
			render: (_, record) => (
				<Tooltip title={record.agent_path ? `Scaffolded at ${record.agent_path}` : "Daily automated crawling agent"}>
					<span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
						<Bot className="h-3.5 w-3.5 text-blue-500" />
						{record.agent_path ? "Active Agent" : "Ready to Scaffold"}
					</span>
				</Tooltip>
			),
		},
		{
			title: "Last Updated",
			dataIndex: "updated_at",
			key: "updated_at",
			width: 170,
			render: (val) => (
				<span className="text-xs text-slate-500 dark:text-slate-400 font-mono">
					{formatDateTime(val)}
				</span>
			),
		},
		{
			title: "Actions",
			key: "actions",
			align: "right",
			width: 260,
			render: (_, record) => (
				<Space size={6} className="justify-end">
					<Button
						size="sm"
						className="bg-blue-600 hover:bg-blue-500 text-white font-medium"
						disabled={runMutation.isPending}
						onClick={() => runMutation.mutate(record.id)}
					>
						<Play className="mr-1 h-3.5 w-3.5" />
						Start discovery
					</Button>
					<Button
						size="sm"
						variant="outline"
						onClick={() => navigate(`/companies/${record.id}`)}
					>
						Console
					</Button>
					<Popconfirm
						title="Delete target company?"
						description="This will permanently delete the company and its discovery history."
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
		<div className="flex w-full flex-col gap-6">
			{/* Page Header */}
			<div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
						<Building2 className="h-6 w-6 text-blue-600" />
						Target Company Directory
					</h1>
					<p className="mt-1 text-sm text-slate-500">
						Manage corporate identity anchors, configure discovery parameters, and spawn automated OpenClaw monitoring agents.
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

			{/* Search & Filter Toolbar */}
			<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
				<CardContent className="p-4 flex flex-col sm:flex-row items-center gap-3 justify-between">
					<div className="flex flex-1 items-center gap-3 w-full">
						<Input
							placeholder="Search by company name or domain..."
							prefix={<Search className="h-4 w-4 text-slate-400 mr-1" />}
							value={searchText}
							onChange={(e) => setSearchText(e.target.value)}
							allowClear
							className="max-w-md h-9"
						/>
						<Select
							value={selectedIndustry}
							onChange={setSelectedIndustry}
							className="w-48 h-9"
							options={[
								{ value: "ALL", label: "All Industries" },
								...industries.map((ind) => ({ value: ind, label: ind })),
							]}
						/>
					</div>
					<div className="text-xs text-slate-500 whitespace-nowrap">
						Showing <span className="font-semibold text-slate-700 dark:text-slate-300">{filteredCompanies.length}</span> of {data.length} targets
					</div>
				</CardContent>
			</Card>

			{/* Company Table */}
			<Card className="border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
				<CardContent className="p-0">
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
										description="No company targets found matching criteria."
									/>
								),
							}}
							scroll={{ x: 1000 }}
						/>
					)}
				</CardContent>
			</Card>

			{/* Create Company Modal */}
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
					Adding a target company automatically generates its official identity anchors and initializes an OpenClaw daily crawler agent.
				</p>
				<CompanyForm onSubmit={(company) => createMutation.mutate(company)} />
			</Modal>
		</div>
	);
}
