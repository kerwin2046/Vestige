import vestigeService from "@/api/services/vestigeService";
import type { StreamSignal } from "@/types/vestige";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/card";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Empty, Table, Tag, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { ArrowLeft, ExternalLink, Flame, Play, Sparkles } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ConfidenceBadge, formatDateTime } from "../components/run-status";

export default function StreamDetailPage() {
	const { id = "" } = useParams();
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [lastAgentRun, setLastAgentRun] = useState<{
		status: string;
		pid?: number | null;
		log_path: string;
		agent_path: string;
	} | null>(null);

	const streamQuery = useQuery({
		queryKey: ["stream", id],
		queryFn: () => vestigeService.getStream(id),
		enabled: Boolean(id),
	});

	const signalsQuery = useQuery({
		queryKey: ["stream-signals", id],
		queryFn: () => vestigeService.listStreamSignals(id, { limit: 100 }),
		enabled: Boolean(id),
		refetchInterval: 10_000,
	});

	const scaffoldMutation = useMutation({
		mutationFn: () => vestigeService.scaffoldStreamAgent(id),
		onSuccess: (data) => {
			message.success(`Agent scaffolded at ${data.agent_path}`);
		},
		onError: (error: Error) => message.error(error.message || "Failed to scaffold agent"),
	});

	const runAgentMutation = useMutation({
		mutationFn: () => vestigeService.runStreamAgent(id, { wait: false }),
		onSuccess: async (data) => {
			setLastAgentRun(data);
			message.success(
				data.pid
					? `OpenClaw started (pid ${data.pid})`
					: `Agent status: ${data.status}`,
			);
			await queryClient.invalidateQueries({ queryKey: ["stream", id] });
			await queryClient.invalidateQueries({ queryKey: ["stream-signals", id] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to start agent"),
	});

	const stream = streamQuery.data;
	const signals = signalsQuery.data?.items ?? [];

	const columns: ColumnsType<StreamSignal> = [
		{
			title: "Signal",
			key: "title",
			render: (_, record) => (
				<div className="min-w-0">
					<a
						href={record.url}
						target="_blank"
						rel="noreferrer"
						className="inline-flex max-w-full items-center gap-1 font-medium text-sky-700 hover:text-sky-800 dark:text-sky-400"
					>
						<span className="truncate">{record.title || record.url}</span>
						<ExternalLink className="h-3 w-3 shrink-0 opacity-50" />
					</a>
					{record.snippet ? (
						<p className="mt-1 line-clamp-2 text-xs text-slate-500">{record.snippet}</p>
					) : null}
				</div>
			),
		},
		{
			title: "Type",
			dataIndex: "source_type",
			width: 140,
			render: (value: string) => <Tag>{value}</Tag>,
		},
		{
			title: "Confidence",
			dataIndex: "confidence",
			width: 110,
			render: (value: number) => <ConfidenceBadge value={value} />,
		},
		{
			title: "Seen",
			dataIndex: "last_seen_at",
			width: 170,
			render: (value: string) => formatDateTime(value),
		},
	];

	if (streamQuery.isError || (!streamQuery.isLoading && !stream)) {
		return (
			<Card className="p-12 text-center">
				<Empty description="Stream not found">
					<Button onClick={() => navigate("/streams")}>Back to Streams</Button>
				</Empty>
			</Card>
		);
	}

	return (
		<div className="space-y-4">
			<div className="flex flex-wrap items-center justify-between gap-3">
				<Button variant="ghost" size="sm" onClick={() => navigate("/streams")}>
					<ArrowLeft className="mr-1 h-4 w-4" />
					Streams
				</Button>
				<div className="flex flex-wrap items-center gap-2">
					<Button
						variant="outline"
						size="sm"
						disabled={scaffoldMutation.isPending}
						onClick={() => scaffoldMutation.mutate()}
					>
						<Sparkles className="mr-1.5 h-4 w-4 text-orange-600" />
						{scaffoldMutation.isPending ? "Scaffolding…" : "Scaffold Agent"}
					</Button>
					<Button
						size="sm"
						className="bg-orange-600 text-white hover:bg-orange-500"
						disabled={runAgentMutation.isPending}
						onClick={() => runAgentMutation.mutate()}
					>
						<Play className="mr-1.5 h-4 w-4" />
						{runAgentMutation.isPending ? "Starting…" : "Run OpenClaw Agent"}
					</Button>
				</div>
			</div>

			{lastAgentRun ? (
				<Alert
					type="success"
					showIcon
					message={
						lastAgentRun.pid
							? `Agent started (pid ${lastAgentRun.pid})`
							: `Agent status: ${lastAgentRun.status}`
					}
					description={
						<div className="space-y-1 text-xs font-mono break-all">
							<div>log: {lastAgentRun.log_path}</div>
							<div>agent: {lastAgentRun.agent_path}</div>
							<div className="text-slate-500">
								CLI: make dispatch-stream
								{stream?.slug ? `  # stream=${stream.slug}` : ""}
							</div>
						</div>
					}
				/>
			) : null}

			<Card className="border-slate-200 shadow-xs dark:border-slate-800">
				<CardHeader className="border-b border-slate-100 p-4 dark:border-slate-800">
					<div className="flex items-start gap-3">
						<div className="flex h-11 w-11 items-center justify-center rounded-xl border border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900 dark:bg-orange-950/40">
							<Flame className="h-5 w-5" />
						</div>
						<div className="min-w-0 flex-1">
							<CardTitle className="text-lg">
								{stream?.name ?? "Loading…"}
							</CardTitle>
							<p className="mt-1 text-sm text-slate-500">
								{stream?.description || "Industry market lens"}
							</p>
							<div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
								<span className="font-mono">{stream?.slug}</span>
								{stream?.kind ? <Tag color="orange">{stream.kind}</Tag> : null}
								<span className="font-mono">{stream?.agent_slug || "mfg-social-pulse"}</span>
								<span>{stream?.signal_count ?? 0} signals</span>
								{(stream?.signals_today ?? 0) > 0 ? (
									<span className="text-emerald-600">{stream?.signals_today} today</span>
								) : null}
							</div>
						</div>
					</div>
				</CardHeader>
				<CardContent className="p-0">
					{signalsQuery.isLoading ? (
						<p className="p-8 text-center text-sm text-slate-400">Loading signals…</p>
					) : signals.length === 0 ? (
						<div className="p-8">
							<Empty
								description="No stream signals yet. Click Run OpenClaw Agent (gateway required) or make dispatch-stream."
								image={Empty.PRESENTED_IMAGE_SIMPLE}
							>
								<Button
									size="sm"
									className="mt-2 bg-orange-600 text-white hover:bg-orange-500"
									disabled={runAgentMutation.isPending}
									onClick={() => runAgentMutation.mutate()}
								>
									<Play className="mr-1.5 h-4 w-4" />
									Run OpenClaw Agent
								</Button>
							</Empty>
						</div>
					) : (
						<Table
							rowKey="id"
							columns={columns}
							dataSource={signals}
							pagination={{ pageSize: 25 }}
						/>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
