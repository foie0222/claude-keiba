from __future__ import annotations
import asyncio
import json
import re
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import AssistantMessage, TextBlock, ResultMessage


def extract_json_from_messages(text: str) -> dict | None:
    """テキストからJSON部分を抽出する"""
    match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


class AgentRunner:
    """claude-agent-sdk経由でエージェントを実行するラッパー"""

    def __init__(self, prompts_dir: Path = Path("agents/prompts")):
        self.prompts_dir = prompts_dir

    def load_prompt(self, agent_name: str) -> str:
        path = self.prompts_dir / f"{agent_name}.md"
        return path.read_text(encoding="utf-8")

    async def run(
        self,
        agent_name: str,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
        max_turns: int = 20,
        mcp_servers: dict | None = None,
        allowed_tools: list[str] | None = None,
        output_schema: dict | None = None,
    ) -> dict:
        """1つのエージェントを実行し、JSON結果を返す"""
        if system_prompt is None:
            system_prompt = self.load_prompt(agent_name)

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            max_turns=max_turns,
            permission_mode="bypassPermissions",
            allowed_tools=allowed_tools or ["Bash", "Read", "Write"],
        )
        if mcp_servers:
            options.mcp_servers = mcp_servers
        if output_schema:
            options.output_format = {"type": "json_schema", "schema": output_schema}

        collected_text = []
        result_data = None

        async for message in query(prompt=user_prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        collected_text.append(block.text)
            elif isinstance(message, ResultMessage):
                if message.structured_output:
                    result_data = message.structured_output

        if result_data:
            return result_data

        full_text = "\n".join(collected_text)
        extracted = extract_json_from_messages(full_text)
        if extracted:
            return extracted

        return {"raw_text": full_text, "error": "JSON extraction failed"}

    async def run_parallel(
        self,
        agents: list[tuple[str, str]],
        **kwargs,
    ) -> dict[str, dict]:
        """複数エージェントを並列実行。agents = [(agent_name, user_prompt), ...]"""
        tasks = [self.run(name, prompt, **kwargs) for name, prompt in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {
            name: (r if not isinstance(r, Exception) else {"error": str(r)})
            for (name, _), r in zip(agents, results)
        }
