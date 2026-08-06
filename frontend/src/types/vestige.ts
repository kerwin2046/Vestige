export type CompanyInput = {
	name: string;
	official_domain?: string;
	industry?: string;
	location?: string;
	aliases: string[];
	tier?: CompanyTier;
	roles?: string[];
	priority?: string;
	source?: string;
	provenance?: Record<string, unknown> | null;
};

export type CompanyTier = "candidate" | "target" | "monitoring";

export type Company = Required<Omit<CompanyInput, "tier" | "roles" | "priority" | "source" | "provenance">> & {
	id: string;
	created_at: string;
	updated_at: string;
	agent_path?: string | null;
	tier: CompanyTier | string;
	roles: string[];
	priority: string;
	source: string;
	provenance?: Record<string, unknown> | null;
};

export type RunStatus =
	| "queued"
	| "running"
	| "succeeded"
	| "failed"
	| "cancel_requested"
	| "cancelled";

export type LaneStatus = "ok" | "empty" | "error" | "seeded" | "skipped" | string;

export type LaneResult = {
	status: LaneStatus;
	source_count?: number;
	error?: string | null;
	meta?: Record<string, unknown>;
};

export type RunSettings = {
	kind?: string;
	search_backend?: string;
	max_urls_to_crawl?: number;
	lanes?: string[];
	channel_limit?: number;
	lane_results?: Record<string, LaneResult>;
	warning?: string;
	imported?: boolean;
	source?: string;
	[key: string]: unknown;
};

export type DiscoveryRun = {
	id: string;
	company_id: string;
	previous_run_id: string | null;
	status: RunStatus;
	stage: string;
	progress: number;
	settings_snapshot: RunSettings;
	error: string | null;
	export_path: string | null;
	created_at: string;
	started_at: string | null;
	finished_at: string | null;
	company: Company;
};

export type DashboardSignal = CompanySignal & {
	company: Company | null;
	score?: number;
	priority?: "High" | "Medium" | "Low" | string;
};

export type SignalSeriesPoint = {
	day: string;
	high: number;
	medium: number;
	low: number;
	total: number;
};

export type SignalTypeShare = {
	key: string;
	count: number;
	share: number;
};

export type PulseFeed = {
	window: string;
	window_label: string;
	must_see: DashboardSignal[];
	feed: DashboardSignal[];
	feed_total: number;
	offset: number;
	limit: number;
	has_more: boolean;
	next_offset: number;
	candidate_count: number;
};

export type DashboardSummary = {
	company_count: number;
	run_count: number;
	queued_count: number;
	source_count: number;
	signal_count: number;
	signals_today: number;
	signal_series: SignalSeriesPoint[];
	top_signal_types: SignalTypeShare[];
	pulse: PulseFeed;
	recent_signals: DashboardSignal[];
	recent_insights: DashboardSignal[];
	recent_runs: DiscoveryRun[];
};

export type RunSource = {
	id: string;
	run_id: string;
	url: string;
	canonical_url: string;
	domain: string;
	source_type: string;
	ownership: string;
	confidence: number;
	title: string;
	snippet: string;
	discovery_path: string;
	bfs_round: number;
	detail: Record<string, unknown> | null;
};

export type CompanySignal = {
	id: string;
	company_id: string;
	url: string;
	canonical_url: string;
	domain: string;
	source_type: string;
	ownership: string;
	confidence: number;
	title: string;
	snippet: string;
	discovery_path: string;
	collector: string;
	detail: Record<string, unknown> | null;
	first_seen_at: string;
	last_seen_at: string;
	last_run_id: string | null;
};

export type CompanySignalsPage = {
	items: CompanySignal[];
	total: number;
};

export type ChannelKind = "platform" | "association";

export type Channel = {
	id: string;
	kind: ChannelKind | string;
	name: string;
	url: string;
	domain: string;
	industry: string;
	country: string;
	channel_type: string;
	score: number;
	status: string;
	source: string;
	has_member_directory: number;
	detail: Record<string, unknown> | null;
	created_at: string;
	updated_at: string;
};

export type ChannelStats = {
	total: number;
	platform_count: number;
	association_count: number;
	with_member_directory: number;
};

