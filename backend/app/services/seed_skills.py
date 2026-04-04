"""内置预设 Skills 种子数据

调用 seed_builtin_skills() 将预设 Skill 写入数据库（已存在则跳过）。
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill

logger = logging.getLogger(__name__)

BUILTIN_SKILLS = [
    {
        "name": "product_research",
        "display_name": "选品分析",
        "description": "对目标产品进行全方位选品分析，包括市场容量、竞争格局、利润空间、进入门槛评估。",
        "category": "analysis",
        "instructions": """# 选品分析 Skill

## 目标
帮助用户对指定产品或品类进行系统化选品分析。

## 执行步骤

1. **确认分析目标**：向用户确认要分析的产品/品类/ASIN/关键词
2. **市场数据收集**：
   - 使用 web_fetch 抓取 Amazon 产品页获取基础数据（标题、价格、评分、评论数）
   - 记录竞品的价格区间和评分分布
3. **竞争格局分析**：
   - 头部卖家数量和市占率
   - 评论数分布（判断市场成熟度）
   - 新品进入难度
4. **利润估算**：
   - 售价 - 采购成本 - 物流 - 平台佣金 - 广告费
   - 给出毛利率和 ROI 估算
5. **结论与建议**：
   - 综合评分（1-10）
   - 明确给出「建议进入 / 谨慎观望 / 不建议」
   - 列出关键风险点

## 输出格式
使用表格和结构化列表，关键数据加粗。

## 完成条件
分析报告输出完成后调用 skill_complete 标记完成。
""",
        "required_tools": ["web_fetch", "memory_write"],
        "source": "builtin",
    },
    {
        "name": "competitor_analysis",
        "display_name": "竞品调研",
        "description": "深入分析指定竞品的 listing、价格策略、评价结构和运营手法。",
        "category": "analysis",
        "instructions": """# 竞品调研 Skill

## 目标
对指定竞品进行深度调研，输出可操作的竞争情报。

## 执行步骤

1. **获取竞品链接**：向用户确认要调研的 ASIN 或产品链接
2. **Listing 分析**：
   - 使用 web_fetch 抓取产品页
   - 分析标题关键词策略
   - 提取卖点（Bullet Points）核心诉求
   - 评估主图和 A+ 内容质量
3. **评价分析**：
   - 好评关键词提取
   - 差评痛点归纳
   - 评价真实性判断
4. **价格策略**：
   - 当前售价和历史价格趋势
   - 优惠券/促销策略
5. **输出报告**：
   - 竞品优劣势总结
   - 差异化机会点
   - 可借鉴的运营手法

## 完成条件
调研报告输出完成后调用 skill_complete 标记完成。
""",
        "required_tools": ["web_fetch", "memory_write"],
        "source": "builtin",
    },
    {
        "name": "listing_optimizer",
        "display_name": "Listing 优化",
        "description": "优化 Amazon 产品 listing 的标题、卖点、描述和关键词。",
        "category": "operations",
        "instructions": """# Listing 优化 Skill

## 目标
帮助用户优化 Amazon 产品 listing，提升搜索排名和转化率。

## 执行步骤

1. **获取当前 Listing**：
   - 使用 web_fetch 抓取用户指定的产品页
   - 提取当前标题、卖点、描述
2. **分析优化空间**：
   - 标题：是否包含核心关键词、品牌词位置、字符数是否合理
   - 卖点：是否突出核心卖点、是否包含使用场景
   - 描述：是否有 A+ 内容、文案吸引力
3. **生成优化方案**：
   - 新标题（2-3 个方案）
   - 新卖点（5 条）
   - 新描述文案
   - 后端搜索关键词建议
4. **对比说明**：
   - 新旧对比表格
   - 每项修改的理由

## 完成条件
优化方案输出完成后调用 skill_complete 标记完成。
""",
        "required_tools": ["web_fetch"],
        "source": "builtin",
    },
]


async def seed_builtin_skills(db: AsyncSession) -> list[dict]:
    """将内置 Skill 写入数据库，已存在则跳过。返回写入结果摘要。"""
    results = []
    for skill_data in BUILTIN_SKILLS:
        existing = await db.execute(
            select(Skill).where(Skill.name == skill_data["name"])
        )
        if existing.scalar_one_or_none():
            results.append({"name": skill_data["name"], "status": "已存在，跳过"})
            continue

        skill = Skill(
            name=skill_data["name"],
            display_name=skill_data.get("display_name"),
            description=skill_data["description"],
            category=skill_data.get("category"),
            instructions=skill_data["instructions"],
            required_tools=skill_data.get("required_tools", []),
            source=skill_data.get("source", "builtin"),
            scope="global",
        )
        db.add(skill)
        results.append({"name": skill_data["name"], "status": "已创建"})

    await db.flush()
    return results
