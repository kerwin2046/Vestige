import type {
	Channel,
	ChannelStats,
	Company,
	CompanyInput,
	CompanyTier,
	DashboardSummary,
	DiscoveryRun,
	RunSettings,
	RunSource,
} from "@/types/vestige";
import apiClient from "../apiClient";

const getDashboard = () => apiClient.get<DashboardSummary>({ url: "/dashboard" });

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

export default {
	getDashboard,
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
	listChannels,
	getChannelStats,
	scaffoldCompanyAgent,
};
