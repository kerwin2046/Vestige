import type {
	Channel,
	ChannelStats,
	Company,
	CompanyInput,
	CompanySignalsPage,
	CompanyTier,
	DashboardSummary,
	DiscoveryRun,
	IntelStream,
	PulseFeed,
	RunSettings,
	RunSource,
	StreamSignalsPage,
} from "@/types/vestige";
import apiClient from "../apiClient";

const getDashboard = (params?: { limit?: number; offset?: number }) =>
	apiClient.get<DashboardSummary>({ url: "/dashboard", params });

const getDashboardFeed = (params?: { limit?: number; offset?: number }) =>
	apiClient.get<PulseFeed>({ url: "/dashboard/feed", params });

const getCompanyActivityRevision = () =>
	apiClient.get<{
		revision: string;
		signal_count: number;
		max_last_signal_at: string | null;
	}>({ url: "/companies/activity-revision" });

const listCompanies = (params?: {
	tier?: string;
	role?: string;
	q?: string;
	source?: string;
	include_activity?: boolean;
}) => apiClient.get<Company[]>({ url: "/companies", params });

const getCompany = (id: string) => apiClient.get<Company>({ url: `/companies/${id}` });

const createCompany = (data: CompanyInput) =>
	apiClient.post<Company>({ url: "/companies", data });

const updateCompany = (id: string, data: CompanyInput) =>
	apiClient.put<Company>({ url: `/companies/${id}`, data });

const promoteCompany = (id: string, tier: CompanyTier = "target") =>
	apiClient.post<Company>({ url: `/companies/${id}/promote`, data: { tier } });

const deleteCompany = (id: string) =>
	apiClient.delete<{ deleted: boolean }>({ url: `/companies/${id}` });

const listRuns = (params?: { company_id?: string; status?: string }) =>
	apiClient.get<DiscoveryRun[]>({ url: "/runs", params });

const getRun = (id: string) => apiClient.get<DiscoveryRun>({ url: `/runs/${id}` });

const createRun = (companyId: string, data: RunSettings) =>
	apiClient.post<DiscoveryRun>({
		url: `/companies/${companyId}/runs`,
		data,
	});

const cancelRun = (id: string) =>
	apiClient.post<DiscoveryRun>({ url: `/runs/${id}/cancel` });

const retryRun = (id: string) =>
	apiClient.post<DiscoveryRun>({ url: `/runs/${id}/retry` });

const listRunSources = (id: string) =>
	apiClient.get<RunSource[]>({ url: `/runs/${id}/sources` });

const listCompanySignals = (id: string, params?: { limit?: number; offset?: number }) =>
	apiClient.get<CompanySignalsPage>({ url: `/companies/${id}/signals`, params });

const listChannels = (params?: {
	kind?: string;
	q?: string;
	industry?: string;
	country?: string;
	limit?: number;
	offset?: number;
}) => apiClient.get<Channel[]>({ url: "/channels", params });

const getChannelStats = () => apiClient.get<ChannelStats>({ url: "/channels/stats" });

const listStreams = (params?: { status?: string; kind?: string }) =>
	apiClient.get<IntelStream[]>({ url: "/streams", params });

const getStream = (idOrSlug: string) =>
	apiClient.get<IntelStream>({ url: `/streams/${idOrSlug}` });

const listStreamSignals = (
	idOrSlug: string,
	params?: { limit?: number; offset?: number },
) =>
	apiClient.get<StreamSignalsPage>({
		url: `/streams/${idOrSlug}/signals`,
		params,
	});

const scaffoldStreamAgent = (idOrSlug: string) =>
	apiClient.post<{
		agent_path: string;
		slug: string;
		stream_id: string;
		stream_slug: string;
	}>({
		url: `/streams/${idOrSlug}/scaffold-agent`,
	});

const runStreamAgent = (
	idOrSlug: string,
	params?: { wait?: boolean; local?: boolean; timeout?: number },
) =>
	apiClient.post<{
		status: string;
		pid?: number | null;
		log_path: string;
		agent_path: string;
		agent_slug?: string;
		stream_slug?: string;
		command: string[];
	}>({
		url: `/streams/${idOrSlug}/run-agent`,
		params,
	});

const scaffoldCompanyAgent = (id: string) =>
	apiClient.post<{ agent_path: string; slug: string }>({
		url: `/companies/${id}/scaffold-agent`,
	});

const runCompanyAgent = (
	id: string,
	params?: { wait?: boolean; local?: boolean; timeout?: number },
) =>
	apiClient.post<{
		status: string;
		pid?: number | null;
		log_path: string;
		agent_path: string;
		command: string[];
		slug: string;
	}>({
		url: `/companies/${id}/run-agent`,
		params,
	});

export default {
	getDashboard,
	getDashboardFeed,
	getCompanyActivityRevision,
	listCompanies,
	getCompany,
	createCompany,
	updateCompany,
	promoteCompany,
	deleteCompany,
	listRuns,
	getRun,
	createRun,
	cancelRun,
	retryRun,
	listRunSources,
	listCompanySignals,
	listChannels,
	getChannelStats,
	listStreams,
	getStream,
	listStreamSignals,
	scaffoldStreamAgent,
	runStreamAgent,
	scaffoldCompanyAgent,
	runCompanyAgent,
};
