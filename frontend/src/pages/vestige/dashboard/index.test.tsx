// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from ".";

vi.mock("@/components/chart", () => ({
	Chart: () => <div data-testid="chart" />,
	useChart: () => ({}),
}));

vi.mock("@/api/services/vestigeService", () => ({
	default: {
		getDashboard: vi.fn().mockResolvedValue({
			company_count: 4,
			run_count: 9,
			queued_count: 0,
			source_count: 128,
			signal_count: 91,
			signals_today: 4,
			signal_series: [
				{ day: "2026-08-01", high: 1, medium: 0, low: 0, total: 1 },
				{ day: "2026-08-02", high: 0, medium: 1, low: 0, total: 1 },
				{ day: "2026-08-03", high: 0, medium: 0, low: 0, total: 0 },
				{ day: "2026-08-04", high: 2, medium: 1, low: 0, total: 3 },
				{ day: "2026-08-05", high: 1, medium: 2, low: 1, total: 4 },
				{ day: "2026-08-06", high: 2, medium: 1, low: 0, total: 3 },
				{ day: "2026-08-07", high: 3, medium: 1, low: 0, total: 4 },
			],
			top_signal_types: [
				{ key: "news_media", count: 40, share: 0.44 },
				{ key: "other", count: 30, share: 0.33 },
			],
			pulse: {
				window: "today",
				window_label: "Today",
				must_see: [
					{
						id: "sig-1",
						company_id: "c1",
						url: "https://news.test/xometry",
						canonical_url: "https://news.test/xometry",
						domain: "news.test",
						source_type: "news_media",
						ownership: "unknown",
						confidence: 0.8,
						title: "Xometry posts Q2 results",
						snippet: "Revenue up",
						discovery_path: "ingest",
						collector: "openclaw",
						detail: null,
						first_seen_at: new Date().toISOString(),
						last_seen_at: new Date().toISOString(),
						last_run_id: null,
						score: 0.72,
						priority: "High",
						company: {
							id: "c1",
							name: "Xometry",
							official_domain: "xometry.com",
							industry: "",
							location: "",
							aliases: [],
							tier: "target",
							roles: [],
							priority: "",
							source: "manual",
							created_at: "2026-08-01T00:00:00Z",
							updated_at: "2026-08-01T00:00:00Z",
						},
					},
				],
				feed: [],
				feed_total: 0,
				offset: 0,
				limit: 25,
				has_more: false,
				next_offset: 0,
				candidate_count: 1,
			},
			recent_signals: [],
			recent_insights: [],
			recent_runs: [],
		}),
	},
}));

describe("Vestige dashboard", () => {
	it("renders competitive pulse feed", async () => {
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

		expect(await screen.findByText("Competitive Intelligence")).toBeInTheDocument();
		expect(screen.getAllByText("Xometry posts Q2 results").length).toBeGreaterThan(0);
		expect(screen.getByText("91")).toBeInTheDocument();
		expect(screen.getByText("signals seen today")).toBeInTheDocument();
		expect(screen.getByText("Must see")).toBeInTheDocument();
		expect(screen.getByText("Recent insights")).toBeInTheDocument();
		expect(screen.getByText("Top signal types")).toBeInTheDocument();
	});
});
