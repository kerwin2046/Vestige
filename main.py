import asyncio
from pipeline import run_rag_pipeline
from config import COMPANY_ANCHOR

async def main():
    # 目标公司在 config.COMPANY_ANCHOR 里配置（名称/官网/行业等身份特征）
    final_report = await run_rag_pipeline(COMPANY_ANCHOR["name"])

    print("\n=================== 📝 Company Web Footprint Intelligence ===================\n")
    print(final_report)
    print("\n=============================================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
