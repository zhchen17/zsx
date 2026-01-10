import json
import re
from typing import List, Dict, Tuple, Callable

# 类型别名
JsonBlock = Dict[str, any]
RuleFunc = Callable[[List[JsonBlock]], Tuple[List[JsonBlock], List[str]]]

def apply_rules(data: List[JsonBlock], rules: List[RuleFunc]) -> Tuple[List[JsonBlock], List[str]]:
    """
    依次对 JSON 数据应用规则，收集所有规则的修改日志
    """
    all_changes = []
    for rule in rules:
        rule_name = rule.__name__
        data, changes = rule(data)
        if changes:
            all_changes.append(f"\n==================== {rule_name} ====================")
            all_changes.extend(changes)
    return data, all_changes

#文本规范化函数，可以在之后标题还原的各方法中选择性使用
def normalize_text(text: str) -> str:
    """
    统一文本规范化：
      - NBSP → 普通空格
      - 多空格压缩
      - 去除行首噪声（符号 / LaTeX math）
    """
    import re

    if not text:
        return ""

    # 1️⃣ NBSP → 空格（关键！）
    t = text.replace("\u00A0", " ")

    # 2️⃣ 去除行首空白
    t = t.lstrip(" \t\n")

    # 3️⃣ 去除常见前缀符号
    t = re.sub(r'^[•·—–\-=]+\s*', '', t)

    # 4️⃣ 去除行首 LaTeX math
    t = re.sub(
        r'^\$\s*\\?[a-zA-Z]+\{?.*?\}?\s*\$\s*',
        '',
        t
    )

    # 5️⃣ 压缩多余空格
    t = re.sub(r'\s+', ' ', t)

    return t.strip()

# 增加章节，按照text内容开头的序号进行识别， 3.2.2 就是三级标题
#改进版：在原有基础上加上了对于Part / Chapter / Section等顶级标题的识别，即使前面有特殊的符号

# def rule_numbered_heading_levels_en(data: List[JsonBlock]) -> Tuple[List[JsonBlock], List[str]]:
#     """
#     自动依据 text 开头的数字编号设置正确的 text_level。
#     规则：
#         X           -> 1级标题
#         X.X         -> 2级标题
#         X.X.X       -> 3级标题
#     最多允许到 7 级。
#     同时：
#         - 识别顶级标题 Part / Chapter / Section，即使前面有 LaTeX/math 符号或空格
#           例如 "$\\Delta$ Chapter 13 Wind Turbines" → text_level=1
#     """
#     import re
#     changes = []
#
#     # 数字编号匹配
#     # pattern = re.compile(r'^(\d+(?:\.\d+)*)\s+')
#     pattern = re.compile(
#         r'^(\d+(?:\.\d+)*)(?:\s+|\u00A0|(?=[A-Za-z]))'
#     )
#
#     # 顶级标题匹配：允许前置符号、空格
#     top_level_pattern = re.compile(
#         r'^[^\w\d]*\s*'                     # 允许前置非字母数字符号 + 空格
#         r'(Part\s*[IVXLCDM\d]*|Chapter\s+\d+|Section\s+\d+)',
#         re.IGNORECASE
#     )
#
#     def looks_like_numeric_row(text: str) -> bool:
#         tokens = text.split()
#         numeric_tokens = 0
#         for t in tokens:
#             t_clean = t.replace(",", "")
#             if re.fullmatch(r"\d+(\.\d+)?", t_clean):
#                 numeric_tokens += 1
#         return numeric_tokens >= 2
#
#     for block in data:
#         raw_text = block.get("text", "").strip()
#         text = normalize_text(raw_text)
#         if not text:
#             continue
#
#         # --------------------------
#         # 1️⃣ 顶级标题识别 → 一级标题,仅支持Part（+希腊数字）/Chapter/Section，后面可以不包含文本
#         # --------------------------
#         if top_level_pattern.match(text):
#             old_level = block.get("text_level")
#             if old_level != 1:
#                 block["text_level"] = 1
#                 changes.append(
#                     f"[rule_numbered_heading_levels_en] page {block.get('page_idx', '?')}\n"
#                     f"修改: \"{text}\"\n"
#                     f"→ 设置 text_level=1（顶级标题：Part/Chapter/Section）\n"
#                 )
#             continue
#
#         # --------------------------
#         # 2️⃣ 数字编号 → 按原规则
#         # --------------------------
#         m = pattern.match(text)
#         if not m:
#             continue
#
#         # 🚫 排除表格数值行
#         if looks_like_numeric_row(text):
#             continue
#
#         numbering = m.group(1)
#         dot_count = numbering.count('.')
#         level = min(dot_count + 1, 7)
#
#         old_level = block.get("text_level")
#
#         if old_level is None:
#             block["text_level"] = level
#             changes.append(
#                 f"[rule_numbered_heading_levels_en] page {block.get('page_idx', '?')}\n"
#                 f"修改: \"{text}\"\n"
#                 f"→ 加入 text_level={level}\n"
#             )
#         elif old_level != level:
#             block["text_level"] = level
#             changes.append(
#                 f"[rule_numbered_heading_levels_en] page {block.get('page_idx', '?')}\n"
#                 f"修改: \"{text}\"\n"
#                 f"→ 修正 text_level: {old_level} → {level}\n"
#             )
#
#     return data, changes

def rule_numbered_heading_levels_en(data: List[JsonBlock]) -> Tuple[List[JsonBlock], List[str]]:
    """
    自动依据 text 开头的数字编号设置正确的 text_level。
    规则：
        X           -> 1级标题
        X.X         -> 2级标题
        X.X.X       -> 3级标题
    最多允许到 7 级。
    同时：
        - 识别顶级标题 Part / Chapter / Section，即使前面有 LaTeX/math 符号或空格
          例如 "$\\Delta$ Chapter 13 Wind Turbines" → text_level=1
        - 行首噪声（如 N、Δ、•、·、—、–、= 等）会被去掉再识别
        - 兼容前面 N 2.3.6 这种情况
    """
    import re
    changes = []

    MAX_LEVEL = 7

    # --------------------------
    # 行首噪声清理
    # --------------------------
    def strip_leading_noise(text: str) -> str:
        t = text.strip()
        # 去掉孤立字母或符号开头（N、Δ、•、·、—、–、= 等）
        t = re.sub(r'^(?:[A-Za-zΔ])\s+', '', t)
        # 去掉常见前缀符号
        t = re.sub(r'^[•·—–\-=]+\s*', '', t)
        # 去掉 LaTeX math
        t = re.sub(r'^\$\s*\\?[a-zA-Z]+\{?.*?\}?\s*\$\s*', '', t)
        t = t.strip()
        return t

    # 数字编号匹配
    numbering_pattern = re.compile(r'^(\d+(?:\.\d+)*)(?:\s+|\u00A0|(?=[A-Za-z]))')

    # 顶级标题匹配
    top_level_pattern = re.compile(
        r'^[^\w\d]*\s*(Part\s*[IVXLCDM\d]*|Chapter\s+\d+|Section\s+\d+)',
        re.IGNORECASE
    )

    # 判断是否是表格数值行
    def looks_like_numeric_row(text: str) -> bool:
        tokens = text.split()
        numeric_tokens = 0
        for t in tokens:
            t_clean = t.replace(",", "")
            if re.fullmatch(r"\d+(\.\d+)?", t_clean):
                numeric_tokens += 1
        return numeric_tokens >= 2

    # --------------------------
    # 主循环
    # --------------------------
    for block in data:
        raw_text = block.get("text", "").strip()
        text = strip_leading_noise(raw_text)
        if not text:
            continue

        # 顶级标题 → 一级标题
        if top_level_pattern.match(text):
            old_level = block.get("text_level")
            if old_level != 1:
                block["text_level"] = 1
                changes.append(
                    f"[rule_numbered_heading_levels_en] page {block.get('page_idx', '?')}\n"
                    f"修改: \"{raw_text}\"\n"
                    f"→ 设置 text_level=1（顶级标题：Part/Chapter/Section）\n"
                )
            continue

        # 数字编号 → 按原规则
        m = numbering_pattern.match(text)
        if not m:
            continue

        if looks_like_numeric_row(text):
            continue

        numbering = m.group(1)
        dot_count = numbering.count('.')
        level = min(dot_count + 1, MAX_LEVEL)

        old_level = block.get("text_level")
        if old_level is None:
            block["text_level"] = level
            changes.append(
                f"[rule_numbered_heading_levels_en] page {block.get('page_idx', '?')}\n"
                f"修改: \"{raw_text}\"\n"
                f"→ 加入 text_level={level}\n"
            )
        elif old_level != level:
            block["text_level"] = level
            changes.append(
                f"[rule_numbered_heading_levels_en] page {block.get('page_idx', '?')}\n"
                f"修改: \"{raw_text}\"\n"
                f"→ 修正 text_level: {old_level} → {level}\n"
            )

    return data, changes

def rule_merge_split_appendix_titles_en(data):
    """
    修正版规则（英文）: 合并 OCR 拆分的附录主标题，并识别附录标题
    """
    import re

    changes = []
    new_data = []
    i = 0

    def safe_concat(a, b):
        if not a:
            return b
        if not b:
            return a
        if a.endswith(" ") or b.startswith(" "):
            return a + b
        return a + " " + b

    # -----------------------------
    # 正则匹配
    # -----------------------------
    appendix_prefix_only = re.compile(r'^(?:appendix|annex(?:e)?)[\s\-]*[A-Z]{1,2}$', re.IGNORECASE)

    appendix_with_title_text = re.compile(r'^(?:appendix|annex(?:e)?)[\s\-]*[A-Z]{1,2}\s+\w{3,}', re.IGNORECASE)

    # 匹配括号行 (支持中英文括号)
    pure_paren_line = re.compile(r'^[\(\（][^）\)]+[\）\)]$')

    # 匹配完整标题行
    appendix_full_title = re.compile(
        r'^(?:appendix|annex(?:e)?)[\s\-]*[A-Z]{1,2}(?:\s*\([^)]+\))?.+', re.IGNORECASE
    )

    while i < len(data):
        block = data[i]
        text = block.get("text", "").strip()

        # -----------------------------
        # 仅处理“孤立的 APPENDIX A / ANNEX B”
        # -----------------------------
        if appendix_prefix_only.match(text):

            # 如果已经有正文标题内容，直接跳过
            if appendix_with_title_text.match(text):
                new_data.append(block)
                i += 1
                continue

            merged_text = text
            j = i + 1

            # -------- 合并下一行 --------
            if j < len(data):
                next1 = data[j].get("text", "").strip()
                if next1:
                    merged_text = safe_concat(merged_text, next1)
                    j += 1

                    # 如果第二行是“纯括号行”，尝试合并第三行
                    if pure_paren_line.match(next1) and j < len(data):
                        next2 = data[j].get("text", "").strip()
                        if next2:
                            merged_text = safe_concat(merged_text, next2)
                            j += 1

            new_block = dict(block)
            new_block["text"] = merged_text


            new_block["text_level"] = 1

            changes.append(
                f"[rule_merge_split_appendix_titles_en] page {block.get('page_idx', '?')}\n"
                f"合并并识别附录标题: \"{text}\" → \"{merged_text}\" text_level=1\n"
            )

            new_data.append(new_block)
            i = j
            continue

        # -----------------------------
        # 单行已经是完整附录标题的情况
        # -----------------------------
        elif appendix_full_title.match(text):
            if "text_level" not in block:
                block["text_level"] = 1
                changes.append(
                    f"[rule_merge_split_appendix_titles_en] page {block.get('page_idx','?')}\n"
                    f"识别附录标题: \"{text}\" → 新增 text_level=1\n"
                )
            new_data.append(block)
            i += 1
            continue

        # -----------------------------
        # 默认不处理
        # -----------------------------
        new_data.append(block)
        i += 1

    return new_data, changes


# def rule_appendix_headings_en(data):
#     """
#     英文附录标题识别（仅识别，不删除正文引用）
#     支持：
#       - APPENDIX / ANNEX + 1-2 个大写字母
#       - 可选括号 (informative / normative / …)，括号内可有空格
#       - 可选标题描述
#     """
#     import re
#     changes = []
#     new_data = []
#
#     def normalize_text(text: str) -> str:
#         # NBSP、零宽空格 -> 普通空格
#         text = re.sub(r'[\u00A0\u200B]', ' ', text)
#         # 去掉行首/行尾空格
#         text = text.strip()
#         # 括号前后空格归一
#         text = re.sub(r'\(\s*([^)]+?)\s*\)', r'(\1)', text)
#         return text
#
#     # 宽松匹配附录标题
#     appendix_title_pattern = re.compile(
#         r'^(appendix|annex)\s*'       # Annex / Appendix
#         r'[A-Z]{1,2}'                 # A 或 AA
#         r'(?:\([^)]+\))?'             # 可选括号，括号内允许空格
#         r'(?:\s+.*)?$',               # 可选标题描述
#         re.IGNORECASE
#     )
#
#     for block in data:
#         text_raw = block.get("text", "")
#         text = normalize_text(text_raw)
#
#         # 匹配附录标题 → 设置 text_level=1
#         if appendix_title_pattern.match(text):
#             old_level = block.get("text_level")
#             block["text_level"] = 1
#             if old_level != 1:
#                 changes.append(
#                     f"[rule_appendix_headings_en] page {block.get('page_idx','?')}\n"
#                     f"识别附录标题: \"{text_raw}\" → 设置 text_level=1 (原: {old_level})\n"
#                 )
#
#         new_data.append(block)
#
#     return new_data, changes



# 增加标题，APPENDIX/ANNEX(xxx)附录标题在不同的块，进行合并
# def rule_merge_split_appendix_titles_en(data):
#     """
#     修正版规则（英文）: 只合并“被 OCR 错分的附录主标题”
#
#     仅在以下情况下触发合并：
#     - 当前行 = 仅包含 'APPENDIX/ANNEX + 编号'
#     - 后面一行才是真正的标题内容
#     """
#     changes = []
#     new_data = []
#     i = 0
#
#     def safe_concat(a, b):
#         if not a:
#             return b
#         if not b:
#             return a
#         if a.endswith(" ") or b.startswith(" "):
#             return a + b
#         return a + " " + b
#
#     # ✅ 1️⃣ 仅匹配“整行就是 APPENDIX A / ANNEX B”
#     appendix_prefix_only = re.compile(
#         r'^(?:appendix|annex)[\s\-]*[A-Z]{1,2}$',
#         re.IGNORECASE
#     )
#
#     # ✅ 2️⃣ 判断是否已经带有标题正文（≥3 个字母的英文词）
#     appendix_with_title_text = re.compile(
#         r'^(?:appendix|annex)[\s\-]*[A-Z]{1,2}\s+\w{3,}',
#         re.IGNORECASE
#     )
#
#     # 括号行：(GLOSSARY OF TERMS)
#     pure_paren_line = re.compile(r'^[\(\（][^）\)]+[\）\)]$')
#
#     while i < len(data):
#         block = data[i]
#         text = block.get("text", "").strip()
#
#         # -----------------------------
#         # 仅处理“孤立的 APPENDIX A”
#         # -----------------------------
#         if appendix_prefix_only.match(text):
#
#             # ❌ 如果已经有正文标题内容，直接跳过
#             if appendix_with_title_text.match(text):
#                 new_data.append(block)
#                 i += 1
#                 continue
#
#             merged_text = text
#             j = i + 1
#
#             # -------- 合并下一行 --------
#             if j < len(data):
#                 next1 = data[j].get("text", "").strip()
#                 if next1:
#                     merged_text = safe_concat(merged_text, next1)
#                     j += 1
#
#                     # 只有当第二行是“纯括号行”时，才允许合并第三行
#                     if pure_paren_line.match(next1) and j < len(data):
#                         next2 = data[j].get("text", "").strip()
#                         if next2:
#                             merged_text = safe_concat(merged_text, next2)
#                             j += 1
#
#             new_block = dict(block)
#             new_block["text"] = merged_text
#             new_block["text_level"] = 1
#             new_data.append(new_block)
#
#             changes.append(
#                 f"[rule_merge_split_appendix_titles_en] page {block.get('page_idx','?')}\n"
#                 f"合并附录标题: \"{text}\" → \"{merged_text}\"\n"
#             )
#
#             i = j
#             continue
#
#         # -----------------------------
#         # 默认不处理
#         # -----------------------------
#         new_data.append(block)
#         i += 1
#
#     return new_data, changes

#增加标题，处理附录中的子标题，字母编号 (A.1 / A.1.2 / AA.1.2.3) → 转为标题

def rule_appendix_headings_en(data):
    """
    英文附录标题识别（仅识别，不删除正文引用）
    支持：
      - APPENDIX / ANNEX + 1-2 个大写字母
      - 可选括号 (informative / normative / …)
      - 可选标题描述

    处理逻辑：
      - 没有 text_level 的块 → 新增 text_level=1
      - 已有 text_level 的块 → 保持不变
    """
    import re
    changes = []
    new_data = []

    def normalize_text(text: str) -> str:
        text = re.sub(r'[\u00A0\u200B]', ' ', text)  # NBSP、零宽空格 -> 普通空格
        text = text.strip()                           # 去掉行首/行尾空格
        text = re.sub(r'\(\s*([^)]+?)\s*\)', r'(\1)', text)  # 括号前后空格归一
        return text

    # 宽松匹配附录标题
    appendix_title_pattern = re.compile(
        r'^(appendix|annex)\s*'       # Annex / Appendix
        r'[A-Z]{1,2}'                 # A 或 AA
        r'(?:\([^)]+\))?'             # 可选括号
        r'(?:\s+.*)?$',               # 可选标题描述
        re.IGNORECASE
    )

    for block in data:
        # 如果已经有 text_level，不做修改
        if "text_level" in block:
            new_data.append(block)
            continue

        text_raw = block.get("text", "")
        text = normalize_text(text_raw)

        if appendix_title_pattern.match(text):
            block["text_level"] = 1  # 新增 text_level=1
            changes.append(
                f"[rule_appendix_headings_en] page {block.get('page_idx','?')}\n"
                f"识别附录标题: \"{text_raw}\" → 新增 text_level=1\n"
            )

        new_data.append(block)

    return new_data, changes





def rule_appendix_subheadings_en(data):
    """
    改进版规则（英文）: 处理附录中的子标题
    支持：
      - A.1 / A.1.2 / AA.1.2.3
      - L2.1 / L2.1.1 / AA2.3.4
    """

    import re
    changes = []
    new_data = []

    # 附录主标题
    appendix_heading_pattern = re.compile(
        r'^\s*(appendix|annex)[\s\-]*[A-Z0-9]{1,3}\b.*$',
        re.IGNORECASE
    )

    # ✅ 改进后的附录子标题编号
    appendix_subheading_pattern = re.compile(
        r"""
        ^(
            [A-Z]{1,3}        # 附录字母
            \d*               # 可选数字（L2）
            (?:\.\d+)+        # .1 / .1.2 / .1.2.3
        )
        \s+
        """,
        re.VERBOSE
    )

    appendix_active = False

    for block in data:
        text = block.get("text", "").strip()

        # 1️⃣ 进入附录区域
        if appendix_heading_pattern.match(text):
            appendix_active = True
            new_data.append(block)
            continue

        if not appendix_active:
            new_data.append(block)
            continue

        # 2️⃣ 处理附录子标题
        m = appendix_subheading_pattern.match(text)
        if m:
            # 结尾标点 → 视为正文
            if text.endswith((":", ",", ";")):
                if "text_level" in block:
                    old = block.pop("text_level")
                    changes.append(
                        f"[rule_appendix_subheadings_en] page {block.get('page_idx','?')}\n"
                        f"修改: \"{text}\"\n"
                        f"→ 删除 text_level={old}（结尾为标点）\n"
                    )
            else:
                num_part = m.group(1)
                level = min(num_part.count(".") + 1, 7)

                old = block.get("text_level")
                block["text_level"] = level
                if old != level:
                    changes.append(
                        f"[rule_appendix_subheadings_en] page {block.get('page_idx','?')}\n"
                        f"修改: \"{text}\"\n"
                        f"→ 设置 text_level={level} (原: {old})\n"
                    )

            new_data.append(block)
            continue

        # 3️⃣ 默认
        new_data.append(block)

    return new_data, changes


#拆分出现在正文段落中的附录标题
def rule_split_appendix_numbered_title(data: List[dict], threshold: int = 10) -> Tuple[List[dict], List[str]]:
    """
    规则：拆分附录子标题（如 A.3.2.1 Approved.）和正文
      - 识别字母 + 数字编号开头的附录标题
      - 拆分到第一个句号
      - 判断标题除去编号后的单词数，不超过 threshold 才拆分
      - 自动设置 text_level（根据编号层级）

    参数：
        data      : 文本块列表，每个块是 dict
        threshold : 首句单词数阈值
    """
    import re
    changes = []
    new_data = []

    def strip_leading_noise(text: str) -> str:
        t = text.strip()
        # 去掉孤立字母或符号开头（N、Δ、•、·、—、–、= 等）
        t = re.sub(r'^(?:[A-Za-zΔ])\s+', '', t)
        # 去掉常见前缀符号
        t = re.sub(r'^[•·—–\-=]+\s*', '', t)
        # 去掉 LaTeX math
        t = re.sub(r'^\$\s*\\?[a-zA-Z]+\{?.*?\}?\s*\$\s*', '', t)
        t = t.strip()
        return t

    def normalize_text(text: str) -> str:
        import re
        text = re.sub(r'[\u00A0\u200B]', ' ', text)  # NBSP、零宽空格 -> 普通空格
        return text.strip()

    for blk in data:
        text_raw = blk.get("text", "").strip()
        if not text_raw:
            new_data.append(blk)
            continue

        text = normalize_text(text_raw)

        text=strip_leading_noise(text)

        # 匹配附录子标题：字母 + 数字编号开头，例如 A.3.2.1
        m = re.match(r'^([A-Z]\.\d+(?:\.\d+)*)(\s+)(.*)', text)
        if not m:
            new_data.append(blk)
            continue

        number_part = m.group(1)  # 编号部分
        rest_text = m.group(3).strip()  # 标题和正文

        # 找到第一个句号，作为标题边界
        first_dot = re.search(r'\.', rest_text)
        if first_dot:
            title_text_only = rest_text[:first_dot.start() + 1].strip()
            remaining_text = rest_text[first_dot.end():].strip()
        else:
            # 没有句号 → 整行作为标题
            title_text_only = rest_text
            remaining_text = ""

        # 统计标题单词数（去掉编号部分）
        title_words = title_text_only.split()
        if len(title_words) <= threshold:
            # 可以拆分标题
            title_text = f"{number_part} {title_text_only}"
            title_level = min(number_part.count('.') + 1, 7)

            # 原块修改为标题块
            blk_title = dict(blk)
            blk_title["text"] = title_text
            blk_title["text_level"] = title_level
            new_data.append(blk_title)

            changes.append(
                f"[rule_split_appendix_numbered_title] page {blk.get('page_idx', '?')}\n"
                f"拆分标题: \"{text}\" → \"{title_text}\" (text_level={title_level})"
            )

            # 剩余正文
            if remaining_text:
                blk_body = {
                    "type": blk.get("type", "text"),
                    "text": remaining_text,
                    "page_idx": blk.get("page_idx")
                }
                new_data.append(blk_body)
                changes.append(
                    f"[rule_split_appendix_numbered_title] page {blk.get('page_idx', '?')}\n"
                    f"拆分正文: \"{remaining_text}\""
                )
        else:
            # 超过阈值 → 不拆分，保留原样
            new_data.append(blk)

    return new_data, changes


#删除首页的所有标题，并记录标题名称，在'前言'后查找有没有相同的标题，实际就是查找文件名称
def rule_remove_cover_title_and_duplicates_en(data):
    """
    英文文档封面标题及重复标题清理规则（改进版）：
    1. 如果第0页检测为封面页（包含关键词，如国际标准/规范等），删除该页所有标题（通常是文件名）。
    2. 在“foreword”或“avant-propos”后的若干标题中，
       删除与封面标题相同的标题，数量等于封面页标题数（忽略空格与全角差异）。
    """
    import re

    changes = []
    new_data = []

    # --- 工具函数：标准化标题，用于比较 ---
    def normalize_title(s):
        """去除空格、全角空格、统一全角冒号"""
        return s.replace(" ", "").replace("　", "").replace("：", ":").strip()

    # --- 第0页检测封面关键词 ---
    cover_keywords = ["INTERNATIONAL", "STANDARD", "NORME", "INTERNATIONALE", "TECHNICAL", "SPECIFICATION"]
    page0_text = " ".join(block.get("text", "") for block in data if block.get("page_idx") == 0)
    is_cover_page = any(re.search(keyword, page0_text, re.IGNORECASE) for keyword in cover_keywords)

    if not is_cover_page:
        changes.append("[rule_remove_cover_title_and_duplicates_en] 未检测到封面关键词（跳过首页处理）")
        return data, changes

    # --- 第1步：记录封面页标题并删除 text_level ---
    cover_titles = []
    for block in data:
        if block.get("page_idx") == 0 and "text_level" in block:
            title_text = block.get("text", "").strip()
            cover_titles.append(title_text)
            old_level = block.pop("text_level")
            changes.append(
                f"[rule_remove_cover_title_and_duplicates_en] page {block.get('page_idx','?')}\n"
                f"删除封面标题: \"{title_text}\" (text_level={old_level})，封面检测通过\n"
            )

    num_cover_titles = len(cover_titles)

    # --- 第2步：查找“foreword”或“avant-propos”标题索引 ---
    preface_index = None
    foreword_pattern = re.compile(r'^\s*foreword\s*$', re.IGNORECASE)
    avant_propos_pattern = re.compile(r'^\s*avant[\s\-]?propos\s*$', re.IGNORECASE)

    for i, block in enumerate(data):
        if "text_level" in block:
            text = block.get("text", "").strip()
            if foreword_pattern.match(text) or avant_propos_pattern.match(text):
                preface_index = i
                break

    # --- 第3步：前言后删除与封面重复的标题，数量等于封面标题数 ---
    if preface_index is not None and cover_titles:
        deleted_count = 0
        j = preface_index + 1
        while j < len(data) and deleted_count < num_cover_titles:
            block = data[j]
            if "text_level" in block:
                text = block.get("text", "").strip()
                for cover_title in cover_titles:
                    if normalize_title(text) == normalize_title(cover_title):
                        old_level = block.pop("text_level")
                        changes.append(
                            f"[rule_remove_cover_title_and_duplicates_en] page {block.get('page_idx','?')}\n"
                            f"删除重复文件名标题: \"{text}\" (text_level={old_level})，因与封面标题相同（忽略空格差异）\n"
                        )
                        deleted_count += 1
                        break  # 找到重复就跳出内层循环
            j += 1
    # --- 第4步：输出结果 ---
    new_data = list(data)
    return new_data, changes

#移除附录下面纵向表格的标题
# def rule_remove_table_titles_in_annex(data):
#     """
#     在 Annex / Appendix 内部：
#     - text_level == 1
#     - 且无编号（A.1 / B.2.3）
#     → 移除标题层级
#
#     Annex 一旦开始，持续到文档结束
#     """
#
#     import re
#     changes = []
#     new_data = []
#
#     annex_title_pattern = re.compile(
#         r'^(?:annex|appendix)(?!es)\s+[A-Z]{1,2}\b',
#         re.IGNORECASE
#     )
#
#     annex_numbered_pattern = re.compile(
#         r'''
#         ^(
#             [A-Z]{1,2}\d+(?:\.\d+)*   # L2 / L2.2 / L2.2.1
#           | [A-Z]{1,2}\.\d+(?:\.\d+)* # A.1 / B.2.3
#         )
#         \b
#         ''',
#         re.VERBOSE
#     )
#
#     inside_annex = False
#
#     for block in data:
#         text = block.get("text", "").strip()
#
#         # ① 严谨进入 Annex：必须是一级标题
#         if (
#             block.get("text_level") == 1
#             and annex_title_pattern.match(text)
#         ):
#             inside_annex = True
#             new_data.append(block)
#             continue
#
#         # ② Annex 内：移除无编号一级标题
#         if inside_annex and block.get("text_level") == 1:
#             if not annex_numbered_pattern.match(text):
#                 old = block.pop("text_level")
#                 changes.append(
#                     f"[rule_remove_table_titles_in_annex] "
#                     f"page {block.get('page_idx','?')}\n"
#                     f"移除 Annex 内无编号一级标题: \"{text}\" "
#                     f"(原 text_level={old})\n"
#                 )
#
#         new_data.append(block)
#
#     return new_data, changes
def rule_remove_table_titles_in_annex(data):
    """
    在 Annex / Appendix 内部：
      - 仅当真正进入 Annex 后才生效
      - Annex 标题必须出现在行首，允许后跟解释、冒号、括号
      - Annex 内：
          * text_level == 1
          * 且无 Annex 编号（A.1 / B.2.3 / L2.1）
        → 移除标题层级
      - 遇到主文档编号（1 / 1.1 / 2.3）立即退出 Annex
    """

    import re
    changes = []
    new_data = []

    # -------------------------------------------------
    # ① Annex / Appendix 进入条件（行首，允许解释）
    # -------------------------------------------------
    annex_enter_pattern = re.compile(
        r'^(annex|appendix|annexe)\s+[A-Z]{1,2}\b.*$',
        re.IGNORECASE
    )

    # -------------------------------------------------
    # ② Annex 内允许的编号子标题
    #    A.1 / B.2.3 / L2.1 / AA2.3.4
    # -------------------------------------------------
    annex_numbered_pattern = re.compile(
        r'''
        ^(
            [A-Z]{1,2}\d+(?:\.\d+)*     # L2 / L2.1 / L2.1.1
          | [A-Z]{1,2}\.\d+(?:\.\d+)*   # A.1 / B.2.3
        )
        \b
        ''',
        re.VERBOSE
    )

    # -------------------------------------------------
    # ③ 主文档编号（用于退出 Annex）
    # -------------------------------------------------
    main_section_pattern = re.compile(
        r'^\d+(?:\.\d+)*\b'
    )

    inside_annex = False

    # -------------------------------------------------
    # ④ 主循环
    # -------------------------------------------------
    for block in data:
        text = block.get("text", "").strip()
        level = block.get("text_level")

        if not text:
            new_data.append(block)
            continue

        # --------------------------
        # A️⃣ 退出 Annex（优先级最高）
        # --------------------------
        if inside_annex and main_section_pattern.match(text):
            inside_annex = False
            new_data.append(block)
            continue

        # --------------------------
        # B️⃣ 进入 Annex
        # --------------------------
        if level == 1 and annex_enter_pattern.match(text):
            inside_annex = True
            new_data.append(block)
            continue

        # --------------------------
        # C️⃣ Annex 内规则
        # --------------------------
        if inside_annex and level == 1:
            # 有 Annex 编号 → 保留
            if annex_numbered_pattern.match(text):
                new_data.append(block)
                continue

            # 无编号 → 移除标题层级
            old = block.pop("text_level", None)
            if old is not None:
                changes.append(
                    f"[rule_remove_table_titles_in_annex] "
                    f"page {block.get('page_idx','?')}\n"
                    f"移除 Annex 内无编号一级标题: \"{text}\" "
                    f"(原 text_level={old})\n"
                )

            new_data.append(block)
            continue

        # --------------------------
        # D️⃣ 默认：原样保留
        # --------------------------
        new_data.append(block)

    return new_data, changes

def rule_rm_between(data):
    """
    删除 “X Terms and definitions” 与下一章（X+1）真正的一级标题之间所有 text_level。
    只删除 text_level，不删除块。
    """

    import re
    changes = []

    # ① 匹配 “3 Terms and definitions” 找到编号
    terms_re = re.compile(r'^\s*(\d+)\s+terms and definitions\b', re.IGNORECASE)

    start = None
    current_chapter = None

    # --- 找到 Terms and definitions 的一级标题 ---
    for i, blk in enumerate(data):
        if blk.get("text_level") == 1:
            text = blk.get("text", "")
            m = terms_re.match(text)
            if m:
                start = i
                current_chapter = int(m.group(1))
                break

    if start is None:
        return data, changes

    # --- ② 下一章编号 = 当前编号 + 1 ---
    next_chapter = current_chapter + 1

    # --- ③ 匹配以下一章节号开头的一级标题 ---
    next_chapter_re = re.compile(rf'^\s*{next_chapter}\b')

    end = None
    for j in range(start + 1, len(data)):
        blk = data[j]
        if blk.get("text_level") == 1:
            text = blk.get("text", "")
            if next_chapter_re.match(text):
                end = j
                break

    if end is None:
        end = len(data)

    # --- ④ 删除 start 和 end 之间的所有 text_level ---
    for k in range(start + 1, end):
        blk = data[k]
        if "text_level" in blk:
            old = blk.pop("text_level")
            changes.append(
                f"[rule_rm_between] page {blk.get('page_idx','?')}\n"
                f"删除 3 章内部的 text_level={old}: \"{blk.get('text','')}\"\n"
            )

    return data, changes

# def rule_smart_dotend_split(data: List[JsonBlock], threshold: int = 10) -> Tuple[List[JsonBlock], List[str]]:
#     """
#     智能处理末尾为句号的文本块，并按首句长度判断是否保留标题层级。
#
#     参数：
#         data      : 文本块列表，每个块是 dict
#         threshold : 首句单词数阈值，超过阈值会删除 text_level
#     """
#     import re
#     changes = []
#     new_data = []
#
#     # ---------------------------
#     # 行首噪声清理函数（仅用于判断编号，不修改原文）
#     # ---------------------------
#     def strip_leading_noise(text: str) -> str:
#         t = text.strip()
#         # 去掉孤立字母或符号开头（N、Δ、•、·、—、–、= 等）
#         t = re.sub(r'^(?:[A-Za-zΔ])\s+', '', t)
#         # 去掉常见前缀符号
#         t = re.sub(r'^[•·—–\-=]+\s*', '', t)
#         # 去掉 LaTeX math
#         t = re.sub(r'^\$\s*\\?[a-zA-Z]+\{?.*?\}?\s*\$\s*', '', t)
#         t = t.strip()
#         return t
#
#     # ---------------------------
#     # 主循环
#     # ---------------------------
#     for blk in data:
#         raw_text = blk.get("text", "").rstrip()
#         old_level = blk.get("text_level")
#
#         if not raw_text:
#             new_data.append(blk)
#             continue
#
#         # 临时处理行首噪声判断编号
#         temp_text = strip_leading_noise(raw_text)
#
#         # ---------------------------
#         # 多级编号标题识别
#         # ---------------------------
#         m = re.match(r'^(\d+(?:\.\d+)*)(?:\s+|\u00A0|(?=[A-Za-z]))', temp_text)
#         if m and old_level is None:
#             number_part = m.group(1)
#             blk["text_level"] = min(number_part.count('.') + 1, 7)
#
#         # 如果仍没有 text_level，跳过
#         level = blk.get("text_level")
#         if not level:
#             new_data.append(blk)
#             continue
#
#         # ---------------------------
#         # 仅处理末尾为句号的文本
#         # ---------------------------
#         if raw_text.endswith("."):
#             # 拆分编号和正文
#             m_split = re.match(r'^(\d+(?:\.\d+)*)(\s*)(.*)', temp_text)
#             if m_split:
#                 number_part = m_split.group(1)
#                 rest_text = m_split.group(3).strip()
#             else:
#                 number_part = ""
#                 rest_text = temp_text
#
#             # 找到首句结束
#             first_dot = re.search(r'\.', rest_text)
#             if first_dot:
#                 first_sentence = rest_text[:first_dot.start()+1].strip()
#                 first_sentence_word_count = len(first_sentence.split())
#             else:
#                 first_sentence = rest_text
#                 first_sentence_word_count = len(first_sentence.split())
#
#             # 超过阈值 → 删除 text_level
#             if first_sentence_word_count > threshold:
#                 old = blk.pop("text_level")
#                 changes.append(
#                     f"[rule_smart_dotend_split] page {blk.get('page_idx','?')}\n"
#                     f"首句单词数={first_sentence_word_count}超过阈值({threshold})，删除 text_level={old}: \"{raw_text}\"\n"
#                 )
#                 new_data.append(blk)
#             else:
#                 # 不超过阈值 → 拆分标题和正文
#                 if number_part:
#                     title_text = f"{number_part} {first_sentence}".strip()
#                     new_level = min(number_part.count('.') + 1, 7)
#                 else:
#                     title_text = first_sentence
#                     new_level = level
#
#                 blk["text"] = title_text
#                 blk["text_level"] = new_level
#                 new_data.append(blk)
#
#                 changes.append(
#                     f"[rule_smart_dotend_split] page {blk.get('page_idx','?')}\n"
#                     f"拆分标题: \"{raw_text}\" → \"{title_text}\" (text_level={new_level}, 原: {old_level})\n"
#                 )
#
#                 # 后半部分正文
#                 remaining_text = rest_text[first_dot.end():].strip() if first_dot else ""
#                 if remaining_text:
#                     new_blk = {
#                         "type": blk.get("type", "text"),
#                         "text": remaining_text,
#                         "page_idx": blk.get("page_idx")
#                     }
#                     new_data.append(new_blk)
#                     changes.append(
#                         f"[rule_smart_dotend_split] page {blk.get('page_idx','?')}\n"
#                         f"拆分正文: \"{remaining_text}\"\n"
#                     )
#         else:
#             new_data.append(blk)
#
#     return new_data, changes

def rule_smart_dotend_split(data: List[JsonBlock], threshold=10) -> Tuple[List[JsonBlock], List[str]]:
    """
    智能处理末尾为句号的文本块，同时保护附录/章节数字标题：
      - 去除行首噪声（符号/空格/命令型 LaTeX math）
      - 支持多级编号标题（有空格或紧贴正文）
      - 判断首句单词数是否超过阈值，决定是否保留标题层级或拆分正文
      - 对数字+字母编号开头标题（如 C.5, C.5.3）不拆分
      - 拆分操作写入日志

    参数：
        data      : 文本块列表，每个块是 dict
        threshold : 首句单词数阈值
    """
    import re
    changes = []
    new_data = []

    # -----------------------------
    # 行首噪声清理
    # -----------------------------
    def strip_leading_noise(text: str) -> str:
        t = text.strip()
        # 去掉孤立字母或符号开头（N、Δ、•、·、—、–、= 等）
        t = re.sub(r'^(?:[A-Za-zΔ])\s+', '', t)
        # 去掉常见前缀符号
        t = re.sub(r'^[•·—–\-=]+\s*', '', t)
        # 去掉 LaTeX math
        t = re.sub(r'^\$\s*\\?[a-zA-Z]+\{?.*?\}?\s*\$\s*', '', t)
        return t.strip()

    # -----------------------------
    # 主循环
    # -----------------------------
    for blk in data:
        text = blk.get("text", "").rstrip()
        level = blk.get("text_level")
        clean_text = normalize_text(strip_leading_noise(text))

        # -----------------------------
        # 数字编号开头（可能含字母，如 C.5, C.5.3）保护
        # -----------------------------
        # 规则：行首字母+数字编号
        if re.match(r'^[A-Z]\.\d+(?:\.\d+)*', clean_text, re.IGNORECASE):
            # 自动补充 text_level（如果没有的话）
            if level is None:
                number_part = re.match(r'^([A-Z]\.\d+(?:\.\d+)*)', clean_text).group(1)
                blk["text_level"] = min(number_part.count('.') + 1, 7)
            new_data.append(blk)
            continue

        # -----------------------------
        # 原有数字编号逻辑（忽略前导 N 等）
        # -----------------------------
        m = re.match(r'^(\d+(?:\.\d+)*)(?:\s+|\u00A0|(?=[A-Za-z]))', clean_text)
        if m and level is None:
            number_part = m.group(1)
            blk["text_level"] = min(number_part.count('.') + 1, 7)
            level = blk["text_level"]

        # -----------------------------
        # 非标题或没有 text_level → 保留
        # -----------------------------
        if not clean_text or level is None:
            new_data.append(blk)
            continue

        # -----------------------------
        # 仅处理末尾句号
        # -----------------------------
        if clean_text.endswith("."):
            # 拆分编号和正文
            m = re.match(r'^(\d+(?:\.\d+)*)(\s*)(.*)', clean_text)
            if m:
                number_part = m.group(1)
                rest_text = m.group(3).strip()
            else:
                number_part = ""
                rest_text = clean_text

            # 找到首句结束位置
            first_dot = re.search(r'\.', rest_text)
            if first_dot:
                first_sentence = rest_text[:first_dot.start()+1].strip()
                first_sentence_word_count = len(first_sentence.split())
            else:
                first_sentence = rest_text
                first_sentence_word_count = len(first_sentence.split())

            # 超过阈值 → 删除 text_level
            if first_sentence_word_count > threshold:
                old = blk.pop("text_level")
                changes.append(
                    f"[rule_smart_dotend_split] page {blk.get('page_idx','?')}\n"
                    f"首句单词数={first_sentence_word_count}超过阈值({threshold})，删除 text_level={old}: \"{clean_text}\"\n"
                )
                new_data.append(blk)
            else:
                # 不超过阈值 → 拆分文本块
                # 前半部分：编号 + 首句
                if number_part:
                    title_text = f"{number_part} {first_sentence}".strip()
                    new_level = min(number_part.count('.') + 1, 7)
                else:
                    title_text = first_sentence
                    new_level = level

                old_level = blk.get("text_level")
                blk["text"] = title_text
                blk["text_level"] = new_level
                new_data.append(blk)

                changes.append(
                    f"[rule_smart_dotend_split] page {blk.get('page_idx','?')}\n"
                    f"拆分标题: \"{clean_text}\" → \"{title_text}\" (text_level={new_level}, 原: {old_level})\n"
                )

                # 后半部分：剩余正文
                remaining_text = rest_text[first_dot.end():].strip()
                if remaining_text:
                    new_blk = {
                        "type": blk.get("type", "text"),
                        "text": remaining_text,
                        "page_idx": blk.get("page_idx")
                    }
                    new_data.append(new_blk)
                    changes.append(
                        f"[rule_smart_dotend_split] page {blk.get('page_idx','?')}\n"
                        f"拆分正文: \"{remaining_text}\"\n"
                    )
        else:
            # 不以句号结尾 → 保留
            new_data.append(blk)

    return new_data, changes


def rule_merge_pure_number_heading_with_text(data: List[JsonBlock]) -> Tuple[List[JsonBlock], List[str]]:
    """
    规则：
    - 识别“纯数字标题块”（如 3 / 3.3 / 3.3.1）
    - 若其后紧跟一个【同页】【一级标题】【非数字开头】文本块
      → 合并为一个标题
    - 根据数字编号校正 text_level
    """
    import re

    changes = []
    new_data = []

    # 纯数字编号（整行）
    pure_number_pattern = re.compile(r'^\d+(?:\.\d+)*$')

    # 数字标题层级计算
    def level_from_number(num: str) -> int:
        return min(num.count('.') + 1, 7)

    i = 0
    while i < len(data):
        blk = data[i]
        text = blk.get("text", "").strip()
        level = blk.get("text_level")

        # 1️⃣ 判断是否是纯数字标题
        if (
            level is not None
            and pure_number_pattern.fullmatch(text)
            and i + 1 < len(data)
        ):
            next_blk = data[i + 1]
            next_text = next_blk.get("text", "").strip()
            next_level = next_blk.get("text_level")

            # 2️⃣ 判断下一个块是否可合并
            if (
                next_level == 1
                and not re.match(r'^\d', next_text)
                and blk.get("page_idx") == next_blk.get("page_idx")
            ):
                number = text
                new_level = level_from_number(number)
                merged_text = f"{number} {next_text}"

                new_blk = {
                    "type": blk.get("type", "text"),
                    "text": merged_text,
                    "text_level": new_level,
                    "page_idx": blk.get("page_idx"),
                }

                new_data.append(new_blk)

                changes.append(
                    f"[rule_merge_pure_number_heading_with_text] "
                    f"page {blk.get('page_idx','?')}\n"
                    f"合并标题: \"{text}\" + \"{next_text}\" → \"{merged_text}\" "
                    f"(text_level={new_level})\n"
                )

                i += 2
                continue

        # 默认：原样保留
        new_data.append(blk)
        i += 1

    return new_data, changes



def rule_rm_key(data):
    """
    删除标题文本为 'Key'（忽略大小写）的 text_level。
    不删除 block，只删除 text_level。
    """
    changes = []

    for blk in data:
        if "text_level" in blk:
            text = blk.get("text", "").strip()
            if text.lower() == "key":
                old = blk.pop("text_level")
                changes.append(
                    f"[rule_rm_key] page {blk.get('page_idx','?')}\n"
                    f"删除 text_level={old}，因为标题为 'Key'\n"
                )

    return data, changes
def rule_rm_iso(data):
    """
    删除所有以 'ISO' 开头的标题（忽略大小写）的 text_level。
    例如: 'ISO 1992', 'ISO/IEC 8000', 'ISO1234'
    """

    import re
    changes = []

    iso_re = re.compile(r'^\s*ISO\b', re.IGNORECASE)

    for blk in data:
        if "text_level" not in blk:
            continue

        text = blk.get("text", "").strip()

        if iso_re.match(text):
            old = blk.pop("text_level")
            changes.append(
                f"[rule_rm_iso] page {blk.get('page_idx','?')}\n"
                f"删除 text_level={old} 因标题以 ISO 开头: \"{text}\"\n"
            )

    return data, changes
def rule_rm_iec_cei(data):
    """
    删除包含大写 'IEC' 或 'CEI' 的标题（严格区分大小写）。
    """

    changes = []

    for blk in data:
        if "text_level" not in blk:
            continue

        text = blk.get("text", "").strip()

        # 精确匹配区分大小写
        if "IEC" in text or "CEI" in text:
            old = blk.pop("text_level")
            changes.append(
                f"[rule_rm_iec_cei] page {blk.get('page_idx','?')}\n"
                f"删除 text_level={old} 因标题包含大写 IEC/CEI: \"{text}\"\n"
            )

    return data, changes


# 目次中不应该出现标题，消除目次中的标题层级，即前言和目次之间，不允许出现标题。
def rule_remove_headings_between_contents_and_foreword_en(data):
    """
    规则（英文版）:
    在“CONTENTS”与“FOREWORD”/“AVANT-PROPOS”之间不允许出现其他标题。
    若存在标题，则删除其 text_level。
    匹配不区分大小写。
    """
    import re
    changes = []

    # === 正则：不区分大小写匹配  ===
    contents_pattern = re.compile(r'^\s*contents\s*$', re.IGNORECASE)
    foreword_pattern = re.compile(r'^\s*foreword\s*$', re.IGNORECASE)
    avant_propos_pattern = re.compile(r'^\s*avant[\s\-]?propos\s*$', re.IGNORECASE)
    # 匹配avant-propos后面出现其他单词的情况
    # avant_propos_pattern = re.compile(r'^\s*avant[\s\-]?propos\b', re.IGNORECASE)

    contents_index = None
    preface_index = None

    # === 第1步：定位 CONTENTS 与 Foreword/Avant-Propos ===
    for i, block in enumerate(data):
        text = block.get("text", "").strip()

        if "text_level" in block:
            if contents_index is None and contents_pattern.match(text):
                contents_index = i
            elif preface_index is None and (
                foreword_pattern.match(text) or avant_propos_pattern.match(text)
            ):
                preface_index = i

    # 如果不存在有效区域，则不处理
    if contents_index is None or preface_index is None or preface_index <= contents_index:
        return data, changes

    # === 第2步：删除两者之间的标题层级 ===
    for j in range(contents_index + 1, preface_index):
        block = data[j]
        if "text_level" in block:
            old_level = block.pop("text_level")
            text = block.get("text", "").strip()
            changes.append(
                f"[rule_remove_headings_between_contents_and_foreword_en] page {block.get('page_idx','?')}\n"
                f"修改: \"{text}\"\n"
                f"→ 删除 text_level={old_level}（位于 CONTENTS 与 FOREWORD/AVANT-PROPOS 之间）\n"
            )
    return data,changes
#删除前言之前的标题
def rule_remove_titles_before_preface_or_contents_en(blocks):
    """
    删除封面页等在 FOREWORD / AVANT-PROPOS / CONTENTS 之前的所有标题层级。
    但 FOREWORD 与 AVANT-PROPOS 自身的层级必须保留。
    """

    import re

    # 目标标题（第一个有效标题）
    first_title_patterns = [
        r'^foreword$',
        r'^avant[-\s]?propos$',
    ]

    # fallback 标题
    fallback_patterns = [
        r'^contents$',
        r'^table of contents$'
    ]

    def is_match(text, patterns):
        t = text.strip().lower()
        return any(re.match(p, t, re.IGNORECASE) for p in patterns)

    # -----------------------------
    # Step 1: 找到 foreword / avant-propos
    # -----------------------------
    first_idx = None

    for i, blk in enumerate(blocks):
        if blk.get("type") == "text" and "text_level" in blk:
            t = blk.get("text", "")
            if is_match(t, first_title_patterns):
                first_idx = i
                break

    # -----------------------------
    # Step 2: fallback → contents
    # -----------------------------
    if first_idx is None:
        for i, blk in enumerate(blocks):
            if blk.get("type") == "text" and "text_level" in blk:
                t = blk.get("text", "")
                if is_match(t, fallback_patterns):
                    first_idx = i
                    break

    # -----------------------------
    # Step 3: 如果仍然没找到 → 不做任何处理
    # -----------------------------
    if first_idx is None:
        return blocks, ["No foreword/avant-propos/contents found, skipped."]

    # -----------------------------
    # Step 4: 删除 first_idx 之前标题的层级
    # -----------------------------
    removed = []
    for i, blk in enumerate(blocks):
        if i < first_idx:
            if blk.get("type") == "text" and "text_level" in blk:
                removed.append(blk["text"])
                blk.pop("text_level", None)   # 删除标题层级

    return blocks, [f"Removed heading levels for {len(removed)} blocks before index {first_idx}."]


def rule_remove_where_heading_level(data):
    """
    规则：若文本内容为 'where'（整行是where,不区分大小写），
    则移除其标题层级 text_level，但保留该文本块。
    """

    import re
    changes = []
    new_data = []

    where_pattern = re.compile(r'^\s*where\s*$', re.IGNORECASE)

    for block in data:
        text = block.get("text", "")

        if where_pattern.match(text) and "text_level" in block:
            old_level = block.pop("text_level")
            changes.append(
                f"[rule_remove_where_heading_level] page {block.get('page_idx','?')}\n"
                f"移除 where 标题层级: \"{text}\" (text_level={old_level})\n"
            )

        new_data.append(block)

    return new_data, changes


#移除两个连续同级标题之间比该标题级别高的不合法标题
def rule_remove_invalid_higher_level_between_same_level_titles(data):
    """
    规则：
    - 防止在同一层级结构内部，出现非法“更高层级”标题
    - 但必须【严格保护】合法的顶级结构边界：
        * PART / PART I / PARTIPAVEMENT...
        * CHAPTER / Chapter 1 / 1
        * APPENDIX / Annex A
    - 同时整合 strip_leading_noise，去除标题行首噪声（符号/空格/命令型 math）
    """

    import re
    changes = []
    new_data = []

    # -------------------------------------------------
    # 1️⃣ 行首噪声清理函数（根据需要进行扩充）
    # -------------------------------------------------
    def strip_leading_noise(text: str) -> str:
        import re
        t = text.lstrip(' \t\n')  # 去掉空格/制表符/换行

        # 1️⃣ 去掉常见前缀符号，如 • · — – - = 等
        t = re.sub(r'^[•·—–\-=]+\s*', '', t)

        # 2️⃣ 去掉行首 LaTeX math，包括命令型和裸符号型
        t = re.sub(r'^\$\s*\\?[a-zA-Z]+\{?.*?\}?\s*\$\s*', '', t)

        # 3️⃣ 去掉行首孤立字母或符号（单个或多个），如 N、Δ、A 等
        t = re.sub(r'^(?:[A-Za-zΔ])\s+', '', t)

        # 4️⃣ 再去掉可能残留的空格
        t = t.lstrip()

        return t

    # -------------------------------------------------
    # 2️⃣ 顶级结构边界检测
    # -------------------------------------------------
    def detect_top_level_boundary(text: str):
        t = text.strip()

        if re.match(r'^part\s*([IVXLCDM]+|\d+)?\s*[A-Z]', t, re.IGNORECASE):
            return "part"
        if re.match(r'^chapter\s+\d+\b', t, re.IGNORECASE):
            return "chapter"
        if re.match(r'^\d+\b', t):
            return "chapter"
        if re.match(
                r'^(appendix|annex|annexe)\s+[A-Z]{1,2}(?:\s|[\(\:\-]|$)',
                t,
                re.IGNORECASE
        ):
            return "appendix"

        return None

    # -------------------------------------------------
    # 3️⃣ 状态：是否处在某个层级内部
    # inside[2] = 当前是否在 level 2 章节中
    # -------------------------------------------------
    inside = {i: False for i in range(2, 8)}

    for block in data:
        text = block.get("text", "").strip()
        level = block.get("text_level")

        # 先清理标题前缀噪声
        clean_text = strip_leading_noise(text)

        # 非标题 → 原样保留
        if level is None:
            new_data.append(block)
            continue

        # -------------------------------------------------
        # 顶级结构边界 → 绝对保护 + reset
        # -------------------------------------------------
        if level == 1:
            boundary = detect_top_level_boundary(clean_text)
            if boundary:
                for k in inside:
                    inside[k] = False
                new_data.append(block)
                continue

        # -------------------------------------------------
        # 非法 level=1（发生在某个子层级内部）
        # -------------------------------------------------
        if level == 1 and any(inside.values()):
            old = block.pop("text_level")
            changes.append(
                f"[rule_remove_invalid_higher_level_between_same_level_titles]\n"
                f"page {block.get('page_idx','?')}\n"
                f"非法一级标题（位于子结构内部）: \"{clean_text}\" "
                f"(原 text_level={old})\n"
            )
            new_data.append(block)
            continue

        # -------------------------------------------------
        # 正常层级推进
        # -------------------------------------------------
        if level >= 2:
            # 进入该层级
            inside[level] = True
            # 退出更深层级
            for k in inside:
                if k > level:
                    inside[k] = False

        new_data.append(block)

    return new_data, changes


#若 text 以 冒号(: ：)结尾，移除其标题层级
def rule_remove_titles_ending_with_punctuation(data):

    import re

    changes = []
    new_data = []

    # 冒号或句号结尾（允许结尾有空格）
    end_punctuation_pattern = re.compile(r'[：:]\s*$')

    for block in data:
        text = block.get("text", "")
        level = block.get("text_level")

        if level is not None and end_punctuation_pattern.search(text):
            old = block.pop("text_level")
            changes.append(
                f"[rule_remove_titles_ending_with_punctuation] "
                f"page {block.get('page_idx','?')}\n"
                f"移除标点结尾标题层级: \"{text}\" "
                f"(原 text_level={old})\n"
            )

        new_data.append(block)

    return new_data, changes

#删除目录项中的内容的标题层级
def rule_remove_content_headings(data: List[dict]) -> Tuple[List[dict], List[str]]:
    """
    规则:
    - 删除“目录项形式”的误判标题层级
    - 目录项特征：文本以页码形式结尾（如 1-56 / 11-37 / III-145 / Ⅱ-77）
    - 只做删除，不新增、不修正标题
    """

    changes = []

    # 行尾页码模式
    page_suffix_pattern = re.compile(
        r"""
        \s+(
            \d+\s*-\s*\d+ |        # 1-56
            [A-Z]{1,4}\s*-\s*\d+ | # A-12, III-145
            [ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\s*-\s*\d+ | # Ⅱ-77
            \d+                       # 末尾纯数字
        )\s*$
        """,
        re.VERBOSE
    )

    for block in data:
        text = block.get("text", "").strip()

        # 只处理“已经被识别成标题”的
        if "text_level" not in block:
            continue

        # 命中目录项形式
        if page_suffix_pattern.search(text):
            old_level = block.pop("text_level")
            changes.append(
                f"[rule_remove_content_headings] page {block.get('page_idx','?')}\n"
                f"目录项去标题: \"{text}\"\n"
                f"→ 删除 text_level={old_level}\n"
            )

    return data, changes

#移除最后一个附录（包括附录子标题）之后的标题
# def rule_remove_headings_after_last_appendix(data):
#     """
#     规则：
#     - 找到最后一个 Appendix / Annex / Annexe 一级标题
#     - 该附录及其所有子标题全部保留
#     - 在“最后一个附录及其子标题之后”出现的标题 → 删除 text_level
#     """
#     import re
#     changes = []
#     new_data = []
#
#     appendix_title_pattern = re.compile(
#         r'^(appendix|annex|annexe)\s+[A-Z0-9]+\b',
#         re.IGNORECASE
#     )
#
#     # -----------------------------
#     # 1. 找到最后一个一级附录标题位置
#     # -----------------------------
#     last_appendix_idx = None
#     last_appendix_level = None
#
#     for i, block in enumerate(data):
#         if (
#             block.get("text_level") == 1
#             and appendix_title_pattern.match(block.get("text", "").strip())
#         ):
#             last_appendix_idx = i
#             last_appendix_level = block["text_level"]
#
#     # 没有附录，直接返回
#     if last_appendix_idx is None:
#         return data, changes
#
#     # -----------------------------
#     # 2. 找到最后一个附录的结束位置
#     #    规则：遇到新的一级标题或附录序列断开，视为结束
#     # -----------------------------
#     appendix_end_idx = len(data)
#     for j in range(last_appendix_idx + 1, len(data)):
#         b = data[j]
#         # 只对一级标题判断附录结束
#         if b.get("text_level") == 1:
#             # 遇到新的一级标题就停止
#             appendix_end_idx = j
#             break
#
#     # -----------------------------
#     # 3. 构造新数据
#     # -----------------------------
#     for idx, block in enumerate(data):
#         # 最后一个附录及其所有子标题 → 原样保留
#         if idx < appendix_end_idx:
#             new_data.append(block)
#             continue
#
#         # 附录之后的新标题 → 删除 text_level
#         if "text_level" in block:
#             old = block.pop("text_level")
#             changes.append(
#                 f"[rule_remove_headings_after_last_appendix] "
#                 f"page {block.get('page_idx','?')}\n"
#                 f"移除附录后标题: \"{block.get('text','').strip()}\" "
#                 f"(原 text_level={old})\n"
#             )
#
#         new_data.append(block)
#
#     return new_data, changes

#移除最后一个附录（包括附录子标题）之后的标题
def rule_remove_headings_after_last_appendix(data):
    """
    规则：
    - 找到最后一个 Appendix / Annex / Annexe 一级标题
    - 该附录及其所有子标题全部保留
    - 在“最后一个附录及其子标题之后”出现的标题 → 删除 text_level
    """
    import re
    changes = []
    new_data = []

    appendix_title_pattern = re.compile(
        r'^(appendix|annex|annexe)\s+[A-Z0-9]+\b',
        re.IGNORECASE
    )

    # -----------------------------
    # 1️⃣ 找到最后一个一级附录标题位置
    # -----------------------------
    last_appendix_idx = None
    last_appendix_level = None

    for i, block in enumerate(data):
        if (
            block.get("text_level") == 1
            and appendix_title_pattern.match(block.get("text", "").strip())
        ):
            last_appendix_idx = i
            last_appendix_level = block["text_level"]

    # 没有附录，直接返回
    if last_appendix_idx is None:
        return data, changes

    # -----------------------------
    # 2️⃣ 找到最后一个附录的结束位置
    #    规则：遇到新的一级标题就结束
    # -----------------------------
    appendix_end_idx = len(data)
    for j in range(last_appendix_idx + 1, len(data)):
        b = data[j]
        if b.get("text_level") == 1:
            appendix_end_idx = j
            break

    # -----------------------------
    # 3️⃣ 构造新数据
    # -----------------------------
    for idx, block in enumerate(data):
        # 仍然在最后一个附录及其子标题范围内 → 原样保留
        if idx <= appendix_end_idx - 1:
            new_data.append(block)
            continue

        # 附录之后的新标题 → 删除 text_level，但排除附录子标题
        if "text_level" in block:
            # 如果 text_level > 1 且是最后一个附录的子标题，则保留
            if block["text_level"] > 1:
                new_data.append(block)
            else:
                old = block.pop("text_level")
                changes.append(
                    f"[rule_remove_headings_after_last_appendix] "
                    f"page {block.get('page_idx','?')}\n"
                    f"移除附录后标题: \"{block.get('text','').strip()}\" "
                    f"(原 text_level={old})\n"
                )
        else:
            new_data.append(block)

    return new_data, changes

def rule_remove_numeric_measurement_titles_in_last_appendix(data):
    """
    规则：
    - 定位最后一个 Appendix / Annex
    - 在该附录内部：
      - 若文本为“数值 + 单位 / 材料描述”
      - 即使被识别成标题，也删除 text_level
    """

    import re
    changes = []

    appendix_title_pattern = re.compile(
        r'^(appendix|annex)\s+[A-Z0-9]+\b',
        re.IGNORECASE
    )

    def looks_like_measurement(text: str) -> bool:
        # 8.00 (in)
        if re.match(r'^\d+(\.\d+)?\s*\([a-zA-Z]+\)\s*$', text):
            return True

        # 8.5 inches granular base
        if re.match(
            r'^\d+(\.\d+)?\s+(in|inch|inches|mm|cm|ft|feet)\b',
            text,
            re.IGNORECASE
        ):
            return True

        # 数值 + 材料
        if re.match(
            r'^\d+(\.\d+)?\s+.*\b(base|layer|course|concrete|asphalt)\b',
            text,
            re.IGNORECASE
        ):
            return True

        return False

    # -----------------------------
    # 找最后一个附录
    # -----------------------------
    last_appendix_idx = None
    for i, block in enumerate(data):
        if (
            block.get("text_level") == 1
            and appendix_title_pattern.match(block.get("text", "").strip())
        ):
            last_appendix_idx = i

    if last_appendix_idx is None:
        return data, changes

    # -----------------------------
    # 在附录内部清洗
    # -----------------------------
    for idx in range(last_appendix_idx + 1, len(data)):
        block = data[idx]
        text = block.get("text", "").strip()

        if "text_level" in block and looks_like_measurement(text):
            old = block.pop("text_level")
            changes.append(
                f"[rule_remove_numeric_measurement_titles_in_last_appendix] "
                f"page {block.get('page_idx','?')}\n"
                f"附录内数值行去标题: \"{text}\" "
                f"(原 text_level={old})\n"
            )

    return data, changes

#删除长度超过10个单词（不包括标题序号）的标题
def rule_remove_long_headings(data, threshold=10):
    """
    规则：
    - 移除除标题编号外，单词数超过阈值的标题
    - 避免影响 Chapter / Part / Section / Annex 等顶级标题
    """
    import re
    changes = []

    # 受保护的顶级标题前缀（不删除这些）
    # protected_prefix = re.compile(
    #     r'^(chapter|part|section|appendix|annex)\b', re.IGNORECASE
    # )

    # 标题编号匹配（如 1, 1.1, 1.1.1 等）
    numbering_pattern = re.compile(r'^(\d+(?:\.\d+)*)\s*')

    for block in data:
        text = block.get("text", "").strip()

        # 只处理有 text_level 的标题
        if "text_level" not in block:
            continue

        # # 避开受保护的顶级标题
        # if protected_prefix.match(text):
        #     continue

        # 去掉编号
        text_wo_number = numbering_pattern.sub("", text).strip()

        # 单词数统计
        word_count = len(text_wo_number.split())

        if word_count > threshold:
            old_level = block.pop("text_level")
            changes.append(
                f"[rule_remove_long_headings] page {block.get('page_idx','?')}\n"
                f"标题过长 ({word_count} > {threshold}): \"{text}\"\n"
                f"→ 删除 text_level={old_level}\n"
            )

    return data, changes

#兜底式规则：整行的purpose、contents、foreword等必须设为标题
def rule_top_level_heading_en(data):
    """
    规则：
    - 如果文本块整行是 purpose、contents、foreword等
    - 允许可选 (informative)
    - 且原本没有 text_level
    → 设置为一级标题（text_level = 1）
    """
    import re
    changes = []

    pattern = re.compile(
        r'^(foreword|preface|purpose|contents|introduction|special notice|executive summary|Bibliographie|index|classification methodology)(?:\s*\(\s*informative\s*\))?$',
        re.IGNORECASE
    )

    for block in data:
        text = block.get("text", "").strip()

        if not text:
            continue

        # 只处理「原本不是标题」的
        if "text_level" in block:
            continue

        if pattern.match(text):
            block["text_level"] = 1
            changes.append(
                f"[rule_foreword_preface_heading_en] page {block.get('page_idx','?')}\n"
                f"识别前言标题: \"{text}\" → 设置 text_level=1\n"
            )

    return data, changes

#===============非通用性规则===================================
#利用过滤掉目录和"Part I .....(可能连写）“的方式过滤掉目录中的残留项目
def rule_remove_toc_residual_items_before_compact_part(data):
    """
    规则：
    - 找到 TABLE OF CONTENTS / CONTENTS
    - 找到正文真正开始的标题：
      PARTIPAVEMENTDESIGNANDMANAGEMENTPRINCIPLES
    - 删除二者之间的所有目录残留项
    """

    import re
    changes = []
    new_data = []

    toc_pattern = re.compile(
        r'^(table\s+of\s+)?contents\b',
        re.IGNORECASE
    )

    # 精确匹配正文 PART 起点（无空格）
    real_part_title_pattern = re.compile(
        r'^partipavementdesignandmanagementprinciples$',
        re.IGNORECASE
    )

    toc_idx = None
    real_part_idx = None

    # -----------------------------
    # 1. 找 TOC
    # -----------------------------
    for i, block in enumerate(data):
        text = block.get("text", "").strip()
        if toc_pattern.match(text):
            toc_idx = i
            break

    if toc_idx is None:
        return data, changes

    # -----------------------------
    # 2. 找正文真正开始的 PART
    # -----------------------------
    for j in range(toc_idx + 1, len(data)):
        text = data[j].get("text", "").strip()
        if real_part_title_pattern.match(text):
            real_part_idx = j
            break

    if real_part_idx is None:
        return data, changes

    # -----------------------------
    # 3. 删除 TOC 与 正文 PART 之间的内容
    # -----------------------------
    for idx, block in enumerate(data):
        if idx <= toc_idx:
            new_data.append(block)
            continue

        if toc_idx < idx < real_part_idx:
            changes.append(
                f"[rule_remove_toc_residual_items_before_compact_part]\n"
                f"page {block.get('page_idx','?')}\n"
                f"移除目录残留项: \"{block.get('text','').strip()}\"\n"
            )
            continue

        new_data.append(block)

    return new_data, changes

#过滤掉整行为“年份+Edition”的标题层级
def rule_remove_year_edition_heading(data):
    """
    规则：
    - 文本整行为 “年份 + Edition”（忽略大小写）
      例如：2020 Edition / 2018 edition.
    - 且存在 text_level
    → 删除标题层级（防止被误判为标题）
    """

    import re
    changes = []
    new_data = []

    year_edition_pattern = re.compile(
        r'^(19|20)\d{2}\s+edition\.?$',
        re.IGNORECASE
    )

    for block in data:
        text = block.get("text", "").strip()

        if "text_level" in block and year_edition_pattern.match(text):
            old = block.pop("text_level")
            changes.append(
                f"[rule_remove_year_edition_heading] "
                f"page {block.get('page_idx','?')}\n"
                f"移除年份版本标题: \"{text}\" "
                f"(原 text_level={old})\n"
            )

        new_data.append(block)

    return new_data, changes


def rule_remove_titles_ending_with_alphanum_hyphen(data: List[JsonBlock]) -> Tuple[List[JsonBlock], List[str]]:
    """
    删除标题层级，如果标题以 '数字+大写字母-数字' 结尾，例如 'Section 2 80A-1'。
    """
    import re
    changes = []
    new_data = []

    # 匹配以 数字+大写字母-数字 结尾
    pattern = re.compile(r'\d+[A-Z]-\d+$')

    for blk in data:
        text = blk.get("text", "").strip()
        if "text_level" in blk and pattern.search(text):
            old_level = blk.pop("text_level")
            changes.append(
                f"[rule_remove_titles_ending_with_alphanum_hyphen] page {blk.get('page_idx','?')}\n"
                f"标题以 '数字+大写字母-数字' 结尾，删除 text_level: \"{text}\" (原 text_level={old_level})"
            )
        new_data.append(blk)

    return new_data, changes


#过滤COMMISSION ÉLECTROTECHNIQUE INTERNATIONALE（国际电工委员会）这样的标题
def rule_remove_iec_full_title(data: List[dict]) -> Tuple[List[dict], List[str]]:
    """
    删除标题为 IEC 全称的层级，包括带或不带重音的 É
    """
    changes = []

    # 匹配 "COMMISSION ÉLECTROTECHNIQUE INTERNATIONALE" 或 "COMMISSION ELECTROTECHNIQUE INTERNATIONALE"
    # re.IGNORECASE 忽略大小写
    iec_title_pattern = re.compile(
        r'^COMMISSION\s+É?LECTROTECHNIQUE\s+INTERNATIONALE$',
        re.IGNORECASE
    )

    for block in data:
        text = block.get("text", "").strip()

        # 只处理已经被识别为标题的
        if "text_level" not in block:
            continue

        # 命中 IEC 全称标题
        if iec_title_pattern.match(text):
            old_level = block.pop("text_level")  # 删除标题层级
            changes.append(
                f"[rule_remove_iec_full_title] page {block.get('page_idx','?')}\n"
                f"IEC 全称去标题: \"{text}\"\n"
                f"→ 删除 text_level={old_level}\n"
            )

    return data, changes



def export_title_structure_to_folder(processed_data, input_file):
    """
    从最终处理后的 processed_data 中提取标题层级结构，
    并保存到 input_file 所在目录。
    """

    import os
    import json

    # 输出文件路径（与 input_file 同目录）
    folder = os.path.dirname(input_file)
    basename = os.path.basename(input_file)
    name, ext = os.path.splitext(basename)
    output_path = os.path.join(folder, f"mix_content.json")

    # 构建目录结构
    lines = []
    for block in processed_data:
        if "text_level" not in block:
            continue

        text = block.get("text", "").strip()
        level = block["text_level"]

        prefix = "=" * (level - 1)
        line = f"{prefix}{text}" if prefix else text
        lines.append(line)

    # 保存 JSON 文件
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(lines, f, ensure_ascii=False, indent=2)

    return output_path


if __name__ == "__main__":
    # 输入输出文件
    # input_file = r"IEC_60751-2022_original_content_list.json"
    input_file = r"NFPA_850-2020_original_content_list.json"
    # input_file = r"NFPA_80A-2022_original_content_list.json"
    # input_file = r"AASHTO-1993_original_content_list.json"(效果待优化)
    # input_file = r"NFPA_1141-2017_original_content_list.json"
    output_file = "j1_mix_EN.json"
    changes_file = "j1_change_EN.txt"
    # 读取输入 JSON
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    rules_list = [
        rule_smart_dotend_split,
        rule_numbered_heading_levels_en,

        rule_merge_split_appendix_titles_en,
        rule_appendix_headings_en,
        rule_appendix_subheadings_en,
        rule_split_appendix_numbered_title,

        rule_merge_pure_number_heading_with_text,

        rule_remove_cover_title_and_duplicates_en,
        rule_remove_headings_between_contents_and_foreword_en,
        rule_remove_titles_before_preface_or_contents_en,
        rule_rm_between,rule_rm_key, rule_rm_iso, rule_rm_iec_cei,
        rule_remove_table_titles_in_annex,
        rule_remove_where_heading_level,
        rule_remove_invalid_higher_level_between_same_level_titles,
        rule_remove_titles_ending_with_punctuation,
        rule_remove_content_headings,
        rule_remove_headings_after_last_appendix,
        rule_remove_numeric_measurement_titles_in_last_appendix,
        rule_remove_toc_residual_items_before_compact_part,
        rule_remove_year_edition_heading,

        rule_remove_iec_full_title,

        rule_remove_long_headings,

        rule_top_level_heading_en,

        rule_remove_titles_ending_with_alphanum_hyphen,




    ]
    # 应用规则
    processed_data, all_changes = apply_rules(data, rules_list)


    # 保存输出 JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=2)

    # 保存修改日志
    # 4️⃣ 合并日志（表格日志附加在普通日志后）
    with open(changes_file, "w", encoding="utf-8") as f:
        f.write("\n".join(all_changes))
        f.write("\n\n" + "=" * 80 + "\n")
        f.write("📊 以下为表格处理规则日志\n")
        f.write("=" * 80 + "\n\n")
        # f.write("\n".join(table_changes))
    print(f"处理完成，结果已保存到 {output_file}")
    print(f"修改日志已保存到 {changes_file}")
    export_title_structure_to_folder(processed_data, input_file)

