import { GLOBAL_CONFIG } from "@/global-config";
import { useUserToken } from "@/store/userStore";
import { useCallback, useEffect } from "react";
import { useRouter } from "../hooks";

type Props = {
	children: React.ReactNode;
};
export default function LoginAuthGuard({ children }: Props) {
	const router = useRouter();
	const { accessToken } = useUserToken();

	const check = useCallback(() => {
		if (GLOBAL_CONFIG.skipAuth) {
			return;
		}
		if (!accessToken) {
			router.replace("/auth/login");
		}
	}, [router, accessToken]);

	useEffect(() => {
		check();
	}, [check]);

	if (GLOBAL_CONFIG.skipAuth || accessToken) {
		return <>{children}</>;
	}

	return null;
}
