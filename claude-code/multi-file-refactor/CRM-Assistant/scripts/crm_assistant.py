from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import parse
from xml.etree import ElementTree as ET
from zipfile import ZipFile

# Add parent common directory to path
COMMON_DIR = Path(__file__).parent.parent.parent / "common"
import sys

sys.path.insert(0, str(COMMON_DIR))

from feishu.client import FeishuClient
from feishu.bitable import coerce_field_value, coerce_row


VALID_INTENT_LEVELS = ["low", "medium", "high"]
VALID_STAGES = ["初次接触", "需求确认", "方案沟通", "推进中", "待成交", "已成交"]
VALID_CHANNELS = ["微信", "邮件", "飞书消息"]


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_env_file(path: str | Path | None = None) -> None:
    target = Path(path) if path else skill_root() / ".env.local"
    if not target.exists():
        return
    for raw_line in target.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def write_text(path: str | Path, value: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value, encoding="utf-8-sig")


def read_json(path: str | Path) -> Any:
    return json.loads(read_text(path))


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def stable_crm_id(prefix: str, *parts: Any) -> str:
    normalized_parts = [str(part or "").strip() for part in parts if str(part or "").strip()]
    payload = "||".join(normalized_parts)
    if not payload:
        payload = prefix
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{digest}"


def get_object_value(obj: Any, property_name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        value = obj.get(property_name, default)
    else:
        value = getattr(obj, property_name, default)
    return default if value is None else value


def resolve_str(path: str | Path | None) -> str | None:
    if not path:
        return None
    return str(Path(path).resolve())


def read_json_if_exists(path: str | Path | None) -> Any:
    if not path:
        return None
    target = Path(path)
    if not target.exists():
        return None
    return read_json(target)


def get_lines(text: str) -> list[str]:
    return [line.strip() for line in re.split(r"\r?\n", text) if line.strip()]


def get_matched_lines(lines: list[str], patterns: list[str]) -> list[str]:
    results: list[str] = []
    for line in lines:
        for pattern in patterns:
            if re.search(pattern, line):
                if line not in results:
                    results.append(line)
                break
    return results


def get_labels(text: str, mapping: dict[str, str]) -> list[str]:
    labels: list[str] = []
    for label, pattern in mapping.items():
        if re.search(pattern, text):
            labels.append(label)
    deduped: list[str] = []
    for item in labels:
        if item not in deduped:
            deduped.append(item)
    return deduped


def join_values(values: list[Any] | None, fallback: str = "暂无") -> str:
    if not values:
        return fallback
    items: list[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in items:
            items.append(text)
    return "；".join(items) if items else fallback


def parse_budget_max(text: str) -> int:
    max_value = 0
    for match in re.finditer(r"(\d+)\s*到\s*(\d+)\s*万", text):
        max_value = max(max_value, int(match.group(2)))
    for match in re.finditer(r"(预算|金额超过)\D{0,8}(\d+)\s*万", text):
        max_value = max(max_value, int(match.group(2)))
    for match in re.finditer(r"(合同金额|金额|控制在|压在)\D{0,8}(\d+)\s*万", text):
        max_value = max(max_value, int(match.group(2)))
    return max_value


def clamp_score(value: int) -> int:
    return max(0, min(100, value))


def has_pattern(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text))


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return datetime.fromisoformat(text)


def isoformat_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def extract_business_value_meta(text: str) -> dict[str, Any] | None:
    source_text = str(text or "")
    if not source_text.strip():
        return None

    range_patterns = [
        r"(预算大概在|预算在|金额在|价格在)?\s*(\d+)\s*(?:到|-|~|～)\s*(\d+)\s*[万wW]",
    ]
    upper_bound_patterns = [
        r"(控制在|控制到|希望先控制在|尽量控制在|压在|不超过|最好压在|金额在|控制在预算内)\s*(\d+)\s*[万wW](?:以内|以下)?",
        r"(\d+)\s*[万wW](?:以内|以下)",
    ]
    lower_bound_patterns = [
        r"(不低于|至少|起步|不少于)\s*(\d+)\s*[万wW](?:以上)?",
        r"(\d+)\s*[万wW](?:以上|起)",
    ]
    approx_patterns = [
        r"(约|大概|差不多|大约|接近)\s*(\d+)\s*[万wW]",
    ]
    exact_patterns = [
        r"(合同金额|签约金额|最终金额|成交金额)\D{0,12}(\d+)\s*[万wW]",
        r"(金额|预算|价格)\D{0,12}(锁定在|锁定为|定在|定为|确定为)?\s*(\d+)\s*[万wW]",
        r"(锁定在|锁定为|定在|定为|确定为|就是)\s*(\d+)\s*[万wW]",
        r"(\d+)\s*[万wW]",
    ]

    for pattern in range_patterns:
        match = re.search(pattern, source_text)
        if match:
            groups = match.groups()
            min_amount = int(groups[-2])
            max_amount = int(groups[-1])
            return {
                "amount_type": "range",
                "min_amount_wan": min_amount,
                "max_amount_wan": max_amount,
                "raw_expression": match.group(0),
            }

    for pattern in upper_bound_patterns:
        match = re.search(pattern, source_text)
        if match:
            groups = match.groups()
            amount = int(groups[-1])
            return {
                "amount_type": "upper_bound",
                "min_amount_wan": None,
                "max_amount_wan": amount,
                "raw_expression": match.group(0),
            }

    for pattern in lower_bound_patterns:
        match = re.search(pattern, source_text)
        if match:
            groups = match.groups()
            amount = int(groups[-1])
            return {
                "amount_type": "lower_bound",
                "min_amount_wan": amount,
                "max_amount_wan": None,
                "raw_expression": match.group(0),
            }

    for pattern in approx_patterns:
        match = re.search(pattern, source_text)
        if match:
            groups = match.groups()
            amount = int(groups[-1])
            return {
                "amount_type": "approx",
                "min_amount_wan": amount,
                "max_amount_wan": amount,
                "raw_expression": match.group(0),
            }

    for pattern in exact_patterns:
        match = re.search(pattern, source_text)
        if match:
            groups = match.groups()
            amount = int(groups[-1])
            return {
                "amount_type": "exact",
                "min_amount_wan": amount,
                "max_amount_wan": amount,
                "raw_expression": match.group(0),
            }

    budget_max = parse_budget_max(source_text)
    if budget_max > 0:
        return {
            "amount_type": "approx",
            "min_amount_wan": budget_max,
            "max_amount_wan": budget_max,
            "raw_expression": str(budget_max),
        }
    return None


def format_business_value(meta: dict[str, Any] | None) -> str | None:
    if not meta:
        return None
    amount_type = str(meta.get("amount_type") or "").strip()
    min_amount = meta.get("min_amount_wan")
    max_amount = meta.get("max_amount_wan")
    if amount_type == "range" and min_amount is not None and max_amount is not None:
        return f"{min_amount}-{max_amount}万"
    if amount_type == "upper_bound" and max_amount is not None:
        return f"{max_amount}万以内"
    if amount_type == "lower_bound" and min_amount is not None:
        return f"{min_amount}万以上"
    if amount_type == "exact" and min_amount is not None:
        return f"{min_amount}万"
    if amount_type == "approx" and min_amount is not None:
        return f"约 {min_amount} 万"
    return None


def get_business_value(text: str) -> str | None:
    return format_business_value(extract_business_value_meta(text))


def get_business_value_or_default(text: str) -> str:
    value = get_business_value(text)
    return value if value else "暂无明确业务价值"


def clean_opportunity_theme(raw_title: str, company_name: Any = None, customer_name: Any = None) -> str:
    title = str(raw_title).strip()
    if not title:
        return ""
    for value in [company_name, customer_name]:
        text = str(value).strip() if value is not None else ""
        if text:
            title = title.replace(text, "")
    title = re.sub(r"[（(][^)）]*[)）]", "", title)
    title = re.sub(r"\s+", "", title)
    title = re.sub(r"^[：:·\-—_]+|[：:·\-—_]+$", "", title)

    # Opportunity identity should be project-level, not meeting-stage-level.
    # E.g. “中国平安龙虾盒子需求梳理会” and “中国平安龙虾盒子方案沟通会”
    # should both normalize to “龙虾盒子”, so they share the same opportunity_id
    # while still producing separate stage snapshots.
    stage_suffixes = [
        "项目签约完成与启动确认会",
        "签约完成与启动确认会",
        "售后协同项目签约完成与启动确认会",
        "项目启动确认会",
        "签约前确认会",
        "内部推进会",
        "方案沟通会",
        "需求梳理会",
        "需求确认会",
        "初步了解会",
        "启动确认会",
        "推进会",
        "确认会",
        "沟通会",
        "讨论会",
        "评审会",
        "交流会",
        "培训会",
        "分享会",
        "启动会",
        "会议",
        "会",
    ]
    changed = True
    while changed and title:
        changed = False
        for suffix in stage_suffixes:
            if title.endswith(suffix) and len(title) > len(suffix):
                title = title[: -len(suffix)]
                title = re.sub(r"^[：:·\-—_]+|[：:·\-—_]+$", "", title)
                changed = True
                break
    # Keep identity at product/opportunity level. Words like “项目” are often
    # added by later-stage meeting titles but should not split the same sales
    # opportunity into a new opportunity_id.
    title = re.sub(r"(定制)?项目$", "定制", title)
    return title.strip()


def infer_opportunity_theme(title: Any, text: str, company_name: Any = None, customer_name: Any = None) -> str:
    title_theme = clean_opportunity_theme(str(title or ""), company_name, customer_name)
    if len(title_theme) >= 4:
        return title_theme
    if re.search(r"资产配置|美元", text):
        return "资产配置"
    if re.search(r"安装|部署|上手|教学|带教|培训|操作手册|场景赋能|模板包", text):
        return "现场教学与场景赋能"
    if re.search(r"巡检|售后|工厂|缺陷闭环|班组周复盘", text):
        return "现场运维协同试点"
    if re.search(r"并网|补件|验收|光伏|资料协同", text):
        return "并网资料协同"
    if re.search(r"CRM|客户信息|会议纪要|客户画像|跟进建议", text):
        return "CRM 一期试点"
    return "商机推进"


def infer_mbti(text: str) -> str:
    patterns = [
        ("ESTJ", r"权限边界|审批链|谁能导出|谁能修改|总部|区域|门店|我这个人比较直接|先给我结论|别讲概念|只看三件事"),
        ("ISTJ", r"字段清单|权限矩阵|归档逻辑|流程节点|导出格式|审批节点图"),
        ("INTJ", r"先确认方案框架|先看整体框架|讲清楚差异|讲清楚逻辑|希望看得更细"),
        ("INTP", r"想先了解一下|先研究一下|先看案例|先看思路"),
        ("ENTJ", r"尽快推进|本月底前|立项方向定下来|推进到采购"),
        ("ENTP", r"可以再扩展|后续更复杂的自动化扩展|多试几个场景"),
        ("INFJ", r"希望大家都能接受|照顾团队感受|长期关系|别让一线太难受"),
        ("INFP", r"不喜欢被高频跟进|别太打扰|慢慢看"),
        ("ENFJ", r"一起参与|都拉上|多方一起看"),
        ("ENFP", r"有意思|可以再聊|后面有机会再聊"),
        ("ISFJ", r"本金安全|流动性|稳健|别太复杂"),
        ("ESFJ", r"员工使用感受|内部流转方便|传阅方便"),
        ("ISTP", r"先试点|先覆盖|先把这三个高频场景做扎实"),
        ("ISFP", r"别发一堆材料|结构简单|不要太重"),
        ("ESTP", r"先做一期|马上看效果|快速见效"),
        ("ESFP", r"直接一点|三点结论|不要太长"),
    ]
    for label, pattern in patterns:
        if re.search(pattern, text):
            return label
    return "未明确"


def infer_single_status(text: str) -> str:
    if re.search(r"单身|一个人决定|我自己决定", text):
        return "是"
    if re.search(r"已婚|我先生|我太太|丈夫|妻子|伴侣", text):
        return "否"
    return "未明确"


def infer_resistance_level(stage: str, risk_concerns: list[str], text: str) -> str:
    high_patterns = r"不希望|必须|一定要|卡住|风险大|别太复杂|系统太重|培训复杂"
    low_patterns = r"整体方向认可|没有大的异议|可以推进|基本就可以"
    if re.search(high_patterns, text) or len(risk_concerns) >= 3:
        return "高"
    if re.search(low_patterns, text) and stage in ["推进中", "待成交", "已成交"]:
        return "低"
    if risk_concerns or stage in ["需求确认", "方案沟通", "推进中"]:
        return "中"
    return "未明确"


def infer_price_sensitivity(customer_text: str, risk_concerns: list[str], budget_max: int) -> str:
    if "价格敏感" in risk_concerns or re.search(r"预算|价格|成本|别太重|值不值", customer_text):
        return "高" if budget_max <= 50 and budget_max > 0 else "中"
    if budget_max >= 80:
        return "低"
    return "未明确"


def calculate_lead_score(
    opportunity_stage: str,
    customer_text: str,
    all_text: str,
    budget_max: int,
    next_meeting_time: datetime | None,
    decision_signals: list[str],
    risk_concerns: list[str],
) -> int:
    timeline_signal = has_pattern(customer_text, r"下周|本周|本月|月底|季度内|尽快|明天|周五之前|六月底前")
    scope_signal = has_pattern(customer_text, r"边界|范围|收敛|梳理清楚|需求对齐|需求确认|必须做|后放|优先级")
    proposal_signal = has_pattern(customer_text, r"报价|方案|演示|保守版|标准版|角色权限表|流程节点")
    acceptance_signal = has_pattern(customer_text, r"可以|能接受|认可|方向比上次清楚多了|没问题")
    procurement_signal = has_pattern(customer_text, r"采购|法务|签批|内部评审|内部推进")
    implementation_signal = has_pattern(customer_text, r"上线一期|先上线|试运行|服务站|启动会|联调|推进清单")
    contract_signal = has_pattern(customer_text, r"合同|定稿|付款|付款节点|合同金额|签约|最终版")
    signoff_signal = has_pattern(customer_text, r"这周就进签约流程|周三可以完成签约|不会再拖|没有新增阻塞|基本通过了")
    closed_won_signal = has_pattern(customer_text, r"已成交|正式成交|成交确认|合同(这周)?已经签完|合同今天上午已经完成双方签署|完成双方签署|签署完成|双方法务盖章|项目已经正式敲定|金额.*已经锁定|这笔商机就按正式成交记录")
    kickoff_signal = has_pattern(customer_text, r"启动会|交付负责人|项目经理|阶段验收|交付执行|接口联调计划")
    budget_signal = budget_max > 0
    multi_role_signal = bool(decision_signals) or has_pattern(customer_text, r"运营管理|质控|信息科技|采购|法务|总部")
    risk_signal = bool(risk_concerns)

    lead_score = {
        "初次接触": 20,
        "需求确认": 30,
        "方案沟通": 32,
        "推进中": 30,
        "待成交": 40,
        "已成交": 50,
    }[opportunity_stage]

    if budget_signal:
        lead_score += 14
    if timeline_signal:
        lead_score += 6
    if next_meeting_time is not None:
        lead_score += 4

    if opportunity_stage == "需求确认":
        if multi_role_signal:
            lead_score += 8
        if scope_signal:
            lead_score += 14
        if risk_signal:
            lead_score += 6
    elif opportunity_stage == "方案沟通":
        if multi_role_signal:
            lead_score += 8
        if proposal_signal:
            lead_score += 16
        if acceptance_signal:
            lead_score += 6
        if has_pattern(customer_text, r"保守版|标准版|双版本|报价结构"):
            lead_score += 4
    elif opportunity_stage == "推进中":
        if procurement_signal:
            lead_score += 16
        if implementation_signal:
            lead_score += 12
        if risk_signal:
            lead_score += 10
    elif opportunity_stage == "待成交":
        if contract_signal:
            lead_score += 20
        if procurement_signal:
            lead_score += 10
        if signoff_signal:
            lead_score += 6
        if kickoff_signal:
            lead_score += 6
        if has_pattern(customer_text, r"付款节点|合同版本|最终合同版本|周三可以完成签约|签约收掉|这周就把签约收掉|把合同版本和付款安排锁定"):
            lead_score += 10
    elif opportunity_stage == "已成交":
        if closed_won_signal:
            lead_score += 25
        if kickoff_signal:
            lead_score += 10
        if has_pattern(all_text, r"金额.*锁定|付款按之前确认|正式签署|阶段验收"):
            lead_score += 11
    else:
        if multi_role_signal:
            lead_score += 6
        if proposal_signal:
            lead_score += 6

    if has_pattern(customer_text, r"不着急|先了解|明年再说|明年再定|先看看|观察一下"):
        lead_score -= 15
    if has_pattern(customer_text, r"暂无预算|预算要等明年|预算还没批"):
        lead_score -= 12

    return clamp_score(lead_score)


def get_sales_region(context: dict[str, Any], text: str) -> str | None:
    context_region = get_object_value(context, "sales_region")
    if context_region and str(context_region).strip():
        return str(context_region).strip()
    for keyword, label in [
        ("华北", "华北地区"),
        ("华东", "华东地区"),
        ("华南", "华南地区"),
        ("西南", "西南地区"),
        ("西北", "西北地区"),
        ("全国", "全国"),
    ]:
        if keyword in text:
            return label
    return None


def get_transcript_text(raw: dict[str, Any]) -> str:
    transcript = raw.get("transcript", {}) or {}
    full_text = transcript.get("full_text")
    if full_text and str(full_text).strip():
        return str(full_text).strip()
    segments = transcript.get("segments") or []
    lines: list[str] = []
    for segment in segments:
        speaker = str(segment.get("speaker") or "发言人").strip() or "发言人"
        text = str(segment.get("text") or "").strip()
        if text:
            lines.append(f"{speaker}：{text}")
    if lines:
        return "\n".join(lines)
    raise ValueError("No transcript.full_text or transcript.segments found in raw input.")


def parse_cn_datetime_text(text: str | None) -> datetime | None:
    if text is None:
        return None
    value = str(text).strip()
    if not value:
        return None
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})\s*(上午|下午)?\s*(\d{1,2}):(\d{2})", value)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        meridiem = match.group(4) or ""
        hour = int(match.group(5))
        minute = int(match.group(6))
        if meridiem == "下午" and hour < 12:
            hour += 12
        if meridiem == "上午" and hour == 12:
            hour = 0
        return datetime.fromisoformat(f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00+08:00")
    return parse_datetime(value)


def parse_cn_duration_to_minutes(text: str | None) -> int | None:
    if text is None:
        return None
    value = str(text).strip()
    if not value:
        return None
    hours = 0
    minutes = 0
    seconds = 0
    hour_match = re.search(r"(\d+)\s*小时", value)
    minute_match = re.search(r"(\d+)\s*分钟", value)
    second_match = re.search(r"(\d+)\s*秒", value)
    if hour_match:
        hours = int(hour_match.group(1))
    if minute_match:
        minutes = int(minute_match.group(1))
    if second_match:
        seconds = int(second_match.group(1))
    total_minutes = hours * 60 + minutes + (1 if seconds >= 30 else 0)
    return total_minutes if total_minutes > 0 else None


def parse_feishu_doc_meeting_markdown(doc_markdown: str, fallback_title: str | None = None, source_doc_url: str | None = None) -> dict[str, Any]:
    text = str(doc_markdown or "").replace("\r\n", "\n")
    lines = text.split("\n")

    meeting_title = str(fallback_title or "飞书会议纪要").strip() or "飞书会议纪要"
    start_time_text: str | None = None
    duration_text: str | None = None
    meeting_url: str | None = source_doc_url

    participants: list[dict[str, Any]] = []
    transcript_lines: list[str] = []
    current_section: str | None = None
    pending_speaker: str | None = None

    basic_info_map: OrderedDict[str, str] = OrderedDict()

    def normalize_section_title(value: str) -> str:
        text_value = str(value or "").strip().strip("#").strip()
        text_value = text_value.strip("* ")
        return text_value

    def is_section(value: str, target: str) -> bool:
        normalized = normalize_section_title(value)
        return normalized == target or normalized.endswith(target)

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if is_section(line, "一、会议基本信息"):
            current_section = "basic_info"
            continue
        if is_section(line, "二、参会人员"):
            current_section = "participants"
            continue
        if is_section(line, "三、文字记录"):
            current_section = "transcript"
            continue

        if current_section == "basic_info":
            bullet_match = re.match(r"-\s*\*\*(.+?)\*\*[:：]\s*(.+)$", line)
            plain_match = re.match(r"(.+?)[:：]\s*(.+)$", line)
            match = bullet_match or plain_match
            if match:
                key = match.group(1).strip().strip("* ")
                value = match.group(2).strip()
                basic_info_map[key] = value
                continue

        if current_section == "participants":
            participant_match = re.match(r"(?:-\s*)?(?:\*\*(.+?)\*\*|(.+?))[｜|](.+?)[｜|](.+?)[｜|](.+)$", line)
            if participant_match:
                name = (participant_match.group(1) or participant_match.group(2) or "").strip()
                participants.append({
                    "user_id": None,
                    "name": name,
                    "role": participant_match.group(3).strip(),
                    "company": participant_match.group(4).strip(),
                    "industry": participant_match.group(5).strip(),
                })
                continue

        if current_section == "transcript":
            speaker_match = re.match(r"^(.+?)\s+(上午|下午)\s*(\d{1,2}:\d{2})$", line)
            if speaker_match:
                pending_speaker = speaker_match.group(1).strip()
                continue
            if pending_speaker and line:
                transcript_lines.append(f"{pending_speaker}：{line}")
                pending_speaker = None
                continue

    if basic_info_map.get("会议主题"):
        meeting_title = basic_info_map["会议主题"]
    if basic_info_map.get("开始时间"):
        start_time_text = basic_info_map["开始时间"]
    if basic_info_map.get("会议链接"):
        meeting_url = re.sub(r"^[\[]|[\)]$", "", basic_info_map["会议链接"]).strip()
        md_link_match = re.search(r"\((https?://[^)]+)\)", basic_info_map["会议链接"])
        if md_link_match:
            meeting_url = md_link_match.group(1).strip()

    start_dt = parse_cn_datetime_text(start_time_text)
    end_dt: datetime | None = None
    if basic_info_map.get("结束时间"):
        end_dt = parse_cn_datetime_text(basic_info_map["结束时间"])
    if end_dt is None and start_dt is not None:
        duration_minutes = parse_cn_duration_to_minutes(duration_text)
        if duration_minutes:
            end_dt = start_dt + timedelta(minutes=duration_minutes)

    company_name = basic_info_map.get("公司名称") or ""
    customer_name = basic_info_map.get("客户名称") or ""
    owner = basic_info_map.get("负责人") or ""
    industry = basic_info_map.get("行业") or ""
    customer_id = basic_info_map.get("客户 ID") or basic_info_map.get("客户ID") or ""
    opportunity_id = basic_info_map.get("商机 ID") or basic_info_map.get("商机ID") or ""
    sales_region = basic_info_map.get("销售区域") or ""
    next_meeting_time_text = basic_info_map.get("下一次会议时间") or ""
    next_meeting_dt = parse_cn_datetime_text(next_meeting_time_text)

    if not participants:
        participant_names = []
        if owner:
            participant_names.append(owner)
        if customer_name and customer_name not in participant_names:
            participant_names.append(customer_name)
        participants = [{"user_id": None, "name": name, "role": "unknown", "company": company_name if name == customer_name else "", "industry": industry} for name in participant_names]

    raw = OrderedDict([
        ("source", "feishu_meeting_doc"),
        ("meeting", OrderedDict([
            ("meeting_id", f"doc_{re.sub(r'[^A-Za-z0-9]+', '_', meeting_title).strip('_') or 'meeting'}"),
            ("title", meeting_title),
            ("start_time", isoformat_or_none(start_dt)),
            ("end_time", isoformat_or_none(end_dt)),
            ("host_user_id", None),
            ("meeting_url", meeting_url),
            ("calendar_event_id", None),
        ])),
        ("participants", participants),
        ("transcript", OrderedDict([
            ("full_text", "\n".join(transcript_lines).strip()),
        ])),
        ("calendar", OrderedDict([
            ("next_meeting_time", isoformat_or_none(next_meeting_dt)),
        ])),
        ("crm_binding", OrderedDict([
            ("customer_id", customer_id or None),
            ("customer_name", customer_name or None),
            ("company_name", company_name or None),
            ("owner", owner or None),
            ("industry", industry or None),
            ("opportunity_id", opportunity_id or None),
            ("sales_region", sales_region or None),
        ])),
    ])
    return raw


def extract_docx_text(docx_path: str | Path) -> str:
    path = Path(docx_path)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(path) as archive:
        data = archive.read("word/document.xml")
    root = ET.fromstring(data)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        parts: list[str] = []
        for text_node in paragraph.findall(".//w:t", ns):
            if text_node.text:
                parts.append(text_node.text)
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def build_context_from_feishu_doc(doc_markdown_path: str | Path, output_dir: str | Path, raw_file_name: str = "feishu_meeting_raw.json", context_file_name: str = "context.json", transcript_file_name: str = "transcript.txt", source_doc_url: str | None = None, fallback_title: str | None = None) -> dict[str, Any]:
    doc_text = read_text(doc_markdown_path)
    raw = parse_feishu_doc_meeting_markdown(doc_text, fallback_title=fallback_title, source_doc_url=source_doc_url)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    raw_path = output / raw_file_name
    write_json(raw_path, raw)
    build_result = build_context_from_feishu(raw_path, output, context_file_name, transcript_file_name)
    result = OrderedDict([
        ("doc_markdown_path", resolve_str(doc_markdown_path)),
        ("raw_input_path", resolve_str(raw_path)),
        ("generated_context", build_result.get("generated_context")),
        ("generated_transcript", build_result.get("generated_transcript")),
    ])
    write_json(output / "build_from_doc_result.json", result)
    return result


def ingest_feishu_doc_to_bitable(
    doc_markdown_path: str | Path,
    output_dir: str | Path,
    source_doc_url: str | None = None,
    fallback_title: str | None = None,
    config_path: str | Path | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
    app_token_or_url: str | None = None,
    customer_table_id: str | None = None,
    opportunity_table_id: str | None = None,
    dry_run: bool = False,
    sync_feishu: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir)
    build_output = output / "build"
    process_output = output / "process"
    build_result = build_context_from_feishu_doc(doc_markdown_path, build_output, source_doc_url=source_doc_url, fallback_title=fallback_title)
    crm_packet = process_transcript(build_output / "transcript.txt", build_output / "context.json", process_output)
    result = OrderedDict([
        ("doc_markdown_path", resolve_str(doc_markdown_path)),
        ("raw_input_path", resolve_str(build_output / "feishu_meeting_raw.json")),
        ("context_path", resolve_str(build_output / "context.json")),
        ("transcript_path", resolve_str(build_output / "transcript.txt")),
        ("crm_packet_path", resolve_str(process_output / "crm_packet.json")),
        ("customer_id", crm_packet["customer_table_row"].get("客户ID")),
        ("opportunity_id", crm_packet["opportunity_snapshot_row"].get("商机ID")),
    ])
    if sync_feishu:
        sync_output = output / "sync"
        sync_result = sync_crm_packet_to_feishu(
            process_output / "crm_packet.json",
            sync_output,
            config_path,
            app_id,
            app_secret,
            app_token_or_url,
            customer_table_id,
            opportunity_table_id,
            dry_run,
        )
        result["sync_result_path"] = resolve_str(sync_output / "feishu_sync_result.json")
        result["customer_action"] = sync_result.get("customer_action")
        result["opportunity_action"] = sync_result.get("opportunity_action")
    write_json(output / "ingest_doc_result.json", result)
    return result


def ingest_docx_to_bitable(
    docx_path: str | Path,
    output_dir: str | Path,
    source_doc_url: str | None = None,
    fallback_title: str | None = None,
    config_path: str | Path | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
    app_token_or_url: str | None = None,
    customer_table_id: str | None = None,
    opportunity_table_id: str | None = None,
    dry_run: bool = False,
    sync_feishu: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    extracted_markdown_path = output / "source_doc.md"
    extracted_markdown_path.write_text(extract_docx_text(docx_path), encoding="utf-8-sig")
    result = ingest_feishu_doc_to_bitable(
        extracted_markdown_path,
        output,
        source_doc_url,
        fallback_title,
        config_path,
        app_id,
        app_secret,
        app_token_or_url,
        customer_table_id,
        opportunity_table_id,
        dry_run,
        sync_feishu,
    )
    result["docx_path"] = resolve_str(docx_path)
    result["extracted_doc_markdown_path"] = resolve_str(extracted_markdown_path)
    write_json(output / "ingest_docx_result.json", result)
    return result


def extract_bitable_app_token(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"/base/([A-Za-z0-9]+)", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9]+", text):
        return text
    return None


def resolve_feishu_value(cli_value: str | None, config: dict[str, Any] | None, config_key: str, env_key: str) -> str | None:
    if cli_value and str(cli_value).strip():
        return str(cli_value).strip()
    config_value = get_object_value(config, config_key)
    if config_value and str(config_value).strip():
        return str(config_value).strip()
    env_value = os.getenv(env_key)
    if env_value and env_value.strip():
        return env_value.strip()
    return None


def build_url(base_url: str, query: dict[str, Any] | None = None) -> str:
    if not query:
        return base_url
    normalized: dict[str, Any] = {}
    for key, value in query.items():
        if value is None:
            continue
        normalized[key] = value
    if not normalized:
        return base_url
    return f"{base_url}?{parse.urlencode(normalized)}"


def map_row_fields(row: dict[str, Any], field_mapping: dict[str, Any] | None = None) -> OrderedDict[str, Any]:
    mapped = OrderedDict()
    mapping = field_mapping or {}
    for source_field, value in row.items():
        target_field = mapping.get(source_field, source_field)
        if target_field is None:
            continue
        target_text = str(target_field).strip()
        if not target_text:
            continue
        mapped[target_text] = value
    return mapped


def normalize_existing_bitable_fields(fields: dict[str, Any], fields_meta: list[dict[str, Any]]) -> OrderedDict[str, Any]:
    fields_by_name = {str(item.get("field_name") or "").strip(): item for item in fields_meta or []}
    normalized = OrderedDict()
    for field_name, value in (fields or {}).items():
        field_meta = fields_by_name.get(str(field_name).strip())
        field_type = int(get_object_value(field_meta, "type", 0) or 0) if field_meta else 0
        if field_type in {1, 3, 4, 15}:
            normalized[field_name] = normalize_feishu_field_value(value)
        else:
            normalized[field_name] = value
    return normalized


def is_weak_field_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        normalized = text.lower()
        if normalized in {"null", "none", "n/a", "na"}:
            return True
        weak_text_values = {
            "未明确",
            "暂无",
            "未知",
            "待确认",
            "待补充",
            "空",
            "空值",
            "无",
            "不详",
            "不明确",
            "无法判断",
            "未提及",
            "未说明",
        }
        if text in weak_text_values:
            return True
        if text.startswith(("暂无明确", "未明确", "待确认")):
            return True
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def merge_multi_value_text(current_value: Any, existing_value: Any) -> str:
    def split_values(value: Any) -> list[str]:
        text = str(value or "").strip()
        if not text:
            return []
        return [item.strip() for item in re.split(r"[；;、,，]", text) if item.strip()]

    values: list[str] = []
    seen: set[str] = set()
    for item in split_values(existing_value) + split_values(current_value):
        if item not in seen:
            seen.add(item)
            values.append(item)
    return "；".join(values)


def merge_row_preserving_existing_values(current_row: OrderedDict[str, Any], existing_fields: dict[str, Any] | None) -> tuple[OrderedDict[str, Any], list[str]]:
    merged = OrderedDict()
    preserved_fields: list[str] = []
    existing = existing_fields or {}
    merge_fields = {"沟通风格", "风险顾虑"}
    for field_name, current_value in current_row.items():
        existing_value = existing.get(field_name)
        if field_name in merge_fields and not is_weak_field_value(existing_value) and not is_weak_field_value(current_value):
            merged[field_name] = merge_multi_value_text(current_value, existing_value)
            continue
        if is_weak_field_value(current_value) and not is_weak_field_value(existing_value):
            merged[field_name] = existing_value
            preserved_fields.append(field_name)
        else:
            merged[field_name] = current_value
    return merged, preserved_fields


def get_summary_value(value: Any, fallback: str) -> str:
    return fallback if is_weak_field_value(value) else str(value).strip()


def build_customer_profile_summary(
    customer_name: Any,
    opportunity_stage: Any,
    mbti: Any,
    single_status: Any,
    communication_style: Any,
    resistance_level: Any,
    price_sensitivity: Any,
    risk_concerns: Any,
) -> str:
    single_status_text = str(single_status).strip() if single_status is not None else ""
    single_status_summary = {
        "是": "单身状态有明确信号",
        "否": "会话中出现伴侣或婚姻相关信号",
        "未明确": "是否单身未明确",
    }.get(single_status_text, "是否单身未明确")
    customer_name_text = get_summary_value(customer_name, "该客户")
    stage_text = get_summary_value(opportunity_stage, "当前")
    mbti_text = get_summary_value(mbti, "未明确")
    communication_text = get_summary_value(communication_style, "常规沟通")
    resistance_text = get_summary_value(resistance_level, "未明确")
    price_text = get_summary_value(price_sensitivity, "未明确")
    risk_text = get_summary_value(risk_concerns, "暂无明显风险顾虑")
    return (
        f"{customer_name_text}当前处于{stage_text}阶段，"
        f"MBTI 倾向{mbti_text}，{single_status_summary}，"
        f"沟通风格偏{communication_text}，"
        f"成交阻力{resistance_text}，价格敏感程度{price_text}，"
        f"主要风险顾虑为{risk_text}。"
    )


def normalize_feishu_field_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text")
                if text is not None:
                    normalized = str(text).strip()
                    if normalized:
                        parts.append(normalized)
                        continue
            normalized = str(item).strip()
            if normalized:
                parts.append(normalized)
        return "".join(parts).strip()
    if isinstance(value, dict):
        text = value.get("text")
        if text is not None:
            return str(text).strip()
    return str(value).strip()


def find_feishu_record_by_field(records: list[dict[str, Any]], field_name: str, expected_value: Any) -> dict[str, Any] | None:
    if expected_value is None:
        return None
    expected_text = str(expected_value).strip()
    if not expected_text:
        return None
    for record in records:
        fields = record.get("fields") or {}
        actual_text = normalize_feishu_field_value(fields.get(field_name))
        if actual_text == expected_text:
            return record
    return None


def find_feishu_record_by_customer_identity(records: list[dict[str, Any]], customer_id: Any, customer_name: Any, company_name: Any) -> dict[str, Any] | None:
    expected_id = str(customer_id or "").strip()
    if expected_id:
        matched = find_feishu_record_by_field(records, "客户ID", expected_id)
        if matched is not None:
            return matched
    expected_name = str(customer_name or "").strip()
    expected_company = str(company_name or "").strip()
    if not expected_name:
        return None
    for record in records:
        fields = record.get("fields") or {}
        actual_name = normalize_feishu_field_value(fields.get("客户名称"))
        actual_company = normalize_feishu_field_value(fields.get("客户公司"))
        if actual_name == expected_name and actual_company == expected_company:
            return record
    return None


def find_feishu_record_by_opportunity_identity(records: list[dict[str, Any]], opportunity_id: Any, opportunity_name: Any, customer_company: Any = None) -> dict[str, Any] | None:
    expected_id = str(opportunity_id or "").strip()
    expected_name = str(opportunity_name or "").strip()
    expected_company = str(customer_company or "").strip()
    if expected_id:
        matched = find_feishu_record_by_field(records, "商机ID", expected_id)
        if matched is not None:
            return matched
    if not expected_name:
        return None
    for record in records:
        fields = record.get("fields") or {}
        actual_name = normalize_feishu_field_value(fields.get("机会名称"))
        actual_company = normalize_feishu_field_value(fields.get("客户公司"))
        if actual_name == expected_name and (not expected_company or actual_company == expected_company):
            return record
    return None


def inspect_feishu_bitable(app_id: str | None, app_secret: str | None, app_token_or_url: str | None, output_dir: str | Path, table_id: str | None = None) -> dict[str, Any]:
    resolved_app_id = app_id or os.getenv("FEISHU_APP_ID")
    resolved_app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
    resolved_app_token_source = (
        app_token_or_url
        or os.getenv("FEISHU_BITABLE_APP_TOKEN")
        or os.getenv("FEISHU_BITABLE_URL")
    )
    if not resolved_app_id or not resolved_app_secret:
        raise ValueError("Missing Feishu app credentials. Provide --app-id/--app-secret or FEISHU_APP_ID/FEISHU_APP_SECRET.")
    app_token = extract_bitable_app_token(resolved_app_token_source)
    if app_token is None:
        raise ValueError("Unable to parse Feishu bitable app token from --app-token-or-url, FEISHU_BITABLE_APP_TOKEN, or FEISHU_BITABLE_URL.")
    client = FeishuClient(app_id=resolved_app_id, app_secret=resolved_app_secret)
    tables = client.bitable_list_tables(app_token)
    result: OrderedDict[str, Any] = OrderedDict([
        ("app_token", app_token),
        ("tables", tables),
    ])
    if table_id:
        result["fields"] = client.bitable_list_fields(app_token, table_id)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "feishu_bitable_inspect.json", result)
    return result


def sync_crm_packet_to_feishu(
    crm_packet_path: str | Path,
    output_dir: str | Path,
    config_path: str | Path | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
    app_token_or_url: str | None = None,
    customer_table_id: str | None = None,
    opportunity_table_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    crm_packet = read_json(crm_packet_path)
    config = read_json_if_exists(config_path) or {}

    resolved_app_id = resolve_feishu_value(app_id, config, "app_id", "FEISHU_APP_ID")
    resolved_app_secret = resolve_feishu_value(app_secret, config, "app_secret", "FEISHU_APP_SECRET")
    resolved_app_token_source = (
        app_token_or_url
        or get_object_value(config, "app_token")
        or get_object_value(config, "bitable_url")
        or os.getenv("FEISHU_BITABLE_APP_TOKEN")
        or os.getenv("FEISHU_BITABLE_URL")
    )
    resolved_app_token = extract_bitable_app_token(str(resolved_app_token_source) if resolved_app_token_source else None)
    if resolved_app_token is None:
        raise ValueError("Missing Feishu app token. Provide --app-token-or-url, config.app_token, config.bitable_url, FEISHU_BITABLE_APP_TOKEN, or FEISHU_BITABLE_URL.")

    resolved_customer_table_id = (
        customer_table_id
        or get_object_value(config, "customer_table_id")
        or os.getenv("FEISHU_CUSTOMER_TABLE_ID")
    )
    resolved_opportunity_table_id = (
        opportunity_table_id
        or get_object_value(config, "opportunity_snapshot_table_id")
        or get_object_value(config, "opportunity_table_id")
        or os.getenv("FEISHU_OPPORTUNITY_TABLE_ID")
    )
    if not resolved_customer_table_id or not str(resolved_customer_table_id).strip():
        raise ValueError("Missing customer table id.")
    if not resolved_opportunity_table_id or not str(resolved_opportunity_table_id).strip():
        raise ValueError("Missing opportunity snapshot table id.")

    customer_field_mapping = get_object_value(config, "customer_field_mapping", {}) or {}
    opportunity_field_mapping = get_object_value(config, "opportunity_field_mapping", {}) or {}
    customer_key_field = str(get_object_value(config, "customer_key_field", "客户ID (fallback: 客户名称+客户公司)")).strip() or "客户ID (fallback: 客户名称+客户公司)"

    customer_rows_source = crm_packet.get("customer_table_rows") or []
    if not customer_rows_source and crm_packet.get("customer_table_row"):
        customer_rows_source = [crm_packet["customer_table_row"]]
    customer_rows = [map_row_fields(row, customer_field_mapping) for row in customer_rows_source]
    customer_row = customer_rows[0] if customer_rows else OrderedDict()
    opportunity_row = map_row_fields(crm_packet["opportunity_snapshot_row"], opportunity_field_mapping)
    customer_keys = [str(row.get("客户ID") or "").strip() or f"{row.get('客户名称', '')}||{row.get('客户公司', '')}" for row in customer_rows]

    report: OrderedDict[str, Any] = OrderedDict([
        ("crm_packet_path", resolve_str(crm_packet_path)),
        ("config_path", resolve_str(config_path)),
        ("app_token", resolved_app_token),
        ("customer_table_id", resolved_customer_table_id),
        ("opportunity_snapshot_table_id", resolved_opportunity_table_id),
        ("customer_key_field", customer_key_field),
        ("customer_key_value", customer_keys[0] if customer_keys else None),
        ("customer_key_values", customer_keys),
        ("dry_run", dry_run),
        ("customer_candidate_row_fields", customer_rows),
        ("customer_row_fields", customer_row),
        ("customer_row_fields_list", customer_rows),
        ("opportunity_row_fields", opportunity_row),
    ])

    if dry_run:
        report["customer_action"] = "preview_only"
        report["opportunity_action"] = "preview_only"
    else:
        if not resolved_app_id or not resolved_app_secret:
            raise ValueError("Missing Feishu app credentials. Provide --app-id/--app-secret, config, or environment variables.")
        client = FeishuClient(app_id=resolved_app_id, app_secret=resolved_app_secret)
        customer_fields_meta = client.bitable_list_fields(resolved_app_token, str(resolved_customer_table_id))
        opportunity_fields_meta = client.bitable_list_fields(resolved_app_token, str(resolved_opportunity_table_id))
        existing_records = client.bitable_list_records(resolved_app_token, str(resolved_customer_table_id))
        customer_actions: list[str] = []
        customer_responses: list[Any] = []
        customer_record_ids: list[str] = []
        customer_preserved_fields_map: OrderedDict[str, list[str]] = OrderedDict()
        effective_customer_rows: list[dict[str, Any]] = []
        for row in customer_rows:
            row_id = row.get("客户ID")
            row_name = row.get("客户名称")
            row_company = row.get("客户公司")
            existing_record = find_feishu_record_by_customer_identity(existing_records, row_id, row_name, row_company)
            coerced_row = coerce_row(row, customer_fields_meta)
            if existing_record is None:
                customer_response = client.bitable_batch_create(
                    resolved_app_token,
                    str(resolved_customer_table_id),
                    [{"fields": coerced_row}],
                )
                customer_actions.append("created")
                customer_responses.append(customer_response)
                effective_customer_rows.append(coerced_row)
                customer_preserved_fields_map[f"{row_name}||{row_company or ''}"] = []
            else:
                existing_record_fields = normalize_existing_bitable_fields(existing_record.get("fields") or {}, customer_fields_meta)
                effective_customer_row, preserved_fields = merge_row_preserving_existing_values(row, existing_record_fields)
                effective_customer_row["客户画像摘要"] = build_customer_profile_summary(
                    effective_customer_row.get("客户名称"),
                    opportunity_row.get("当前阶段"),
                    effective_customer_row.get("MBTI"),
                    effective_customer_row.get("是否单身"),
                    effective_customer_row.get("沟通风格"),
                    effective_customer_row.get("成交阻力"),
                    effective_customer_row.get("价格敏感程度"),
                    effective_customer_row.get("风险顾虑"),
                )
                effective_customer_row = coerce_row(effective_customer_row, customer_fields_meta)
                customer_response = client.bitable_batch_update(
                    resolved_app_token,
                    str(resolved_customer_table_id),
                    [{"record_id": existing_record["record_id"], "fields": effective_customer_row}],
                )
                customer_actions.append("updated")
                customer_responses.append(customer_response)
                customer_record_ids.append(existing_record.get("record_id"))
                effective_customer_rows.append(effective_customer_row)
                customer_preserved_fields_map[f"{row_name}||{row_company or ''}"] = preserved_fields
        report["customer_action"] = customer_actions[0] if len(customer_actions) == 1 else "batch"
        report["customer_actions"] = customer_actions
        if customer_record_ids:
            report["customer_record_id"] = customer_record_ids[0]
            report["customer_record_ids"] = customer_record_ids
        report["customer_row_fields"] = effective_customer_rows[0] if effective_customer_rows else customer_row
        report["customer_row_fields_list"] = effective_customer_rows
        report["customer_preserved_fields"] = next(iter(customer_preserved_fields_map.values()), []) if customer_preserved_fields_map else []
        report["customer_preserved_fields_map"] = customer_preserved_fields_map
        report["customer_response"] = customer_responses[0] if len(customer_responses) == 1 else customer_responses
        report["customer_responses"] = customer_responses

        existing_opportunity_records = client.bitable_list_records(resolved_app_token, str(resolved_opportunity_table_id))
        existing_opportunity_record = find_feishu_record_by_opportunity_identity(
            existing_opportunity_records,
            opportunity_row.get("商机ID"),
            opportunity_row.get("机会名称"),
            opportunity_row.get("客户公司"),
        )
        coerced_opportunity_row = coerce_row(opportunity_row, opportunity_fields_meta)
        if existing_opportunity_record is None:
            opportunity_response = client.bitable_batch_create(
                resolved_app_token,
                str(resolved_opportunity_table_id),
                [{"fields": coerced_opportunity_row}],
            )
            report["opportunity_action"] = "created"
        else:
            opportunity_response = client.bitable_batch_update(
                resolved_app_token,
                str(resolved_opportunity_table_id),
                [{"record_id": existing_opportunity_record["record_id"], "fields": coerced_opportunity_row}],
            )
            report["opportunity_action"] = "updated"
            report["opportunity_record_id"] = existing_opportunity_record.get("record_id")
        report["opportunity_row_fields"] = coerced_opportunity_row
        report["opportunity_response"] = opportunity_response

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "feishu_sync_result.json", report)
    return report


def get_first_participant_by_role(participants: list[dict[str, Any]], roles: list[str]) -> dict[str, Any] | None:
    for participant in participants:
        if participant.get("role") in roles:
            return participant
    return None


def get_participants_by_role(participants: list[dict[str, Any]], roles: list[str]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for participant in participants:
        if participant.get("role") in roles:
            matched.append(participant)
    return matched


def split_participants_by_identity(participants: list[dict[str, Any]], company_name: Any = None, owner: Any = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    company_text = str(company_name or "").strip()
    owner_text = str(owner or "").strip()
    internal_company_hints = ["载极", "我方", "本方", "销售", "顾问", "实施", "方案", "客服", "交付"]

    external_contacts: list[dict[str, Any]] = []
    internal_contacts: list[dict[str, Any]] = []
    fallback_unknowns: list[dict[str, Any]] = []

    for participant in participants:
        role_text = str(participant.get("role") or "").strip()
        participant_company = str(participant.get("company") or "").strip()
        participant_name = str(participant.get("name") or "").strip()
        normalized_role = role_text.lower()

        if normalized_role in {"external", "guest", "customer"}:
            external_contacts.append(participant)
            continue
        if normalized_role in {"internal", "host", "owner"}:
            internal_contacts.append(participant)
            continue
        if owner_text and participant_name == owner_text:
            internal_contacts.append(participant)
            continue
        if company_text and participant_company and participant_company == company_text:
            external_contacts.append(participant)
            continue
        if participant_company and any(hint in participant_company for hint in internal_company_hints):
            internal_contacts.append(participant)
            continue
        if role_text and any(hint in role_text for hint in internal_company_hints):
            internal_contacts.append(participant)
            continue
        fallback_unknowns.append(participant)

    if not external_contacts and fallback_unknowns:
        external_contacts.extend(fallback_unknowns)
    else:
        for participant in fallback_unknowns:
            if participant not in external_contacts and participant not in internal_contacts:
                external_contacts.append(participant)

    return external_contacts, internal_contacts


def normalize_contact(person: dict[str, Any] | None) -> OrderedDict[str, Any] | None:
    if person is None:
        return None
    name = str(person.get("name") or "").strip()
    company = str(person.get("company") or "").strip()
    industry = str(person.get("industry") or "").strip()
    role = str(person.get("role") or "unknown").strip() or "unknown"
    user_id = person.get("user_id")
    if not any([name, company, industry, user_id]):
        return None
    return OrderedDict([
        ("user_id", user_id),
        ("name", name or None),
        ("role", role),
        ("company", company or None),
        ("industry", industry or None),
    ])


def dedupe_contacts(contacts: list[dict[str, Any]]) -> list[OrderedDict[str, Any]]:
    deduped: list[OrderedDict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for contact in contacts:
        normalized = normalize_contact(contact)
        if normalized is None:
            continue
        key = (
            str(normalized.get("name") or "").strip(),
            str(normalized.get("company") or "").strip(),
            str(normalized.get("user_id") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def normalize_transcript_speakers(transcript_text: str, owner: Any = None, customer_name: Any = None) -> str:
    text = str(transcript_text or "").strip()
    if not text:
        return text

    normalized_lines: list[str] = []
    for raw_line in text.splitlines():
        line = str(raw_line).strip()
        if not line:
            continue
        speaker_match = re.match(r"^([^：:]+)[：:](.*)$", line)
        if not speaker_match:
            normalized_lines.append(line)
            continue
        speaker = speaker_match.group(1).strip()
        content = speaker_match.group(2).strip()
        normalized_lines.append(f"{speaker}：{content}")
    return "\n".join(normalized_lines)


def build_context_from_feishu(raw_input_path: str | Path, output_dir: str | Path, context_file_name: str = "context.json", transcript_file_name: str = "transcript.txt") -> dict[str, Any]:
    raw = read_json(raw_input_path)
    participants = list(raw.get("participants") or [])
    crm_binding = raw.get("crm_binding") or {}
    existing_customer_fields = get_object_value(crm_binding, "existing_customer_fields", {}) or {}
    company_name = get_object_value(crm_binding, "company_name")
    owner = get_object_value(crm_binding, "owner")
    split_external_contacts, split_internal_contacts = split_participants_by_identity(participants, company_name=company_name, owner=owner)
    external_contacts = dedupe_contacts(split_external_contacts)
    internal_contacts = dedupe_contacts(split_internal_contacts)
    external_participant = external_contacts[0] if external_contacts else None
    internal_participant = internal_contacts[0] if internal_contacts else None
    transcript_text = get_transcript_text(raw)

    customer_name = get_object_value(crm_binding, "customer_name")
    if customer_name is None and external_participant is not None:
        customer_name = external_participant.get("name")
    if company_name is None and external_participant is not None:
        company_name = external_participant.get("company")
    if owner is None and internal_participant is not None:
        owner = internal_participant.get("name")
    industry = get_object_value(crm_binding, "industry")
    if industry is None and external_participant is not None:
        industry = external_participant.get("industry")

    transcript_text = normalize_transcript_speakers(transcript_text, owner=owner, customer_name=customer_name)

    meeting = raw.get("meeting") or {}
    calendar = raw.get("calendar") or {}
    context = OrderedDict([
        ("customer_id", get_object_value(crm_binding, "customer_id")),
        ("customer_name", customer_name),
        ("company_name", company_name),
        ("owner", owner),
        ("industry", industry),
        ("external_contacts", external_contacts),
        ("internal_contacts", internal_contacts),
        ("opportunity_id", get_object_value(crm_binding, "opportunity_id")),
        ("current_stage", get_object_value(crm_binding, "current_stage", "未知")),
        ("sales_region", get_object_value(crm_binding, "sales_region")),
        ("meeting_time", meeting.get("start_time")),
        ("next_meeting_time", calendar.get("next_meeting_time")),
        ("channel", "飞书会议纪要导入"),
        ("source_meeting_id", meeting.get("meeting_id")),
        ("source_event_id", meeting.get("calendar_event_id")),
        ("source_title", meeting.get("title")),
        ("existing_customer_fields", existing_customer_fields),
    ])

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    context_path = output / context_file_name
    transcript_path = output / transcript_file_name
    write_json(context_path, context)
    write_text(transcript_path, transcript_text)

    result = OrderedDict([
        ("raw_input_path", resolve_str(raw_input_path)),
        ("generated_context", resolve_str(context_path)),
        ("generated_transcript", resolve_str(transcript_path)),
    ])
    write_json(output / "build_result.json", result)
    return result


def process_transcript(transcript_path: str | Path, context_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    context = read_json(context_path)
    transcript = read_text(transcript_path)
    lines = get_lines(transcript)
    company_name = get_object_value(context, "company_name")
    industry_name = get_object_value(context, "industry")
    source_channel = get_object_value(context, "channel", "手动导入")
    existing_customer_fields = get_object_value(context, "existing_customer_fields", {}) or {}
    external_contacts = [item for item in (get_object_value(context, "external_contacts", []) or []) if isinstance(item, dict)]
    internal_contacts = [item for item in (get_object_value(context, "internal_contacts", []) or []) if isinstance(item, dict)]
    external_names = [str(item.get("name") or "").strip() for item in external_contacts if str(item.get("name") or "").strip()]
    internal_names = [str(item.get("name") or "").strip() for item in internal_contacts if str(item.get("name") or "").strip()]

    def line_speaker(line: str) -> str | None:
        match = re.match(r"^([^：:]+)[：:](.*)$", line)
        return match.group(1).strip() if match else None

    def line_content(line: str) -> str:
        match = re.match(r"^([^：:]+)[：:](.*)$", line)
        return match.group(2).strip() if match else str(line).strip()

    def clean_text_value(text: Any) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip(" ；;，,。\n\t")

    def dedupe_texts(values: list[Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = clean_text_value(value)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
        return result

    def shorten_content(text: str, max_len: int = 34) -> str:
        cleaned = clean_text_value(text)
        return cleaned if len(cleaned) <= max_len else f"{cleaned[:max_len].rstrip()}…"

    def summarize_line(line: str, max_len: int = 28) -> str:
        speaker = line_speaker(line)
        content = shorten_content(line_content(line), max_len=max_len)
        if speaker and content:
            return f"{speaker}：{content}"
        return content or clean_text_value(line)

    def summarize_lines(lines_list: list[str], max_items: int = 3, max_len: int = 28) -> list[str]:
        return dedupe_texts([summarize_line(item, max_len=max_len) for item in lines_list[:max_items]])

    def detect_budget_phrase(text: str) -> str | None:
        patterns = [
            r"([0-9一二三四五六七八九十百千万\.]+\s*[万Ww])\s*以内",
            r"控制在\s*([0-9一二三四五六七八九十百千万\.]+\s*[万Ww])\s*以内",
            r"([0-9一二三四五六七八九十百千万\.]+\s*[万Ww])\s*以上",
            r"([0-9一二三四五六七八九十百千万\.]+\s*[万Ww])\s*[到至-]\s*([0-9一二三四五六七八九十百千万\.]+\s*[万Ww])",
            r"预算[^。；;，,]{0,20}?([0-9一二三四五六七八九十百千万\.]+\s*[万Ww])",
        ]
        cleaned = clean_text_value(text)
        for pattern in patterns:
            match = re.search(pattern, cleaned)
            if not match:
                continue
            groups = [clean_text_value(g) for g in match.groups() if g]
            if "以内" in match.group(0):
                return f"预算控制在{groups[0]}以内"
            if "以上" in match.group(0):
                return f"预算下限约{groups[0]}"
            if len(groups) >= 2:
                return f"预算区间约{groups[0]}-{groups[1]}"
            if groups:
                return f"预算参考值约{groups[0]}"
        return None

    def build_need_summary(lines_list: list[str], business_value: str | None = None) -> list[str]:
        summaries: list[str] = []
        joined = " ".join(lines_list)
        if re.search("问题单|流转|闭环|周报|回访", joined):
            summaries.append("先梳理问题单流转、回访、周报与异常闭环流程")
        if re.search("角色|权限|谁能看|谁能改|谁能导出|数据隔离", joined):
            summaries.append("明确服务站、区域、总部与质控的角色权限边界")
        if re.search("一页纸|简版|不要十几页|核心流程节点|权限表", joined):
            summaries.append("先提供一页纸结论、权限表和核心流程节点")
        if re.search("录入太复杂|培训周期|三步以内|现场处理节奏", joined):
            summaries.append("一线录入尽量轻量，避免影响现场处理节奏")
        budget_summary = detect_budget_phrase(joined)
        if budget_summary is not None:
            summaries.append(budget_summary)
        elif business_value:
            summaries.append(f"预算口径先按{business_value}控制")
        return dedupe_texts(summaries)[:4]

    def build_concern_summary(concern_lines_list: list[str], risk_labels: list[str]) -> list[str]:
        summaries: list[str] = []
        for label in risk_labels:
            mapping = {
                "价格敏感": "客户对一期投入与范围控制较敏感",
                "交付风险": "客户担心交付复杂度和上线推进风险",
                "合规与数据安全": "客户重点关注权限、数据隔离与合规边界",
                "效果不确定": "客户希望先验证阶段价值，避免一次性铺太大",
                "时间窗口紧张": "客户希望尽快推进并收敛下一轮决策时间",
            }
            if label in mapping:
                summaries.append(mapping[label])
        if not summaries and concern_lines_list:
            summaries.extend(summarize_lines(concern_lines_list, max_items=2, max_len=24))
        return dedupe_texts(summaries)[:3]

    def build_next_step_summary(next_lines: list[str], stage: str) -> list[str]:
        joined = " ".join(next_lines)
        summaries: list[str] = []
        if re.search("一页纸|简版|权限表|核心流程节点", joined):
            summaries.append("先发一页纸结论、角色权限表和核心流程节点")
        if re.search("邮箱|邮件", joined):
            summaries.append("正式说明材料通过邮件发送，简版可先用即时消息同步")
        if re.search("下周三|内部会|再拉一轮", joined):
            summaries.append("下周三前完成需求边界收敛并准备内部会")
        if re.search("报价|正式报价", joined):
            summaries.append("在边界和优先级明确前暂不推进正式报价")
        default_map = {
            "已成交": "转入启动会、交付排期和验收准备",
            "待成交": "锁定合同、付款节点和签约排期",
            "推进中": "继续跟进关键角色并收敛实施边界",
            "方案沟通": "补齐方案与报价材料并确认下轮沟通",
            "需求确认": "补齐需求边界并推动进入方案沟通",
            "初次接触": "先发简版总结并继续培育意向",
        }
        if not summaries:
            summaries.append(default_map[stage])
        return dedupe_texts(summaries)[:3]

    def build_recommended_action(contact_names: list[str], next_step_summaries: list[str], stage: str) -> str:
        target = "、".join(contact_names) if contact_names else "客户"
        if next_step_summaries:
            if len(contact_names) > 1:
                return f"向{target}同步会议结论，并{join_values(next_step_summaries[:2], '按约定推进下一步')}"
            return f"向{target}同步会议结论，并{join_values(next_step_summaries[:2], '按约定推进下一步')}"
        default_map = {
            "已成交": "切换到交付执行节奏，确认启动会、责任分工与阶段验收安排",
            "待成交": "推动最终确认并准备签约/付款材料",
            "推进中": "整理推进清单，锁定关键角色并跟进采购/法务节点",
            "方案沟通": "24小时内发送定制方案/报价并确认下一次沟通",
            "需求确认": "补齐关键需求信息并推动进入方案讨论",
            "初次接触": "发送简洁会后摘要并继续培育客户意向",
        }
        return default_map[stage]

    customer_lines = [line for line in lines if line_speaker(line) in external_names]
    if not customer_lines:
        customer_lines = [line for line in lines if re.search(r"^(客户|张总|陈女士|刘总|孙总|客户A|客户B|客户C|客户D)[:：]", line)]
    if not customer_lines:
        customer_lines = lines[:]
    all_text = " ".join(lines)
    customer_text = " ".join(customer_lines)

    need_lines = get_matched_lines(customer_lines, ["希望", "想", "需要", "重点", "最好", "计划", "目标", "关注", "更在意", "最大的痛点", "先了解", "有意思"])
    concern_lines = get_matched_lines(customer_lines, ["担心", "顾虑", "怕", "不太喜欢", "不喜欢", "不希望", "合规", "隐私", "安全", "风险", "别太复杂", "不要太长", "别搞太重", "培训周期不要太长"])
    next_action_lines = get_matched_lines(lines, ["下周", "下次", "再约", "安排", "发我", "发邮件", "邮箱", "邮件", "报价", "方案", "演示", "见面", "周一", "周二", "周三", "周四", "周五", "今晚", "明天", "试点"])

    risk_concern_map = OrderedDict([
        ("价格敏感", "预算|价格|成本|报价"),
        ("交付风险", "实施|交付|上线|周期拖长|培训周期"),
        ("合规与数据安全", "合规|数据安全|权限|隐私|资金进出"),
        ("效果不确定", "效果|ROI|值不值|产出"),
        ("时间窗口紧张", "本周|下周|本月|月底|季度内|尽快|周五之前|明天"),
    ])
    communication_style_map = OrderedDict([
        ("偏好微信触达", "微信"),
        ("偏好简洁表达", "简洁|不要太长|别太长|三点结论|直接"),
        ("偏好先看材料", "先发|先看|发我|材料|方案发我|清单"),
        ("偏好多方共同沟通", "一起看|一起聊|都参与|拉上"),
        ("偏好邮件接收", "发邮件|发我邮箱|邮箱给我|邮件给我|今晚发我邮箱"),
    ])
    decision_signal_map = OrderedDict([
        ("本人为关键决策人", "我本人会盯|我来拍板|我定|我决定|先跟我沟通"),
        ("家庭共同决策", "我先生|我太太|先生会一起看|太太也会看"),
        ("企业多角色决策", "CFO|CTO|采购|法务|财务总监|运营负责人|董事会|合伙人|信息科技|质控负责人"),
        ("明确预算", "预算|金额超过"),
        ("明确时间表", "下周|本周|本月|月底|季度内|明天|周五之前|六月底前|下周一|下周三|下周四"),
    ])
    risk_concerns = get_labels(customer_text, risk_concern_map)
    communication_style = get_labels(customer_text, communication_style_map)
    decision_signals = get_labels(customer_text, decision_signal_map)

    budget_max = parse_budget_max(customer_text)

    meeting_time = parse_datetime(get_object_value(context, "meeting_time"))
    next_meeting_time = parse_datetime(get_object_value(context, "next_meeting_time"))
    sales_region = get_sales_region(context, all_text)
    business_value = get_business_value_or_default(all_text)

    opportunity_stage = "初次接触"
    if re.search("已成交|正式成交|成交确认|合同(这周)?已经签完|合同今天上午已经完成双方签署|完成双方签署|签署完成|双方法务盖章|项目已经正式敲定|金额.*已经锁定|这笔商机就按正式成交记录", customer_text):
        opportunity_stage = "已成交"
    elif re.search("合同|签约|付款|定稿", customer_text):
        opportunity_stage = "待成交"
    elif re.search("采购|法务|上线一期", customer_text):
        opportunity_stage = "推进中"
    elif re.search("先把需求对齐|先确认需求|先把边界梳理清楚|先确认范围|先把流程梳理清楚|先做需求确认|先把需求确认完整", customer_text):
        opportunity_stage = "需求确认"
    elif re.search("报价|演示|实施清单|字段清单|保守版|平衡版", customer_text):
        opportunity_stage = "方案沟通"
    elif need_lines:
        opportunity_stage = "需求确认"

    lead_score = calculate_lead_score(
        opportunity_stage,
        customer_text,
        all_text,
        budget_max,
        next_meeting_time,
        decision_signals,
        risk_concerns,
    )
    intent_level = "high" if lead_score >= 75 else ("medium" if lead_score >= 60 else "low")
    if intent_level == "low" and opportunity_stage == "初次接触":
        opportunity_stage = "初次接触"

    high_value_flag = (
        lead_score >= 75
        or budget_max >= 80
        or bool(re.search("家族办公室|资产配置|两家工厂|集团|高净值", all_text))
        or bool(re.search("家族办公室", str(get_object_value(context, "industry", ""))))
    )

    follow_up_time = next_meeting_time if next_meeting_time is not None else (meeting_time + timedelta(days=2) if meeting_time else None)

    contact_lines_map: OrderedDict[str, list[str]] = OrderedDict()
    for name in external_names:
        contact_lines_map[name] = [line for line in lines if line_speaker(line) == name]
    if not contact_lines_map:
        fallback_name = str(get_object_value(context, "customer_name") or "客户").strip() or "客户"
        contact_lines_map[fallback_name] = customer_lines[:]

    aggregated_contact_names = "、".join(external_names) if external_names else str(get_object_value(context, "customer_name") or "客户")
    shared_customer_id = str(get_object_value(context, "customer_id") or "").strip() or None
    need_summaries = build_need_summary(need_lines, business_value=business_value)
    concern_summaries = build_concern_summary(concern_lines, risk_concerns)
    next_step_summaries = build_next_step_summary(next_action_lines, opportunity_stage)
    recommended_action = build_recommended_action(external_names, next_step_summaries, opportunity_stage)
    channel = "邮件" if "偏好邮件接收" in communication_style else ("微信" if "偏好微信触达" in communication_style else "飞书消息")

    summary_parts = [
        f"{aggregated_contact_names}本次会议已完成需求梳理",
        f"当前重点是{join_values(need_summaries[:2], '补充关键需求信息')}",
        f"主要顾虑包括{join_values(concern_summaries[:2], '暂无明显新增顾虑')}",
        f"下一步建议{join_values(next_step_summaries[:2], recommended_action)}",
    ]
    summary = "；".join(summary_parts) + "。"
    mbti = infer_mbti(all_text)
    single_status = infer_single_status(customer_text)
    resistance_level = infer_resistance_level(opportunity_stage, risk_concerns, customer_text)
    price_sensitivity = infer_price_sensitivity(customer_text, risk_concerns, budget_max)
    latest_progress = f"本次会议后，客户处于{opportunity_stage}阶段，Lead Score {lead_score}。当前建议：{join_values(next_step_summaries[:2], recommended_action)}。"

    opportunity_theme = infer_opportunity_theme(
        get_object_value(context, "source_title"),
        all_text,
        company_name,
        aggregated_contact_names,
    )
    if company_name:
        opportunity_name = f"{company_name} - {opportunity_theme}"
    else:
        opportunity_name = opportunity_theme
    opportunity_description = {
        "已成交": "客户已完成合同签署或成交确认，当前重点已转向项目启动、交付排期与阶段验收。",
        "待成交": "客户已进入合同/定稿推进阶段，重点是锁定签约前材料与排期。",
        "推进中": "客户已进入多角色内部推进阶段，需同步采购、法务或实施边界。",
        "方案沟通": "客户已进入方案、报价或演示讨论阶段，正在细化可落地方案。",
        "需求确认": "客户已明确核心需求与约束条件，下一步应推动进入方案沟通。",
        "初次接触": "客户当前仍处于接触或观察阶段，适合继续培育与补充需求理解。",
    }[opportunity_stage]

    discussion_points = need_summaries[:]
    if business_value and not any(business_value in item for item in discussion_points):
        discussion_points.append(f"预算口径：{business_value}")
    key_points = dedupe_texts(need_summaries[:2] + next_step_summaries[:2])
    commitments = next_step_summaries[:3]
    meeting_id_suffix = meeting_time.strftime("%Y%m%d%H%M") if meeting_time else "unknown"
    meeting_customer_id = get_object_value(context, "customer_id") or "multi"

    meeting_record = OrderedDict([
        ("meeting_id", f"MTG-{meeting_customer_id}-{meeting_id_suffix}"),
        ("customer_id", get_object_value(context, "customer_id")),
        ("customer_name", aggregated_contact_names),
        ("customer_names", external_names),
        ("company_name", company_name),
        ("meeting_time", isoformat_or_none(meeting_time)),
        ("summary", summary),
        ("discussion_points", discussion_points),
        ("customer_needs", need_lines),
        ("customer_concerns", concern_lines),
        ("next_actions", next_action_lines),
        ("commitments", commitments),
    ])

    customer_profile_updates: list[OrderedDict[str, Any]] = []
    customer_table_rows: list[OrderedDict[str, Any]] = []
    customer_preserved_fields_map: OrderedDict[str, list[str]] = OrderedDict()
    for index, contact in enumerate(external_contacts or [{"name": get_object_value(context, "customer_name"), "company": company_name, "industry": industry_name}]):
        contact_name = str(contact.get("name") or "").strip() or f"联系人{index + 1}"
        contact_company = str(contact.get("company") or company_name or "").strip() or company_name
        contact_industry = str(contact.get("industry") or industry_name or "").strip() or industry_name
        contact_role = str(contact.get("role") or "").strip()
        scoped_lines = contact_lines_map.get(contact_name, customer_lines)
        scoped_text = " ".join(scoped_lines) if scoped_lines else customer_text
        scoped_mbti = infer_mbti(scoped_text or all_text)
        scoped_single_status = infer_single_status(scoped_text or customer_text)
        scoped_risk_concerns = get_labels(scoped_text or customer_text, risk_concern_map) or risk_concerns
        scoped_communication_style = get_labels(scoped_text or customer_text, communication_style_map) or communication_style
        scoped_resistance_level = infer_resistance_level(opportunity_stage, scoped_risk_concerns, scoped_text or customer_text)
        scoped_price_sensitivity = infer_price_sensitivity(scoped_text or customer_text, scoped_risk_concerns, budget_max)
        scoped_profile_summary = build_customer_profile_summary(
            contact_name,
            opportunity_stage,
            scoped_mbti,
            scoped_single_status,
            join_values(scoped_communication_style, "常规沟通"),
            scoped_resistance_level,
            scoped_price_sensitivity,
            join_values(scoped_risk_concerns, "暂无明显风险顾虑"),
        )
        resolved_customer_id = shared_customer_id or stable_crm_id("C", contact_company, contact_name)
        profile_update = OrderedDict([
            ("customer_id", resolved_customer_id),
            ("customer_name", contact_name),
            ("company_name", contact_company),
            ("industry", contact_industry),
            ("mbti", scoped_mbti),
            ("single_status", scoped_single_status),
            ("resistance_level", scoped_resistance_level),
            ("price_sensitivity", scoped_price_sensitivity),
            ("risk_concerns", scoped_risk_concerns),
            ("communication_style", scoped_communication_style),
            ("profile_summary", scoped_profile_summary),
        ])
        customer_profile_updates.append(profile_update)

        row_existing_fields = existing_customer_fields
        if isinstance(existing_customer_fields, dict) and any(isinstance(v, dict) for v in existing_customer_fields.values()):
            composite_key = f"{contact_name}||{contact_company or ''}"
            row_existing_fields = existing_customer_fields.get(composite_key) or existing_customer_fields.get(contact_name) or {}
        customer_table_row = OrderedDict([
            ("客户ID", resolved_customer_id),
            ("客户名称", contact_name),
            ("客户公司", contact_company),
            ("职务", contact_role),
            ("行业", contact_industry),
            ("MBTI", profile_update["mbti"]),
            ("是否单身", profile_update["single_status"]),
            ("沟通风格", join_values(profile_update["communication_style"])),
            ("成交阻力", profile_update["resistance_level"]),
            ("价格敏感程度", profile_update["price_sensitivity"]),
            ("风险顾虑", join_values(profile_update["risk_concerns"])),
            ("客户画像摘要", profile_update["profile_summary"]),
            ("客户负责人", get_object_value(context, "owner")),
            ("最后更新时间", isoformat_or_none(meeting_time)),
            ("数据来源", source_channel),
        ])
        customer_table_row, preserved_customer_fields = merge_row_preserving_existing_values(customer_table_row, row_existing_fields)
        customer_table_row["客户画像摘要"] = build_customer_profile_summary(
            customer_table_row.get("客户名称"),
            opportunity_stage,
            customer_table_row.get("MBTI"),
            customer_table_row.get("是否单身"),
            customer_table_row.get("沟通风格"),
            customer_table_row.get("成交阻力"),
            customer_table_row.get("价格敏感程度"),
            customer_table_row.get("风险顾虑"),
        )
        customer_table_rows.append(customer_table_row)
        customer_preserved_fields_map[f"{contact_name}||{contact_company or ''}"] = preserved_customer_fields

    draft_message = (
        f"{aggregated_contact_names} 您好，今天沟通内容我先帮您收个简版：\n"
        f"1. 当前重点：{join_values(need_summaries[:2], '核心需求已记录')}。\n"
        f"2. 重点关注：{join_values(concern_summaries[:2], '本次暂无突出顾虑')}。\n"
        f"3. 下一步安排：{join_values(next_step_summaries[:2], recommended_action)}。\n"
        f"我会先通过{channel}发您精简版材料，您看完后我们再按约定时间推进。"
    )
    brief_trigger = next_meeting_time - timedelta(hours=1) if next_meeting_time is not None else None
    opening_focus_items = need_summaries[:2]
    opening_concern_items = concern_summaries[:2]
    opening_next_items = next_step_summaries[:2]

    if opening_focus_items:
        opening_focus_text = "、".join(opening_focus_items)
        opening_focus_sentence = f"这次先围绕{opening_focus_text}来对齐。"
    else:
        opening_focus_sentence = "这次先围绕当前核心需求来对齐。"

    if opening_concern_items:
        opening_concern_text = "、".join(opening_concern_items)
        opening_concern_sentence = f"重点回应{opening_concern_text}。"
    else:
        opening_concern_sentence = "重点回应当前推进中的关键顾虑。"

    if opening_next_items:
        opening_next_text = "，再".join([opening_next_items[0], *opening_next_items[1:]])
        opening_next_sentence = f"会后先{opening_next_text}。"
    else:
        opening_next_sentence = f"会后按{recommended_action}继续推进。"

    opening_script = f"{opening_focus_sentence}{opening_concern_sentence}{opening_next_sentence}"

    resolved_opportunity_id = str(get_object_value(context, "opportunity_id") or "").strip() or stable_crm_id("O", company_name, opportunity_theme)
    opportunity_update = OrderedDict([
        ("opportunity_id", resolved_opportunity_id),
        ("opportunity_name", opportunity_name),
        ("opportunity_description", opportunity_description),
        ("sales_region", sales_region),
        ("business_value", business_value),
        ("lead_score", lead_score),
        ("intent_level", intent_level),
        ("opportunity_stage", opportunity_stage),
        ("high_value_flag", bool(high_value_flag)),
        ("recommended_action", recommended_action),
        ("next_follow_up_at", isoformat_or_none(follow_up_time)),
        ("latest_progress", latest_progress),
    ])
    follow_up_task = OrderedDict([
        ("task_title", f"跟进 {aggregated_contact_names} - {opportunity_stage}"),
        ("owner", get_object_value(context, "owner")),
        ("due_at", isoformat_or_none(follow_up_time)),
        ("channel", channel),
        ("draft_message", draft_message),
        ("checklist", ["确认客户核心需求是否完整记录", "按推荐动作发送材料或推进下一次沟通", "更新飞书多维表格中的商机状态"]),
    ])
    pre_meeting_brief = OrderedDict([
        ("next_meeting_at", isoformat_or_none(next_meeting_time)),
        ("trigger_at", isoformat_or_none(brief_trigger)),
        ("headline", f"{aggregated_contact_names} 会前行动简报"),
        ("opening_script", opening_script),
        ("key_points", key_points),
        ("watchouts", concern_summaries[:]),
        ("materials_to_prepare", ["客户画像摘要", "上次会议结论", "与本次需求对应的方案/案例/报价材料"]),
    ])
    opportunity_snapshot_row = OrderedDict([
        ("商机ID", resolved_opportunity_id),
        ("客户ID", join_values([row.get("客户ID") for row in customer_table_rows if row.get("客户ID")], "")),
        ("客户名称", aggregated_contact_names),
        ("客户公司", company_name),
        ("机会名称", opportunity_update["opportunity_name"]),
        ("商机描述", opportunity_update["opportunity_description"]),
        ("当前阶段", opportunity_update["opportunity_stage"]),
        ("Lead Score", opportunity_update["lead_score"]),
        ("意向等级", opportunity_update["intent_level"]),
        ("高净值优先", opportunity_update["high_value_flag"]),
        ("销售区域", opportunity_update["sales_region"]),
        ("业务价值", opportunity_update["business_value"]),
        ("推荐动作", opportunity_update["recommended_action"]),
        ("最新进展", opportunity_update["latest_progress"]),
        ("下次跟进时间", opportunity_update["next_follow_up_at"]),
        ("最近会议时间", meeting_record["meeting_time"]),
        ("商机负责人", get_object_value(context, "owner")),
        ("数据来源", source_channel),
    ])
    customer_table_row = customer_table_rows[0] if customer_table_rows else OrderedDict()
    customer_profile_update = customer_profile_updates[0] if customer_profile_updates else OrderedDict()
    preserved_customer_fields = next(iter(customer_preserved_fields_map.values()), [])
    feishu_payload = OrderedDict([
        ("customer_table", [OrderedDict([("mode", "upsert"), ("key_field", "客户ID (fallback: 客户名称+客户公司)"), ("key", str(row.get("客户ID") or "").strip() or f"{row.get('客户名称', '')}||{row.get('客户公司', '')}"), ("update_fields", row)]) for row in customer_table_rows]),
        ("opportunity_snapshot_table", OrderedDict([("mode", "append"), ("append_row", opportunity_snapshot_row)])),
    ])
    crm_packet = OrderedDict([
        ("input", OrderedDict([("transcript_path", resolve_str(transcript_path)), ("context_path", resolve_str(context_path)), ("customer_id", get_object_value(context, "customer_id")), ("opportunity_id", get_object_value(context, "opportunity_id"))])),
        ("meeting", meeting_record),
        ("customer_profile_update", customer_profile_update),
        ("customer_profile_updates", customer_profile_updates),
        ("opportunity_update", opportunity_update),
        ("follow_up_task", follow_up_task),
        ("pre_meeting_brief", pre_meeting_brief),
        ("customer_table_row", customer_table_row),
        ("customer_table_rows", customer_table_rows),
        ("customer_preserved_fields", preserved_customer_fields),
        ("customer_preserved_fields_map", customer_preserved_fields_map),
        ("opportunity_snapshot_row", opportunity_snapshot_row),
        ("feishu_bitable_payload", feishu_payload),
    ])

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "meeting_record.json", meeting_record)
    write_json(output / "customer_profile_update.json", customer_profile_update)
    write_json(output / "customer_profile_updates.json", customer_profile_updates)
    write_json(output / "opportunity_update.json", opportunity_update)
    write_json(output / "follow_up_task.json", follow_up_task)
    write_json(output / "pre_meeting_brief.json", pre_meeting_brief)
    write_json(output / "customer_table_row.json", customer_table_row)
    write_json(output / "customer_table_rows.json", customer_table_rows)
    write_json(output / "opportunity_snapshot_row.json", opportunity_snapshot_row)
    write_json(output / "crm_packet.json", crm_packet)
    return crm_packet


def build_example_block(example: dict[str, Any]) -> str:
    return "\r\n".join([
        f"### 示例：{example['name']}",
        f"任务提示：{example['task_hint']}",
        "",
        "输入 context:",
        "```json",
        json.dumps(example["input"]["context"], ensure_ascii=False, indent=2),
        "```",
        "",
        "输入 transcript:",
        "```text",
        example["input"]["transcript"],
        "```",
        "",
        "参考输出:",
        "```json",
        json.dumps(example["output"], ensure_ascii=False, indent=2),
        "```",
    ])


def build_llm_prompt(transcript_path: str | Path, context_path: str | Path, output_dir: str | Path, example_names: list[str] | None = None) -> dict[str, Any]:
    names = example_names or ["zhongguoyidong_ops_rich", "ningdeshidai_service_rich"]
    template = read_text(skill_root() / "references" / "llm_prompt_template.md")
    schema = read_text(skill_root() / "references" / "llm_output_schema.md")
    context_json = read_text(context_path)
    transcript_text = read_text(transcript_path)
    example_blocks = [build_example_block(read_json(skill_root() / "assets" / "few_shot" / f"{name}.json")) for name in names]
    system_prompt = "\r\n".join([template, "", "以下是输出 schema，请严格遵守：", "", schema]).strip()
    user_prompt = "\r\n".join([
        "以下是 few-shot 示例，请学习其抽取方式、阶段判断标准和输出风格：",
        "",
        "\r\n\r\n".join(example_blocks),
        "",
        "现在请处理新的输入。",
        "",
        "输入 context:",
        "```json",
        context_json,
        "```",
        "",
        "输入 transcript:",
        "```text",
        transcript_text,
        "```",
        "",
        "请只输出 JSON，不要输出解释。",
    ]).strip()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prompt_package = OrderedDict([
        ("system_prompt", system_prompt),
        ("user_prompt", user_prompt),
        ("examples", names),
        ("transcript_path", resolve_str(transcript_path)),
        ("context_path", resolve_str(context_path)),
    ])
    write_json(output / "prompt_package.json", prompt_package)
    write_text(output / "system_prompt.txt", system_prompt)
    write_text(output / "user_prompt.txt", user_prompt)
    return prompt_package


def assert_has_property(obj: dict[str, Any], property_name: str, scope: str) -> None:
    if obj is None:
        raise ValueError(f"Missing object [{scope}] in model output.")
    if property_name not in obj:
        raise ValueError(f"Missing property [{scope}.{property_name}] in model output.")


def validate_datetime(value: Any, field_name: str) -> None:
    if value is None or not str(value).strip():
        return
    try:
        datetime.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Invalid datetime in [{field_name}]: {value}") from exc


def validate_model_output(model_output_path: str | Path) -> dict[str, Any]:
    model = read_json(model_output_path)
    customer_profile_scope = "customer_profile_updates" if "customer_profile_updates" in model else "customer_profile_update"
    for top in ["meeting", customer_profile_scope, "opportunity_update", "follow_up_task", "pre_meeting_brief"]:
        assert_has_property(model, top, "root")
    for field in ["customer_id", "customer_name", "company_name", "meeting_time", "summary"]:
        assert_has_property(model["meeting"], field, "meeting")
    primary_profile = (model.get("customer_profile_updates") or [model.get("customer_profile_update")])[0]
    for field in ["customer_id", "company_name", "industry", "mbti", "single_status", "resistance_level", "price_sensitivity", "profile_summary"]:
        assert_has_property(primary_profile, field, customer_profile_scope)
    for field in ["opportunity_id", "opportunity_name", "opportunity_description", "sales_region", "business_value", "lead_score", "intent_level", "opportunity_stage", "high_value_flag", "recommended_action", "latest_progress"]:
        assert_has_property(model["opportunity_update"], field, "opportunity_update")
    for field in ["task_title", "owner", "channel", "draft_message", "checklist"]:
        assert_has_property(model["follow_up_task"], field, "follow_up_task")
    for field in ["headline", "opening_script", "key_points", "watchouts", "materials_to_prepare"]:
        assert_has_property(model["pre_meeting_brief"], field, "pre_meeting_brief")
    if model["opportunity_update"]["intent_level"] not in VALID_INTENT_LEVELS:
        raise ValueError(f"Invalid opportunity_update.intent_level: {model['opportunity_update']['intent_level']}")
    if model["opportunity_update"]["opportunity_stage"] not in VALID_STAGES:
        raise ValueError(f"Invalid opportunity_update.opportunity_stage: {model['opportunity_update']['opportunity_stage']}")
    channel = model["follow_up_task"].get("channel")
    if channel and channel not in VALID_CHANNELS:
        raise ValueError(f"Invalid follow_up_task.channel: {channel}")
    lead_score = int(model["opportunity_update"]["lead_score"])
    if lead_score < 0 or lead_score > 100:
        raise ValueError("lead_score must be between 0 and 100.")
    validate_datetime(model["meeting"].get("meeting_time"), "meeting.meeting_time")
    validate_datetime(model["opportunity_update"].get("next_follow_up_at"), "opportunity_update.next_follow_up_at")
    validate_datetime(model["follow_up_task"].get("due_at"), "follow_up_task.due_at")
    validate_datetime(model["pre_meeting_brief"].get("next_meeting_at"), "pre_meeting_brief.next_meeting_at")
    validate_datetime(model["pre_meeting_brief"].get("trigger_at"), "pre_meeting_brief.trigger_at")
    return model


def convert_model_output_to_crm(model_output_path: str | Path, output_dir: str | Path, context_path: str | Path | None = None) -> dict[str, Any]:
    model = validate_model_output(model_output_path)
    context = read_json(context_path) if context_path and Path(context_path).exists() else None
    source_channel = get_object_value(context, "channel", "LLM 结构化输出")
    owner = get_object_value(context, "owner", model["follow_up_task"]["owner"])
    existing_customer_fields = get_object_value(context, "existing_customer_fields", {}) or {}
    profile_updates = model.get("customer_profile_updates") or [model["customer_profile_update"]]
    customer_table_rows: list[OrderedDict[str, Any]] = []
    customer_preserved_fields_map: OrderedDict[str, list[str]] = OrderedDict()
    for profile in profile_updates:
        customer_name = get_object_value(profile, "customer_name", model["meeting"]["customer_name"])
        company_name = get_object_value(profile, "company_name", model["meeting"]["company_name"])
        row_existing_fields = existing_customer_fields
        if isinstance(existing_customer_fields, dict) and any(isinstance(v, dict) for v in existing_customer_fields.values()):
            row_existing_fields = existing_customer_fields.get(f"{customer_name}||{company_name or ''}") or existing_customer_fields.get(customer_name) or {}
        customer_table_row = OrderedDict([
            ("客户ID", profile["customer_id"]),
            ("客户名称", customer_name),
            ("客户公司", company_name),
            ("行业", profile["industry"]),
            ("MBTI", get_object_value(profile, "mbti", "未明确")),
            ("是否单身", get_object_value(profile, "single_status", "未明确")),
            ("沟通风格", join_values(profile.get("communication_style"))),
            ("成交阻力", get_object_value(profile, "resistance_level", "未明确")),
            ("价格敏感程度", get_object_value(profile, "price_sensitivity", "未明确")),
            ("风险顾虑", join_values(profile.get("risk_concerns"))),
            ("客户画像摘要", profile["profile_summary"]),
            ("客户负责人", owner),
            ("最后更新时间", model["meeting"]["meeting_time"]),
            ("数据来源", source_channel),
        ])
        customer_table_row, preserved_customer_fields = merge_row_preserving_existing_values(customer_table_row, row_existing_fields)
        customer_table_row["客户画像摘要"] = build_customer_profile_summary(
            customer_table_row.get("客户名称"),
            get_object_value(model["opportunity_update"], "opportunity_stage", "当前"),
            customer_table_row.get("MBTI"),
            customer_table_row.get("是否单身"),
            customer_table_row.get("沟通风格"),
            customer_table_row.get("成交阻力"),
            customer_table_row.get("价格敏感程度"),
            customer_table_row.get("风险顾虑"),
        )
        customer_table_rows.append(customer_table_row)
        customer_preserved_fields_map[f"{customer_name}||{company_name or ''}"] = preserved_customer_fields
    customer_table_row = customer_table_rows[0] if customer_table_rows else OrderedDict()
    preserved_customer_fields = next(iter(customer_preserved_fields_map.values()), []) if customer_preserved_fields_map else []
    opportunity_snapshot_row = OrderedDict([
        ("商机ID", model["opportunity_update"]["opportunity_id"]),
        ("客户ID", model["meeting"]["customer_id"]),
        ("客户名称", model["meeting"]["customer_name"]),
        ("客户公司", model["meeting"]["company_name"]),
        ("机会名称", model["opportunity_update"]["opportunity_name"]),
        ("商机描述", model["opportunity_update"]["opportunity_description"]),
        ("当前阶段", model["opportunity_update"]["opportunity_stage"]),
        ("Lead Score", model["opportunity_update"]["lead_score"]),
        ("意向等级", model["opportunity_update"]["intent_level"]),
        ("高净值优先", model["opportunity_update"]["high_value_flag"]),
        ("销售区域", model["opportunity_update"]["sales_region"]),
        ("业务价值", model["opportunity_update"]["business_value"]),
        ("推荐动作", model["opportunity_update"]["recommended_action"]),
        ("最新进展", model["opportunity_update"]["latest_progress"]),
        ("下次跟进时间", model["opportunity_update"].get("next_follow_up_at")),
        ("最近会议时间", model["meeting"]["meeting_time"]),
        ("商机负责人", owner),
        ("数据来源", source_channel),
    ])
    primary_profile = profile_updates[0]
    crm_packet = OrderedDict([
        ("input", OrderedDict([("model_output_path", resolve_str(model_output_path)), ("context_path", resolve_str(context_path) if context_path and Path(context_path).exists() else None)])),
        ("meeting", model["meeting"]),
        ("customer_profile_update", primary_profile),
        ("customer_profile_updates", profile_updates),
        ("opportunity_update", model["opportunity_update"]),
        ("follow_up_task", model["follow_up_task"]),
        ("pre_meeting_brief", model["pre_meeting_brief"]),
        ("customer_table_row", customer_table_row),
        ("customer_table_rows", customer_table_rows),
        ("customer_preserved_fields", preserved_customer_fields),
        ("customer_preserved_fields_map", customer_preserved_fields_map),
        ("opportunity_snapshot_row", opportunity_snapshot_row),
        (
            "feishu_bitable_payload",
            OrderedDict([
                (
                    "customer_table",
                    [
                        OrderedDict([
                            ("mode", "upsert"),
                            ("key_field", "客户ID (fallback: 客户名称+客户公司)"),
                            ("key", str(row.get("客户ID") or "").strip() or f"{row.get('客户名称', '')}||{row.get('客户公司', '')}"),
                            ("update_fields", row),
                        ])
                        for row in customer_table_rows
                    ],
                ),
                (
                    "opportunity_snapshot_table",
                    OrderedDict([
                        ("mode", "append"),
                        ("append_row", opportunity_snapshot_row),
                    ]),
                ),
            ]),
        ),
    ])
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "meeting_record.json", model["meeting"])
    write_json(output / "customer_profile_update.json", primary_profile)
    write_json(output / "customer_profile_updates.json", profile_updates)
    write_json(output / "opportunity_update.json", model["opportunity_update"])
    write_json(output / "follow_up_task.json", model["follow_up_task"])
    write_json(output / "pre_meeting_brief.json", model["pre_meeting_brief"])
    write_json(output / "customer_table_row.json", customer_table_row)
    write_json(output / "customer_table_rows.json", customer_table_rows)
    write_json(output / "opportunity_snapshot_row.json", opportunity_snapshot_row)
    write_json(output / "crm_packet.json", crm_packet)
    return crm_packet


def run_sample_tests(output_root: str | Path) -> None:
    sample_dir = skill_root() / "assets" / "samples"
    expected_dir = skill_root() / "assets" / "expected"
    context_files = sorted(sample_dir.glob("*_context.json"))
    if not context_files:
        print(f"[SKIP] No sample contexts found in {sample_dir}")
        return
    failures = 0
    checked = 0
    for context_file in context_files:
        sample_name = context_file.stem.replace("_context", "")
        transcript_path = sample_dir / f"{sample_name}_transcript.txt"
        expected_path = expected_dir / f"{sample_name}.json"
        out_dir = Path(output_root) / sample_name
        if not transcript_path.exists():
            raise FileNotFoundError(f"Missing transcript for sample {sample_name}")
        if not expected_path.exists():
            print(f"[SKIP] {sample_name} (missing expected assertion file)")
            continue
        checked += 1
        packet = process_transcript(transcript_path, context_file, out_dir)
        expected = read_json(expected_path)
        errors: list[str] = []
        if packet["opportunity_update"]["intent_level"] != expected["intent_level"]:
            errors.append(f"intent_level expected [{expected['intent_level']}] actual [{packet['opportunity_update']['intent_level']}]")
        if int(packet["opportunity_update"]["lead_score"]) < int(expected["min_lead_score"]):
            errors.append(f"lead_score expected >= {expected['min_lead_score']} actual [{packet['opportunity_update']['lead_score']}]")
        if packet["opportunity_update"]["opportunity_stage"] != expected["opportunity_stage"]:
            errors.append(f"opportunity_stage expected [{expected['opportunity_stage']}] actual [{packet['opportunity_update']['opportunity_stage']}]")
        if bool(packet["opportunity_update"]["high_value_flag"]) != bool(expected["high_value_flag"]):
            errors.append(f"high_value_flag expected [{expected['high_value_flag']}] actual [{packet['opportunity_update']['high_value_flag']}]")
        all_tags: list[str] = []
        customer_profile = packet["customer_profile_update"]
        scalar_tags = [
            customer_profile.get("mbti"),
            customer_profile.get("single_status"),
            customer_profile.get("resistance_level"),
            customer_profile.get("price_sensitivity"),
        ]
        for tag in scalar_tags:
            text = str(tag).strip() if tag is not None else ""
            if text and text not in all_tags:
                all_tags.append(text)
        for group in ["risk_concerns", "communication_style"]:
            for tag in customer_profile.get(group, []):
                if tag not in all_tags:
                    all_tags.append(tag)
        for tag in expected["required_tags"]:
            if tag not in all_tags:
                errors.append(f"missing required tag [{tag}]")
        required_channel = expected.get("required_channel")
        if required_channel and packet["follow_up_task"]["channel"] != required_channel:
            errors.append(f"required_channel expected [{required_channel}] actual [{packet['follow_up_task']['channel']}]")
        for snippet in expected["summary_must_include"]:
            if snippet not in packet["meeting"]["summary"]:
                errors.append(f"summary missing snippet [{snippet}]")
        if bool(expected["pre_meeting_should_exist"]) != bool(packet["pre_meeting_brief"].get("next_meeting_at")):
            errors.append(f"pre_meeting existence expected [{expected['pre_meeting_should_exist']}] actual [{bool(packet['pre_meeting_brief'].get('next_meeting_at'))}]")
        if errors:
            failures += 1
            print(f"[FAIL] {sample_name}")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"[PASS] {sample_name}")
    if checked == 0:
        print("[SKIP] No sample tests were executed because no expected assertion files were found.")
        return
    if failures:
        raise RuntimeError(f"{failures} sample test(s) failed.")


def run_feishu_pipeline_tests(output_root: str | Path) -> None:
    raw_dir = skill_root() / "assets" / "feishu_raw"
    expected_dir = skill_root() / "assets" / "expected"
    raw_files = sorted(raw_dir.glob("*.json"))
    if not raw_files:
        raise ValueError(f"No Feishu raw sample files found in {raw_dir}")
    failures = 0
    checked = 0
    for raw_file in raw_files:
        sample_name = raw_file.stem
        expected_path = expected_dir / f"{sample_name}.json"
        if not expected_path.exists():
            print(f"[SKIP] {sample_name} (missing expected assertion file)")
            continue
        checked += 1
        sample_output = Path(output_root) / sample_name
        build_output = sample_output / "build"
        process_output = sample_output / "process"
        build_context_from_feishu(raw_file, build_output)
        packet = process_transcript(build_output / "transcript.txt", build_output / "context.json", process_output)
        expected = read_json(expected_path)
        errors: list[str] = []
        if packet["opportunity_update"]["intent_level"] != expected["intent_level"]:
            errors.append(f"intent_level expected [{expected['intent_level']}] actual [{packet['opportunity_update']['intent_level']}]")
        if int(packet["opportunity_update"]["lead_score"]) < int(expected["min_lead_score"]):
            errors.append(f"lead_score expected >= {expected['min_lead_score']} actual [{packet['opportunity_update']['lead_score']}]")
        if packet["opportunity_update"]["opportunity_stage"] != expected["opportunity_stage"]:
            errors.append(f"opportunity_stage expected [{expected['opportunity_stage']}] actual [{packet['opportunity_update']['opportunity_stage']}]")
        if errors:
            failures += 1
            print(f"[FAIL] {sample_name}")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"[PASS] {sample_name}")
    if checked == 0:
        print("[SKIP] No Feishu pipeline tests were executed because no expected assertion files were found.")
        return
    if failures:
        raise RuntimeError(f"{failures} Feishu pipeline test(s) failed.")


def run_merge_policy_tests() -> None:
    existing_fields = {
        "客户名称": "李昊",
        "是否单身": "是",
        "MBTI": "ESTJ",
        "职务": "运营管理部项目经理",
        "价格敏感程度": "中",
        "沟通风格": "偏好微信触达；偏好邮件接收",
        "风险顾虑": "价格敏感；合规与数据安全",
    }
    current_row = OrderedDict([
        ("客户名称", "李昊"),
        ("是否单身", "未明确"),
        ("MBTI", "未明确"),
        ("职务", "运营管理部高级项目经理"),
        ("价格敏感程度", "未明确"),
        ("沟通风格", "偏好先看材料；偏好邮件接收"),
        ("风险顾虑", "交付风险；合规与数据安全"),
    ])
    merged, preserved_fields = merge_row_preserving_existing_values(current_row, existing_fields)
    expected = {
        "是否单身": "是",
        "MBTI": "ESTJ",
        "职务": "运营管理部高级项目经理",
        "价格敏感程度": "中",
        "沟通风格": "偏好微信触达；偏好邮件接收；偏好先看材料",
        "风险顾虑": "价格敏感；合规与数据安全；交付风险",
    }
    errors: list[str] = []
    for field_name, expected_value in expected.items():
        actual_value = merged.get(field_name)
        if actual_value != expected_value:
            errors.append(f"{field_name} expected [{expected_value}] actual [{actual_value}]")
    for field_name in ["是否单身", "MBTI", "价格敏感程度"]:
        if field_name not in preserved_fields:
            errors.append(f"{field_name} should be marked as preserved")
    theme_round1 = infer_opportunity_theme("中国平安龙虾盒子需求梳理会", "", "中国平安", "张琪、李昊")
    theme_round2 = infer_opportunity_theme("中国平安龙虾盒子方案沟通会", "", "中国平安", "张琪、李昊、王拓")
    opportunity_id_round1 = stable_crm_id("O", "中国平安", theme_round1)
    opportunity_id_round2 = stable_crm_id("O", "中国平安", theme_round2)
    if theme_round1 != "龙虾盒子":
        errors.append(f"round1 theme expected [龙虾盒子] actual [{theme_round1}]")
    if theme_round2 != "龙虾盒子":
        errors.append(f"round2 theme expected [龙虾盒子] actual [{theme_round2}]")
    if opportunity_id_round1 != opportunity_id_round2:
        errors.append(f"opportunity IDs should match for same project stages: {opportunity_id_round1} vs {opportunity_id_round2}")
    if errors:
        for error_item in errors:
            print(f"[FAIL] {error_item}")
        raise RuntimeError(f"{len(errors)} merge policy assertion(s) failed.")
    print("[PASS] merge policy preserves explicit customer fields and accepts explicit updates")
    print("[PASS] opportunity identity is stable across meeting-stage titles")


def run_model_output_tests(output_root: str | Path) -> None:
    model_dir = skill_root() / "runtime" / "llm_outputs"
    sample_dir = skill_root() / "assets" / "samples"
    model_files = sorted(model_dir.rglob("model_output.json"))
    if not model_files:
        raise ValueError(f"No model_output.json files found under {model_dir}")
    for model_file in model_files:
        sample_name = model_file.parent.name
        context_path = sample_dir / f"{sample_name}_context.json"
        out_dir = Path(output_root) / sample_name
        validate_model_output(model_file)
        packet = convert_model_output_to_crm(model_file, out_dir, context_path if context_path.exists() else None)
        if packet["feishu_bitable_payload"].get("customer_table") is None:
            raise RuntimeError(f"customer_table missing in {sample_name}")
        if packet["feishu_bitable_payload"].get("opportunity_snapshot_table") is None:
            raise RuntimeError(f"opportunity_snapshot_table missing in {sample_name}")
        print(f"[PASS] {sample_name}")


def run_customer_journey(manifest_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rounds: list[dict[str, Any]] = []
    for item in manifest["rounds"]:
        round_name = item["round_id"]
        context_path = skill_root() / item["context_path"]
        transcript_path = skill_root() / item["transcript_path"]
        round_output = output / round_name
        packet = process_transcript(transcript_path, context_path, round_output)
        rounds.append(OrderedDict([
            ("round_id", round_name),
            ("label", item["label"]),
            ("meeting_time", packet["meeting"]["meeting_time"]),
            ("lead_score", packet["opportunity_update"]["lead_score"]),
            ("intent_level", packet["opportunity_update"]["intent_level"]),
            ("opportunity_stage", packet["opportunity_update"]["opportunity_stage"]),
            ("high_value_flag", packet["opportunity_update"]["high_value_flag"]),
            ("recommended_action", packet["opportunity_update"]["recommended_action"]),
            ("summary", packet["meeting"]["summary"]),
            ("next_follow_up_at", packet["opportunity_update"]["next_follow_up_at"]),
        ]))
    sorted_rounds = sorted(rounds, key=lambda item: datetime.fromisoformat(item["meeting_time"]))
    progression_notes: list[str] = []
    for i, current in enumerate(sorted_rounds):
        if i == 0:
            progression_notes.append(f"第1轮为{current['label']}，阶段：{current['opportunity_stage']}，Lead Score {current['lead_score']}")
            continue
        previous = sorted_rounds[i - 1]
        delta = int(current["lead_score"]) - int(previous["lead_score"])
        direction = "提升" if delta > 0 else ("下降" if delta < 0 else "持平")
        delta_text = f" {delta}" if delta != 0 else ""
        progression_notes.append(f"{current['label']} 从 {previous['opportunity_stage']} -> {current['opportunity_stage']}，Lead Score {current['lead_score']}（{direction}{delta_text}）")
    journey = OrderedDict([
        ("customer_id", manifest["customer_id"]),
        ("customer_name", manifest["customer_name"]),
        ("opportunity_id", manifest["opportunity_id"]),
        ("total_rounds", len(sorted_rounds)),
        ("journey_theme", manifest["journey_theme"]),
        ("stage_path", [item["opportunity_stage"] for item in sorted_rounds]),
        ("latest_stage", sorted_rounds[-1]["opportunity_stage"]),
        ("latest_lead_score", sorted_rounds[-1]["lead_score"]),
        ("latest_intent", sorted_rounds[-1]["intent_level"]),
        ("progression_notes", progression_notes),
        ("rounds", sorted_rounds),
    ])
    write_json(output / "journey_summary.json", journey)
    return journey


def ingest_feishu_raw_to_bitable(
    raw_input_path: str | Path,
    output_dir: str | Path,
    config_path: str | Path | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
    app_token_or_url: str | None = None,
    customer_table_id: str | None = None,
    opportunity_table_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir)
    build_output = output / "build"
    process_output = output / "process"
    sync_output = output / "sync"

    build_result = build_context_from_feishu(raw_input_path, build_output)
    crm_packet = process_transcript(build_output / "transcript.txt", build_output / "context.json", process_output)
    sync_result = sync_crm_packet_to_feishu(
        process_output / "crm_packet.json",
        sync_output,
        config_path,
        app_id,
        app_secret,
        app_token_or_url,
        customer_table_id,
        opportunity_table_id,
        dry_run,
    )
    result = OrderedDict([
        ("raw_input_path", resolve_str(raw_input_path)),
        ("build_result_path", resolve_str(build_output / "build_result.json")),
        ("crm_packet_path", resolve_str(process_output / "crm_packet.json")),
        ("sync_result_path", resolve_str(sync_output / "feishu_sync_result.json")),
        ("customer_id", crm_packet["customer_table_row"].get("客户ID")),
        ("opportunity_id", crm_packet["opportunity_snapshot_row"].get("商机ID")),
        ("customer_action", sync_result.get("customer_action")),
        ("opportunity_action", sync_result.get("opportunity_action")),
    ])
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "ingest_result.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CRM Assistant Python CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("process-transcript")
    p.add_argument("--transcript-path", required=True)
    p.add_argument("--context-path", required=True)
    p.add_argument("--output-dir", required=True)

    p = sub.add_parser("build-context-from-feishu")
    p.add_argument("--raw-input-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--context-file-name", default="context.json")
    p.add_argument("--transcript-file-name", default="transcript.txt")

    p = sub.add_parser("build-context-from-feishu-doc")
    p.add_argument("--doc-markdown-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--raw-file-name", default="feishu_meeting_raw.json")
    p.add_argument("--context-file-name", default="context.json")
    p.add_argument("--transcript-file-name", default="transcript.txt")
    p.add_argument("--source-doc-url")
    p.add_argument("--fallback-title")

    p = sub.add_parser("ingest-docx-to-bitable")
    p.add_argument("--docx-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--source-doc-url")
    p.add_argument("--fallback-title")
    p.add_argument("--config-path")
    p.add_argument("--app-id")
    p.add_argument("--app-secret")
    p.add_argument("--app-token-or-url")
    p.add_argument("--customer-table-id")
    p.add_argument("--opportunity-table-id")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--sync-feishu", action="store_true")

    p = sub.add_parser("build-llm-prompt")
    p.add_argument("--transcript-path", required=True)
    p.add_argument("--context-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--example-names", nargs="*", default=["zhongguoyidong_ops_rich", "ningdeshidai_service_rich"])

    p = sub.add_parser("validate-model-output")
    p.add_argument("--model-output-path", required=True)

    p = sub.add_parser("convert-model-output")
    p.add_argument("--model-output-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--context-path")

    p = sub.add_parser("run-sample-tests")
    p.add_argument("--output-root", default=str(skill_root() / "runtime"))

    p = sub.add_parser("run-feishu-pipeline-tests")
    p.add_argument("--output-root", default=str(skill_root() / "runtime" / "feishu_pipeline_py"))

    p = sub.add_parser("run-model-output-tests")
    p.add_argument("--output-root", default=str(skill_root() / "runtime" / "from_model_py"))

    sub.add_parser("run-merge-policy-tests")

    p = sub.add_parser("run-customer-journey")
    p.add_argument("--manifest-path", required=True)
    p.add_argument("--output-dir", required=True)

    p = sub.add_parser("inspect-feishu-bitable")
    p.add_argument("--app-id")
    p.add_argument("--app-secret")
    p.add_argument("--app-token-or-url")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--table-id")

    p = sub.add_parser("sync-feishu-bitable")
    p.add_argument("--crm-packet-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--config-path")
    p.add_argument("--app-id")
    p.add_argument("--app-secret")
    p.add_argument("--app-token-or-url")
    p.add_argument("--customer-table-id")
    p.add_argument("--opportunity-table-id")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("ingest-feishu-raw-to-bitable")
    p.add_argument("--raw-input-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--config-path")
    p.add_argument("--app-id")
    p.add_argument("--app-secret")
    p.add_argument("--app-token-or-url")
    p.add_argument("--customer-table-id")
    p.add_argument("--opportunity-table-id")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("ingest-feishu-doc-to-bitable")
    p.add_argument("--doc-markdown-path", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--source-doc-url")
    p.add_argument("--fallback-title")
    p.add_argument("--config-path")
    p.add_argument("--app-id")
    p.add_argument("--app-secret")
    p.add_argument("--app-token-or-url")
    p.add_argument("--customer-table-id")
    p.add_argument("--opportunity-table-id")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--sync-feishu", action="store_true")
    return parser


def main() -> None:
    load_env_file()
    args = build_parser().parse_args()
    if args.command == "process-transcript":
        process_transcript(args.transcript_path, args.context_path, args.output_dir)
        print(f"CRM packet generated at: {args.output_dir}")
    elif args.command == "build-context-from-feishu":
        build_context_from_feishu(args.raw_input_path, args.output_dir, args.context_file_name, args.transcript_file_name)
        print(f"Feishu raw input converted at: {args.output_dir}")
    elif args.command == "build-context-from-feishu-doc":
        build_context_from_feishu_doc(
            args.doc_markdown_path,
            args.output_dir,
            args.raw_file_name,
            args.context_file_name,
            args.transcript_file_name,
            args.source_doc_url,
            args.fallback_title,
        )
        print(f"Feishu doc input converted at: {args.output_dir}")
    elif args.command == "ingest-docx-to-bitable":
        ingest_docx_to_bitable(
            args.docx_path,
            args.output_dir,
            args.source_doc_url,
            args.fallback_title,
            args.config_path,
            args.app_id,
            args.app_secret,
            args.app_token_or_url,
            args.customer_table_id,
            args.opportunity_table_id,
            args.dry_run,
            args.sync_feishu,
        )
        print(f"DOCX input fully converted at: {args.output_dir}")
    elif args.command == "build-llm-prompt":
        build_llm_prompt(args.transcript_path, args.context_path, args.output_dir, args.example_names)
        print(f"LLM prompt package generated at: {args.output_dir}")
    elif args.command == "validate-model-output":
        validate_model_output(args.model_output_path)
        print(f"Model output is valid: {args.model_output_path}")
    elif args.command == "convert-model-output":
        convert_model_output_to_crm(args.model_output_path, args.output_dir, args.context_path)
        print(f"Converted model output to CRM artifacts at: {args.output_dir}")
    elif args.command == "run-sample-tests":
        run_sample_tests(args.output_root)
        print(f"All sample tests passed. Output root: {args.output_root}")
    elif args.command == "run-feishu-pipeline-tests":
        run_feishu_pipeline_tests(args.output_root)
        print(f"All Feishu pipeline tests passed. Output root: {args.output_root}")
    elif args.command == "run-model-output-tests":
        run_model_output_tests(args.output_root)
        print(f"All model output tests passed. Output root: {args.output_root}")
    elif args.command == "run-merge-policy-tests":
        run_merge_policy_tests()
        print("All merge policy tests passed.")
    elif args.command == "run-customer-journey":
        run_customer_journey(args.manifest_path, args.output_dir)
        print(f"Customer journey generated at: {args.output_dir}")
    elif args.command == "inspect-feishu-bitable":
        inspect_feishu_bitable(args.app_id, args.app_secret, args.app_token_or_url, args.output_dir, args.table_id)
        print(f"Feishu bitable inspection generated at: {args.output_dir}")
    elif args.command == "sync-feishu-bitable":
        sync_crm_packet_to_feishu(
            args.crm_packet_path,
            args.output_dir,
            args.config_path,
            args.app_id,
            args.app_secret,
            args.app_token_or_url,
            args.customer_table_id,
            args.opportunity_table_id,
            args.dry_run,
        )
        print(f"Feishu bitable sync result generated at: {args.output_dir}")
    elif args.command == "ingest-feishu-raw-to-bitable":
        ingest_feishu_raw_to_bitable(
            args.raw_input_path,
            args.output_dir,
            args.config_path,
            args.app_id,
            args.app_secret,
            args.app_token_or_url,
            args.customer_table_id,
            args.opportunity_table_id,
            args.dry_run,
        )
        print(f"Feishu raw input fully ingested to bitable at: {args.output_dir}")
    elif args.command == "ingest-feishu-doc-to-bitable":
        ingest_feishu_doc_to_bitable(
            args.doc_markdown_path,
            args.output_dir,
            args.source_doc_url,
            args.fallback_title,
            args.config_path,
            args.app_id,
            args.app_secret,
            args.app_token_or_url,
            args.customer_table_id,
            args.opportunity_table_id,
            args.dry_run,
            args.sync_feishu,
        )
        print(f"Feishu doc input fully converted at: {args.output_dir}")


if __name__ == "__main__":
    main()
