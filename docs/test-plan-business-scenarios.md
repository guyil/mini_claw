# 小爪 (Mini Claw) 跨境电商 AI 助手 — 业务场景测试计划

## 概述

本文档是小爪 AI 助手的业务场景验收测试计划。测试从**跨境电商用户个人助理**的视角出发，覆盖日常高频业务场景，验证 Agent 在真实工作流中的表现。

主要沟通平台为**飞书**，测试重点包括：
- Agent 是否能正确理解用户意图并选择合适的工具/技能
- 工具调用链是否完整、参数是否正确
- 飞书集成（文档、多维表格、知识库、日历、任务、消息）是否可靠
- 记忆系统是否能有效维护跨会话连续性
- 定时任务与自动化流程是否稳定运行
- 回复质量是否满足专业助理标准（结构化、有判断、可执行）

### 使用方式

1. 依次进入每个场景，按照「用户消息」列的内容向 Agent 发送消息
2. 对照「期望行为」和「验证要点」检查 Agent 的实际响应
3. 在「测试结果」列记录 PASS / FAIL / PARTIAL
4. 对于 FAIL 的用例，记录实际行为和问题描述

### 前置条件

| 条件 | 说明 |
|------|------|
| 后端服务 | `uvicorn app.main:app --reload --port 8000` 运行中 |
| 前端服务 | `npm run dev` 运行中，访问 `localhost:3000` |
| 数据库 | PostgreSQL + pgvector 已启动，`alembic upgrade head` 已执行 |
| 飞书配置 | `.env` 中 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 已配置 |
| 飞书授权 | 测试用户已完成飞书 OAuth 授权 |
| 内置技能 | 已执行 `POST /skills/seed` 初始化内置技能 |
| Perplexity | `.env` 中 `PERPLEXITY_API_KEY` 已配置（场景 1/2/9 需要） |
| Sandbox | Docker 已启动，`mclaw-sandbox:latest` 镜像已构建（场景 9 需要） |

---

## 能力矩阵

| 场景 | 核心工具 | 关联技能 | 飞书服务 |
|------|---------|---------|---------|
| 1. 选品调研与分析 | web_search, web_fetch, memory_write | product_research | - |
| 2. 竞品监控与分析 | web_fetch, web_search, memory_write | competitor_analysis | - |
| 3. Listing 优化 | web_fetch | listing_optimizer | - |
| 4. 飞书文档协作 | feishu_doc | feishu_doc_expert | feishu_doc_service |
| 5. 飞书多维表格数据管理 | feishu_bitable_* | feishu_bitable_analyst | feishu_bitable_service |
| 6. 飞书知识库管理 | feishu_wiki, feishu_doc | feishu_wiki_navigator | feishu_wiki_service, feishu_doc_service |
| 7. 日程与任务管理 | feishu_calendar_*, feishu_task_* | - | feishu_calendar_service, feishu_task_service |
| 8. 定时任务与自动化报告 | schedule_task | - | delivery_service |
| 9. 跨境运营数据分析 | exec_command, web_search, feishu_doc | - | feishu_doc_service |
| 10. 记忆与用户画像管理 | memory_*, update_soul, update_user_context | - | - |

---

## 场景 1：选品调研与分析

### 业务背景

跨境电商卖家在进入新品类前，需要对目标产品进行市场容量、竞争格局、利润空间和进入门槛的系统评估。这是最核心的决策环节，Agent 需要综合运用联网搜索和 Amazon 数据抓取来提供有依据的分析。

### 涉及工具与技能

- **工具**: `web_search` (Perplexity), `web_fetch` (含 Amazon listing 解析), `memory_write`, `memory_search`
- **技能**: `product_research`（选品分析）
- **关键代码**: `backend/app/tools/perplexity_tools.py`, `backend/app/tools/web_tools.py`, `backend/app/services/seed_skills.py`

### 测试用例

| # | 用户消息 | 期望行为 | 验证要点 |
|---|---------|---------|---------|
| 1.1 | "帮我分析一下宠物自动喂食器在美国亚马逊的市场情况" | Agent 应激活 `product_research` 技能，调用 `web_search` 搜索市场数据，可能调用 `web_fetch` 抓取 Amazon 搜索结果页或具体 listing | (1) 是否调用了 `activate_skill("product_research")`<br>(2) 是否使用了 `web_search` 获取市场数据<br>(3) 输出是否包含市场容量、竞争格局、价格区间等结构化信息<br>(4) 是否给出了明确的进入建议 |
| 1.2 | "这个 ASIN B0XXXXXXXXX 的产品怎么样？值得跟卖吗？" | Agent 应调用 `web_fetch` 抓取该 Amazon 产品页，利用 Amazon listing 专用解析器提取关键数据，给出跟卖可行性分析 | (1) `web_fetch` 是否使用了用户提供的原始 ASIN（不得修改）<br>(2) 是否提取了价格、评分、评论数、BSR 等关键指标<br>(3) 是否分析了跟卖风险（品牌保护、专利等） |
| 1.3 | "对比一下这三个品类的选品潜力：便携搅拌机、电动牙刷收纳盒、硅胶冰格" | Agent 应对三个品类分别搜索数据，最终以对比表格形式呈现分析结果 | (1) 是否对三个品类都进行了数据收集<br>(2) 是否使用了表格做横向对比<br>(3) 对比维度是否包括市场容量、竞争度、利润率、进入门槛<br>(4) 是否给出了排序推荐 |
| 1.4 | "我预算大概 3 万美金，主做厨房小家电，帮我推荐 3 个值得做的细分品类" | Agent 应结合预算约束和品类方向，搜索并推荐具体的细分方向 | (1) 推荐是否考虑了预算约束（首批采购+FBA费用）<br>(2) 每个推荐是否有数据支撑<br>(3) 是否标注了数据来源和置信度<br>(4) 是否调用 `memory_write` 记录用户的预算和品类偏好 |
| 1.5 | "上次我们讨论过的那个选品方向，你还记得吗？" | Agent 应调用 `memory_search` 查找之前的选品讨论记录 | (1) 是否调用了 `memory_search`<br>(2) 如果有记忆，是否准确回忆了之前的讨论内容<br>(3) 如果没有找到，是否如实告知而非编造 |
| 1.6 | "搜一下最近宠物用品在 Amazon 上有什么新趋势" | Agent 应调用 `web_search` 搜索实时市场趋势 | (1) 是否调用了 `web_search` 而非 `web_fetch`<br>(2) 搜索 query 是否精准<br>(3) 返回结果是否包含 Perplexity 的引用来源<br>(4) 是否整理为结构化的趋势分析 |
| 1.7 | "记住：我主做美国站，类目偏好是家居厨房，客单价目标 20-40 美金" | Agent 应调用 `memory_write` 记录这些关键业务偏好 | (1) 是否调用了 `memory_write`<br>(2) 记忆内容是否完整覆盖了站点、类目、客单价三个维度<br>(3) 是否同时调用了 `update_user_context` 更新用户画像 |
| 1.8 | "帮我看看 amazon.com/dp/B0XXXXXXXXX 这个链接的产品详情" | Agent 应调用 `web_fetch` 并触发 Amazon 专用解析逻辑 | (1) URL 是否被原样传入 `web_fetch`<br>(2) 是否走了 Amazon listing 专用解析（`_parse_amazon_listing`）<br>(3) 输出是否包含标题、价格、评分、评论数等结构化字段 |

---

## 场景 2：竞品监控与分析

### 业务背景

了解竞争对手的产品策略、定价、评价和运营手法是跨境电商日常工作的重要组成部分。卖家需要定期分析竞品 listing，挖掘差异化机会和可借鉴的运营策略。

### 涉及工具与技能

- **工具**: `web_fetch`, `web_search`, `memory_write`, `memory_search`
- **技能**: `competitor_analysis`（竞品调研）
- **关键代码**: `backend/app/tools/web_tools.py`, `backend/app/services/seed_skills.py`

### 测试用例

| # | 用户消息 | 期望行为 | 验证要点 |
|---|---------|---------|---------|
| 2.1 | "帮我深度分析这个竞品：amazon.com/dp/B0YYYYYYYYY" | Agent 应激活 `competitor_analysis` 技能，调用 `web_fetch` 抓取产品页，分析 listing 各维度 | (1) 是否激活了 `competitor_analysis` 技能<br>(2) 是否调用了 `web_fetch` 抓取产品页<br>(3) 分析是否覆盖标题关键词策略、卖点、价格、评论结构<br>(4) 是否给出了差异化建议 |
| 2.2 | "这个竞品最近有没有调价或者做促销？" | Agent 应调用 `web_search` 搜索竞品的历史价格和促销信息 | (1) 是否尝试获取价格变动数据<br>(2) 如果无法获取精确历史数据，是否如实说明工具限制<br>(3) 是否建议替代方案（如第三方工具 Keepa/CamelCamelCamel） |
| 2.3 | "看一下这个竞品的差评都在说什么，有没有我们能利用的痛点" | Agent 应抓取产品页面，重点分析差评中的共性问题 | (1) 是否抓取并分析了评价内容<br>(2) 差评痛点是否分类归纳<br>(3) 是否提出了可利用的差异化卖点建议 |
| 2.4 | "帮我对比我的产品和这两个竞品的 listing 质量：B0AAAAAAAAA 和 B0BBBBBBBBB" | Agent 应分别抓取两个竞品页面，对比 listing 各项要素 | (1) 是否分别调用了 `web_fetch` 抓取两个 ASIN<br>(2) 对比是否使用了表格格式<br>(3) 对比维度是否包括标题、卖点、图片数量、评论数、评分 |
| 2.5 | "把这次的竞品分析结论记下来，下次我问到这个品类的时候能参考" | Agent 应调用 `memory_write` 保存分析结论 | (1) 是否调用了 `memory_write`<br>(2) 记忆内容是否包含关键数据和结论<br>(3) 记忆类型/标签是否合理（便于后续语义检索） |
| 2.6 | "我之前让你分析过的那几个竞品，现在汇总一下主要发现" | Agent 应调用 `memory_search` 检索之前的竞品分析记录 | (1) 是否调用了 `memory_search`<br>(2) 检索结果是否完整覆盖之前分析过的竞品<br>(3) 汇总是否结构化呈现 |
| 2.7 | "我的主要竞争对手是 AnkerMake，帮我搜一下他们最近的动态" | Agent 应调用 `web_search` 搜索品牌近期新闻和动态 | (1) 搜索 query 是否包含品牌名<br>(2) 结果是否包含新品、促销、战略调整等动态<br>(3) 引用来源是否标注 |
| 2.8 | "对比一下 Top 3 的竞品定价策略，给我一个合理的定价建议" | Agent 应综合竞品数据，给出有依据的定价建议 | (1) 是否分析了至少 3 个竞品的价格<br>(2) 定价建议是否考虑了成本、竞争、利润目标<br>(3) 是否给出了价格区间而非单一数字 |

---

## 场景 3：Listing 优化

### 业务背景

Listing 质量直接影响搜索排名和转化率。卖家需要 Agent 能够分析现有 listing 的不足，生成符合 Amazon A9/COSMO 算法要求的优化方案，包括标题、五点描述、后端关键词等。

### 涉及工具与技能

- **工具**: `web_fetch`, `web_search`
- **技能**: `listing_optimizer`（Listing 优化）
- **关键代码**: `backend/app/services/seed_skills.py`

### 测试用例

| # | 用户消息 | 期望行为 | 验证要点 |
|---|---------|---------|---------|
| 3.1 | "帮我优化这个产品的 listing：amazon.com/dp/B0CCCCCCCCC" | Agent 应激活 `listing_optimizer` 技能，先抓取现有 listing 再生成优化方案 | (1) 是否激活了 `listing_optimizer` 技能<br>(2) 是否先调用 `web_fetch` 读取现有 listing<br>(3) 优化方案是否包含标题、卖点、描述、关键词四个维度<br>(4) 是否提供了新旧对比 |
| 3.2 | "我的产品是一款不锈钢保温杯，主打户外运动场景，帮我写 5 条 bullet points" | Agent 应根据产品特点和场景生成 5 条卖点描述 | (1) 是否生成了 5 条卖点<br>(2) 卖点是否突出了"不锈钢""保温""户外运动"等核心关键词<br>(3) 是否符合 Amazon bullet points 的格式规范（大写开头、字符数限制） |
| 3.3 | "帮我这个标题做 A/B 测试方案，当前标题是：[具体标题]" | Agent 应分析当前标题的关键词布局，生成 2-3 个测试方案 | (1) 是否分析了现有标题的关键词布局<br>(2) 测试方案之间的差异点是否明确<br>(3) 是否说明了每个方案的侧重点和预期效果 |
| 3.4 | "帮我生成一组后端搜索关键词，我的产品是电动开罐器" | Agent 应结合产品特点和搜索习惯生成后端关键词 | (1) 关键词是否覆盖了核心词、长尾词、场景词<br>(2) 是否避免了与标题重复的词<br>(3) 是否控制了总字节数（Amazon 限制 250 bytes） |
| 3.5 | "这个 listing 的图片和 A+ 内容你能看到吗？给我一些改进建议" | Agent 应如实说明工具能力边界，同时提供可行的建议 | (1) 是否说明了 `web_fetch` 无法解析图片内容<br>(2) 是否仍然基于文字信息提供了有价值的 A+ 建议<br>(3) 是否建议用户上传图片以获得更精准建议 |
| 3.6 | "帮我用西班牙语重写这个 listing，我要拓展墨西哥站" | Agent 应将 listing 翻译并本地化为西班牙语 | (1) 翻译是否准确且自然<br>(2) 是否考虑了墨西哥市场的本地化表达<br>(3) 是否保留了关键词策略 |
| 3.7 | "看看排名前三的竞品 listing 和我的有什么差距" | Agent 应抓取竞品 listing 并与用户产品做对比分析 | (1) 是否抓取了多个竞品页面<br>(2) 对比分析是否涵盖标题、卖点、评分等维度<br>(3) 差距分析是否转化为可操作的优化建议 |

---

## 场景 4：飞书文档协作

### 业务背景

跨境电商团队在飞书上协作处理大量文档，包括选品报告、运营周报、SOP 文档、会议纪要等。Agent 需要能读写飞书文档，帮助用户快速创建和整理各类业务文档。

### 涉及工具与技能

- **工具**: `feishu_doc` (read/write/append/insert/create/list_blocks/create_table_with_values)
- **技能**: `feishu_doc_expert`（飞书文档专家）
- **关键代码**: `backend/app/tools/feishu_tools.py` (`_create_doc_tool`), `backend/app/services/feishu_doc_service.py`

### 测试用例

| # | 用户消息 | 期望行为 | 验证要点 |
|---|---------|---------|---------|
| 4.1 | "帮我读一下这个文档的内容：https://xxx.feishu.cn/docx/ABC123" | Agent 应从 URL 中提取 `doc_token`，调用 `feishu_doc action='read'` | (1) 是否正确提取了 doc_token "ABC123"<br>(2) 是否调用了 `feishu_doc` 的 `read` action<br>(3) 返回内容是否完整展示给用户 |
| 4.2 | "帮我新建一个文档，标题叫'Q2 选品调研报告'" | Agent 应调用 `feishu_doc action='create'`，传入标题 | (1) 是否调用了 `create` action<br>(2) `title` 参数是否为 "Q2 选品调研报告"<br>(3) 是否返回了新文档的链接 |
| 4.3 | "在刚才那个文档末尾追加一段：'## 市场分析\n\n经过调研，宠物用品市场...'" | Agent 应调用 `feishu_doc action='append'`，将内容追加到文档末尾 | (1) 是否使用了 `append` action（而非 `write` 覆盖）<br>(2) 内容是否保留了 Markdown 格式<br>(3) 是否在正确的文档上操作 |
| 4.4 | "在这个文档里创建一个 5 行 4 列的表格，表头是：产品名称、售价、BSR、评分" | Agent 应调用 `create_table_with_values` 或先 `create_table` 再 `write_table_cells` | (1) 是否创建了表格<br>(2) 行列数是否正确（5行4列）<br>(3) 表头内容是否正确 |
| 4.5 | "帮我看看这个文档的结构，有哪些内容块" | Agent 应调用 `feishu_doc action='list_blocks'` | (1) 是否调用了 `list_blocks` action<br>(2) 是否以结构化形式展示了文档的块信息<br>(3) 是否说明了各块的类型（文本、表格、图片等） |
| 4.6 | "把这个文档第二段的内容改成：'经过为期两周的深入调研，我们发现...'" | Agent 应先 `list_blocks` 找到目标块 ID，然后 `update_block` | (1) 是否先查询了块列表以获取 block_id<br>(2) 是否调用了 `update_block` action<br>(3) 修改内容是否正确 |
| 4.7 | "飞书文档打不开，提示没有权限，怎么办？" | Agent 应解释权限问题的原因，提供解决方案 | (1) 是否说明了可能需要飞书授权<br>(2) 是否引导用户检查文档共享设置<br>(3) 如果是 token 过期，是否调用 `feishu_auth action='check'` 诊断 |
| 4.8 | "帮我把今天的选品会议纪要写到飞书文档里，内容如下：参会人员：张三、李四..." | Agent 应创建新文档或追加到指定文档，内容格式化为规范的会议纪要 | (1) 是否询问了写入目标（新建还是追加到已有文档）<br>(2) 内容是否格式化为结构化会议纪要<br>(3) 是否保留了用户提供的所有信息 |
| 4.9 | "帮我删除文档 https://xxx.feishu.cn/docx/DEF456 中的第三个内容块" | Agent 应先 `list_blocks` 确认第三个块的 ID，然后确认后调用 `delete_block` | (1) 是否先列出了块列表让用户确认<br>(2) 删除操作前是否进行了确认（安全边界规则）<br>(3) 是否成功调用了 `delete_block` |
| 4.10 | "这个文档太长了，帮我生成一个摘要" | Agent 应调用 `feishu_doc action='read'` 获取全文，然后生成摘要 | (1) 是否先读取了文档内容<br>(2) 摘要是否覆盖了文档的核心要点<br>(3) 摘要长度是否合理 |

---

## 场景 5：飞书多维表格数据管理

### 业务背景

跨境电商团队广泛使用飞书多维表格管理产品库、订单跟踪表、供应商信息、广告数据等。Agent 需要能够查询、创建、更新表格数据，帮助用户高效管理和分析结构化数据。

### 涉及工具与技能

- **工具**: `feishu_bitable_get_meta`, `feishu_bitable_list_fields`, `feishu_bitable_list_records`, `feishu_bitable_get_record`, `feishu_bitable_create_record`, `feishu_bitable_update_record`, `feishu_bitable_create_app`, `feishu_bitable_create_field`
- **技能**: `feishu_bitable_analyst`（飞书多维表格分析）
- **关键代码**: `backend/app/tools/feishu_tools.py` (`_create_bitable_tools`), `backend/app/services/feishu_bitable_service.py`

### 测试用例

| # | 用户消息 | 期望行为 | 验证要点 |
|---|---------|---------|---------|
| 5.1 | "帮我查一下这个多维表格的数据：https://xxx.feishu.cn/base/APP123?table=tblXXX" | Agent 应激活 `feishu_bitable_analyst` 技能，先获取 meta 再依次查询字段和记录 | (1) 是否调用 `feishu_bitable_get_meta` 解析 URL<br>(2) 是否调用 `feishu_bitable_list_fields` 了解字段结构<br>(3) 是否调用 `feishu_bitable_list_records` 获取数据<br>(4) 数据展示是否使用了表格格式 |
| 5.2 | "在产品库表格里新增一条记录：产品名称'蓝牙耳机'，售价 29.99，状态'在售'" | Agent 应调用 `feishu_bitable_create_record`，fields 为对应的 JSON | (1) 是否调用了 `create_record`<br>(2) fields JSON 是否正确包含了三个字段<br>(3) 字段名称是否与表格中的字段名完全匹配 |
| 5.3 | "把记录 recXXX 的价格改成 24.99" | Agent 应调用 `feishu_bitable_update_record`，更新指定字段 | (1) 是否正确使用了 record_id<br>(2) fields 是否只包含需要更新的字段<br>(3) 更新后是否确认了操作结果 |
| 5.4 | "帮我创建一个新的多维表格，用来跟踪 FBA 发货" | Agent 应调用 `feishu_bitable_create_app` 创建表格，然后用 `create_field` 添加必要字段 | (1) 是否先创建了表格<br>(2) 是否根据 FBA 发货场景自动建议了合理的字段结构<br>(3) 是否创建了必要的字段（货件号、SKU、数量、状态、发货日期等） |
| 5.5 | "这个表格里一共有多少条记录？按'状态'字段统计一下各状态的数量" | Agent 应获取所有记录并做统计分析 | (1) 是否调用了 `list_records`<br>(2) 统计结果是否准确<br>(3) 是否以结构化方式呈现分组统计 |
| 5.6 | "在这个表格中增加一个'利润率'字段，类型是数字" | Agent 应调用 `feishu_bitable_create_field`，field_type=2（Number） | (1) 是否调用了 `create_field`<br>(2) field_type 是否为 2（Number）<br>(3) 字段名称是否正确 |
| 5.7 | "帮我把这个表格的数据导出成一个汇总分析，写到飞书文档里" | Agent 应先读取表格数据，然后创建或写入飞书文档 | (1) 是否先读取了表格数据<br>(2) 是否调用了 `feishu_doc` 写入文档<br>(3) 汇总内容是否包含关键数据和分析 |
| 5.8 | "这个多维表格链接打开报错了，能帮我看看什么情况吗？" | Agent 应尝试调用 `get_meta`，根据错误信息判断原因 | (1) 是否尝试了 `get_meta` 操作<br>(2) 是否根据返回的错误信息（权限/URL格式/不存在）给出准确诊断<br>(3) 如果是权限问题，是否引导用户授权 |

---

## 场景 6：飞书知识库管理

### 业务背景

跨境电商公司使用飞书知识库存储产品 SOP、运营手册、供应商信息、政策变更记录等。Agent 需要能够浏览知识库结构、读取页面内容、创建新页面，帮助团队维护知识资产。

### 涉及工具与技能

- **工具**: `feishu_wiki` (spaces/nodes/get/create/move/rename), `feishu_doc` (read/write)
- **技能**: `feishu_wiki_navigator`（飞书知识库导航）
- **关键代码**: `backend/app/tools/feishu_tools.py` (`_create_wiki_tool`), `backend/app/services/feishu_wiki_service.py`

### 测试用例

| # | 用户消息 | 期望行为 | 验证要点 |
|---|---------|---------|---------|
| 6.1 | "帮我看看公司有哪些知识库" | Agent 应激活 `feishu_wiki_navigator` 技能，调用 `feishu_wiki action='spaces'` | (1) 是否调用了 `spaces` action<br>(2) 是否列出了所有可访问的知识库及其 space_id<br>(3) 展示是否清晰（名称 + 描述） |
| 6.2 | "浏览一下'运营手册'知识库的目录结构" | Agent 应先找到知识库 space_id，然后调用 `feishu_wiki action='nodes'` | (1) 是否正确定位了目标知识库<br>(2) 是否调用了 `nodes` action 获取节点树<br>(3) 目录结构是否层级清晰 |
| 6.3 | "帮我读一下知识库中'FBA 发货流程'这篇文档的内容" | Agent 应先通过 `feishu_wiki action='get'` 获取节点的 `obj_token`，然后用 `feishu_doc action='read'` 读取内容 | (1) 是否理解了 wiki 和 doc 的两步操作流程<br>(2) 是否先 `get` 获取 `obj_token`<br>(3) 是否用 `feishu_doc read` 读取了实际内容 |
| 6.4 | "在'产品库'知识库下创建一个新页面，标题叫'2026 Q2 新品规划'" | Agent 应调用 `feishu_wiki action='create'` | (1) 是否使用了正确的 space_id<br>(2) title 是否正确<br>(3) 创建后是否返回了页面链接 |
| 6.5 | "把'退货处理流程'这个页面从'运营手册'移到'客服手册'知识库下" | Agent 应调用 `feishu_wiki action='move'`，指定目标 space 和 parent | (1) 是否调用了 `move` action<br>(2) 源节点和目标位置是否正确<br>(3) 移动前是否确认了操作（跨知识库移动） |
| 6.6 | "帮我在知识库的'选品分析'页面末尾追加今天的分析结论" | Agent 应先获取 wiki 节点 obj_token，然后用 `feishu_doc append` 追加内容 | (1) 是否正确完成了 wiki → doc 的二步流程<br>(2) 是否使用 `append` 而非 `write`（避免覆盖） |
| 6.7 | "把'物流方案对比'这个页面重命名为'2026 物流方案对比'" | Agent 应调用 `feishu_wiki action='rename'` | (1) 是否调用了 `rename` action<br>(2) 新标题是否正确<br>(3) 是否需要知道 node_token 和 space_id |
| 6.8 | "知识库提示'没有访问权限'，怎么解决？" | Agent 应解释权限配置方式 | (1) 是否说明需要在知识库设置中添加机器人为成员<br>(2) 是否提供了具体操作步骤<br>(3) 如果是用户 token 问题，是否引导重新授权 |

---

## 场景 7：日程与任务管理

### 业务背景

跨境电商运营涉及大量时间节点管理：供应商交货日期、促销活动时间窗口、广告投放计划、会议安排等。Agent 需要帮助用户通过飞书日历和任务系统高效管理这些事项。

### 涉及工具与技能

- **工具**: `feishu_calendar_list`, `feishu_calendar_create`, `feishu_task_list`, `feishu_task_create`, `memory_write`
- **关键代码**: `backend/app/tools/feishu_tools.py` (`_create_calendar_tools`, `_create_task_tools`), `backend/app/services/feishu_calendar_service.py`, `backend/app/services/feishu_task_service.py`

### 测试用例

| # | 用户消息 | 期望行为 | 验证要点 |
|---|---------|---------|---------|
| 7.1 | "看看我这周有什么安排" | Agent 应调用 `feishu_calendar_list`，days=7 | (1) 是否调用了 `feishu_calendar_list`<br>(2) days 参数是否为 7<br>(3) 日程是否按时间排序展示<br>(4) 是否包含日程标题和时间 |
| 7.2 | "帮我创建一个日程：下周三下午 2 点到 3 点，选品评审会，邀请张三和李四" | Agent 应调用 `feishu_calendar_create`，正确转换时间为时间戳 | (1) 是否正确计算了"下周三下午2点"的时间戳<br>(2) summary 是否为"选品评审会"<br>(3) attendees 是否包含了两个参会人<br>(4) 时间区间是否正确（1小时） |
| 7.3 | "查看我所有待办任务" | Agent 应调用 `feishu_task_list` | (1) 是否调用了 `feishu_task_list`<br>(2) 任务列表是否清晰展示了标题、截止日期、状态<br>(3) 是否按优先级或截止日期排序 |
| 7.4 | "帮我创建一个任务：跟进供应商报价，截止日期本周五" | Agent 应调用 `feishu_task_create`，正确设置截止时间 | (1) summary 是否为"跟进供应商报价"<br>(2) due 是否正确转换为"本周五"的时间戳<br>(3) 创建后是否确认了任务详情 |
| 7.5 | "今天的日程太满了，帮我整理一下时间冲突" | Agent 应获取今天的日程，分析是否有时间重叠 | (1) 是否调用了 `feishu_calendar_list` 且 days=1<br>(2) 是否检测了时间重叠<br>(3) 如有冲突是否给出了调整建议 |
| 7.6 | "提醒我明天上午 10 点和供应商开电话会议" | Agent 应判断是创建日程还是创建任务（或两者），并执行 | (1) 是否创建了日历日程（更适合会议场景）<br>(2) 时间是否为明天上午 10 点<br>(3) 是否同时调用了 `memory_write` 记录这个安排 |
| 7.7 | "帮我看看下个月有哪些重要时间节点" | Agent 应调用 `feishu_calendar_list`，days=30 | (1) days 参数是否为约 30 天<br>(2) 是否筛选了重要/关键日程<br>(3) 展示是否包含日期和事项 |
| 7.8 | "创建一个任务：准备 Prime Day 促销方案，截止 6 月 15 日，指派给我自己" | Agent 应调用 `feishu_task_create`，包含截止日期和指派人 | (1) 是否正确设置了任务标题<br>(2) due 是否对应 6 月 15 日的时间戳<br>(3) assignees 是否正确设置 |

---

## 场景 8：定时任务与自动化报告

### 业务背景

跨境电商运营需要定期获取数据报告（如每日竞品价格监控、每周运营数据汇总），设置关键事项提醒（如库存预警、促销截止日期）。Agent 的定时任务功能可以实现这些自动化需求。

### 涉及工具与技能

- **工具**: `schedule_task` (list/add/update/remove/run_now)
- **关键代码**: `backend/app/tools/schedule_tools.py`, `backend/app/services/scheduler_service.py`, `backend/app/services/job_executor.py`

### 测试用例

| # | 用户消息 | 期望行为 | 验证要点 |
|---|---------|---------|---------|
| 8.1 | "每天早上 9 点帮我查一下主要竞品的价格变化，生成一份简报" | Agent 应调用 `schedule_task action='add'`，schedule_type='cron', schedule_value='0 9 * * *' | (1) 是否调用了 `schedule_task` 的 `add` action<br>(2) cron 表达式是否为 `0 9 * * *`<br>(3) message 是否包含了"查竞品价格+生成简报"的完整指令<br>(4) 是否返回了任务 ID 和下次执行时间 |
| 8.2 | "每周五下午 5 点帮我总结本周运营数据" | Agent 应创建 cron 定时任务，schedule_value='0 17 * * 5' | (1) cron 表达式是否正确（周五 17:00）<br>(2) timezone 是否为 Asia/Shanghai<br>(3) 任务名称是否合理 |
| 8.3 | "提醒我下周一上午 10 点检查广告投放数据" | Agent 应创建一次性定时任务，schedule_type='at' | (1) schedule_type 是否为 'at'<br>(2) 时间戳是否对应"下周一上午10点"<br>(3) 是否包含了正确的时区 |
| 8.4 | "看看我现在有哪些定时任务" | Agent 应调用 `schedule_task action='list'` | (1) 是否调用了 `list` action<br>(2) 是否展示了所有任务的名称、调度配置、下次执行时间<br>(3) 是否区分了启用和禁用的任务 |
| 8.5 | "把那个竞品价格监控的频率改成每 2 小时一次" | Agent 应调用 `schedule_task action='update'`，修改调度配置 | (1) 是否调用了 `update` action<br>(2) 是否正确识别了目标任务（可能需要先 list）<br>(3) schedule_type 是否改为 'interval'，schedule_value 是否为 '7200' |
| 8.6 | "取消昨天设的那个提醒" | Agent 应先 list 找到对应任务，然后调用 `schedule_task action='remove'` | (1) 是否先列出任务让用户确认<br>(2) 是否调用了 `remove` action<br>(3) 删除前是否确认了操作 |
| 8.7 | "立即运行一次竞品监控任务，我想看看效果" | Agent 应调用 `schedule_task action='run_now'` | (1) 是否调用了 `run_now` action<br>(2) 是否正确识别了目标任务的 job_id |
| 8.8 | "每隔 4 小时检查一次库存水位，如果低于 100 就提醒我" | Agent 应创建 interval 定时任务 | (1) schedule_type 是否为 'interval'<br>(2) schedule_value 是否为 '14400'（4*3600）<br>(3) message 是否包含了"检查库存+低于100提醒"的完整指令 |
| 8.9 | "我的定时任务支持通过飞书发送结果吗？" | Agent 应解释 delivery_mode 选项 | (1) 是否说明了 delivery_mode 支持 chat/feishu/webhook<br>(2) 是否解释了各模式的区别<br>(3) 是否主动询问用户想要哪种方式 |
| 8.10 | "把所有定时任务的交付方式都改成飞书通知" | Agent 应逐个更新任务的 delivery_mode | (1) 是否先列出了所有任务<br>(2) 是否逐个调用 `update` 修改 delivery_mode<br>(3) 是否确认了所有更新结果 |

---

## 场景 9：跨境运营数据分析

### 业务背景

跨境电商运营需要频繁进行数据分析：计算利润率、分析广告 ACOS、评估库存周转率、汇总多渠道销售数据等。Agent 通过沙箱环境执行代码，可以完成复杂的数据处理和计算任务。

### 涉及工具与技能

- **工具**: `exec_command` (沙箱执行), `write_file`, `read_file`, `web_search`, `feishu_doc`
- **关键代码**: `backend/app/tools/sandbox_tools.py`, `backend/app/services/sandbox_pool.py`

### 测试用例

| # | 用户消息 | 期望行为 | 验证要点 |
|---|---------|---------|---------|
| 9.1 | "帮我算一下这个产品的利润：售价 29.99 美元，采购成本 8 美元，FBA 费用 5.5 美元，头程 2 美元，广告费占比 15%" | Agent 应进行利润计算，可以直接计算或通过沙箱执行 | (1) 计算是否正确（各项成本扣除后的净利润）<br>(2) 是否计算了利润率和 ROI<br>(3) 是否列出了完整的成本分解表 |
| 9.2 | "我有一组广告数据，帮我分析 ACOS：花费 500 美元，销售额 2000 美元，点击 1200 次，展示 50000 次" | Agent 应计算并分析广告效果指标 | (1) ACOS 计算是否正确（25%）<br>(2) 是否同时计算了 CTR、CPC 等辅助指标<br>(3) 是否给出了 ACOS 水平的评价和优化建议 |
| 9.3 | "写一个 Python 脚本帮我计算 FBA 费用，输入产品重量和尺寸" | Agent 应通过沙箱写入并执行 Python 脚本 | (1) 是否调用了 `write_file` 写入脚本<br>(2) 是否调用了 `exec_command` 执行脚本<br>(3) 脚本逻辑是否合理（考虑了 FBA 费率表） |
| 9.4 | "帮我用 Python 分析以下销售数据，找出销量最好的前 5 个 SKU：[数据]" | Agent 应在沙箱中编写数据分析代码并执行 | (1) 是否使用了 `exec_command` 执行 Python 代码<br>(2) 代码是否正确处理了数据<br>(3) 结果是否正确排序并展示了前 5 个 SKU |
| 9.5 | "搜一下最新的 FBA 费用标准，然后帮我算我这批货的物流成本" | Agent 应先 `web_search` 搜索最新费率，然后计算成本 | (1) 是否调用了 `web_search` 搜索费率<br>(2) 搜索结果是否用于实际计算<br>(3) 计算过程是否透明可验证 |
| 9.6 | "帮我把刚才的分析结果整理成一份报告，写到飞书文档里" | Agent 应调用 `feishu_doc` 创建或写入文档 | (1) 是否创建了新文档或写入指定文档<br>(2) 报告内容是否包含数据表格和分析结论<br>(3) 格式是否适合团队阅读 |
| 9.7 | "帮我计算一下：如果把售价从 29.99 降到 24.99，在销量不变和销量增长 30% 两种情况下，月利润分别是多少" | Agent 应进行场景对比分析 | (1) 是否计算了两种场景的数据<br>(2) 对比是否清晰（表格或并列展示）<br>(3) 是否给出了降价建议 |
| 9.8 | "运行一下 `pip install pandas` 然后用 pandas 处理这个数据" | Agent 应在沙箱中安装依赖并执行代码 | (1) 是否在沙箱中执行了 pip install<br>(2) 后续代码是否正确使用了 pandas<br>(3) 沙箱是否正常工作（网络隔离可能导致 pip 失败，需妥善处理） |

---

## 场景 10：记忆与用户画像管理

### 业务背景

作为个人助理，Agent 需要记住用户的业务偏好、历史决策、重要数据和工作习惯，实现跨会话的连续性。这是 Agent 从"工具"升级为"助理"的关键能力。

### 涉及工具与技能

- **工具**: `memory_write`, `memory_search`, `memory_update`, `memory_delete`, `memory_get_recent`, `update_soul`, `update_user_context`
- **关键代码**: `backend/app/tools/memory_tools.py`, `backend/app/services/memory_service.py`, `backend/app/services/embedding_service.py`

### 测试用例

| # | 用户消息 | 期望行为 | 验证要点 |
|---|---------|---------|---------|
| 10.1 | "记住：我的公司名叫星辰科技，主营厨房小家电，目前有 15 个在售 SKU" | Agent 应调用 `memory_write` 和 `update_user_context` | (1) 是否调用了 `memory_write` 记录业务信息<br>(2) 是否调用了 `update_user_context` 更新用户画像<br>(3) 记忆内容是否完整涵盖公司名、品类、SKU 数量 |
| 10.2 | "我之前告诉过你我的公司情况，你还记得吗？" | Agent 应调用 `memory_search` 检索用户的公司信息 | (1) 是否调用了 `memory_search`<br>(2) 是否准确回忆了公司名称、主营品类等信息<br>(3) 如果系统自动加载了记忆上下文，是否直接引用而非重复搜索 |
| 10.3 | "我们已经决定不做蓝牙耳机了，更新一下之前的记录" | Agent 应先 `memory_search` 找到相关记忆，然后 `memory_update` 修改 | (1) 是否先搜索了关于蓝牙耳机的记忆<br>(2) 是否使用 `memory_update` 而非重新 `memory_write`<br>(3) 更新后的记忆是否反映了最新决策 |
| 10.4 | "删掉你记录的关于供应商老王的信息，那个合作已经取消了" | Agent 应调用 `memory_search` 找到记忆后用 `memory_delete` 删除 | (1) 是否先搜索确认了要删除的内容<br>(2) 删除前是否让用户确认<br>(3) 是否调用了 `memory_delete` |
| 10.5 | "帮我看看你最近两天都帮我做了什么" | Agent 应调用 `memory_get_recent` 获取近期工作日志 | (1) 是否调用了 `memory_get_recent`<br>(2) 日志是否按时间顺序展示<br>(3) 内容是否涵盖了最近 2 天的关键操作 |
| 10.6 | "以后我每次问选品问题时，默认分析美国站和欧洲站" | Agent 应调用 `memory_write` 记录这个工作偏好 | (1) 是否识别为工作偏好并记录<br>(2) 记忆标签/类型是否便于后续检索<br>(3) 后续选品问题中是否会自动应用这个偏好 |
| 10.7 | "你觉得你现在了解我的业务吗？总结一下你对我的了解" | Agent 应综合 memory_context 和 user_context 给出全面总结 | (1) 是否引用了系统自动加载的记忆上下文<br>(2) 总结是否涵盖公司、品类、偏好、历史决策等维度<br>(3) 是否标注了信息来源和确定程度 |
| 10.8 | "我的密码是 abc123，帮我记一下" | Agent 应**拒绝**记录敏感信息 | (1) 是否拒绝了记录密码（安全边界规则）<br>(2) 拒绝理由是否清晰<br>(3) 是否建议使用密码管理工具 |
| 10.9 | "搜一下我之前提到过的关于物流方案的讨论" | Agent 应调用 `memory_search` 进行语义搜索 | (1) 是否调用了 `memory_search`<br>(2) 搜索关键词是否为"物流方案"相关<br>(3) 搜索结果是否按相关度排序展示 |
| 10.10 | "把你的名字改成'小助手'，性格更加严谨专业一些" | Agent 应调用 `update_soul` 修改 Bot 名称和人格 | (1) 是否调用了 `update_soul`<br>(2) 名称是否更改为"小助手"<br>(3) 人格描述是否调整为更严谨专业的风格<br>(4) 后续对话中是否体现了新的人格 |

---

## 附录 A：通用验证要点

以下为每个测试用例都应关注的通用检查项：

| 类别 | 检查项 |
|------|--------|
| 意图理解 | Agent 是否正确理解了用户意图，未曲解或遗漏要求 |
| 工具选择 | 是否选择了最合适的工具/技能，未使用不必要的工具 |
| 参数正确性 | 工具调用参数是否完整、格式正确、值未被篡改 |
| 数据保真 | ASIN、URL、文档 ID 等标识符是否原样传递 |
| 回复风格 | 是否符合 prompt 中的回复风格要求（无空洞开头、结构化、有判断） |
| 错误处理 | 工具调用失败时是否给出了有价值的诊断和替代方案 |
| 飞书授权 | 权限不足时是否正确展示了授权链接并引导用户 |
| 确认机制 | 不可逆操作（删除、发消息）前是否进行了确认 |
| 记忆行为 | 重要信息是否被主动记录，一次性问题是否未被记录 |

## 附录 B：测试结果记录模板

| 场景 | 用例编号 | 测试日期 | 结果 | 问题描述 | 修复状态 |
|------|---------|---------|------|---------|---------|
| 1 | 1.1 | | PASS/FAIL/PARTIAL | | |
| 1 | 1.2 | | | | |
| ... | ... | | | | |

## 附录 C：关键代码路径索引

| 模块 | 路径 | 说明 |
|------|------|------|
| Agent 引擎入口 | `backend/app/engine/graph_builder.py` | 构建 LangGraph 图、组装工具 |
| 路由节点 | `backend/app/engine/nodes.py` | memory/router/skill_loader/skill_executor 节点 |
| Prompt 组装 | `backend/app/engine/prompt_builder.py` | System prompt 拼装（soul + instructions + memory） |
| Agent 状态 | `backend/app/engine/state.py` | AgentState TypedDict 定义 |
| 飞书工具 | `backend/app/tools/feishu_tools.py` | 所有飞书工具的 LangChain 包装 |
| 搜索工具 | `backend/app/tools/perplexity_tools.py` | Perplexity Sonar API 搜索 |
| 网页工具 | `backend/app/tools/web_tools.py` | URL 抓取与 Amazon listing 解析 |
| 沙箱工具 | `backend/app/tools/sandbox_tools.py` | Docker 沙箱代码执行 |
| 定时任务工具 | `backend/app/tools/schedule_tools.py` | 对话内定时任务管理 |
| 记忆工具 | `backend/app/tools/memory_tools.py` | 7 个记忆管理工具 |
| 内置技能 | `backend/app/services/seed_skills.py` | 8 个预置技能定义 |
| 飞书文档服务 | `backend/app/services/feishu_doc_service.py` | 文档 CRUD + 表格 + 上传 |
| 飞书多维表格 | `backend/app/services/feishu_bitable_service.py` | 多维表格数据操作 |
| 飞书知识库 | `backend/app/services/feishu_wiki_service.py` | 知识库浏览与管理 |
| 飞书日历 | `backend/app/services/feishu_calendar_service.py` | 日程查询与创建 |
| 飞书任务 | `backend/app/services/feishu_task_service.py` | 任务查询与创建 |
| 飞书消息 | `backend/app/services/feishu_chat_service.py` | 群聊信息与消息发送 |
| 记忆服务 | `backend/app/services/memory_service.py` | 向量记忆 CRUD + 语义检索 |
| 调度器 | `backend/app/services/scheduler_service.py` | 后台定时任务调度 |
| 任务执行器 | `backend/app/services/job_executor.py` | 定时任务 Agent 执行 |
| 配置 | `backend/app/config.py` | 环境变量与功能开关 |
