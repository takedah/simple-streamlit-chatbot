FROM --platform=linux/x86_64 python:3.13

# 作業ディレクトリ
WORKDIR /app

# 依存パッケージをインストール
RUN pip install uv mcp streamlit strands-agents strands-agents-tools

# アプリ本体をコピー
COPY . /app

# 公開ポート
EXPOSE 80

# Streamlitを起動
CMD ["streamlit", "run", "app.py", "--server.port=80", "--server.address=0.0.0.0"]