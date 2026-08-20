#!/bin/bash
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
cd "${SCRIPT_DIR}" || exit

# 环境检测优先级：
# 1. 用户已有环境（/home/user/myenv，v1.0.0 用的）
# 2. 工具自带 venv（.venv）
# 3. 都没有 → 自动创建
if [ -x "/home/user/myenv/bin/python3" ]; then
    PY="/home/user/myenv/bin/python3"
elif [ -f ".venv/bin/python3" ]; then
    PY="${SCRIPT_DIR}/.venv/bin/python3"
else
    echo "首次运行：自动创建环境并安装 playwright（约 2 分钟）..."
    if command -v uv &>/dev/null; then
        uv venv .venv
        uv pip install --python .venv/bin/python playwright
    else
        python3 -m venv .venv
        .venv/bin/pip install playwright
    fi
    .venv/bin/playwright install chromium
    PY="${SCRIPT_DIR}/.venv/bin/python3"
    echo "✅ 环境就绪"
fi

pkill -f chromium 2>/dev/null 2>&1

"${PY}" "${SCRIPT_DIR}/screenshot.py" "$@"
