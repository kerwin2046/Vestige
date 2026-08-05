import apiClient from "@/api/apiClient";
import { beforeEach, describe, expect, it, vi } from "vitest";
import vestigeService from "./vestigeService";

vi.mock("@/api/apiClient", () => ({
	default: {
		get: vi.fn(),
		post: vi.fn(),
		put: vi.fn(),
		delete: vi.fn(),
	},
}));

describe("vestigeService", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("maps dashboard and company endpoints", async () => {
		await vestigeService.getDashboard();
		await vestigeService.listCompanies();
		await vestigeService.createCompany({ name: "Xometry", aliases: [] });

		expect(apiClient.get).toHaveBeenNthCalledWith(1, { url: "/dashboard" });
		expect(apiClient.get).toHaveBeenNthCalledWith(2, { url: "/companies" });
		expect(apiClient.post).toHaveBeenCalledWith({
			url: "/companies",
			data: { name: "Xometry", aliases: [] },
		});
	});

	it("maps run actions", async () => {
		await vestigeService.createRun("company-1", { search_backend: "exa" });
		await vestigeService.cancelRun("run-1");
		await vestigeService.retryRun("run-1");

		expect(apiClient.post).toHaveBeenNthCalledWith(1, {
			url: "/companies/company-1/runs",
			data: { search_backend: "exa" },
		});
		expect(apiClient.post).toHaveBeenNthCalledWith(2, {
			url: "/runs/run-1/cancel",
		});
		expect(apiClient.post).toHaveBeenNthCalledWith(3, {
			url: "/runs/run-1/retry",
		});
	});
});

