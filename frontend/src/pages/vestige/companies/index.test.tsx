// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import vestigeService from "@/api/services/vestigeService";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CompaniesPage from ".";

vi.mock("@/api/services/vestigeService", () => ({
	default: {
		listCompanies: vi.fn(),
		createCompany: vi.fn(),
		deleteCompany: vi.fn(),
		createRun: vi.fn(),
	},
}));

function renderPage() {
	const client = new QueryClient({
		defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
	});
	return render(
		<MemoryRouter>
			<QueryClientProvider client={client}>
				<CompaniesPage />
			</QueryClientProvider>
		</MemoryRouter>,
	);
}

describe("Companies page", () => {
	beforeEach(() => {
		vi.mocked(vestigeService.listCompanies).mockResolvedValue([
			{
				id: "company-1",
				name: "Xometry",
				official_domain: "xometry.com",
				industry: "Manufacturing",
				location: "US",
				aliases: [],
				created_at: "2026-07-21T00:00:00Z",
				updated_at: "2026-07-21T00:00:00Z",
			},
		]);
		vi.mocked(vestigeService.createRun).mockResolvedValue({} as never);
	});

	afterEach(() => {
		cleanup();
	});

	it("lists companies and starts discovery", async () => {
		renderPage();

		expect(await screen.findByText("Xometry")).toBeInTheDocument();
		fireEvent.click(screen.getByRole("button", { name: "Start discovery" }));

		await waitFor(() => {
			expect(vestigeService.createRun).toHaveBeenCalledWith("company-1", {});
		});
	});

	it("creates a company without editing config.py", async () => {
		vi.mocked(vestigeService.createCompany).mockResolvedValue({} as never);
		renderPage();

		fireEvent.click(await screen.findByRole("button", { name: /New company/i }));
		fireEvent.change(await screen.findByLabelText("Company name"), { target: { value: "Acme" } });
		fireEvent.change(screen.getByLabelText("Official domain"), { target: { value: "acme.com" } });
		fireEvent.click(screen.getByRole("button", { name: "Save company" }));

		await waitFor(() => {
			expect(vestigeService.createCompany).toHaveBeenCalledWith({
				name: "Acme",
				official_domain: "acme.com",
				industry: "",
				location: "",
				aliases: [],
			});
		});
	});
});
