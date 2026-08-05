import type { CompanyInput } from "@/types/vestige";
import { Form, Input } from "antd";
import { useEffect } from "react";

type Props = {
	initialValues?: Partial<CompanyInput>;
	onSubmit: (values: CompanyInput) => void;
	formId?: string;
};

export default function CompanyForm({ initialValues, onSubmit, formId = "company-form" }: Props) {
	const [form] = Form.useForm<CompanyInput & { aliases_text?: string }>();

	useEffect(() => {
		form.setFieldsValue({
			name: initialValues?.name ?? "",
			official_domain: initialValues?.official_domain ?? "",
			industry: initialValues?.industry ?? "",
			location: initialValues?.location ?? "",
			aliases_text: (initialValues?.aliases ?? []).join(", "),
		});
	}, [form, initialValues]);

	return (
		<Form
			id={formId}
			form={form}
			layout="vertical"
			requiredMark="optional"
			onFinish={(values) => {
				onSubmit({
					name: values.name.trim(),
					official_domain: (values.official_domain ?? "").trim(),
					industry: (values.industry ?? "").trim(),
					location: (values.location ?? "").trim(),
					aliases: (values.aliases_text ?? "")
						.split(",")
						.map((item) => item.trim())
						.filter(Boolean),
				});
			}}
		>
			<Form.Item
				label="Company name"
				name="name"
				rules={[{ required: true, message: "Company name is required" }]}
			>
				<Input aria-label="Company name" placeholder="Acme Inc." autoFocus />
			</Form.Item>
			<Form.Item
				label="Official domain"
				name="official_domain"
				extra="Used as the primary identity anchor for disambiguation."
			>
				<Input aria-label="Official domain" placeholder="example.com" />
			</Form.Item>
			<div className="grid grid-cols-1 gap-0 sm:grid-cols-2 sm:gap-4">
				<Form.Item label="Industry" name="industry">
					<Input aria-label="Industry" placeholder="Manufacturing" />
				</Form.Item>
				<Form.Item label="Location" name="location">
					<Input aria-label="Location" placeholder="United States" />
				</Form.Item>
			</div>
			<Form.Item
				label="Aliases"
				name="aliases_text"
				extra="Comma-separated alternate names used during search and scoring."
			>
				<Input aria-label="Aliases" placeholder="Acme, Acme Corp" />
			</Form.Item>
		</Form>
	);
}
