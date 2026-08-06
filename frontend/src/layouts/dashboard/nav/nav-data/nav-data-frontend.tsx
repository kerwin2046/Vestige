import { Icon } from "@/components/icon";
import type { NavProps } from "@/components/nav";

export const frontendNavData: NavProps["data"] = [
	{
		name: "Workspace",
		items: [
			{
				title: "Pulse",
				path: "/dashboard",
				icon: <Icon icon="solar:widget-add-bold-duotone" size="22" />,
			},
			{
				title: "Streams",
				path: "/streams",
				icon: <Icon icon="solar:flame-bold-duotone" size="22" />,
			},
			{
				title: "Companies",
				path: "/companies",
				icon: <Icon icon="solar:buildings-2-bold-duotone" size="22" />,
			},
			{
				title: "Channels",
				path: "/channels",
				icon: <Icon icon="solar:radar-2-bold-duotone" size="22" />,
			},
			{
				title: "Discovery Runs",
				path: "/runs",
				icon: <Icon icon="solar:history-bold-duotone" size="22" />,
			},
		],
	},
];
