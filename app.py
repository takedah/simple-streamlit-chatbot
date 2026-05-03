import asyncio
import boto3
import streamlit as st
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters

# CodeArtifact の認証設定
CODEARTIFACT_DOMAIN = "CodeArtifact のドメイン名"
AWS_ACCOUNT_ID = "CodeArtifact の AWS アカウント ID"
REGION = "ap-northeast-1"  # CodeArtifact のリポジトリがあるリージョン
REPOSITORY_NAME = "pypi-store"

# 推論プロファイルが日本国内に限定されているモデルを選択
PROFILE_ID = "jp.amazon.nova-2-lite-v1:0"

# フロントエンドを描画
st.title("Strands MCPエージェント お試し版")
st.text("MCPサーバーを使って、Nova Liteがあなたの質問に答えます！")
prompt = st.chat_input("質問を入力")

if prompt:
    # ユーザーのプロンプトを表示
    with st.chat_message("user"):
        st.markdown(prompt)

    # エージェントの応答を表示
    with st.chat_message("assistant"):
        with st.spinner("考え中…"):

            # CodeArtifact から PyPI のあるリポジトリを使うための
            # 認証トークンを取得する設定
            sdk_client = boto3.client("codeartifact", region_name=REGION)
            code_artifact_token = sdk_client.get_authorization_token(
                domain=CODEARTIFACT_DOMAIN,
                domainOwner=AWS_ACCOUNT_ID,
            )

            # uvx がデフォルトの PyPI の URL ではなく、
            # CodeArtifact の VPC エンドポイントへ接続するようにする設定
            uv_index_url = (
                "https://aws:"
                + code_artifact_token["authorizationToken"]
                + "@"
                + CODEARTIFACT_DOMAIN
                + "-"
                + AWS_ACCOUNT_ID
                + ".d.codeartifact."
                + REGION
                + ".amazonaws.com/pypi/"
                + REPOSITORY_NAME
                + "/simple/"
            )

            # MCPクライアント作成
            # args に --default-index を指定することで、
            # PyPI の URL ではなく指定した URL からパッケージをダウンロードできる
            # 元のハンズオン記事では AWS Documentation MCP Server を使っているが、
            # インターネット接続がない環境では正常に動作しないため、
            # 閉域環境でも動作する Fetch MCP Server を使うようにした。
            client = MCPClient(
                lambda: stdio_client(
                    StdioServerParameters(
                        command="uvx",
                        args=[
                            "--default-index",
                            uv_index_url,
                            "mcp-server-fetch",
                        ],
                    )
                )
            )

            with client:
                # エージェント作成
                agent = Agent(
                    model=PROFILE_ID,
                    system_prompt="思考も回答も日本語で行ってください。",
                    tools=client.list_tools_sync(),
                )

                # ストリーミング表示の準備
                container = st.container()
                state = {
                    "text_holder": container.empty(),
                    "buffer": "",
                    "shown_tools": set(),
                }

                # Strandsをストリーミング実行する非同期関数を定義
                async def run_stream():
                    async for event in agent.stream_async(prompt):
                        current_tool = event.get("current_tool_use", {})
                        tool_id = current_tool.get("toolUseId")
                        tool_name = current_tool.get("name")

                        # ツール実行を検出して表示
                        if (
                            tool_id
                            and tool_name
                            and tool_id not in state["shown_tools"]
                        ):
                            state["shown_tools"].add(tool_id)
                            if state["buffer"]:
                                state["text_holder"].markdown(state["buffer"])
                                state["buffer"] = ""
                            container.info(f"🔧 **{tool_name}** ツールを実行中...")
                            state["text_holder"] = container.empty()

                        # テキストを抽出して表示
                        if event.get("data"):
                            state["buffer"] += event["data"]
                            state["text_holder"].markdown(state["buffer"] + "▌")

                    # 最終表示
                    if state["buffer"]:
                        state["text_holder"].markdown(state["buffer"])

                # 非同期関数を実行
                asyncio.run(run_stream())