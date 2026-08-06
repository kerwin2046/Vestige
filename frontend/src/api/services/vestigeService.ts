import type {
	Channel,
	ChannelStats,
	Company,
	CompanyInput,
	CompanySignalsPage,
	CompanyTier,
	DashboardSummary,
	DiscoveryRun,
	PulseFeed,
	RunSettings,
	RunSource,
} from "@/types/vestige";
import apiClient from "../apiClient";

const getDashboard = (params?: { limit?: number; offset?: number }) =>
	apiClient.get<DashboardSummary>({ url: "/dashboard", params });

const getDashboardFeed = (params?: { limit?: number; offset?: number }) =>
	apiClient.get<PulseFeed>({ url: "/dashboard/feed", params });

const listCompanies = (params?: {
	tier?: string;
	role?: string;
	q?: string;
	source?: string;
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
	scaffoldCompanyAgent,
	runCompanyAgent,
};
