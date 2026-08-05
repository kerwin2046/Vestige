import type { RouteObject } from "react-router";
import { Component } from "./utils";

export function getFrontendDashboardRoutes(): RouteObject[] {
	const frontendDashboardRoutes: RouteObject[] = [
		{ path: "dashboard", element: Component("/pages/vestige/dashboard") },
		{ path: "companies", element: Component("/pages/vestige/companies") },
		{ path: "companies/:id", element: Component("/pages/vestige/companies/detail") },
		{ path: "companies/:id/compare", element: Component("/pages/vestige/companies/compare") },
		{ path: "runs", element: Component("/pages/vestige/runs") },
		{ path: "runs/:id", element: Component("/pages/vestige/runs/detail") },
	];
	return frontendDashboardRoutes;
}
