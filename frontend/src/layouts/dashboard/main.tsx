import { AuthGuard } from "@/components/auth/auth-guard";
import { LineLoading } from "@/components/loading";
import { GLOBAL_CONFIG } from "@/global-config";
import Page403 from "@/pages/sys/error/Page403";
import { flattenTrees } from "@/utils/tree";
import { clone, concat } from "ramda";
import { Suspense } from "react";
import { Outlet, ScrollRestoration, useLocation } from "react-router";
import { backendNavData } from "./nav/nav-data/nav-data-backend";
import { frontendNavData } from "./nav/nav-data/nav-data-frontend";

/**
 * find auth by path
 * @param path
 * @returns
 */
function findAuthByPath(path: string): string[] {
	const foundItem = allItems.find((item) => item.path === path);
	return foundItem?.auth || [];
}

const navData = GLOBAL_CONFIG.routerMode === "frontend" ? clone(frontendNavData) : backendNavData;
const allItems = navData.reduce((acc: any[], group) => {
	const flattenedItems = flattenTrees(group.items);
	return concat(acc, flattenedItems);
}, []);

const Main = () => {
	const { pathname } = useLocation();
	const currentNavAuth = findAuthByPath(pathname);

	return (
		<AuthGuard checkAny={currentNavAuth} fallback={<Page403 />}>
			<main
				data-slot="slash-layout-main"
				className="flex w-full max-w-full flex-auto flex-col px-4 py-4"
			>
				<Suspense fallback={<LineLoading />}>
					<Outlet />
					<ScrollRestoration />
				</Suspense>
			</main>
		</AuthGuard>
	);
};

export default Main;
