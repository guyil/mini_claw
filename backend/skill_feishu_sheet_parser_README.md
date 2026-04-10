# feishu_sheet_parser

## 已完成内容
- 本地开发了一个可解析飞书 sheet 导出文本/HTML 的 skill 原型
- 核心能力：从文本或 HTML 中提取 `品类/Category -> BSR URL` mapping
- 产物文件：
  - `parser.py`
  - `feishu_sheet_parser.zip`

## 当前限制
当前 `install_skill` 工具只支持 `http://` 或 `https://` URL 安装，不支持本地 `file://` 路径，因此无法在当前会话内直接“自行安装”本地 zip。

## 解析逻辑
1. 输入飞书 sheet 导出的文本或 HTML
2. 识别其中的 URL
3. 将 URL 同行或上一行的文本识别为品类名
4. 输出结构化 JSON mapping

## 示例输出
[
  {"category": "TENS Units", "bsr_url": "https://www.amazon.com/Best-Sellers-TENS-Units/zgbs/3776761"}
]

## 下一步接入方式
### 方案A（最快）
把 zip 放到一个可访问的 https 链接，然后调用：
`install_skill({"url":"https://.../feishu_sheet_parser.zip"})`

### 方案B（更稳）
直接把飞书 sheet 导出为 CSV/XLSX/HTML，我用当前原型先解析出 mapping，再继续做 Amazon BSR 调研。

## 当前文件位置
- `feishu_sheet_parser.zip`
- `parser.py`

