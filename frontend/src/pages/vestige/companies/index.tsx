import vestigeService from "@/api/services/vestigeService";
import { Icon } from "@/components/icon";
import type { Company } from "@/types/vestige";
import { Button } from "@/ui/button";
import { Card, CardContent, CardHeader } from "@/ui/card";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Empty, Modal, Popconfirm, Space, Table, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useState } from "react";
import { useNavigate } from "react-router";
import { formatDateTime } from "../components/run-status";
import CompanyForm from "./company-form";

export default function CompaniesPage() {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [createOpen, setCreateOpen] = useState(false);

	const { data = [], isLoading, isError, refetch } = useQuery({
		queryKey: ["companies"],
		queryFn: vestigeService.listCompanies,
	});

	const createMutation = useMutation({
		mutationFn: vestigeService.createCompany,
		onSuccess: async (company) => {
			const agentHint = company.agent_path
				? ` · agent: ${company.agent_path}`
				: "";
			message.success(`Company created${agentHint}`);
			setCreateOpen(false);
			await queryClient.invalidateQueries({ queryKey: ["companies"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to create company"),
	});

	const deleteMutation = useMutation({
		mutationFn: vestigeService.deleteCompany,
		onSuccess: async () => {
			message.success("Company deleted");
			await queryClient.invalidateQueries({ queryKey: ["companies"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
		},
		onError: (error: Error) => message.error(error.message || "Failed to delete company"),
	});

	const runMutation = useMutation({
		mutationFn: (companyId: string) => vestigeService.createRun(companyId, {}),
		onSuccess: async () => {
			message.success("Discovery run queued");
			await queryClient.invalidateQueries({ queryKey: ["runs"] });
			await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
			navigate("/runs");
		},
		onError: (error: Error) => message.error(error.message || "Failed to start discovery"),
	});

	const columns: ColumnsType<Company> = [
		{
			title: "Company",
			dataIndex: "name",
			render: (_, record) => (
				<div className="flex flex-col">
					<button
						type="button"
						className="w-fit text-left font-medium text-primary hover:underline"
						onClick={() => navigate(`/companies/${record.id}`)}
					>
						{record.name}
					</button>
					<span className="text-xs text-text-secondary">
						{record.official_domain || "No official domain"}
					</span>
				</div>
			),
		},
		{
			title: "Industry",
			dataIndex: "industry",
			width: 160,
			render: (value: string) => value || "—",
		},
		{
			title: "Location",
			dataIndex: "location",
			width: 140,
			render: (value: string) => value || "—",
		},
		{
			title: "Updated",
			dataIndex: "updated_at",
			width: 180,
			render: formatDateTime,
		},
		{
			title: "Actions",
			key: "actions",
			align: "right",
			width: 280,
			render: (_, record) => (
				<Space size={4} wrap className="justify-end">
					<Button
						size="sm"
						disabled={runMutation.isPending}
						onClick={() => runMutation.mutate(record.id)}
					>
						Start discovery
					</Button>
					<Button size="sm" variant="outline" onClick={() => navigate(`/companies/${record.id}`)}>
						Open
					</Button>
					<Popconfirm
						title="Delete this company?"
						description="All related runs and sources will be removed."
						okText="Delete"
						okButtonProps={{ danger: true }}
						onConfirm={() => deleteMutation.mutate(record.id)}
					>
						<Button size="sm" variant="ghost">
							<Icon icon="mingcute:delete-2-fill" size={16} className="text-error" />
						</Button>
					</Popconfirm>
				</Space>
			),
		},
	];

	return (
		<div className="flex w-full flex-col gap-4">
			<div className="flex items-start justify-between gap-4">
				<div>
					<Typography.Title level={4} className="!mb-1">
						Companies
					</Typography.Title>
					<Typography.Text type="secondary">
						Manage identity anchors and launch footprint discovery runs.
					</Typography.Text>
				</div>
				<Button onClick={() => setCreateOpen(true)}>
					<Icon icon="mingcute:add-line" size={16} />
					New company
				</Button>
			</div>

			<Card>
				<CardHeader className="flex-row items-center justify-between space-y-0">
					<div className="font-medium">Company list</div>
					<Typography.Text type="secondary">{data.length} total</Typography.Text>
				</CardHeader>
				<CardContent>
					{isError ? (
						<Empty
							description="Failed to load companies"
							image={Empty.PRESENTED_IMAGE_SIMPLE}
						>
							<Button variant="outline" onClick={() => refetch()}>
								Retry
							</Button>
						</Empty>
					) : (
						<Table
							rowKey="id"
							size="middle"
							loading={isLoading}
							columns={columns}
							dataSource={data}
							pagination={{ pageSize: 10, showSizeChanger: true, hideOnSinglePage: true }}
							locale={{
								emptyText: (
									<Empty
										image={Empty.PRESENTED_IMAGE_SIMPLE}
										description="No companies yet. Create a target company to begin."
									/>
								),
							}}
							scroll={{ x: 900 }}
						/>
					)}
				</CardContent>
			</Card>

			<Modal
				title="New company"
				open={createOpen}
				onCancel={() => setCreateOpen(false)}
				okText="Save company"
				okButtonProps={{
					htmlType: "submit",
					form: "company-form",
					loading: createMutation.isPending,
				}}
				destroyOnClose
				width={560}
			>
				<CompanyForm onSubmit={(company) => createMutation.mutate(company)} />
			</Modal>
		</div>
	);
}
