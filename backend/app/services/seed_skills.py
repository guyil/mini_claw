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
    {
        "name": "feishu_doc_expert",
        "display_name": "飞书文档专家",
        "description": "读写飞书文档，支持富文本、表格、图片等结构化内容操作。",
        "category": "feishu",
        "instructions": """# 飞书文档专家 Skill

## 核心工具
`feishu_doc` — 统一的飞书文档操作工具。

## Token 提取
从 URL 提取 doc_token: `https://xxx.feishu.cn/docx/ABC123` → `doc_token='ABC123'`

## 读取工作流
1. 先用 `action='read'` 获取纯文本内容和块统计
2. 如果返回结果包含 `hint`（有表格/图片），用 `action='list_blocks'` 获取结构化块数据
3. 对特定块用 `action='get_block'` 查看详情

## 写入工作流
- **替换全文**: `action='write'`, 传入 Markdown 格式的 `content`
- **追加内容**: `action='append'`, 在文档末尾追加
- **插入内容**: `action='insert'`, 需要 `after_block_id`（先用 list_blocks 获取）
- **创建新文档**: `action='create'`, 传入 `title`

## 表格操作
1. `action='create_table'` 创建空表格（指定 row_size, column_size）
2. `action='write_table_cells'` 向表格写入数据（values 为二维数组 JSON）
3. `action='create_table_with_values'` 一步创建带数据的表格

## 块操作
- `action='update_block'` 更新文本内容
- `action='delete_block'` 删除块

## Markdown 支持
写入时支持: 标题(#), 列表(-/1.), 代码块(```), 引用(>), 粗体(**), 斜体(*),
删除线(~~), 链接([text](url)), 分割线(---), 待办(- [ ]/- [x])

## 限制
- 一次最多插入 50 个块
- 图片/文件上传需要有效的 drive 权限

## 完成条件
文档操作完成后调用 skill_complete 标记完成。
""",
        "required_tools": ["feishu_doc"],
        "source": "builtin",
    },
    {
        "name": "feishu_wiki_navigator",
        "display_name": "飞书知识库导航",
        "description": "浏览和管理飞书知识库空间、节点，配合文档工具读写页面内容。",
        "category": "feishu",
        "instructions": """# 飞书知识库导航 Skill

## 核心工具
`feishu_wiki` — 知识库结构操作
`feishu_doc` — 页面内容读写

## 核心工作流: Wiki + Doc 协作

### 浏览知识库
1. `feishu_wiki action='spaces'` → 获取知识库列表
2. `feishu_wiki action='nodes' space_id='xxx'` → 浏览节点树
3. `feishu_wiki action='get' token='xxx'` → 获取节点详情，得到 `obj_token`

### 读取/编辑页面内容
知识库页面的内容操作需要两步：
1. 用 `feishu_wiki action='get'` 获取节点的 `obj_token`
2. 用 `feishu_doc action='read' doc_token='{obj_token}'` 读写内容

### 创建知识库页面
`feishu_wiki action='create' space_id='xxx' title='标题'`

### 移动/重命名
- `feishu_wiki action='move'`
- `feishu_wiki action='rename'`

## 权限提示
如果返回"没有访问权限"，需要在知识库设置中添加机器人为成员。

## 完成条件
操作完成后调用 skill_complete 标记完成。
""",
        "required_tools": ["feishu_wiki", "feishu_doc"],
        "source": "builtin",
    },
    {
        "name": "feishu_bitable_analyst",
        "display_name": "飞书多维表格分析",
        "description": "查询和操作飞书多维表格数据，适用于数据管理和分析场景。",
        "category": "feishu",
        "instructions": """# 飞书多维表格分析 Skill

## 核心工具
`feishu_bitable_get_meta` — 从 URL 获取表格元数据
`feishu_bitable_list_fields` — 列出字段定义
`feishu_bitable_list_records` — 列出数据记录
`feishu_bitable_get_record` — 获取单条记录
`feishu_bitable_create_record` — 创建记录
`feishu_bitable_update_record` — 更新记录
`feishu_bitable_create_app` — 创建新表格
`feishu_bitable_create_field` — 添加字段

## 工作流

### 查看表格数据
1. 用 `feishu_bitable_get_meta` 传入 URL，获取 app_token 和 table_id
2. 用 `feishu_bitable_list_fields` 了解字段结构
3. 用 `feishu_bitable_list_records` 获取数据

### URL 格式
- `/base/APP_TOKEN?table=TABLE_ID`
- `/wiki/NODE_TOKEN?table=TABLE_ID`

### 字段类型
1=Text, 2=Number, 3=SingleSelect, 4=MultiSelect, 5=DateTime,
7=Checkbox, 11=User, 15=URL, 17=Attachment, 20=Formula

### 创建记录
fields 参数为 JSON: `{"字段名": "值"}`

## 完成条件
数据操作完成后调用 skill_complete 标记完成。
""",
        "required_tools": [
            "feishu_bitable_get_meta", "feishu_bitable_list_fields",
            "feishu_bitable_list_records", "feishu_bitable_get_record",
            "feishu_bitable_create_record", "feishu_bitable_update_record",
        ],
        "source": "builtin",
    },
    {
        "name": "feishu_drive_manager",
        "display_name": "飞书云空间管理",
        "description": "浏览、管理飞书云空间中的文件和文件夹，支持文件操作和评论。",
        "category": "feishu",
        "instructions": """# 飞书云空间管理 Skill

## 核心工具
`feishu_drive` — 云空间文件操作

## Actions
- `list` — 列出文件夹内容 (folder_token)
- `info` — 获取文件信息 (file_token, file_type)
- `create_folder` — 创建文件夹 (name, folder_token)
- `move` — 移动文件 (file_token, file_type, target_folder_token)
- `delete` — 删除文件 (file_token, file_type)
- `list_comments` — 列出评论
- `add_comment` — 添加评论
- `reply_comment` — 回复评论

## 文件类型
doc, sheet, bitable, mindnote, file, docx, folder

## 注意事项
- 机器人无法访问根文件夹，需要用户创建文件夹并共享给机器人
- 删除操作不可逆，请确认后再执行

## 完成条件
文件操作完成后调用 skill_complete 标记完成。
""",
        "required_tools": ["feishu_drive"],
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
