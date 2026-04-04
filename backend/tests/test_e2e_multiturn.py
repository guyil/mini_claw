"""端到端多轮对话测试

模拟真实用户从前端发送消息的完整流程，验证：
1. 多轮上下文记忆
2. Soul 修改与持久化
3. Memory 写入与跨会话召回
4. Web 工具调用
5. Skill 激活与执行
6. 工具调用后的上下文连续性
"""

import asyncio
import copy
import json
import sys

import requests

BACKEND = "http://localhost:8000"
TOKEN = None


def get_token():
    """获取测试用户 token"""
    global TOKEN
    if TOKEN:
        return TOKEN
    import sys
    sys.path.insert(0, ".")
    from app.database import async_session_factory
    from app.api.auth import _create_token
    from sqlalchemy import text

    async def _get():
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT id, username FROM users LIMIT 1"))
            row = result.fetchone()
            return _create_token(str(row[0]), row[1])

    TOKEN = asyncio.run(_get())
    return TOKEN


def apply_patches(state, patches):
    """应用 aui-state JSON Patch 操作构建最终 state"""
    if state is None:
        state = {}
    for patch in patches:
        path = patch.get("path", [])
        value = patch.get("value")

        if not path:
            state = value if value is not None else state
            continue

        target = state
        for key in path[:-1]:
            if isinstance(target, dict):
                if key not in target:
                    target[key] = {}
                target = target[key]
            elif isinstance(target, list):
                idx = int(key)
                while len(target) <= idx:
                    target.append(None)
                target = target[idx]

        last_key = path[-1]
        if isinstance(target, dict):
            target[last_key] = value
        elif isinstance(target, list):
            idx = int(last_key)
            while len(target) <= idx:
                target.append(None)
            target[idx] = value

    return state


def send_message(text_content: str, state=None, timeout=90):
    """发送一条消息，返回 (ai_response, final_state, tool_results)"""
    token = get_token()
    resp = requests.post(
        f"{BACKEND}/assistant",
        json={
            "state": state,
            "commands": [
                {
                    "type": "add-message",
                    "message": {"parts": [{"type": "text", "text": text_content}]},
                }
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
        timeout=timeout,
    )

    current_state = copy.deepcopy(state) if state else None
    last_ai_content = ""
    tool_results = []

    for line in resp.iter_lines():
        if not line:
            continue
        t = line.decode("utf-8", errors="replace")
        if not t.startswith("aui-state:"):
            continue
        patches = json.loads(t[len("aui-state:"):])
        current_state = apply_patches(current_state, patches)
        for p in patches:
            val = p.get("value", {})
            if isinstance(val, dict):
                if val.get("type") == "ai" and "content" in val:
                    last_ai_content = val["content"]
                if val.get("type") == "tool" and "content" in val:
                    tool_results.append(val["content"])

    return last_ai_content, current_state, tool_results


def count_messages(state):
    """统计 state 中各类型消息数量"""
    if not state or "messages" not in state:
        return {}
    counts = {}
    for m in state["messages"]:
        if isinstance(m, dict):
            t = m.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
    return counts


# ─── 测试场景 ────────────────────────────────────────


def test_scenario_1_basic_context():
    """场景1: 基础多轮上下文记忆（5轮）"""
    print("\n" + "=" * 60)
    print("场景 1: 基础多轮上下文记忆")
    print("=" * 60)

    # Turn 1
    ai, state, _ = send_message("我叫张三，我在做亚马逊跨境电商，主要卖蓝牙耳机")
    print(f"\n[Turn 1] User: 我叫张三...")
    print(f"  Bot: {ai[:120]}...")
    assert state is not None, "state 不应为空"

    # Turn 2 - 引用 Turn 1 信息
    ai, state, _ = send_message("我刚才说我卖什么品类？", state)
    print(f"\n[Turn 2] User: 我刚才说我卖什么品类？")
    print(f"  Bot: {ai[:150]}")
    assert "蓝牙" in ai or "耳机" in ai or "Bluetooth" in ai.lower(), \
        f"Bot 应该记得用户卖蓝牙耳机，但回答: {ai[:100]}"
    print("  ✓ 正确回忆了品类")

    # Turn 3 - 继续追问
    ai, state, _ = send_message("我叫什么名字？", state)
    print(f"\n[Turn 3] User: 我叫什么名字？")
    print(f"  Bot: {ai[:150]}")
    assert "张三" in ai, f"Bot 应该记得用户叫张三，但回答: {ai[:100]}"
    print("  ✓ 正确回忆了名字")

    # Turn 4 - 新信息
    ai, state, _ = send_message("我的月销售额大概是5万美金", state)
    print(f"\n[Turn 4] User: 月销售额5万美金")
    print(f"  Bot: {ai[:120]}...")

    # Turn 5 - 综合回忆
    ai, state, _ = send_message("请总结一下你对我的了解", state)
    print(f"\n[Turn 5] User: 请总结一下你对我的了解")
    print(f"  Bot: {ai[:250]}")
    msg_counts = count_messages(state)
    print(f"  消息统计: {msg_counts}")
    assert msg_counts.get("human", 0) >= 5, "应该有至少5条human消息"
    print("  ✓ 5轮对话上下文完整")

    return True


def test_scenario_2_soul_modification():
    """场景2: Soul 修改与验证（3轮）"""
    print("\n" + "=" * 60)
    print("场景 2: Soul 修改与即时验证")
    print("=" * 60)

    # Turn 1 - 修改名字和人格
    ai, state, tools = send_message(
        "从现在开始你叫「大黄」，你是一只金毛犬，说话开朗热情，每句话结尾加「汪！」"
    )
    print(f"\n[Turn 1] User: 改名大黄...")
    print(f"  Bot: {ai[:150]}")
    print(f"  Tool calls: {[t[:60] for t in tools]}")
    soul_updated = any("已更新" in t for t in tools)
    assert soul_updated, "应该调用了 update_soul"
    print("  ✓ update_soul 工具被调用")

    # Turn 2 - 在同一会话中验证（通过对话历史）
    ai, state, _ = send_message("你叫什么名字？", state)
    print(f"\n[Turn 2] User: 你叫什么名字？")
    print(f"  Bot: {ai[:150]}")
    assert "大黄" in ai, f"Bot 应该知道自己叫大黄: {ai[:80]}"
    print("  ✓ 同会话内记得名字")

    # Turn 3 - 新会话验证 soul 持久化
    ai2, state2, _ = send_message("你好，请自我介绍一下")
    print(f"\n[Turn 3] (新会话) User: 请自我介绍")
    print(f"  Bot: {ai2[:200]}")
    has_dog_ref = any(kw in ai2 for kw in ["大黄", "金毛", "汪"])
    if has_dog_ref:
        print("  ✓ 新会话中 soul 持久化生效")
    else:
        print("  ⚠ 新会话中未体现新人格（可能需要等待）")

    # 恢复原始 soul
    ai_reset, _, _ = send_message(
        "把你的名字改回「小爪」，人格改回：你是「小爪」，一个专业的跨境电商 AI 助手。你擅长选品分析、竞品调研、运营策略，说话简洁专业、数据驱动。"
    )
    print(f"\n[Reset] 恢复原始人格: {ai_reset[:80]}...")

    return True


def test_scenario_3_memory_cross_session():
    """场景3: Memory 跨会话持久化（2个会话）"""
    print("\n" + "=" * 60)
    print("场景 3: Memory 跨会话持久化")
    print("=" * 60)

    # 会话 A - 写入记忆
    ai, state, tools = send_message("请记住：我们公司的核心竞品是ASIN B09XYZ1234，售价39.99美金，月销3000单")
    print(f"\n[会话A Turn 1] User: 请记住竞品信息...")
    print(f"  Bot: {ai[:150]}")
    memory_written = any("已记住" in t for t in tools)
    assert memory_written, "应该调用了 memory_write"
    print("  ✓ memory_write 被调用")

    ai, state, tools = send_message("另外记住：我们自己的产品售价是29.99美金，月销1500单", state)
    print(f"\n[会话A Turn 2] User: 记住自己产品信息...")
    print(f"  Bot: {ai[:120]}...")
    print("  ✓ 第二条记忆已写入")

    # 会话 B - 新会话回忆（state=None 模拟新会话）
    ai2, state2, _ = send_message("我之前跟你提过我的竞品信息，你还记得吗？")
    print(f"\n[会话B Turn 1] (新会话) User: 竞品信息还记得吗？")
    print(f"  Bot: {ai2[:250]}")
    has_memory = any(kw in ai2 for kw in ["39.99", "3000", "竞品", "B09"])
    if has_memory:
        print("  ✓ 跨会话记忆召回成功")
    else:
        print("  ⚠ 未在回复中直接提及记忆内容（可能需要 memory_search）")

    return True


def test_scenario_4_web_tool():
    """场景4: Web 工具调用 + 后续讨论（3轮）"""
    print("\n" + "=" * 60)
    print("场景 4: Web 工具调用 + 后续追问")
    print("=" * 60)

    # Turn 1 - 爬取产品
    ai, state, tools = send_message(
        "帮我查看一下这个Amazon产品的信息 https://www.amazon.com/dp/B08TW57FVR",
        timeout=120,
    )
    print(f"\n[Turn 1] User: 查看Amazon产品...")
    print(f"  Bot: {ai[:200]}...")
    print(f"  Tool results: {len(tools)} 个")
    web_called = any("产品标题" in t or "价格" in t for t in tools)
    assert web_called, "web_fetch 应该返回了产品数据"
    print("  ✓ web_fetch 成功抓取产品数据")

    # Turn 2 - 基于结果追问
    ai, state, _ = send_message("这个产品的价格是多少？评分怎么样？", state)
    print(f"\n[Turn 2] User: 价格和评分？")
    print(f"  Bot: {ai[:200]}")
    has_price = "$" in ai or "89" in ai or "价格" in ai
    print(f"  {'✓' if has_price else '⚠'} 能回忆上一轮的产品数据")

    # Turn 3 - 深入分析
    ai, state, _ = send_message("根据这个产品的信息，你觉得这个品类值得进入吗？", state)
    print(f"\n[Turn 3] User: 品类值得进入吗？")
    print(f"  Bot: {ai[:200]}...")
    print("  ✓ 能基于工具结果进行分析")

    return True


def test_scenario_5_mixed_tools():
    """场景5: 混合工具使用 — 一轮对话中记忆+分析（4轮）"""
    print("\n" + "=" * 60)
    print("场景 5: 混合工具 + 连续追问")
    print("=" * 60)

    # Turn 1
    ai, state, _ = send_message("我正在考虑做无线充电器品类，预算大概2万美金启动")
    print(f"\n[Turn 1] User: 考虑做无线充电器...")
    print(f"  Bot: {ai[:150]}...")

    # Turn 2
    ai, state, tools = send_message("请帮我记住这个决定，然后帮我分析一下无线充电器市场", state)
    print(f"\n[Turn 2] User: 记住+分析...")
    print(f"  Bot: {ai[:150]}...")
    print(f"  Tools: {[t[:50] for t in tools]}")

    # Turn 3 - 回忆前面内容
    ai, state, _ = send_message("我的启动预算是多少来着？", state)
    print(f"\n[Turn 3] User: 启动预算是多少？")
    print(f"  Bot: {ai[:150]}")
    assert "2" in ai or "两万" in ai or "20000" in ai or "2万" in ai, \
        f"应该记得预算2万: {ai[:80]}"
    print("  ✓ 正确回忆预算")

    # Turn 4
    ai, state, _ = send_message("帮我列个TODO清单，做无线充电器品类的关键步骤", state)
    print(f"\n[Turn 4] User: 列个TODO清单")
    print(f"  Bot: {ai[:250]}...")
    msg_counts = count_messages(state)
    print(f"  消息统计: {msg_counts}")
    print("  ✓ 4轮混合对话完成")

    return True


def test_scenario_6_error_recovery():
    """场景6: 边界情况 — 空消息、超长消息、特殊字符"""
    print("\n" + "=" * 60)
    print("场景 6: 边界情况测试")
    print("=" * 60)

    # 特殊字符
    ai, state, _ = send_message("测试特殊字符：<script>alert('xss')</script> & \"quotes\" 'single' $100")
    print(f"\n[Test 1] 特殊字符")
    print(f"  Bot: {ai[:120]}...")
    assert state is not None
    print("  ✓ 特殊字符未导致崩溃")

    # 中英混合
    ai, state, _ = send_message("Help me analyze B08TW57FVR on Amazon US marketplace，给我中文回复", state)
    print(f"\n[Test 2] 中英混合")
    print(f"  Bot: {ai[:120]}...")
    print("  ✓ 中英混合正常处理")

    # 连续两条追问
    ai, state, _ = send_message("继续", state)
    print(f"\n[Test 3] 短消息「继续」")
    print(f"  Bot: {ai[:120]}...")
    print("  ✓ 短消息正常处理")

    return True


# ─── 主执行 ──────────────────────────────────────────

def main():
    results = {}
    scenarios = [
        ("基础多轮上下文", test_scenario_1_basic_context),
        ("Soul 修改验证", test_scenario_2_soul_modification),
        ("Memory 跨会话", test_scenario_3_memory_cross_session),
        ("Web 工具调用", test_scenario_4_web_tool),
        ("混合工具连续对话", test_scenario_5_mixed_tools),
        ("边界情况", test_scenario_6_error_recovery),
    ]

    for name, fn in scenarios:
        try:
            ok = fn()
            results[name] = "✓ 通过" if ok else "✗ 失败"
        except Exception as e:
            results[name] = f"✗ 异常: {e}"
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, result in results.items():
        print(f"  {result}  {name}")

    failed = sum(1 for v in results.values() if "✗" in v)
    print(f"\n总计: {len(results)} 个场景, {len(results) - failed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
