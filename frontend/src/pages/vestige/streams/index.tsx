import vestigeService from "@/api/services/vestigeService";
import type { IntelStream } from "@/types/vestige";
import { Badge } from "@/ui/badge";
import { Card, CardContent } from "@/ui/card";
import { useQuery } from "@tanstack/react-query";
import { Empty, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Flame, Radio } from "lucide-react";
import { useNavigate } from "react-router";
import { formatDateTime } from "../components/run-status";

export default function StreamsPage() {
	const navigate = useNavigate();

	const streamsQuery = useQuery({
		queryKey: ["streams"],
		queryFn: () => vestigeService.listStreams({ status: "active" }),
	});

	const streams = streamsQuery.data ?? [];

	const columns: ColumnsType<IntelStream> = [
		{
			title: "Stream",
			key: "name",
			render: (_, record) => (
				<button
					type="button"
					className="flex items-center gap-3 text-left"
					onClick={() => navigate(`/streams/${record.slug}`)}
				>
					<div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900 dark:bg-orange-950/40 dark:text-orange-400">
						<Flame className="h-4 w-4" />
					</div>
					<div className="min-w-0">
						<div className="font-semibold text-slate-900 dark:text-slate-100">
							{record.name}
						</div>
						<div className="truncate text-xs text-slate-500">{record.description || record.slug}</div>
					</div>
				</button>
			),
		},
		{
			title: "Kind",
			dataIndex: "kind",
			width: 140,
			render: (value: string) => <Tag color="orange">{value}</Tag>,
		},
		{
			title: "Signals",
			key: "counts",
			width: 140,
			render: (_, record) => (
				<div className="text-sm">
					<span className="font-semibold">{record.signal_count}</span>
					<span className="text-slate-400"> total</span>
					{record.signals_today > 0 ? (
						<div className="text-xs text-emerald-600">{record.signals_today} today</div>
					) : null}
				</div>
			),
		},
		{
			title: "Last signal",
			dataIndex: "last_signal_at",
			width: 180,
			render: (value: string | null) =>
				value ? formatDateTime(value) : <span className="text-slate-400">—</span>,
		},
		{
			title: "Agent",
			dataIndex: "agent_slug",
			width: 160,
			render: (value: string) => (
				<span className="font-mono text-xs text-slate-500">{value || "—"}</span>
			),
		},
	];

	return (
		<div className="space-y-4">
			<div className="flex items-end justify-between gap-4">
				<div>
					<h1 className="flex items-center gap-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
						<Radio className="h-5 w-5 text-orange-600" />
						Intel Streams
					</h1>
					<p className="mt-1 text-sm text-slate-500">
						Market lenses — industry social heat, not companies
					</p>
				</div>
				<Badge variant="secondary">{streams.length} active</Badge>
			</div>

			<Card className="border-slate-200 shadow-xs dark:border-slate-800">
				<CardContent className="p-0">
					{streamsQuery.isLoading ? (
						<p className="p-8 text-center text-sm text-slate-400">Loading streams…</p>
					) : streams.length === 0 ? (
						<div className="p-8">
							<Empty
								description="No streams yet. Run make migrate-mfg-stream to seed Manufacturing Social Pulse."
								image={Empty.PRESENTED_IMAGE_SIMPLE}
							/>
						</div>
					) : (
						<Table
							rowKey="id"
							columns={columns}
							dataSource={streams}
							pagination={false}
							onRow={(record) => ({
								onClick: () => navigate(`/streams/${record.slug}`),
								className: "cursor-pointer",
							})}
						/>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
