"""chrome-devtools-mcp のSDK連携テスト。

前提: Chrome がリモートデバッグモードで起動していること
  ./scripts/start_chrome_debug.sh

Usage: python scripts/test_chrome_mcp.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import AssistantMessage, TextBlock, ResultMessage


async def main():
    print("=== chrome-devtools-mcp テスト ===")
    print("Chrome DevTools MCP経由でブラウザ操作をテストします\n")

    options = ClaudeAgentOptions(
        system_prompt="あなたはテストエージェントです。指示に従ってブラウザを操作してください。",
        max_turns=10,
        permission_mode="bypassPermissions",
        mcp_servers={
            "chrome": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "chrome-devtools-mcp@latest",
                         "--browserUrl=http://127.0.0.1:9222"],
            },
        },
        allowed_tools=[
            "mcp__chrome__navigate_page",
            "mcp__chrome__evaluate_script",
            "mcp__chrome__take_snapshot",
            "mcp__chrome__list_pages",
            "mcp__chrome__new_page",
        ],
    )

    prompt = (
        "以下の手順でテストしてください:\n"
        "1. list_pages でブラウザのタブ一覧を取得して表示\n"
        "2. navigate_page で https://example.com を開く\n"
        "3. evaluate_script で document.title を取得して表示\n"
        "最後に結果を JSON で出力: {\"success\": true, \"title\": \"取得したタイトル\"}"
    )

    collected = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    collected.append(block.text)
                    print(f"[Agent] {block.text[:200]}")
        elif isinstance(message, ResultMessage):
            print(f"\n[Result] subtype={message.subtype}")
            if message.structured_output:
                print(json.dumps(message.structured_output, indent=2))

    print("\n=== テスト完了 ===")


if __name__ == "__main__":
    asyncio.run(main())
