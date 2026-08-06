import vestigeService from "@/api/services/vestigeService";
import type { IntelStream } from "@/types/vestige";
import { Badge } from "@/ui/badge";
import { Button } from "@/ui/button";
import { Card, CardContent } from "@/ui/card";
import { useQuery } from "@tanstack/react-query";
import { Empty, Input, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Activity, Flame, Radio, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { ActivitySparkCard } from "../components/activity-spark-card";
import { formatDateTime } from "../components/run-status";

function isActive24h(value: string | null | undefined) {
	if (!value) return false;
	const ts = Date.parse(value);
	if (Number.isNaN(ts)) return false;
	return Date.now() - ts <= 24 * 60 * 60 * 1000;
}

function StreamActivityCell({ stream }: { stream: IntelStream }) {
	const activity = stream.activity;
	const total = activity?.total_signals ?? stream.signal_count ?? 0;
	const new24h = activity?.new_24h ?? stream.signals_today ?? 0;
	const live = activity?.active_24h ?? isActive24h(stream.last_signal_at);
	const level = activity?.activity_level ?? (live ? (new24h > 0 ? "low" : "quiet") : "quiet");
	return (
		<ActivitySparkCard
			total={total}
			newCount24h={new24h}
			lastSignalAt={activity?.last_signal_at ?? stream.last_signal_at}
			active24h={live}
			level={level}
		/>
	);
}

export default function StreamsPage() {
	const navigate = useNavigate();
	const [searchText, setSearchText] = useState("");
	const [sortLiveFirst, setSortLiveFirst] = useState(true);

	const streamsQuery = useQuery({
		queryKey: ["streams"],
		queryFn: () => vestigeService.listStreams({ status: "active" }),
		refetchInterval: 15_000,
		refetchOnWindowFocus: true,
	});

	const streams = streamsQuery.data ?? [];
	const filteredStreams = useMemo(() => {
		const q = searchText.trim().toLowerCase();
		const rows = streams.filter((stream) => {
			if (!q) return true;
			return (
				stream.name.toLowerCase().includes(q) ||
				stream.slug.toLowerCase().includes(q) ||
				(stream.description || "").toLowerCase().includes(q)
			);
		});
		if (!sortLiveFirst) return rows;
		return [...rows].sort((a, b) => {
			const aLive = a.activity?.active_24h ?? isActive24h(a.last_signal_at) ? 1 : 0;
			const bLive = b.activity?.active_24h ?? isActive24h(b.last_signal_at) ? 1 : 0;
			if (aLive !== bLive) return bLive - aLive;
			const aNew24h = a.activity?.new_24h ?? a.signals_today ?? 0;
			const bNew24h = b.activity?.new_24h ?? b.signals_today ?? 0;
			if (aNew24h !== bNew24h) {
				return bNew24h - aNew24h;
			}
			const aLast = Date.parse(a.activity?.last_signal_at ?? a.last_signal_at ?? "");
			const bLast = Date.parse(b.activity?.last_signal_at ?? b.last_signal_at ?? "");
			if (!Number.isNaN(aLast) && !Number.isNaN(bLast) && aLast !== bLast) return bLast - aLast;
			return (b.activity?.total_signals ?? b.signal_count ?? 0) - (a.activity?.total_signals ?? a.signal_count ?? 0);
		});
	}, [streams, searchText, sortLiveFirst]);

	const pulseSummary = useMemo(() => {
		const live = filteredStreams.filter((s) => s.activity?.active_24h ?? isActive24h(s.last_signal_at)).length;
		const covered = filteredStreams.filter((s) => (s.activity?.total_signals ?? s.signal_count ?? 0) > 0).length;
		const today = filteredStreams.reduce((sum, s) => sum + (s.activity?.new_24h ?? s.signals_today ?? 0), 0);
		return { live, covered, today };
	}, [filteredStreams]);

	const columns: ColumnsType<IntelStream> = [
		{
			title: "Stream",
			key: "name",
			render: (_, record) => (
				<button
					type="button"
					className="flex items-center gap-3 text-left"
					onClick={() => navigate(`/streams/${record.slug}`)}
				>
					<div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900 dark:bg-orange-950/40 dark:text-orange-400">
						<Flame className="h-4 w-4" />
					</div>
					<div className="min-w-0">
						<div className="font-semibold text-slate-900 dark:text-slate-100">
							{record.name}
						</div>
						<div className="truncate text-xs text-slate-500">{record.description || record.slug}</div>
					</div>
				</button>
			),
		},
		{
			title: (
				<span className="inline-flex items-center gap-1">
					<Radio className="h-3.5 w-3.5" /> Activity
				</span>
			),
			key: "activity",
			width: 240,
			render: (_, record) => <StreamActivityCell stream={record} />,
		},
		{
			title: "Kind",
			dataIndex: "kind",
			width: 140,
			render: (value: string) => <Tag color="orange">{value}</Tag>,
		},
		{
			title: "Last signal",
			dataIndex: "last_signal_at",
			width: 180,
			render: (value: string | null) =>
				value ? formatDateTime(value) : <span className="text-slate-400">—</span>,
		},
		{
			title: "Agent",
			dataIndex: "agent_slug",
			width: 160,
			render: (value: string) => (
				<span className="font-mono text-xs text-slate-500">{value || "—"}</span>
			),
		},
	];

	return (
		<div className="space-y-4">
			<div className="flex items-end justify-between gap-4">
				<div>
					<h1 className="flex items-center gap-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
						<Radio className="h-5 w-5 text-orange-600" />
						Intel Streams
					</h1>
					<p className="mt-1 text-sm text-slate-500">
						Market lenses — industry social heat, not companies
					</p>
				</div>
				<Badge variant="secondary">{streams.length} active</Badge>
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
						{pulseSummary.covered}
					</div>
					<div className="text-xs text-slate-500">streams with signals</div>
				</div>
				<div className="rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-950">
					<div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Shown</div>
					<div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900 dark:text-slate-50">
						{filteredStreams.length}
					</div>
					<div className="text-xs text-slate-500">live-sorted</div>
				</div>
			</div>

			<Card className="border-slate-200 shadow-xs dark:border-slate-800">
				<CardContent className="p-0">
					<div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3 dark:border-slate-800">
						<div className="flex flex-wrap items-center gap-2">
							<Input
								placeholder="Search stream"
								prefix={<Search className="mr-1 h-4 w-4 text-slate-400" />}
								value={searchText}
								onChange={(e) => setSearchText(e.target.value)}
								allowClear
								className="w-[220px]"
							/>
							<label className="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
								<input
									type="checkbox"
									checked={sortLiveFirst}
									onChange={(e) => setSortLiveFirst(e.target.checked)}
									className="rounded border-slate-300"
								/>
								Sort live first
							</label>
						</div>
						<Button
							variant="outline"
							size="sm"
							onClick={() => {
								setSearchText("");
								setSortLiveFirst(true);
							}}
						>
							Clear filters
						</Button>
					</div>
					{streamsQuery.isLoading ? (
						<p className="p-8 text-center text-sm text-slate-400">Loading streams…</p>
					) : filteredStreams.length === 0 ? (
						<div className="p-8">
							<Empty
								description={
									streams.length === 0
										? "No streams yet. Run make migrate-mfg-stream to seed Manufacturing Social Pulse."
										: "No streams match your filters."
								}
								image={Empty.PRESENTED_IMAGE_SIMPLE}
							/>
						</div>
					) : (
						<Table
							rowKey="id"
							columns={columns}
							dataSource={filteredStreams}
							pagination={false}
							onRow={(record) => ({
								onClick: () => navigate(`/streams/${record.slug}`),
								className: "cursor-pointer",
							})}
						/>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
