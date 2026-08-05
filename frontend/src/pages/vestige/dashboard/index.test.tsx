// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from ".";

vi.mock("@/api/services/vestigeService", () => ({
	default: {
		getDashboard: vi.fn().mockResolvedValue({
			company_count: 4,
			run_count: 9,
			queued_count: 2,
			source_count: 128,
			recent_runs: [],
		}),
	},
}));

describe("Vestige dashboard", () => {
	it("renders persisted discovery metrics", async () => {
		const client = new QueryClient({
			defaultOptions: { queries: { retry: false } },
		});
		render(
			<MemoryRouter>
				<QueryClientProvider client={client}>
					<DashboardPage />
				</QueryClientProvider>
			</MemoryRouter>,
		);

		expect(await screen.findByText("Companies")).toBeInTheDocument();
		expect(screen.getByText("4")).toBeInTheDocument();
		expect(screen.getByText("Total runs")).toBeInTheDocument();
		expect(screen.getByText("9")).toBeInTheDocument();
		expect(screen.getByText("Discovered sources")).toBeInTheDocument();
		expect(screen.getByText("128")).toBeInTheDocument();
	});
});
