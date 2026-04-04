FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    # 网络工具
    curl wget ca-certificates \
    # JSON / 数据处理
    jq csvtool sqlite3 \
    # Python 运行时
    python3 python3-pip python3-venv \
    # Node.js 运行时
    nodejs npm \
    # 文档处理
    pandoc \
    # 媒体处理
    imagemagick \
    # 版本控制
    git \
    # 基础工具
    bash coreutils unzip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages \
    requests beautifulsoup4 pandas openpyxl \
    aiohttp lxml cssselect

RUN useradd -m -u 1000 -s /bin/bash agent

USER agent
WORKDIR /workspace

CMD ["sleep", "infinity"]
