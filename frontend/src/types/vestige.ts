export type CompanyInput = {
	name: string;
	official_domain?: string;
	industry?: string;
	location?: string;
	aliases: string[];
};

export type Company = Required<CompanyInput> & {
	id: string;
	created_at: string;
	updated_at: string;
	agent_path?: string | null;
};

export type RunStatus =
	| "queued"
	| "running"
	| "succeeded"
	| "failed"
	| "cancel_requested"
	| "cancelled";

export type RunSettings = {
	kind?: string;
	search_backend?: string;
	max_urls_to_crawl?: number;
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

export type DashboardSummary = {
	company_count: number;
	run_count: number;
	queued_count: number;
	source_count: number;
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

