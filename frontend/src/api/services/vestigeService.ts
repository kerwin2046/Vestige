import type {
	Company,
	CompanyInput,
	DashboardSummary,
	DiscoveryRun,
	RunSettings,
	RunSource,
} from "@/types/vestige";
import apiClient from "../apiClient";

const getDashboard = () => apiClient.get<DashboardSummary>({ url: "/dashboard" });

const listCompanies = () => apiClient.get<Company[]>({ url: "/companies" });

const getCompany = (id: string) => apiClient.get<Company>({ url: `/companies/${id}` });

const createCompany = (data: CompanyInput) =>
	apiClient.post<Company>({ url: "/companies", data });

const updateCompany = (id: string, data: CompanyInput) =>
	apiClient.put<Company>({ url: `/companies/${id}`, data });

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

export default {
	getDashboard,
	listCompanies,
	getCompany,
	createCompany,
	updateCompany,
	deleteCompany,
	listRuns,
	getRun,
	createRun,
	cancelRun,
	retryRun,
	listRunSources,
};

