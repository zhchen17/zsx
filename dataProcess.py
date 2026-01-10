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
# 增加章节，按照text内容开头的序号进行识别， 3.2.2 就是三级标题
def rule_numbered_heading_levels(data: List[JsonBlock]) -> Tuple[List[JsonBlock], List[str]]:
    """
    规则1: 自动识别/校正数字开头的标题并赋予正确的 text_level (最多7级)
    """
    import re
    changes = []
    numbered_pattern = re.compile(r'^\d+(\.\d+)*\s*')  # 匹配数字编号，如 3 / 3.1 / 3.1.4

    for block in data:
        text = block.get("text", "").strip()
        if not text:
            continue

        # 判断是否符合标题模式
        m = numbered_pattern.match(text)
        if not m:
            continue

        # 过滤误判：数字后紧跟字母/右括号/标点/横杠
        remainder = text[m.end():].strip()
        if remainder and re.match(r'^[\),;:\-]', remainder):
            continue

        # 计算层级（小数点个数 + 1，最多7）
        num_part = m.group(0).strip()
        dot_count = num_part.count('.')
        level = min(dot_count + 1, 7)

        old_level = block.get("text_level")

        # 如果没有 text_level → 新增
        if old_level is None:
            block["text_level"] = level
            changes.append(
                f"[rule_numbered_heading_levels] page {block.get('page_idx', '?')}\n"
                f"修改: \"{text}\"\n"
                f"→ 加入 text_level={level}\n"
            )
        # 如果已有 text_level，但不等于计算结果 → 修正
        elif old_level != level:
            block["text_level"] = level
            changes.append(
                f"[rule_numbered_heading_levels] page {block.get('page_idx', '?')}\n"
                f"修改: \"{text}\"\n"
                f"→ 修正 text_level: {old_level} → {level}\n"
            )

    return data, changes
# 修复增加章节产生的bug，将目录错误识别为标题进行降级
def rule_remove_catalog_headings(data):
    """
    规则: 删除目录条目型标题（编号 + 标题 + 页码）
    条件：
    - text_level 存在（被误识别为标题）
    - 文本以数字开头
    - 文本以数字结尾
    - 中间包含至少一个汉字
    """
    import re
    changes = []
    new_data = []

    pattern = re.compile(r'^\d+(\.\d+)*.+\d+$')  # 形如 "5 标题内容 2" / "6.1 子标题 15"

    for block in data:
        if "text_level" in block:
            text = block.get("text", "").strip()

            # 满足编号开头+页码结尾模式，并且包含汉字
            if pattern.match(text) and re.search(r'[\u4e00-\u9fff]', text):
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_remove_catalog_headings] page {block.get('page_idx','?')}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 删除 text_level={old_level}，因检测为目录条目（编号+标题+页码）\n"
                )

        new_data.append(block)

    return new_data, changes
# 删减内容，分离 3.1沥青混合料回收料  reclaimed asphalt pavement (RAP)采用铣刨、开挖等方式从沥青路面上获得的旧沥青混合料。
# def rule_split_numbered_term_with_definition(data):
#     """
#     规则: 拆分 '编号+中文+英文+正文' 的字典
#     示例:
#       "3.8 自然对流 natural convection 由流体各部分温度不均匀造成的浮升力所引起的流体运动。"
#       → 标题: "3.8 自然对流 natural convection"
#         正文: "由流体各部分温度不均匀造成的浮升力所引起的流体运动。"
#     """
#     import re
#     changes = []
#     new_data = []
#
#     # 改进后的模式：数字和中文之间允许空格，中文和英文之间也允许空格
#     pattern = re.compile(
#         r"^(?P<num>\d+(?:\.\d+)*)\s*"
#         r"(?P<zh>[\u4e00-\u9fff]{1,8})\s*"
#         r"(?P<en>[A-Za-z][A-Za-z\s\-]*\)?)(?P<body>.*)$"
#     )
#
#     for block in data:
#         text = block.get("text", "").strip()
#         if not text:
#             new_data.append(block)
#             continue
#
#         # 必须以编号开头且以句号结尾
#         if not re.match(r"^\d", text) or not text.endswith("。"):
#             new_data.append(block)
#             continue
#
#         m = pattern.match(text)
#         if not m:
#             new_data.append(block)
#             continue
#
#         num = m.group("num")
#         zh = m.group("zh")
#         en = m.group("en").strip()
#         body = m.group("body").strip()
#
#         # 判断层级
#         level = min(num.count(".") + 1, 7)
#
#         # 标题部分（编号 + 中文 + 英文）
#         title_text = f"{num} {zh} {en}".strip()
#
#         # 新的标题块
#         title_block = dict(block)
#         title_block["text"] = title_text
#         title_block["text_level"] = level
#
#         new_data.append(title_block)
#
#         # 如果正文存在，生成正文块
#         if body:
#             body_block = {
#                 "type": "text",
#                 "text": body,
#                 "page_idx": block.get("page_idx", None)
#             }
#             new_data.append(body_block)
#
#         # 日志
#         changes.append(
#             f"[rule_split_numbered_term_with_definition] page {block.get('page_idx','?')}\n"
#             f"修改: \"{text}\"\n"
#             f"→ 拆分为标题: \"{title_text}\"\n"
#             f"  和正文: \"{body}\"\n"
#         )
#
#     return new_data, changes
# 先定位 '术语和定义',然后这个规则只适用于它和下一个同级标题之间的子标题
# def rule_split_term_definition(data):
#     """
#     规则2: 在“术语和定义”章节中，把子标题里夹带的正文切分出来
#     """
#     changes = []
#     new_data = []
#
#     def split_term_title_body(text: str):
#         """
#         切分子标题为 (标题部分, 正文部分)
#         1. 优先用括号作为切分点
#         2. 否则找最后一个连续英文串作为结尾
#         3. 否则不切分
#         """
#         # 1. 有括号缩写 → 以括号结尾为标题
#         m = re.match(r"^(.*?\([^)]+\))(.+)$", text)
#         if m:
#             return m.group(1).strip(), m.group(2).strip()
#
#         # 2. 找最后一个英文串作为标题结尾
#         m = re.match(r"^(.*?[A-Za-z]+)([\u4e00-\u9fff].*)$", text)
#         if m:
#             return m.group(1).strip(), m.group(2).strip()
#
#         # 3. 默认：无法切分
#         return text.strip(), ""
#
#     # 1. 找到“术语和定义”标题
#     term_start_idx = None
#     term_level = None
#     for i, block in enumerate(data):
#         if "text_level" in block and "术语和定义" in block.get("text", ""):
#             term_start_idx = i
#             term_level = block["text_level"]
#             break
#     if term_start_idx is None:
#         return data, changes
#
#     # 2. 找到结束位置
#     term_end_idx = len(data)
#     for j in range(term_start_idx + 1, len(data)):
#         block = data[j]
#         if "text_level" in block and block["text_level"] <= term_level:
#             term_end_idx = j
#             break
#
#     # 3. 遍历术语和定义范围
#     for idx, block in enumerate(data):
#         if idx <= term_start_idx or idx >= term_end_idx:
#             new_data.append(block)
#             continue
#
#         if "text_level" not in block or block["text_level"] <= term_level:
#             new_data.append(block)
#             continue
#
#         text = block.get("text", "").strip()
#         if not text:
#             new_data.append(block)
#             continue
#
#         # 切分
#         title_text, body_text = split_term_title_body(text)
#
#         if body_text:
#             # 标题
#             title_block = dict(block)
#             title_block["text"] = title_text
#             # 正文
#             body_block = {
#                 "type": "text",
#                 "text": body_text,
#                 "page_idx": block.get("page_idx", None)
#             }
#             new_data.append(title_block)
#             new_data.append(body_block)
#             # 日志
#             changes.append(
#                 f"[rule_split_term_definition] page {block.get('page_idx','?')}\n"
#                 f"修改: \"{text}\"\n"
#                 f"→ 拆分为标题: \"{title_text}\"\n"
#                 f"  和正文: \"{body_text}\"\n"
#             )
#         else:
#             new_data.append(block)
#
#     return new_data, changes
# 合并标题，如果标题以 第xx部分开头，并且上一个字典也是标题，那么就合并
def rule_merge_consecutive_part_titles(data):
    """
    规则: 合并主标题 + '第xx部分' 标题
    适用范围: 全文（不仅是前10个字典）
    条件:
      - 当前字典是标题，且以 '第xx部分' 开头
      - 上一个字典也是标题
    """
    import re
    changes = []
    new_data = []
    i = 0

    part_pattern = re.compile(r"^第\d+部分")

    while i < len(data):
        block = data[i]
        text = block.get("text", "").strip()

        if "text_level" in block and part_pattern.match(text) and new_data:
            prev_block = new_data[-1]
            if "text_level" in prev_block:
                # 合并标题
                merged_text = f"{prev_block.get('text','').strip()} {text}"
                prev_block["text"] = merged_text

                changes.append(
                    f"[rule_merge_consecutive_part_titles] page {block.get('page_idx','?')}\n"
                    f"合并: \"{prev_block.get('text','')}\" + \"{text}\"\n"
                    f"→ \"{merged_text}\"\n"
                )

                i += 1  # 跳过当前块
                continue

        # 默认保留
        new_data.append(block)
        i += 1

    return new_data, changes
# 删除标题，"2016- 01- 01实施" → 删除 text_level
def rule_remove_date_headings(data):
    """
    规则: 前10个字典中，删除日期类/纯数字分隔符型误判标题
    例如:
      "2016- 01- 01实施" → 删除 text_level
      "581- 21- 01" → 删除 text_level
    """
    import re
    changes = []
    new_data = []

    # 原本的日期匹配: 4位年-月-日 / 年月日 / ...
    date_pattern = re.compile(r"\d{4}\s*[-年./]\s*\d{1,2}\s*[-月./]\s*\d{1,2}")

    # 新增: 纯数字+横杠/斜杠分隔 (至少两段数字)
    numeric_dash_pattern = re.compile(r"^\s*\d+(?:\s*[-/]\s*\d+){1,}\s*$")

    for idx, block in enumerate(data):
        if idx < 10 and "text_level" in block:
            text = block.get("text", "").strip()
            if date_pattern.search(text) or numeric_dash_pattern.match(text):
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_remove_date_headings] page {block.get('page_idx','?')} idx {idx}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 删除 text_level={old_level} (日期/数字型误判标题)\n"
                )
        new_data.append(block)

    return new_data, changes
# 删除标题，先读取标题，以句号和冒号结尾的text，删除标题层级，该规则只对标题生效
def rule_remove_false_headings(data):
    """
    规则3: 删除错误识别的标题
    条件：text 以标点符号结尾的标题，降级为正文（删除 text_level）
          但如果以括号 ) 或 ） 结尾，则保留
    """
    import string
    changes = []
    new_data = []

    # 英文+中文标点集合
    punctuation = set(string.punctuation) | set("。？！，、；：‘’“”【】《》〈〉—…﹏")

    for block in data:
        if "text_level" in block:
            text = block.get("text", "").strip()
            if text:
                last_char = text[-1]
                if last_char in punctuation and last_char not in (")", "）"):
                    old_level = block.pop("text_level")
                    changes.append(
                        f"[rule_remove_false_headings] page {block.get('page_idx','?')}\n"
                        f"修改: \"{text}\"\n"
                        f"→ 删除 text_level={old_level}，降级为正文\n"
                    )
        new_data.append(block)

    return new_data, changes
# 删除标题，先读取标题，删除 带“地方标准标准”，“国家标准” 和 “发布”的，以及由纯字母加符号组成的，删除该标题
def rule_remove_front_misheadings(data):
    """
    规则4: 过滤前10个字典中的误判标题
    条件：
    1. 如果标题中包含 “标准” 或 “发布” → 删除 text_level
       （注意字间可能有空格，先去空格再判断）
    2. 如果标题不包含任何汉字（纯字母/符号/数字） → 删除 text_level
    """
    changes = []
    new_data = []

    for idx, block in enumerate(data):
        if idx >= 10:
            new_data.append(block)
            continue

        if "text_level" in block:
            text = block.get("text", "").strip()
            text_no_space = text.replace(" ", "")

            # 条件1: 包含“标准”或“发布”
            if any(keyword in text_no_space for keyword in ["国家标准", "地方标准","方标准","发布"]):
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_remove_front_misheadings] page {block.get('page_idx','?')} idx {idx}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 删除 text_level={old_level}，因包含 '标准' 或 '发布'\n"
                )
                new_data.append(block)
                continue

            # 条件2: 没有汉字
            if not re.search(r'[\u4e00-\u9fff]', text_no_space):
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_remove_front_misheadings] page {block.get('page_idx','?')} idx {idx}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 删除 text_level={old_level}，因不含汉字（纯字母/符号）\n"
                )
                new_data.append(block)
                continue

        new_data.append(block)

    return new_data, changes
# 删除标题，先读取标题，删除以 “表”和“图”
def rule_downgrade_table_figure_headings(data):
    """
    规则: 将图表标题降级为正文
    条件：text 以“表”或“图”开头，并且是标题（有 text_level）
    """
    changes = []
    new_data = []

    for block in data:
        if "text_level" in block:
            text = block.get("text", "").strip()
            if text.startswith(("表", "图")):
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_downgrade_table_figure_headings] page {block.get('page_idx','?')}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 删除 text_level={old_level}，降级为正文\n"
                )
        new_data.append(block)

    return new_data, changes
# 增加标题，'附录 + 字母 + 文字' 视为一级标题
def rule_appendix_headings(data):
    """
    规则: '附录 + 字母 + 文字' 视为一级标题
    例如: '附 录 A（规范性）分离材料...' → 一级标题
    """
    import re
    changes = []
    new_data = []

    pattern = re.compile(r'^附\s*录\s*[A-Z]{1,2}.*')

    for block in data:
        text = block.get("text", "").strip()
        if not text:
            new_data.append(block)
            continue

        if pattern.match(text):
            old_level = block.get("text_level")
            block["text_level"] = 1
            if old_level != 1:  # 只在修改时记录日志
                changes.append(
                    f"[rule_appendix_headings] page {block.get('page_idx','?')}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 设置 text_level=1 (原: {old_level})\n"
                )

        new_data.append(block)

    return new_data, changes
# 增加标题，附录 （规范性） 附录标题在不同的行，进行合并
def rule_merge_split_appendix_titles(data):
    """
    规则: 合并被 OCR 错分的附录标题
    拼接逻辑:
    1. '附录A' + 'xxx' → 合并
    2. '附录A' + '（说明）' + 'xxx' → 合并
    如果第二条不是括号形式，就只合并两条，不继续向后拼
    """
    import re
    changes = []
    new_data = []
    i = 0

    def safe_concat(a, b):
        """拼接两段文字，中间智能加空格"""
        if not a:
            return b
        if not b:
            return a
        if a.endswith(" ") or b.startswith(" "):
            return a + b
        return a + " " + b

    while i < len(data):
        block = data[i]
        text = block.get("text", "").strip()

        # 匹配 "附录 + 字母" 起点
        if re.match(r"^附\s*录\s*[A-Z]{1,2}$", text):
            merged_text = text
            j = i + 1

            if j < len(data):
                next_text = data[j].get("text", "").strip()
                if next_text:
                    merged_text = safe_concat(merged_text, next_text)
                    j += 1

                    # 只有当第二条是括号形式时才继续看第三条
                    if j < len(data):
                        next2_text = data[j].get("text", "").strip()
                        if re.match(r"^[（(][^）)]+[）)]$", next_text) and next2_text:
                            merged_text = safe_concat(merged_text, next2_text)
                            j += 1

            new_block = dict(block)
            new_block["text"] = merged_text
            new_block["text_level"] = 1
            new_data.append(new_block)

            changes.append(
                f"[rule_merge_split_appendix_titles] page {block.get('page_idx','?')}\n"
                f"合并附录标题: \"{text}\" → \"{merged_text}\"\n"
            )

            i = j
            continue

        # 匹配 "附录A（规范性）" 起点
        if re.match(r"^附\s*录\s*[A-Z]{1,2}\s*（[^）]+）$", text):
            merged_text = text
            j = i + 1
            if j < len(data):
                next_text = data[j].get("text", "").strip()
                if next_text:
                    merged_text = safe_concat(merged_text, next_text)
                    j += 1

            new_block = dict(block)
            new_block["text"] = merged_text
            new_block["text_level"] = 1
            new_data.append(new_block)

            changes.append(
                f"[rule_merge_split_appendix_titles] page {block.get('page_idx','?')}\n"
                f"合并附录标题: \"{text}\" → \"{merged_text}\"\n"
            )

            i = j
            continue

        # 默认保持原样
        new_data.append(block)
        i += 1

    return new_data, changes
def rule_appendix_subheadings(data):
    """
    规则: 处理附录中的子标题
    1. 字母编号 (A.1 / A.1.2 / AA.1.2.3) → 转为标题
       层级 = 小数点个数 + 1 (最多7级)
       若结尾为句号/逗号/冒号 → 降级为正文
    2. 中文数字 (一、 二、 三、) → 一级标题
    3. 仅在附录标题之后生效（每个附录标题都会触发）
    """
    import re
    changes = []
    new_data = []

    # 正则模式
    letter_num_pattern = re.compile(r"^([A-Z]{1,2}(?:\.\d+)+)\s*")  # A.1 / A.1.2 / AA.1.2.3
    chinese_num_pattern = re.compile(r"^(一|二|三|四|五|六|七|八|九|十)[、.]")

    appendix_active = False  # 是否进入附录区域

    for block in data:
        text = block.get("text", "").strip()

        # 检测附录标题
        if "附录" in text:
            appendix_active = True
            new_data.append(block)
            continue

        if not appendix_active:
            new_data.append(block)
            continue

        # -------- 1. 字母编号标题 --------
        m = letter_num_pattern.match(text)
        if m:
            # 检查结尾是否是句号/逗号/冒号
            if text.endswith(("。", "，", ":", "：", ".")):
                if "text_level" in block:
                    old_level = block.pop("text_level")
                    changes.append(
                        f"[rule_appendix_subheadings] page {block.get('page_idx','?')}\n"
                        f"修改: \"{text}\"\n"
                        f"→ 删除 text_level={old_level} (因结尾符号)\n"
                    )
            else:
                # 计算层级
                num_part = m.group(1)
                dot_count = num_part.count(".")
                level = min(dot_count + 1, 7)
                old_level = block.get("text_level")
                block["text_level"] = level
                if old_level != level:
                    changes.append(
                        f"[rule_appendix_subheadings] page {block.get('page_idx','?')}\n"
                        f"修改: \"{text}\"\n"
                        f"→ 设置 text_level={level} (原: {old_level})\n"
                    )
            new_data.append(block)
            continue

        # -------- 2. 中文数字标题 --------
        if chinese_num_pattern.match(text):
            old_level = block.get("text_level")
            block["text_level"] = 1
            if old_level != 1:
                changes.append(
                    f"[rule_appendix_subheadings] page {block.get('page_idx','?')}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 设置 text_level=1 (原: {old_level})\n"
                )
            new_data.append(block)
            continue

        # -------- 默认 --------
        new_data.append(block)

    return new_data, changes

# 标题合并，标题只有 术语和定义部分，标题为3.1  内容在下一行，合并
# def rule_merge_number_only_headings(data):
#     """
#     规则: 如果一个标题只有序号 (如 '3.1')，则与下一行合并
#     条件:
#       - 当前块是标题，且 text 只包含编号
#       - 下一块存在，且 text 不是以句号/逗号/冒号/顿号结尾
#     """
#     import re
#     changes = []
#     new_data = []
#     i = 0
#
#     number_only_pattern = re.compile(r"^\d+(\.\d+)*$")
#
#     while i < len(data):
#         block = data[i]
#         text = block.get("text", "").strip()
#
#         if "text_level" in block and number_only_pattern.match(text):
#             if i + 1 < len(data):
#                 next_block = data[i + 1]
#                 next_text = next_block.get("text", "").strip()
#                 if next_text and not next_text.endswith(("。", "，", ":", "：", "、")):
#                     merged_text = f"{text} {next_text}"
#                     new_block = dict(block)
#                     new_block["text"] = merged_text
#                     new_data.append(new_block)
#
#                     changes.append(
#                         f"[rule_merge_number_only_headings] page {block.get('page_idx','?')}\n"
#                         f"合并: \"{text}\" + \"{next_text}\"\n"
#                         f"→ \"{merged_text}\"\n"
#                     )
#
#                     i += 2  # 跳过下一个块
#                     continue
#
#         new_data.append(block)
#         i += 1
#
#     return new_data, changes
# 增加标题，特殊文件，术语和定义章节  583-14-25  下一行  有效电压   合并成三级标题
def rule_merge_special_numbered_terms(data):
    """
    规则: 在 '术语和定义' 章节内，处理形如 '数字-数字-数字' 的特殊编号标题
    - 横杠数量+1 = 层级 (最多7)
    - 合并后续1~2个字典的内容作为标题正文
    """
    import re
    changes = []
    new_data = []

    # 匹配类似 123-45-67 的编号
    special_num_pattern = re.compile(r"^\d+(?:-\d+){0,6}$")

    # 检测进入 "术语和定义" 范围
    in_terms = False

    i = 0
    while i < len(data):
        block = data[i]
        text = block.get("text", "").strip()

        # 遇到 "术语和定义" → 开启规则
        if "text_level" in block and "术语和定义" in text:
            in_terms = True
            new_data.append(block)
            i += 1
            continue

        # 未进入术语和定义 → 原样保留
        if not in_terms:
            new_data.append(block)
            i += 1
            continue

        # 术语和定义内，检查是否是特殊编号
        if special_num_pattern.match(text):
            dash_count = text.count("-")
            level = min(dash_count + 1, 7)

            # 合并后续字典内容
            merged_text = text
            j = i + 1
            merge_blocks = []

            if j < len(data):
                merged_text += " " + data[j].get("text", "").strip()
                merge_blocks.append(data[j])
                j += 1

                # 如果再下一个是标题，且不是数字开头 → 继续合并
                if j < len(data):
                    next_text = data[j].get("text", "").strip()
                    if "text_level" in data[j] and not re.match(r"^\d", next_text):
                        merged_text += " " + next_text
                        merge_blocks.append(data[j])
                        j += 1

            # 构建新标题
            new_block = dict(block)
            new_block["text"] = merged_text
            new_block["text_level"] = level
            new_data.append(new_block)

            # 日志
            changes.append(
                f"[rule_merge_special_numbered_terms] page {block.get('page_idx','?')}\n"
                f"合并特殊编号: \"{text}\" → \"{merged_text}\" (text_level={level})\n"
            )

            i = j  # 跳过合并过的块
            continue

        # 默认情况
        new_data.append(block)
        i += 1

    return new_data, changes
# 删除标题，删除术语下面  纯数字的标题 例如 3.2
def rule_remove_pure_number_headings(data):
    """
    规则: 删除纯数字序号型标题
    条件：
      - 块有 text_level
      - text 完全匹配 "数字.数字.数字" 格式
    操作：
      - 删除 text_level，降级为正文
    """
    import re
    changes = []
    new_data = []

    number_only_pattern = re.compile(r"^\d+(?:\.\d+)*$")

    for block in data:
        if "text_level" in block:
            text = block.get("text", "").strip()
            if number_only_pattern.match(text):
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_remove_pure_number_headings] page {block.get('page_idx','?')}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 删除 text_level={old_level} (纯数字标题降级为正文)\n"
                )
        new_data.append(block)

    return new_data, changes
# 删除标题，删除超过30个字的标题
def rule_remove_long_headings(data):
    """
    规则: 删除过长的标题 (text > 30)
    """
    changes = []
    new_data = []

    for block in data:
        if "text_level" in block:
            text = block.get("text", "").strip()
            if len(text) > 45:
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_remove_long_headings] page {block.get('page_idx','?')}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 删除 text_level={old_level}，因标题长度超过30\n"
                )
        new_data.append(block)

    return new_data, changes
# 删除标题， 术语分行后的一些内容，被单独识别为了标题  例如 电网企业 power grid enterprise
def rule_remove_split_number_titles(data):
    """
    规则: 删除被错误拆开的标题（上一行是纯序号，当前行是文字）
    """
    import re
    changes = []
    new_data = []

    number_only_pattern = re.compile(r'^\d+(\.\d+)*$')  # 匹配纯序号，如 3.1 或 3.1.14

    for i, block in enumerate(data):
        if "text_level" not in block:
            new_data.append(block)
            continue

        text = block.get("text", "").strip()

        # 当前标题不是数字开头
        if not re.match(r'^\d', text):
            if i > 0:
                prev_text = data[i - 1].get("text", "").strip()
                # 如果上一行是纯序号
                if number_only_pattern.match(prev_text):
                    old_level = block.pop("text_level")
                    changes.append(
                        f"[rule_remove_split_number_titles] page {block.get('page_idx','?')}\n"
                        f"修改: \"{text}\" (上一行为序号: \"{prev_text}\")\n"
                        f"→ 删除 text_level={old_level}，降级为正文\n"
                    )

        new_data.append(block)

    return new_data, changes
# 删除标题，先读取所有标题，删除由纯公式组成的标题
def rule_remove_formula_headings(data):
    """
    规则: 删除公式型标题（OCR 误识别公式为标题）
    条件：
    - 有 text_level
    - 文本中不包含汉字
    - 文本中包含公式常见符号或 LaTeX 公式结构
    """
    import re
    changes = []
    new_data = []

    formula_pattern = re.compile(r'[=+\-*/^√πΣ∑∫≤≥≈≠{}$\\]')

    for block in data:
        if "text_level" in block:
            text = block.get("text", "").strip()

            # 条件1: 不含汉字
            if re.search(r'[\u4e00-\u9fff]', text):
                new_data.append(block)
                continue

            # 条件2: 含公式符号
            if formula_pattern.search(text):
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_remove_formula_headings] page {block.get('page_idx','?')}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 删除 text_level={old_level}，因检测为公式型标题\n"
                )

        new_data.append(block)

    return new_data, changes
# 删除标题,"印刷", "出版", "初版", "发行"
def rule_remove_date_headings(data):
    """
    规则: 删除出版/印刷类伪标题
    条件：
    - 有 text_level（被识别为标题）
    - 文本包含 '年' 和 '月'（疑似出版时间）
      或包含 '印刷' / '出版' / '初版' / '发行'
    """
    import re
    changes = []
    new_data = []

    keywords = ["印刷", "出版", "初版", "发行"]

    for block in data:
        if "text_level" not in block:
            new_data.append(block)
            continue

        text = block.get("text", "").strip()

        # 条件1: 包含年月
        has_date = ("年" in text and "月" in text)

        # 条件2: 包含关键字
        has_keyword = any(k in text for k in keywords)

        if has_date or has_keyword:
            old_level = block.pop("text_level")
            changes.append(
                f"[rule_remove_date_headings] page {block.get('page_idx','?')}\n"
                f"修改: \"{text}\"\n"
                f"→ 删除 text_level={old_level}，因检测为出版/印刷信息\n"
            )

        new_data.append(block)

    return new_data, changes
# 删除标题，有些内容在表格中，但是没有识别出这是一个标题，仅根据特殊字样“质量评价报告”删除
def rule_remove_quality_report_headings(data):
    """
    规则: 删除带有“质量评价报告”的标题（降级为正文）
    """
    changes = []
    new_data = []

    for block in data:
        if "text_level" in block:
            text = block.get("text", "").strip()
            if "质量评价报告" in text:
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_remove_quality_report_headings] page {block.get('page_idx','?')}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 删除 text_level={old_level}，因包含 '质量评价报告'\n"
                )
        new_data.append(block)

    return new_data, changes
# 删除标题，a) 等  字母加括号开头的标题删除
def rule_remove_letter_parenthesis_headings(data):
    """
    规则: 删除以字母+括号开头的标题（如 a) / A) / a）/ A））
    适配半角 () 和全角 （）
    """
    import re
    changes = []
    new_data = []

    # 匹配：字母 + 半角/全角右括号
    pattern = re.compile(r'^[A-Za-z][\)\）]')

    for block in data:
        if "text_level" in block:
            text = block.get("text", "").strip()
            if pattern.match(text):
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_remove_letter_parenthesis_headings] page {block.get('page_idx','?')}\n"
                    f"修改: \"{text}\"\n"
                    f"→ 删除 text_level={old_level}，因开头是字母+括号（列表项误判为标题）\n"
                )
        new_data.append(block)

    return new_data, changes
# 删除标题，将“参考文献”作为最后一个标题，删除此后所有的标题
def rule_references_as_last_heading(data):
    """
    规则: '参考文献' 作为最后一个标题
    1. 如果某个块内容是 '参考文献'，设置为一级标题
    2. 删除它之后所有块的 text_level
    """
    changes = []
    new_data = []
    found = False

    for i, block in enumerate(data):
        text = block.get("text", "").strip().replace(" ", "")

        if not found and text == "参考文献":
            old_level = block.get("text_level")
            block["text_level"] = 1
            new_data.append(block)
            changes.append(
                f"[rule_references_as_last_heading] page {block.get('page_idx','?')}\n"
                f"修改: \"参考文献\"\n"
                f"→ 设置为 text_level=1 (原: {old_level})，并清除其后的所有标题\n"
            )
            found = True
            continue

        if found:
            if "text_level" in block:
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_references_as_last_heading] page {block.get('page_idx','?')}\n"
                    f"修改: \"{block.get('text','')}\"\n"
                    f"→ 删除 text_level={old_level} (参考文献之后)\n"
                )

        new_data.append(block)

    return new_data, changes
# 删除标题，将"目次"的下一个标题删除
def rule_downgrade_heading_after_contents(data):
    """
    规则: 如果当前标题是“目次”，则取消它后面紧跟的下一个标题的 text_level。
    用于去掉目录页的伪标题。
    """
    changes = []
    new_data = []

    for i, block in enumerate(data):
        new_data.append(block)

        # 检查当前是否为“目次”标题
        if "text_level" in block and block.get("text", "").strip() == "目次":
            # 检查下一条
            if i + 1 < len(data):
                next_block = data[i + 1]
                if "text_level" in next_block:
                    old_level = next_block.pop("text_level")
                    changes.append(
                        f"[rule_downgrade_heading_after_contents] page {next_block.get('page_idx','?')}\n"
                        f"修改: \"{next_block.get('text','').strip()}\"\n"
                        f"→ 删除 text_level={old_level}，因位于“目次”之后（目录页内容）\n"
                    )

    return new_data, changes
# 删除标题，判断最一页是否为出版信息页，如果是，删除所有标题
def rule_remove_cover_title_and_duplicates(data):
    """
    规则: 如果第0页是封面页（包含“国家标准”“实施”“发布”），
          则删除该页所有标题，并在“前言”后的两个标题字典中，
          若标题与首页标题相同，也删除。
    """
    changes = []
    new_data = []

    # === 第0页文本检测：判断是否为封面页 ===
    cover_keywords = ["国家标准", "实施", "发布"]
    page0_text = " ".join(block.get("text", "") for block in data if block.get("page_idx") == 0)
    is_cover_page = any(keyword in page0_text for keyword in cover_keywords)

    if not is_cover_page:
        changes.append("[rule_remove_cover_title_and_duplicates] 未检测到封面关键词（跳过首页处理）")
        return data, changes  # 直接返回原数据

    # === 第1步：记录封面页标题 ===
    cover_titles = []
    for block in data:
        if block.get("page_idx") == 0 and "text_level" in block:
            title_text = block.get("text", "").strip()
            cover_titles.append(title_text)
            old_level = block.pop("text_level")
            changes.append(
                f"[rule_remove_cover_title_and_duplicates] page {block.get('page_idx','?')}\n"
                f"删除封面标题: \"{title_text}\" (text_level={old_level})，封面检测通过\n"
            )

    # === 第2步：查找“前言”标题索引 ===
    preface_index = None
    for i, block in enumerate(data):
        if "text_level" in block and block.get("text", "").strip().startswith("前言"):
            preface_index = i
            break

    # === 第3步：在“前言”后的两个标题字典中查找重复文件名 ===
    if preface_index is not None and cover_titles:
        title_count = 0
        j = preface_index + 1

        while j < len(data) and title_count < 2:
            block = data[j]
            if "text_level" in block:
                title_count += 1
                text = block.get("text", "").strip()

                if text in cover_titles:
                    old_level = block.pop("text_level")
                    changes.append(
                        f"[rule_remove_cover_title_and_duplicates] page {block.get('page_idx','?')}\n"
                        f"删除重复文件名标题: \"{text}\" (text_level={old_level})，因与封面标题相同\n"
                    )
            j += 1

    # === 第4步：输出结果 ===
    new_data = list(data)  # 返回原列表（内部已修改）

    return new_data, changes
#删除首页的所有标题，并记录标题名称，在'前言'后查找有没有相同的标题，实际就是查找文件名称
def rule_remove_cover_title_and_duplicates(data):
    """
    规则:
    1. 如果第0页检测为封面页（包含“国家标准”“实施”“发布”），
       删除该页所有标题（一般是文件名）。
    2. 在“前言”后的两个标题字典中，若标题与首页标题相同（忽略空格与全角差异），
       也删除。
    """

    changes = []
    new_data = []

    # === 工具函数：标准化标题，用于比较 ===
    def normalize_title(s):
        """去除空格、全角空格、统一全角冒号"""
        return s.replace(" ", "").replace("　", "").replace("：", ":").strip()

    # === 第0页文本检测：判断是否为封面页 ===
    cover_keywords = ["国家标准", "实施", "发布","地方标准"]
    page0_text = " ".join(block.get("text", "") for block in data if block.get("page_idx") == 0)
    is_cover_page = any(keyword in page0_text for keyword in cover_keywords)

    if not is_cover_page:
        changes.append("[rule_remove_cover_title_and_duplicates] 未检测到封面关键词（跳过首页处理）")
        return data, changes  # 直接返回原数据

    # === 第1步：记录封面页标题 ===
    cover_titles = []
    for block in data:
        if block.get("page_idx") == 0 and "text_level" in block:
            title_text = block.get("text", "").strip()
            cover_titles.append(title_text)
            old_level = block.pop("text_level")
            changes.append(
                f"[rule_remove_cover_title_and_duplicates] page {block.get('page_idx','?')}\n"
                f"删除封面标题: \"{title_text}\" (text_level={old_level})，封面检测通过\n"
            )

    # === 第2步：查找“前言”标题索引 ===
    preface_index = None
    for i, block in enumerate(data):
        if "text_level" in block and block.get("text", "").strip().startswith("前言"):
            preface_index = i
            break

    # === 第3步：在“前言”后的两个标题字典中查找重复文件名 ===
    if preface_index is not None and cover_titles:
        title_count = 0  # 记录已扫描到的标题数
        j = preface_index + 1

        while j < len(data) and title_count < 2:
            block = data[j]
            if "text_level" in block:
                title_count += 1  # 计入标题
                text = block.get("text", "").strip()

                # 标准化比较（忽略空格、全角符号差异）
                if any(normalize_title(text) == normalize_title(title) for title in cover_titles):
                    old_level = block.pop("text_level")
                    changes.append(
                        f"[rule_remove_cover_title_and_duplicates] page {block.get('page_idx','?')}\n"
                        f"删除重复文件名标题: \"{text}\" (text_level={old_level})，因与封面标题相同（忽略空格差异）\n"
                    )
            j += 1

    # === 第4步：输出结果 ===
    new_data = list(data)
    return new_data, changes
# 前言和目次之前，不允许出现标题。
def rule_remove_headings_between_contents_and_preface(data):
    """
    规则: 在“目次”与“前言”之间不允许出现其他标题。
    若存在标题，则删除其 text_level。
    """
    changes = []
    new_data = []

    # === 第1步：查找“目次”或“目录”与“前言”的索引 ===
    contents_index = None
    preface_index = None

    for i, block in enumerate(data):
        if "text_level" in block:
            text = block.get("text", "").strip()
            if contents_index is None and (text == "目次" or text == "目录"):
                contents_index = i
            elif preface_index is None and text.startswith("前言"):
                preface_index = i

    # 如果没有“目次”或没有“前言”，则不处理
    if contents_index is None or preface_index is None or preface_index <= contents_index:
        return data, changes

    # === 第2步：删除两者之间的标题层级 ===
    for j in range(contents_index + 1, preface_index):
        block = data[j]
        if "text_level" in block:
            old_level = block.pop("text_level")
            text = block.get("text", "").strip()
            changes.append(
                f"[rule_remove_headings_between_contents_and_preface] page {block.get('page_idx','?')}\n"
                f"修改: \"{text}\"\n"
                f"→ 删除 text_level={old_level}，因位于“目次”和“前言”之间\n"
            )

    # === 第3步：返回结果 ===
    new_data = list(data)
    return new_data, changes

# 删除目次和范围中间，出了前言以外的所有标题
def rule_clean_titles_between_contents_and_scope3(data):
    """
    规则: 读取“目次”后的3个标题，
    若其中包含“范围”，则删除“目次”和“范围”之间的标题（非前言）
    """
    import re
    changes = []
    new_data = []

    # === 找到“目次”或“目录”标题索引 ===
    contents_index = None
    for i, block in enumerate(data):
        if "text_level" in block:
            text = block.get("text", "").strip()
            if text in ("目次", "目录"):
                contents_index = i
                break

    if contents_index is None:
        return data, changes  # 没找到“目次”不处理

    # === 收集“目次”后的3个标题 ===
    next_titles = []
    j = contents_index + 1
    while j < len(data) and len(next_titles) < 5:
        block = data[j]
        if "text_level" in block:
            title_text = re.sub(r"\s+", "", block.get("text", ""))  # 去空格匹配
            next_titles.append((j, title_text))
        j += 1

    if not next_titles:
        return data, changes

    # === 查找是否有包含“范围”的标题 ===
    scope_index = None
    for idx, title in next_titles:
        if "范围" in title:
            scope_index = idx
            break

    if scope_index is None:
        return data, changes  # 没找到“范围”不处理

    # === 删除“目次”和“范围”之间的非前言标题 ===
    for idx, title in next_titles:
        if contents_index < idx < scope_index:
            if any(k in title for k in ["前言", "引言"]):
                continue  # 前言、引言保留
            block = data[idx]
            if "text_level" in block:
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_clean_titles_between_contents_and_scope3] page {block.get('page_idx','?')}\n"
                    f"修改: \"{block.get('text','').strip()}\"\n"
                    f"→ 删除 text_level={old_level}，因位于“目次”和“范围”之间且非前言\n"
                )

    new_data = list(data)
    return new_data, changes

# 删除标题，删除正文里的附录
def rule_remove_appendix_before_numbered_headings(data):
    """
    规则: 删除那些后面紧跟数字标题的“附录”开头标题（疑似误识别的正文）
    - 遍历所有以“附录”开头的标题
    - 读取其后最多3个标题
    - 若发现后续标题以数字开头，则删除当前“附录”标题的text_level
    """
    import re
    changes = []
    new_data = []

    appendix_pattern = re.compile(r"^附\s*录")   # 匹配“附录”或“附 录”
    number_pattern = re.compile(r"^\d")          # 匹配以数字开头的标题

    # === 找出所有“附录”开头的标题索引 ===
    appendix_indices = []
    for i, block in enumerate(data):
        if "text_level" in block:
            text = block.get("text", "").strip()
            if appendix_pattern.match(text):
                appendix_indices.append(i)

    # === 遍历每个“附录”标题 ===
    for idx in appendix_indices:
        # 向后查看最多3个标题
        lookahead = 0
        j = idx + 1
        should_delete = False

        while j < len(data) and lookahead < 3:
            next_block = data[j]
            if "text_level" in next_block:
                next_text = next_block.get("text", "").strip()
                # 如果后面出现以数字开头的标题 → 删除当前附录
                if number_pattern.match(next_text):
                    should_delete = True
                    break
                lookahead += 1
            j += 1

        # 删除当前附录标题
        if should_delete:
            block = data[idx]
            if "text_level" in block:
                old_level = block.pop("text_level")
                changes.append(
                    f"[rule_remove_appendix_before_numbered_headings] page {block.get('page_idx','?')}\n"
                    f"修改: \"{block.get('text','').strip()}\"\n"
                    f"→ 删除 text_level={old_level}，因其后出现数字开头标题（疑似误识别的附录）\n"
                )

    new_data = list(data)
    return new_data, changes
# 删除标题，附录表格中的一二三四
def rule_remove_orphan_numbered_headings(data):
    """
    规则: 删除与表格无关的“一 二 三 四 ... 七”开头的标题
    逻辑:
    1. 读取所有标题。
    2. 当检测到 "一" 时，向后收集连续的 "二三四..." 标题（直到不连续或到七为止）。
    3. 检查 "一" 的上一个标题是否为 "表" 开头。
       - 如果不是 "表" → 删除这一组连续的序号标题。
    """
    import re
    changes = []
    new_data = []

    # 匹配中文数字序号开头标题
    num_titles = ["一", "二", "三", "四", "五", "六", "七"]
    num_pattern = re.compile(r"^(" + "|".join(num_titles) + r")[、\.\s．].*")
    table_pattern = re.compile(r"^表[\sA-Z0-9．\.\-]*")

    i = 0
    while i < len(data):
        block = data[i]
        text = block.get("text", "").strip()

        # 如果是“一”开头标题
        if "text_level" in block and text.startswith("一"):
            seq_indices = [i]  # 存放连续序号标题的索引
            current_idx = num_titles.index("一")

            # 向后收集连续的序号标题
            j = i + 1
            while j < len(data):
                next_block = data[j]
                if "text_level" not in next_block:
                    j += 1
                    continue
                next_text = next_block.get("text", "").strip()

                # 检查是否是下一序号
                if current_idx + 1 < len(num_titles) and next_text.startswith(num_titles[current_idx + 1]):
                    seq_indices.append(j)
                    current_idx += 1
                    j += 1
                else:
                    break

            # 检查“一”的上一个标题
            prev_is_table = False
            if i > 0:
                prev_block = data[i - 1]
                prev_text = prev_block.get("text", "").strip()
                if table_pattern.match(prev_text):
                    prev_is_table = True

            # 如果上一个标题不是表 → 删除这些序号标题
            if not prev_is_table:
                for idx in seq_indices:
                    b = data[idx]
                    if "text_level" in b:
                        old_level = b.pop("text_level")
                        changes.append(
                            f"[rule_remove_orphan_numbered_headings] page {b.get('page_idx','?')}\n"
                            f"修改: \"{b.get('text','').strip()}\"\n"
                            f"→ 删除 text_level={old_level}，因与表无关的序号标题组（从“一”开始）\n"
                        )

            # 移动到下一段
            i = j
        else:
            i += 1

    new_data = list(data)
    return new_data, changes




# 表格合并
# def rule_merge_crosspage_tables(data):
#     """
#     规则: 合并跨页表格
#     条件:
#     - 当前表格的 table_caption 含有 "续"
#     - 上一个 block 也是表格
#     操作:
#     - 将续表的行合并到上一张表格
#     - 删除续表中的重复表头行
#     - 续表本身不再保留
#     """
#     from bs4 import BeautifulSoup
#
#     changes = []
#     new_data = []
#     last_table = None
#
#     for idx, block in enumerate(data):
#         if block["type"] == "table":
#             caption = "".join(block.get("table_caption", []))
#
#             # 条件: caption 含有 "续" 且上一个 block 是表格
#             if "续" in caption and new_data and new_data[-1]["type"] == "table":
#                 last_table = new_data[-1]  # 上一个表格
#
#                 # 解析 HTML
#                 last_soup = BeautifulSoup(last_table["table_body"], "html.parser")
#                 curr_soup = BeautifulSoup(block["table_body"], "html.parser")
#
#                 # 去掉续表里的表头
#                 curr_rows = curr_soup.find_all("tr")
#                 if curr_rows and "序号" in curr_rows[0].get_text():
#                     curr_rows = curr_rows[1:]
#
#                 # 合并行
#                 for row in curr_rows:
#                     last_soup.table.append(row)
#
#                 # 更新上一张表格
#                 old_html_len = len(last_table["table_body"])
#                 last_table["table_body"] = str(last_soup)
#
#                 changes.append(
#                     f"[rule_merge_crosspage_tables] page {block.get('page_idx','?')}\n"
#                     f"合并: {caption} → 合并到上一表格\n"
#                     f"修改: 表格 HTML 长度 {old_html_len} → {len(last_table['table_body'])}\n"
#                 )
#
#                 # 不保留当前表格
#                 continue
#
#         # 默认保留
#         new_data.append(block)
#
#     return new_data, changes
def rule_merge_crosspage_tables(data):
    """
    规则: 合并跨页表格
    条件:
    - 当前表格的 table_caption 含有 "续"
    - 上一个 block 也是表格，且二者都含 table_body
    操作:
    - 将续表的行合并到上一张表格
    - 删除续表中的重复表头行
    - 续表本身不再保留
    """
    from bs4 import BeautifulSoup

    changes = []
    new_data = []

    for idx, block in enumerate(data):
        if block.get("type") == "table":
            caption = "".join(block.get("table_caption", []))

            # 条件: caption 含 "续" 且上一个 block 是表格
            if "续" in caption and new_data and new_data[-1].get("type") == "table":
                last_table = new_data[-1]

                # 安全检查：两个表格必须都有 table_body
                if "table_body" not in block or "table_body" not in last_table:
                    changes.append(
                        f"[rule_merge_crosspage_tables] page {block.get('page_idx','?')}\n"
                        f"跳过: {caption} → 缺少 table_body 字段，无法合并\n"
                    )
                    # 当前表格保留，避免数据丢失
                    new_data.append(block)
                    continue

                # 解析 HTML
                last_soup = BeautifulSoup(last_table["table_body"], "html.parser")
                curr_soup = BeautifulSoup(block["table_body"], "html.parser")

                # 去掉续表里的表头
                curr_rows = curr_soup.find_all("tr")
                if curr_rows and "序号" in curr_rows[0].get_text():
                    curr_rows = curr_rows[1:]

                # 合并行
                for row in curr_rows:
                    last_soup.table.append(row)

                # 更新上一张表格内容
                old_html_len = len(last_table["table_body"])
                last_table["table_body"] = str(last_soup)

                changes.append(
                    f"[rule_merge_crosspage_tables] page {block.get('page_idx','?')}\n"
                    f"合并: {caption} → 合并到上一表格\n"
                    f"修改: 表格 HTML 长度 {old_html_len} → {len(last_table['table_body'])}\n"
                )

                # 不保留当前表格
                continue

        # 默认保留
        new_data.append(block)

    return new_data, changes

# 表头去重
def rule_remove_duplicate_table_headers(data):
    """
    规则: 遍历所有表格，去掉 table_body 中重复的表头行。
    逻辑:
    - 找出所有 type == 'table' 且包含 table_body 的字典；
    - 解析 HTML；
    - 删除重复表头（同内容的行）；
    - 更新 table_body。
    """
    from bs4 import BeautifulSoup
    changes = []
    new_data = []

    def row_text(row):
        """提取行的纯文本内容，去除空格后连接"""
        return " | ".join([cell.get_text(strip=True) for cell in row.find_all(["td", "th"])])

    for block in data:
        # 只处理表格字典
        if block.get("type") != "table" or "table_body" not in block:
            new_data.append(block)
            continue

        table_html = block["table_body"]
        soup = BeautifulSoup(table_html, "html.parser")
        rows = soup.find_all("tr")
        if not rows:
            new_data.append(block)
            continue

        header_text = row_text(rows[0])
        new_rows = []
        seen_header_count = 0

        for row in rows:
            text = row_text(row)
            # 检测重复表头
            if text == header_text:
                seen_header_count += 1
                if seen_header_count > 1:
                    changes.append(
                        f"[rule_remove_duplicate_table_headers] page {block.get('page_idx','?')}\n"
                        f"检测到重复表头: {header_text}\n→ 已删除重复表头行。\n"
                    )
                    continue  # 跳过重复表头
            new_rows.append(row)

        # 替换表格内容
        if soup.table:
            soup.table.clear()
            for r in new_rows:
                soup.table.append(r)
            new_html = str(soup)
            if len(new_html) != len(table_html):
                block["table_body"] = new_html

        new_data.append(block)

    return new_data, changes



if __name__ == "__main__":
    # 输入输出文件
    # input_file = "E:\程序备份\KO\zsx\jsonProcess\\table\GBT114692013.json"
    input_file = "./title/DB3301T200373-2022_content_list.json"
    output_file = "j1_mix.json"
    changes_file = "j1_change.txt"
    # 读取输入 JSON
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 定义规则列表
    rules_list = [
        rule_numbered_heading_levels,rule_remove_catalog_headings,rule_remove_false_headings,rule_merge_consecutive_part_titles,rule_remove_date_headings,rule_remove_front_misheadings,rule_downgrade_table_figure_headings,
        rule_merge_split_appendix_titles,rule_appendix_headings,rule_appendix_subheadings,rule_merge_special_numbered_terms,rule_remove_pure_number_headings,rule_remove_long_headings,
        rule_remove_split_number_titles,rule_remove_formula_headings,rule_remove_date_headings,rule_remove_quality_report_headings,rule_remove_letter_parenthesis_headings
        # 以后还会加更多规则
        ,rule_merge_crosspage_tables, rule_downgrade_heading_after_contents, rule_remove_cover_title_and_duplicates,rule_remove_cover_title_and_duplicates,rule_remove_headings_between_contents_and_preface
        ,rule_clean_titles_between_contents_and_scope3,rule_remove_appendix_before_numbered_headings,rule_remove_orphan_numbered_headings

        , rule_references_as_last_heading,rule_remove_duplicate_table_headers
    ]
    # 应用规则
    processed_data, all_changes = apply_rules(data, rules_list)
    # 保存输出 JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=2)

    # 保存修改日志
    with open(changes_file, "w", encoding="utf-8") as f:
        f.write("\n".join(all_changes))

    print(f"处理完成，结果已保存到 {output_file}")
    print(f"修改日志已保存到 {changes_file}")
