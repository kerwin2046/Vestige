import vestigeService from "@/api/services/vestigeService";
import type { Channel } from "@/types/vestige";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import { Card, CardContent } from "@/ui/card";
import { useQuery } from "@tanstack/react-query";
import { Empty, Input, Radio, Select, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
	Building2,
	ExternalLink,
	Globe,
	Landmark,
	RadioTower,
	Search,
	Users,
} from "lucide-react";
import { useMemo, useState } from "react";

export default function ChannelsPage() {
	const [kind, setKind] = useState<"all" | "platform" | "association">("all");
	const [searchText, setSearchText] = useState("");
	const [industry, setIndustry] = useState("ALL");
	const [country, setCountry] = useState("ALL");

	const statsQuery = useQuery({
		queryKey: ["channel-stats"],
		queryFn: vestigeService.getChannelStats,
	});

	const channelsQuery = useQuery({
		queryKey: ["channels", kind],
		queryFn: () =>
			vestigeService.listChannels({
				kind: kind === "all" ? undefined : kind,
				limit: 1000,
			}),
	});

	const channels = channelsQuery.data ?? [];

	const industries = useMemo(() => {
		const set = new Set<string>();
		channels.forEach((c) => {
			if (c.industry) set.add(c.industry);
		});
		return Array.from(set).sort();
	}, [channels]);

	const countries = useMemo(() => {
		const set = new Set<string>();
		channels.forEach((c) => {
			if (c.country) set.add(c.country);
		});
		return Array.from(set).sort();
	}, [channels]);

	const filtered = useMemo(() => {
		const q = searchText.trim().toLowerCase();
		return channels.filter((c) => {
			const matchesSearch =
				!q ||
				c.name.toLowerCase().includes(q) ||
				c.domain.toLowerCase().includes(q) ||
				c.channel_type.toLowerCase().includes(q);
			const matchesIndustry = industry === "ALL" || c.industry === industry;
			const matchesCountry = country === "ALL" || c.country === country;
			return matchesSearch && matchesIndustry && matchesCountry;
		});
	}, [channels, searchText, industry, country]);

	const columns: ColumnsType<Channel> = [
		{
			title: "Channel",
			key: "name",
			render: (_, record) => (
				<div className="flex items-center gap-3">
					<div
						className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border text-sm font-bold ${
							record.kind === "association"
								? "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-900"
								: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-900"
						}`}
					>
						{record.kind === "association" ? (
							<Landmark className="h-4 w-4" />
						) : (
							<Globe className="h-4 w-4" />
						)}
					</div>
					<div className="min-w-0">
						<div className="font-semibold text-slate-900 dark:text-slate-100 truncate">
							{record.name}
						</div>
						{record.url ? (
							<a
								href={record.url.startsWith("http") ? record.url : `https://${record.domain || record.url}`}
								target="_blank"
								rel="noreferrer"
								className="inline-flex items-center gap-1 text-xs font-mono text-slate-500 hover:text-blue-600"
							>
								{record.domain || record.url}
								<ExternalLink className="h-3 w-3 opacity-60" />
							</a>
						) : (
							<span className="text-xs font-mono text-slate-400">{record.domain || "—"}</span>
						)}
					</div>
				</div>
			),
		},
		{
			title: "Kind",
			dataIndex: "kind",
			width: 130,
			render: (value: string) =>
				value === "association" ? (
					<Tag color="gold">Association</Tag>
				) : (
					<Tag color="blue">Platform</Tag>
				),
		},
		{
			title: "Type / Industry",
			key: "meta",
			width: 220,
			render: (_, record) => (
				<div className="flex flex-col gap-1">
					{record.channel_type ? (
						<span className="text-xs text-slate-700 dark:text-slate-300">{record.channel_type}</span>
					) : (
						<span className="text-xs text-slate-400">—</span>
					)}
					{record.industry ? (
						<span className="inline-flex items-center gap-1 text-xs text-slate-500">
							<Building2 className="h-3 w-3" />
							{record.industry}
						</span>
					) : null}
				</div>
			),
		},
		{
			title: "Country",
			dataIndex: "country",
			width: 140,
			render: (value: string) => value || "—",
		},
		{
			title: "Score",
			dataIndex: "score",
			width: 90,
			render: (score: number) => (
				<span className="font-mono text-xs font-semibold">
					{Number(score || 0).toFixed(2)}
				</span>
			),
		},
		{
			title: "Directory",
			dataIndex: "has_member_directory",
			width: 110,
			render: (value: number) =>
				value ? (
					<Badge variant="success" className="inline-flex items-center gap-1">
						<Users className="h-3 w-3" />
						Yes
					</Badge>
				) : (
					<span className="text-xs text-slate-400">—</span>
				),
		},
	];

	const stats = statsQuery.data;

	return (
		<div className="flex w-full flex-col gap-6">
			<div className="flex flex-col gap-2">
				<h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
					<RadioTower className="h-6 w-6 text-blue-600" />
					Discovery Channels
				</h1>
				<p className="text-sm text-slate-500 max-w-3xl">
					B2B platforms and industry associations used as channel seeds for company footprint discovery.
					These are not target companies — they are places to look for companies.
				</p>
			</div>

			<div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
				<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
					<CardContent className="p-4">
						<div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Channels</div>
						<div className="mt-2 text-2xl font-bold">{stats?.total ?? "—"}</div>
					</CardContent>
				</Card>
				<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
					<CardContent className="p-4">
						<div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Platforms</div>
						<div className="mt-2 text-2xl font-bold">{stats?.platform_count ?? "—"}</div>
					</CardContent>
				</Card>
				<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
					<CardContent className="p-4">
						<div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Associations</div>
						<div className="mt-2 text-2xl font-bold">{stats?.association_count ?? "—"}</div>
					</CardContent>
				</Card>
				<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
					<CardContent className="p-4">
						<div className="text-xs font-semibold uppercase tracking-wider text-slate-500">With Member Directory</div>
						<div className="mt-2 text-2xl font-bold">{stats?.with_member_directory ?? "—"}</div>
					</CardContent>
				</Card>
			</div>

			<Card className="border-slate-200 dark:border-slate-800 shadow-xs">
				<CardContent className="p-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
					<div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center">
						<Radio.Group
							value={kind}
							onChange={(e) => setKind(e.target.value)}
							buttonStyle="solid"
							optionType="button"
							options={[
								{ label: "All", value: "all" },
								{ label: "Platforms", value: "platform" },
								{ label: "Associations", value: "association" },
							]}
						/>
						<Input
							placeholder="Search name, domain, type..."
							prefix={<Search className="h-4 w-4 text-slate-400 mr-1" />}
							value={searchText}
							onChange={(e) => setSearchText(e.target.value)}
							allowClear
							className="max-w-md"
						/>
						<Select
							value={industry}
							onChange={setIndustry}
							className="w-44"
							options={[
								{ value: "ALL", label: "All Industries" },
								...industries.map((item) => ({ value: item, label: item })),
							]}
						/>
						<Select
							value={country}
							onChange={setCountry}
							className="w-44"
							options={[
								{ value: "ALL", label: "All Countries" },
								...countries.map((item) => ({ value: item, label: item })),
							]}
						/>
					</div>
					<div className="text-xs text-slate-500">
						Showing <span className="font-semibold text-slate-700 dark:text-slate-300">{filtered.length}</span> channels
					</div>
				</CardContent>
			</Card>

			<Card className="border-slate-200 dark:border-slate-800 shadow-xs overflow-hidden">
				<CardContent className="p-0">
					{channelsQuery.isError ? (
						<div className="p-12 text-center">
							<Empty description="Failed to load channels" image={Empty.PRESENTED_IMAGE_SIMPLE}>
								<Button variant="outline" onClick={() => channelsQuery.refetch()}>
									Retry
								</Button>
							</Empty>
						</div>
					) : (
						<Table
							rowKey="id"
							size="middle"
							loading={channelsQuery.isLoading}
							columns={columns}
							dataSource={filtered}
							pagination={{ pageSize: 20, showSizeChanger: true }}
							locale={{
								emptyText: (
									<Empty
										image={Empty.PRESENTED_IMAGE_SIMPLE}
										description="No channels yet. Run: make import-b2b"
									/>
								),
							}}
							scroll={{ x: 1000 }}
						/>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
