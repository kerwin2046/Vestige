import { frontendNavData } from "@/layouts/dashboard/nav/nav-data/nav-data-frontend";
import { GLOBAL_CONFIG } from "@/global-config";
import type { RouteObject } from "react-router";
import { describe, expect, it } from "vitest";
import { getFrontendDashboardRoutes } from "./frontend";

function routePaths(routes: RouteObject[], parent = ""): string[] {
	const paths: string[] = [];
	for (const route of routes) {
		const current = route.path ? `${parent}/${route.path}`.replaceAll("//", "/") : parent;
		if (route.path) paths.push(current);
		if (route.children) paths.push(...routePaths(route.children, current));
	}
	return paths;
}

function navPaths(): string[] {
	return frontendNavData.flatMap((group) => group.items.map((item) => item.path));
}

describe("Vestige product shell", () => {
	it("exposes only the core product routes", () => {
		const paths = routePaths(getFrontendDashboardRoutes());

		expect(paths).toContain("/dashboard");
		expect(paths).toContain("/companies");
		expect(paths).toContain("/runs");
		expect(paths).toContain("/runs/:id");
		expect(paths).toContain("/companies/:id/compare");
		expect(paths).not.toContain("/workbench");
	});

	it("uses product navigation and branding", () => {
		expect(navPaths()).toEqual(["/dashboard", "/companies", "/runs"]);
		expect(GLOBAL_CONFIG.appName).toBe("Vestige");
		expect(GLOBAL_CONFIG.defaultRoute).toBe("/dashboard");
	});
});

