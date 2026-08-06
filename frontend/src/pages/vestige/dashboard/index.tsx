import vestigeService from "@/api/services/vestigeService";
import { Chart, useChart } from "@/components/chart";
import type { DashboardSignal, DiscoveryRun, SignalSeriesPoint } from "@/types/vestige";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { useQuery } from "@tanstack/react-query";
import { Alert, Checkbox, Empty, Select } from "antd";
import {
	ArrowRight,
	Building2,
	ExternalLink,
	RefreshCw,
	Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { formatDateTime } from "../components/run-status";

const READ_KEY = "vestige.pulse.readIds";

const AVATAR_COLORS = [
	"bg-rose-500",
	"bg-emerald-600",
	"bg-sky-600",
	"bg-amber-500",
	"bg-teal-600",
	"bg-indigo-500",
	"bg-orange-500",
	"bg-cyan-600",
];

function labelSourceType(value: string) {
	return value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function relativeTime(value: string | null | undefined) {
	if (!value) return "—";
	const ts = Date.parse(value);
	if (Number.isNaN(ts)) return formatDateTime(value);
	const delta = Date.now() - ts;
	const minutes = Math.floor(delta / 60_000);
	if (minutes < 1) return "just now";
	if (minutes < 60) return `${minutes}m ago`;
	const hours = Math.floor(minutes / 60);
	if (hours < 24) return `${hours}h ago`;
	const days = Math.floor(hours / 24);
	if (days < 7) return `${days}d ago`;
	return formatDateTime(value);
}

function priorityOf(confidence: number): "High" | "Medium" | "Low" {
	if (confidence >= 0.8) return "High";
	if (confidence >= 0.5) return "Medium";
	return "Low";
}

function avatarColor(seed: string) {
	let hash = 0;
	for (let i = 0; i < seed.length; i += 1) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
	return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

function loadReadIds(): Set<string> {
	try {
		const raw = localStorage.getItem(READ_KEY);
		if (!raw) return new Set();
		const parsed = JSON.parse(raw);
		return new Set(Array.isArray(parsed) ? parsed.map(String) : []);
	} catch {
		return new Set();
	}
}

function saveReadIds(ids: Set<string>) {
	localStorage.setItem(READ_KEY, JSON.stringify([...ids].slice(-500)));
}

function isFresh(value: string | null | undefined) {
	if (!value) return false;
	const ts = Date.parse(value);
	if (Number.isNaN(ts)) return false;
	return Date.now() - ts < 24 * 60 * 60 * 1000;
}

function Sparkline({
	values,
	stroke = "#22c55e",
}: {
	values: number[];
	stroke?: string;
}) {
	const width = 88;
	const height = 28;
	if (!values.length) {
		return <svg width={width} height={height} aria-hidden />;
	}
	const max = Math.max(...values, 1);
	const min = Math.min(...values, 0);
	const span = Math.max(max - min, 1);
	const points = values
		.map((value, index) => {
			const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
			const y = height - ((value - min) / span) * (height - 4) - 2;
			return `${x},${y}`;
		})
		.join(" ");
	return (
		<svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
			<polyline fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" points={points} />
		</svg>
	);
}

function MetricCard({
	label,
	value,
	hint,
	series,
	stroke,
	loading,
}: {
	label: string;
	value: string | number;
	hint: string;
	series: number[];
	stroke: string;
	loading?: boolean;
}) {
	return (
		<div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)] dark:border-slate-800 dark:bg-slate-950">
			<div className="flex items-start justify-between gap-3">
				<div>
					<div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
						{label}
					</div>
					<div className="mt-1 text-[28px] font-semibold leading-none tracking-tight text-slate-900 dark:text-slate-50">
						{loading ? "—" : value}
					</div>
					<div className="mt-2 text-xs text-slate-500">{hint}</div>
				</div>
				<Sparkline values={series} stroke={stroke} />
			</div>
		</div>
	);
}

function PriorityChip({ level }: { level: "High" | "Medium" | "Low" }) {
	const styles =
		level === "High"
			? "bg-emerald-50 text-emerald-700 ring-emerald-200"
			: level === "Medium"
				? "bg-amber-50 text-amber-700 ring-amber-200"
				: "bg-slate-100 text-slate-600 ring-slate-200";
	return (
		<span className={`inline-flex rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${styles}`}>
			{level}
		</span>
	);
}

function SignalRow({
	item,
	unread,
	onOpenCompany,
	onOpenSignal,
}: {
	item: DashboardSignal;
	unread: boolean;
	onOpenCompany: (id: string) => void;
	onOpenSignal: (id: string) => void;
}) {
	const companyName = item.company?.name ?? "Unknown company";
	const title = item.title?.trim() || item.url;
	const priority =
		(item.priority as "High" | "Medium" | "Low" | undefined) ||
		priorityOf(item.confidence ?? 0);
	const themes = Array.isArray(item.detail?.themes)
		? (item.detail?.themes as string[]).slice(0, 2)
		: typeof item.detail?.themes === "string"
			? String(item.detail.themes)
					.split(",")
					.map((t) => t.trim())
					.filter(Boolean)
					.slice(0, 2)
			: [];
	const sourceLine = [companyName, item.collector].filter(Boolean).join(" · ");

	return (
		<article
			className={`group flex gap-3 border-b border-slate-100 px-4 py-4 last:border-b-0 hover:bg-slate-50/90 dark:border-slate-800 dark:hover:bg-slate-900/40 ${
				unread ? "bg-emerald-50/30 dark:bg-emerald-950/10" : ""
			}`}
		>
			<button
				type="button"
				onClick={() => onOpenCompany(item.company_id)}
				className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-semibold text-white shadow-sm ${avatarColor(companyName)}`}
				title={companyName}
			>
				{companyName[0]?.toUpperCase() ?? "?"}
			</button>
			<div className="min-w-0 flex-1">
				<div className="flex flex-wrap items-center gap-x-2 gap-y-1">
					<button
						type="button"
						onClick={() => onOpenCompany(item.company_id)}
						className="text-[11px] font-semibold uppercase tracking-wide text-sky-700 hover:text-sky-800 dark:text-sky-400"
					>
						{sourceLine}
					</button>
					{unread ? (
						<span className="rounded-full bg-emerald-500 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-white">
							New
						</span>
					) : null}
					<div className="ml-auto flex items-center gap-2">
						<PriorityChip level={priority} />
						<span className="text-xs text-slate-400">{relativeTime(item.last_seen_at)}</span>
					</div>
				</div>
				<a
					href={item.url}
					target="_blank"
					rel="noreferrer"
					onClick={() => onOpenSignal(item.id)}
					className="mt-1 inline-flex max-w-full items-start gap-1.5 text-[15px] font-semibold leading-snug text-sky-700 hover:text-sky-800 dark:text-sky-400"
				>
					<span className="line-clamp-2">{title}</span>
					<ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0 opacity-40" />
				</a>
				{item.snippet ? (
					<p className="mt-1 line-clamp-2 text-sm leading-relaxed text-slate-500">
						{item.snippet}
					</p>
				) : null}
				<div className="mt-2 flex flex-wrap items-center gap-1.5">
					<span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
						{labelSourceType(item.source_type || "other")}
					</span>
					{themes.map((theme) => (
						<span
							key={theme}
							className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300"
						>
							{theme}
						</span>
					))}
					{item.domain ? (
						<span className="font-mono text-[11px] text-slate-400">{item.domain}</span>
					) : null}
					<span className="ml-auto text-xs font-semibold tabular-nums text-slate-500">
						{Math.round((item.confidence ?? 0) * 100)}%
					</span>
				</div>
			</div>
		</article>
	);
}

export default function DashboardPage() {
	const navigate = useNavigate();
	const [companyFilter, setCompanyFilter] = useState<string>("all");
	const [typeFilter, setTypeFilter] = useState<string>("all");
	const [collectorFilter, setCollectorFilter] = useState<string>("all");
	const [unreadOnly, setUnreadOnly] = useState(false);
	const [readIds, setReadIds] = useState<Set<string>>(() => loadReadIds());
	const [updatedLabel, setUpdatedLabel] = useState("Updated just now");
	const [extraFeed, setExtraFeed] = useState<DashboardSignal[]>([]);
	const [loadingMore, setLoadingMore] = useState(false);
	const [feedMeta, setFeedMeta] = useState<{
		has_more: boolean;
		next_offset: number;
		feed_total: number;
		window_label: string;
	} | null>(null);

	const { data, isLoading, isError, refetch, isRefetching, dataUpdatedAt } = useQuery({
		queryKey: ["dashboard"],
		queryFn: () => vestigeService.getDashboard({ limit: 25, offset: 0 }),
		refetchInterval: 12_000,
	});

	useEffect(() => {
		if (!data?.pulse) return;
		setExtraFeed([]);
		setFeedMeta({
			has_more: data.pulse.has_more,
			next_offset: data.pulse.next_offset,
			feed_total: data.pulse.feed_total,
			window_label: data.pulse.window_label,
		});
	}, [data?.pulse]);

	useEffect(() => {
		if (!dataUpdatedAt) return;
		const tick = () => setUpdatedLabel(`Updated ${relativeTime(new Date(dataUpdatedAt).toISOString())}`);
		tick();
		const id = window.setInterval(tick, 30_000);
		return () => window.clearInterval(id);
	}, [dataUpdatedAt]);

	const mustSee = data?.pulse?.must_see ?? data?.recent_insights ?? [];
	const baseFeed = data?.pulse?.feed ?? [];
	const feed = useMemo(() => [...baseFeed, ...extraFeed], [baseFeed, extraFeed]);
	const filterPool = useMemo(() => [...mustSee, ...feed], [mustSee, feed]);
	const series = data?.signal_series ?? [];
	const activeRuns =
		data?.recent_runs?.filter(
			(r: DiscoveryRun) => r.status === "running" || r.status === "queued",
		) ?? [];

	const companyOptions = useMemo(() => {
		const map = new Map<string, string>();
		for (const item of filterPool) {
			if (item.company_id) map.set(item.company_id, item.company?.name ?? item.company_id.slice(0, 8));
		}
		return [...map.entries()].map(([value, label]) => ({ value, label }));
	}, [filterPool]);

	const typeOptions = useMemo(() => {
		const set = new Set(filterPool.map((item) => item.source_type || "other"));
		return [...set].sort().map((value) => ({ value, label: labelSourceType(value) }));
	}, [filterPool]);

	const collectorOptions = useMemo(() => {
		const set = new Set(filterPool.map((item) => item.collector || "unknown").filter(Boolean));
		return [...set].sort().map((value) => ({ value, label: value }));
	}, [filterPool]);

	const applyFilters = (items: DashboardSignal[]) =>
		items.filter((item) => {
			if (companyFilter !== "all" && item.company_id !== companyFilter) return false;
			if (typeFilter !== "all" && (item.source_type || "other") !== typeFilter) return false;
			if (collectorFilter !== "all" && (item.collector || "unknown") !== collectorFilter) return false;
			if (unreadOnly && (readIds.has(item.id) || !isFresh(item.last_seen_at))) return false;
			return true;
		});

	const filteredMustSee = useMemo(
		() => applyFilters(mustSee),
		[mustSee, companyFilter, typeFilter, collectorFilter, unreadOnly, readIds],
	);
	const filteredFeed = useMemo(
		() => applyFilters(feed),
		[feed, companyFilter, typeFilter, collectorFilter, unreadOnly, readIds],
	);

	const markRead = (id: string) => {
		setReadIds((prev) => {
			const next = new Set(prev);
			next.add(id);
			saveReadIds(next);
			return next;
		});
	};

	const loadMore = async () => {
		if (!feedMeta?.has_more || loadingMore) return;
		setLoadingMore(true);
		try {
			const page = await vestigeService.getDashboardFeed({
				limit: 25,
				offset: feedMeta.next_offset,
			});
			setExtraFeed((prev) => {
				const seen = new Set([...baseFeed, ...prev].map((item) => item.id));
				return [...prev, ...page.feed.filter((item) => !seen.has(item.id))];
			});
			setFeedMeta({
				has_more: page.has_more,
				next_offset: page.next_offset,
				feed_total: page.feed_total,
				window_label: page.window_label,
			});
		} finally {
			setLoadingMore(false);
		}
	};

	const totalsSeries = series.map((point: SignalSeriesPoint) => point.total);
	const todaySeries = series.map((point) => point.total);
	const queueSeries = Array.from({ length: 7 }, (_, i) =>
		i === 6 ? data?.queued_count ?? 0 : 0,
	);
	const shownCount = filteredMustSee.length + filteredFeed.length;
	const windowLabel = feedMeta?.window_label ?? data?.pulse?.window_label ?? "Ranked";

	const trendChart = useChart({
		colors: ["#10b981", "#f59e0b", "#94a3b8"],
		legend: { show: true, position: "top", horizontalAlign: "right" },
		xaxis: {
			categories: series.map((point) => point.day.slice(5)),
			labels: { style: { colors: "#94a3b8", fontSize: "11px" } },
		},
		yaxis: { labels: { style: { colors: "#94a3b8", fontSize: "11px" } } },
		stroke: { curve: "smooth", width: 2 },
		grid: { borderColor: "#f1f5f9", strokeDashArray: 4 },
		tooltip: { shared: true },
	});

	const donutChart = useChart({
		labels: (data?.top_signal_types ?? []).map((item) => labelSourceType(item.key)),
		colors: ["#10b981", "#0ea5e9", "#f59e0b", "#6366f1", "#f43f5e", "#94a3b8"],
		legend: { show: false },
		dataLabels: { enabled: false },
		plotOptions: {
			pie: {
				donut: {
					size: "68%",
					labels: {
						show: true,
						total: {
							show: true,
							label: "Types",
							formatter: () => String(data?.top_signal_types?.length ?? 0),
						},
					},
				},
			},
		},
	});

	return (
		<div className="flex w-full flex-col gap-5">
			<div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
				<div>
					<div className="flex flex-wrap items-center gap-3">
						<h1 className="text-[28px] font-semibold tracking-tight text-slate-900 dark:text-slate-50">
							Competitive Intelligence
						</h1>
						<div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-700 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-900">
							<span className="relative flex h-2 w-2">
								<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" />
								<span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
							</span>
							Live pulse
						</div>
						<span className="text-xs text-slate-400">{updatedLabel}</span>
					</div>
					<p className="mt-1 max-w-2xl text-sm text-slate-500">
						Ranked by recency, confidence, and target priority — not raw chronology.
					</p>
				</div>
				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={() => refetch()}
						disabled={isRefetching}
						className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
					>
						<RefreshCw className={`h-3.5 w-3.5 ${isRefetching ? "animate-spin" : ""}`} />
						Refresh
					</button>
					<Button
						size="sm"
						className="bg-emerald-600 text-white hover:bg-emerald-500"
						onClick={() => navigate("/companies")}
					>
						<Building2 className="mr-2 h-4 w-4" />
						Targets
					</Button>
				</div>
			</div>

			{isError ? (
				<Alert
					type="error"
					showIcon
					message="Failed to load pulse feed"
					action={
						<Button size="sm" variant="outline" onClick={() => refetch()}>
							Retry
						</Button>
					}
				/>
			) : null}

			{activeRuns.length > 0 ? (
				<Alert
					type="info"
					showIcon
					icon={<Zap className="h-4 w-4 text-blue-500" />}
					message={
						<div className="flex items-center justify-between gap-3 font-medium">
							<span>
								{activeRuns.length} discovery job
								{activeRuns.length > 1 ? "s" : ""} in queue or running
							</span>
							<Button
								variant="link"
								size="sm"
								className="h-auto p-0 text-blue-600"
								onClick={() => navigate("/runs")}
							>
								View runs <ArrowRight className="ml-1 h-3.5 w-3.5" />
							</Button>
						</div>
					}
					className="border-blue-200 bg-blue-50/70 dark:border-blue-900 dark:bg-blue-950/30"
				/>
			) : null}

			<div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
				<MetricCard
					label="Today"
					value={data?.signals_today ?? 0}
					hint="signals seen today"
					series={todaySeries}
					stroke="#22c55e"
					loading={isLoading}
				/>
				<MetricCard
					label="Ledger"
					value={data?.signal_count ?? 0}
					hint="company signals total"
					series={totalsSeries}
					stroke="#0ea5e9"
					loading={isLoading}
				/>
				<MetricCard
					label="Targets"
					value={data?.company_count ?? 0}
					hint="companies monitored"
					series={[Math.max(0, (data?.company_count ?? 0) - 3), data?.company_count ?? 0]}
					stroke="#8b5cf6"
					loading={isLoading}
				/>
				<MetricCard
					label="Queue"
					value={data?.queued_count ?? 0}
					hint="queued / running jobs"
					series={queueSeries}
					stroke="#eab308"
					loading={isLoading}
				/>
			</div>

			<div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
				<Card className="overflow-hidden border-slate-200/80 shadow-[0_1px_2px_rgba(15,23,42,0.04)] dark:border-slate-800">
					<CardHeader className="space-y-3 border-b border-slate-100 pb-4 dark:border-slate-800">
						<div className="flex flex-wrap items-center justify-between gap-3">
							<div>
								<CardTitle className="text-base font-semibold">Signal feed</CardTitle>
								<p className="mt-0.5 text-xs text-slate-500">
									Must-see first, then ranked feed · window: {windowLabel}
								</p>
							</div>
							<span className="rounded-full bg-slate-100 px-2.5 py-1 font-mono text-[11px] text-slate-500 dark:bg-slate-800">
								{shownCount} shown
								{feedMeta ? ` / ${feedMeta.feed_total + mustSee.length}` : ""}
							</span>
						</div>
						<div className="flex flex-wrap items-center gap-2">
							<Select
								size="small"
								className="min-w-[140px]"
								value={companyFilter}
								onChange={(value) => setCompanyFilter(value)}
								options={[{ value: "all", label: "All targets" }, ...companyOptions]}
							/>
							<Select
								size="small"
								className="min-w-[130px]"
								value={collectorFilter}
								onChange={(value) => setCollectorFilter(value)}
								options={[{ value: "all", label: "Channels" }, ...collectorOptions]}
							/>
							<Select
								size="small"
								className="min-w-[140px]"
								value={typeFilter}
								onChange={(value) => setTypeFilter(value)}
								options={[{ value: "all", label: "Signal types" }, ...typeOptions]}
							/>
							<Checkbox
								checked={unreadOnly}
								onChange={(e) => setUnreadOnly(e.target.checked)}
								className="text-xs text-slate-600"
							>
								Unread only
							</Checkbox>
						</div>
					</CardHeader>
					<CardContent className="p-0">
						{isLoading ? (
							<div className="px-5 py-12 text-center text-sm text-slate-500">Loading pulse…</div>
						) : shownCount === 0 ? (
							<div className="px-5 py-10">
								<Empty
									image={Empty.PRESENTED_IMAGE_SIMPLE}
									description="No signals match the current filters."
								>
									<Button size="sm" onClick={() => navigate("/companies")}>
										Open companies
									</Button>
								</Empty>
							</div>
						) : (
							<>
								{filteredMustSee.length > 0 ? (
									<div className="border-b border-emerald-100 bg-emerald-50/40 dark:border-emerald-900/40 dark:bg-emerald-950/20">
										<div className="flex items-center justify-between px-4 pt-3">
											<span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-300">
												Must see
											</span>
											<span className="text-[11px] text-emerald-700/70 dark:text-emerald-300/70">
												{filteredMustSee.length} high-signal items
											</span>
										</div>
										{filteredMustSee.map((item) => (
											<SignalRow
												key={`must-${item.id}`}
												item={item}
												unread={!readIds.has(item.id) && isFresh(item.last_seen_at)}
												onOpenCompany={(id) => navigate(`/companies/${id}`)}
												onOpenSignal={markRead}
											/>
										))}
									</div>
								) : null}
								{filteredFeed.map((item) => (
									<SignalRow
										key={item.id}
										item={item}
										unread={!readIds.has(item.id) && isFresh(item.last_seen_at)}
										onOpenCompany={(id) => navigate(`/companies/${id}`)}
										onOpenSignal={markRead}
									/>
								))}
								{feedMeta?.has_more ? (
									<div className="border-t border-slate-100 p-4 dark:border-slate-800">
										<Button
											variant="outline"
											size="sm"
											className="w-full"
											disabled={loadingMore}
											onClick={() => void loadMore()}
										>
											{loadingMore ? "Loading…" : "Load more"}
										</Button>
									</div>
								) : null}
							</>
						)}
					</CardContent>
				</Card>

				<div className="flex flex-col gap-4">
					<Card className="border-slate-200/80 shadow-[0_1px_2px_rgba(15,23,42,0.04)] dark:border-slate-800">
						<CardHeader className="border-b border-slate-100 pb-3 dark:border-slate-800">
							<CardTitle className="text-sm font-semibold">Recent insights</CardTitle>
						</CardHeader>
						<CardContent className="space-y-3 p-4">
							{mustSee.length === 0 ? (
								<p className="text-xs text-slate-400">No high-confidence insights yet.</p>
							) : (
								mustSee.slice(0, 6).map((item) => (
									<button
										key={item.id}
										type="button"
										className="flex w-full items-start justify-between gap-3 rounded-xl px-1 py-1 text-left hover:bg-slate-50 dark:hover:bg-slate-900/50"
										onClick={() => navigate(`/companies/${item.company_id}`)}
									>
										<div className="min-w-0">
											<div className="truncate text-sm font-medium text-slate-800 dark:text-slate-100">
												{item.title || item.url}
											</div>
											<div className="mt-0.5 truncate text-[11px] text-slate-400">
												{item.company?.name ?? "Company"} · {relativeTime(item.last_seen_at)}
											</div>
										</div>
										<PriorityChip
											level={
												(item.priority as "High" | "Medium" | "Low") ||
												priorityOf(item.confidence ?? 0)
											}
										/>
									</button>
								))
							)}
						</CardContent>
					</Card>

					<Card className="border-slate-200/80 shadow-[0_1px_2px_rgba(15,23,42,0.04)] dark:border-slate-800">
						<CardHeader className="border-b border-slate-100 pb-3 dark:border-slate-800">
							<div className="flex items-center justify-between">
								<CardTitle className="text-sm font-semibold">Signals over time</CardTitle>
								<span className="text-[11px] text-slate-400">Last 7 days</span>
							</div>
						</CardHeader>
						<CardContent className="p-3 pt-2">
							{series.some((point) => point.total > 0) ? (
								<Chart
									type="line"
									height={180}
									options={trendChart}
									series={[
										{ name: "High", data: series.map((p) => p.high) },
										{ name: "Medium", data: series.map((p) => p.medium) },
										{ name: "Low", data: series.map((p) => p.low) },
									]}
								/>
							) : (
								<p className="py-8 text-center text-xs text-slate-400">Not enough history yet.</p>
							)}
						</CardContent>
					</Card>

					<Card className="border-slate-200/80 shadow-[0_1px_2px_rgba(15,23,42,0.04)] dark:border-slate-800">
						<CardHeader className="border-b border-slate-100 pb-3 dark:border-slate-800">
							<CardTitle className="text-sm font-semibold">Top signal types</CardTitle>
						</CardHeader>
						<CardContent className="p-4">
							{(data?.top_signal_types ?? []).length ? (
								<div className="flex items-center gap-3">
									<div className="w-[120px] shrink-0">
										<Chart
											type="donut"
											height={120}
											options={donutChart}
											series={(data?.top_signal_types ?? []).map((item) => item.count)}
										/>
									</div>
									<div className="min-w-0 flex-1 space-y-1.5">
										{(data?.top_signal_types ?? []).slice(0, 5).map((item) => (
											<div key={item.key} className="flex items-center justify-between gap-2 text-xs">
												<span className="truncate text-slate-600 dark:text-slate-300">
													{labelSourceType(item.key)}
												</span>
												<span className="font-semibold tabular-nums text-slate-800 dark:text-slate-100">
													{Math.round(item.share * 100)}%
												</span>
											</div>
										))}
									</div>
								</div>
							) : (
								<p className="py-6 text-center text-xs text-slate-400">No type breakdown yet.</p>
							)}
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	);
}
