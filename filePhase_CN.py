import os
import json
import time
import requests


def fix_json_v1(content: list):
    """
    调用接口修复 OCR JSON 文本
    :param content: list of dict (原始 JSON 数据)
    :return: (result, elapsed)
    """
    begin = time.time()

    url = "https://ko.zhonghuapu.com/koapi/query_haograph/FilePhase"  # 接口地址
    payload = {"content": content}  # 把 JSON 列表作为 content 传过去
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()  # 假设返回 JSON
    except requests.exceptions.RequestException as e:
        print(f"\n请求失败，错误: {e}")
        return None, 0

    end = time.time()
    elapsed = end - begin
    return result, elapsed

def export_title_structure(processed_data, input_file):
    """
    从最终处理后的 processed_data 中提取标题层级结构，
    并保存到 input_file 同目录的 mix_content.json
    """
    folder = os.path.dirname(input_file)
    if not folder:
        folder = "."

    output_path = os.path.join(folder, "mix_content.json")

    lines = []
    for block in processed_data:
        if "text_level" not in block:
            continue

        text = block.get("text", "").strip()
        level = block["text_level"]

        prefix = "=" * (level - 1)
        line = f"{prefix}{text}" if prefix else text
        lines.append(line)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(lines, f, ensure_ascii=False, indent=2)

    print(f"📁 已导出目录骨架 → {output_path}")
    return output_path


def process_json_file(input_file: str, output_file: str = None, changes_file: str = None):
    """
    处理一个 JSON 文件：调用接口修复并保存结果
    """
    if not os.path.exists(input_file):
        print(f"❌ 文件不存在: {input_file}")
        return

    # 读取输入 JSON
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 调用接口
    fixed_result, elapsed = fix_json_v1(data)
    if fixed_result is None:
        return

    # --- 关键部分：解析接口返回 ---
    if isinstance(fixed_result, dict):
        processed_data = fixed_result.get("processed_data", [])
        all_changes = fixed_result.get("changes", [])
    else:
        # 防御：接口返回不是字典
        processed_data = fixed_result
        all_changes = []

    # 输出文件名
    if not output_file:
        base, ext = os.path.splitext(input_file)
        output_file = base + "_fixed.json"
    if not changes_file:
        base, ext = os.path.splitext(input_file)
        changes_file = base + "_changes.txt"

    # 保存输出 JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=2)

    # 保存修改日志
    with open(changes_file, "w", encoding="utf-8") as f:
        if isinstance(all_changes, list):
            f.write("\n".join(all_changes))
        else:
            f.write(str(all_changes))

    print(f"✅ 处理完成，耗时 {elapsed:.2f} 秒")
    print(f"👉 结果已保存到 {output_file}")
    print(f"👉 修改日志已保存到 {changes_file}")
    export_title_structure(processed_data, input_file)

    print(f"👉 修改日志已保存到 {changes_file}")
    return output_file, changes_file
from typing import List, Dict
def save_headings_to_txt(
    json_path: str,
    output_txt_path: str,
    dash_char: str = "—"
):
    """
    从 JSON 文件中提取所有标题(text_level存在的 text block)，
    按层级用 '—' 表示，并保存到本地 txt 文件。

    参数：
    - json_path: 输入 JSON 文件路径
    - output_txt_path: 输出 txt 文件路径
    - dash_char: 层级符号，默认 '—'
    """

    # ---------- 读取 JSON ----------
    with open(json_path, "r", encoding="utf-8") as f:
        data: List[Dict] = json.load(f)

    headings = []

    # ---------- 遍历并收集标题 ----------
    for block in data:
        if block.get("type") != "text":
            continue

        level = block.get("text_level")
        text = block.get("text", "").strip()

        if level is None or not text:
            continue

        prefix = dash_char * level
        headings.append(f"{prefix} {text}")

    # ---------- 写入 txt ----------
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(headings))

    print(f"已保存 {len(headings)} 条标题到 {output_txt_path}")


# === 使用示例 ===
if __name__ == "__main__":
    input_path = r"./JTGTF302014_original_content_list.json"
    output_path = "j1_mix.json"
    changes_path = "j1_change.txt"
    process_json_file(input_path, output_path, changes_path)
    save_headings_to_txt(
        json_path="./j1_mix.json",
        output_txt_path="./headings.txt"
    )

