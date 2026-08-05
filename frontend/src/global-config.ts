import packageJson from "../package.json";

/**
 * Global application configuration type definition
 */
export type GlobalConfig = {
	/** Application name */
	appName: string;
	/** Application version number */
	appVersion: string;
	/** Default route path for the application */
	defaultRoute: string;
	/** Public path for static assets */
	publicPath: string;
	/** Base URL for API endpoints */
	apiBaseUrl: string;
	/** Routing mode: frontend routing or backend routing */
	routerMode: "frontend" | "backend";
	/** Skip login guard in local development */
	skipAuth: boolean;
	/** Enable MSW mock handlers */
	enableMsw: boolean;
};

/**
 * Global configuration constants
 * Reads configuration from environment variables and package.json
 *
 * @warning
 * Please don't use the import.meta.env to get the configuration, use the GLOBAL_CONFIG instead
 */
export const GLOBAL_CONFIG: GlobalConfig = {
	appName: "Vestige",
	appVersion: packageJson.version,
	defaultRoute: import.meta.env.VITE_APP_DEFAULT_ROUTE || "/dashboard",
	publicPath: import.meta.env.VITE_APP_PUBLIC_PATH || "/",
	apiBaseUrl: import.meta.env.VITE_APP_API_BASE_URL || "/api",
	routerMode: import.meta.env.VITE_APP_ROUTER_MODE || "frontend",
	skipAuth: import.meta.env.VITE_APP_SKIP_AUTH === "true",
	enableMsw: import.meta.env.VITE_APP_ENABLE_MSW !== "false",
};
