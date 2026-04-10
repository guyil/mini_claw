FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null; \
    sed -i 's|http://security.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/ubuntu.sources 2>/dev/null; \
    sed -i 's|http://archive.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null; \
    sed -i 's|http://security.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null; \
    true

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

RUN pip3 install --break-system-packages -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com \
    requests beautifulsoup4 pandas openpyxl \
    aiohttp lxml cssselect

RUN useradd -m -s /bin/bash agent || usermod -l agent -d /home/agent -m $(getent passwd 1000 | cut -d: -f1) 2>/dev/null || true

USER agent
WORKDIR /workspace

CMD ["sleep", "infinity"]
