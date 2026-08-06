import type { RouteObject } from "react-router";
import { Component } from "./utils";

export function getFrontendDashboardRoutes(): RouteObject[] {
	const frontendDashboardRoutes: RouteObject[] = [
		{ path: "dashboard", element: Component("/pages/vestige/dashboard") },
		{ path: "streams", element: Component("/pages/vestige/streams") },
		{ path: "streams/:id", element: Component("/pages/vestige/streams/detail") },
		{ path: "companies", element: Component("/pages/vestige/companies") },
		{ path: "companies/:id", element: Component("/pages/vestige/companies/detail") },
		{ path: "companies/:id/compare", element: Component("/pages/vestige/companies/compare") },
		{ path: "channels", element: Component("/pages/vestige/channels") },
		{ path: "runs", element: Component("/pages/vestige/runs") },
		{ path: "runs/:id", element: Component("/pages/vestige/runs/detail") },
	];
	return frontendDashboardRoutes;
}
