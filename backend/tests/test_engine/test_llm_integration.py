"""LLM 集成测试

通过 LiteLLM Proxy（OpenAI 兼容 API）调用真实 LLM，验证：
1. ChatOpenAI 能正确连接自托管 LiteLLM 代理
2. 模型能正确理解和回答中文问题
3. 系统 prompt 能按人设回复
4. tool calling 能正确触发
5. activate_skill 路由能正确工作

用 `pytest -m llm` 显式运行。
"""

import pytest

pytestmark = pytest.mark.llm
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from app.config import settings
from app.engine.prompt_builder import build_system_prompt


@pytest.fixture
def llm():
    """使用配置中的 LiteLLM 代理创建 LLM 实例"""
    base = settings.litellm_api_base.rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    return ChatOpenAI(
        model=settings.default_model,
        temperature=settings.default_temperature,
        base_url=base,
        api_key=settings.litellm_api_key,
    )


class TestLLMConnection:
    """验证 LLM 连接和基本调用"""

    @pytest.mark.asyncio
    async def test_basic_invoke(self, llm):
        """基本调用：LLM 能返回非空回复"""
        response = await llm.ainvoke([HumanMessage(content="用一个字回答：1+1等于几？")])
        assert isinstance(response, AIMessage)
        assert len(response.content) > 0
        assert any(x in response.content for x in ("2", "二", "两"))

    @pytest.mark.asyncio
    async def test_chinese_understanding(self, llm):
        """中文理解：LLM 能正确做算术推理"""
        response = await llm.ainvoke([
            HumanMessage(
                content=(
                    "誉文科技旗下 AUVON 品牌的 B07D58V8LD 产品"
                    "去年的销量是100万，今年销量预计是去年的205%，"
                    "请问今年 B07D58V8LD 的销量是多少万？只回答数字。"
                )
            )
        ])
        assert isinstance(response, AIMessage)
        assert "205" in response.content

    @pytest.mark.asyncio
    async def test_system_prompt_with_llm(self, llm):
        """系统 prompt：LLM 能按 Bot 人设回复"""
        system = build_system_prompt(
            soul="你是一个名叫小爪的跨境电商选品助手，说话简洁专业。",
            instructions="回答时先自我介绍。",
            user_context="用户叫小美，做家居品类。",
            skills=[],
            memory="",
        )
        response = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content="你好"),
        ])
        assert isinstance(response, AIMessage)
        assert len(response.content) > 0


class TestLLMWithTools:
    """验证 LLM 的 tool calling 能力"""

    @pytest.mark.asyncio
    async def test_tool_calling_with_required(self, llm):
        """使用 tool_choice=required 确保 LLM 调用 tool"""

        @tool
        def memory_search(query: str) -> str:
            """搜索Bot记忆库中的历史数据。当用户询问任何历史数据时必须调用。"""
            return f"搜索结果: {query}"

        llm_with_tools = llm.bind_tools([memory_search], tool_choice="required")
        response = await llm_with_tools.ainvoke([
            SystemMessage(content="你是选品助手。用户查数据时调用 memory_search。"),
            HumanMessage(content="帮我查一下去年 B07D58V8LD 的销量数据"),
        ])
        assert isinstance(response, AIMessage)
        assert response.tool_calls, "LLM 应调用 memory_search 工具"
        assert response.tool_calls[0]["name"] == "memory_search"

    @pytest.mark.asyncio
    async def test_activate_skill_tool(self, llm):
        """验证 LLM 能正确调用 activate_skill（使用 tool_choice=required）"""

        @tool
        def activate_skill(skill_name: str) -> str:
            """激活一个技能来处理用户请求。当用户请求匹配某个技能时调用。"""
            return f"已激活技能: {skill_name}"

        system_prompt = build_system_prompt(
            soul="你是跨境电商选品助手。",
            instructions="当用户要求竞品分析时，必须 activate_skill。",
            user_context=None,
            skills=[{
                "name": "amazon-competitor-analysis",
                "description": "当用户提到竞品分析、competitor analysis、对比竞品、分析 ASIN 时激活此技能。",
            }],
            memory="",
        )

        llm_with_tools = llm.bind_tools([activate_skill], tool_choice="required")
        response = await llm_with_tools.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="帮我分析一下 B07D58V8LD 这个ASIN的竞品情况"),
        ])
        assert isinstance(response, AIMessage)
        assert response.tool_calls, "LLM 应调用 activate_skill"
        assert response.tool_calls[0]["name"] == "activate_skill"


class TestCreateLLMHelper:
    """验证 _create_llm 工厂函数"""

    def test_create_llm_with_proxy(self):
        """使用代理配置创建 LLM 实例"""
        from app.engine.nodes import _create_llm

        bot_config = {"model_name": "gemini/gemini-2.0-flash", "temperature": 0.5}
        llm = _create_llm(bot_config)
        assert isinstance(llm, ChatOpenAI)
        assert llm.model_name == "gemini/gemini-2.0-flash"
        assert llm.temperature == 0.5

    def test_create_llm_default_config(self):
        """使用默认配置创建 LLM 实例"""
        from app.engine.nodes import _create_llm

        llm = _create_llm({})
        assert isinstance(llm, ChatOpenAI)
        assert llm.model_name == settings.default_model
