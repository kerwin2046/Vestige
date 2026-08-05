import { Icon } from "@/components/icon";
import type { NavProps } from "@/components/nav";

export const frontendNavData: NavProps["data"] = [
	{
		name: "Vestige",
		items: [
			{
				title: "Overview",
				path: "/dashboard",
				icon: <Icon icon="solar:chart-2-bold-duotone" size="24" />,
			},
			{
				title: "Companies",
				path: "/companies",
				icon: <Icon icon="solar:buildings-2-bold-duotone" size="24" />,
			},
			{
				title: "Runs",
				path: "/runs",
				icon: <Icon icon="solar:history-bold-duotone" size="24" />,
			},
		],
	},
];
