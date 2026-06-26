#!/usr/bin/env python3
"""
Build an honest handoff pack for a content task.

Default mode is discovery only. Use --yes with --task or --core-file after the
user confirms the intended task.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


ALLOWED_EXTENSIONS = {
    ".md",
    ".markdown",
    ".txt",
    ".docx",
    ".html",
    ".htm",
    ".pdf",
    ".pptx",
    ".csv",
    ".xlsx",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".mp3",
    ".m4a",
    ".wav",
    ".mp4",
    ".mov",
    ".srt",
    ".vtt",
}

TEXT_EXTENSIONS = {
    ".md",
    ".markdown",
    ".txt",
    ".html",
    ".htm",
    ".csv",
    ".json",
    ".srt",
    ".vtt",
}

MEDIA_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp3", ".m4a", ".wav", ".mp4", ".mov"}

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "target",
    ".next",
    ".venv",
    "venv",
    "handoffs",
}

GENERIC_TOKENS = {
    "ai",
    "agent",
    "codex",
    "claude",
    "claudecode",
    "chatgpt",
    "gemini",
    "cursor",
    "openai",
    "云厂商",
    "腾讯",
    "龙虾",
    "小龙虾",
    "openclaw",
    "workbuddy",
    "codebuddy",
    "36氪",
    "html",
    "markdown",
    "deep",
    "research",
    "report",
    "reports",
    "script",
    "interview",
    "project",
    "content",
    "state",
    "resume",
    "prompt",
    "task",
    "boundary",
    "template",
    "templates",
    "reference",
    "references",
    "workflow",
    "manifest",
    "pattern",
    "patterns",
    "title",
    "generated",
    "new",
    "readme",
    "readme.md",
    "md",
    "docx",
    "pdf",
    "pptx",
    "xlsx",
    "csv",
    "json",
    "mp3",
    "index",
    "code",
    "dashboard",
    "skills",
    "skill",
    "readonly",
    "mail",
    "http",
    "https",
    "www",
    "com",
    "cn",
    "亿元",
    "同比增长",
    "来源",
    "建议",
    "内容",
    "项目",
    "采访",
    "专访",
    "媒体专访",
    "调研",
    "报告",
    "脚本",
    "提纲",
    "作战手册",
    "视频",
    "视频框架",
    "框架",
    "人物档案",
    "资料",
    "素材",
    "来源",
    "风险",
    "清单",
    "最终",
    "建议",
    "判断",
    "投前",
    "版本",
    "导出",
}

GENERIC_SUFFIXES = [
    "采访前调研作战手册",
    "专访作战手册",
    "采访作战手册",
    "作战手册",
    "视频框架采访提纲",
    "视频框架",
    "采访提纲",
    "访谈脚本",
    "调研报告",
    "判断报告",
    "投前判断报告",
    "深度研究",
    "人物档案",
    "采访调研",
    "脚本",
    "报告",
    "提纲",
    "调研",
]

SENSITIVE_NAME_PATTERNS = [
    re.compile(r"(^|[._-])env($|[._-])", re.I),
    re.compile(r"id_(rsa|ed25519|dsa|ecdsa)", re.I),
    re.compile(r"(secret|token|password|passwd|credential|credentials|apikey|api_key|private[-_]?key)", re.I),
    re.compile(r"\.(pem|key|p12|pfx|crt|cer|sqlite|db)$", re.I),
]

SENSITIVE_CONTENT_PATTERNS = [
    re.compile(r"(api[_-]?key|openai_api_key|token|password|client_secret|private_key)\s*[:=]\s*['\"]?[^'\"\s]{8,}", re.I),
    re.compile(r"-----BEGIN (RSA |OPENSSH |EC |DSA |PRIVATE )?PRIVATE KEY-----", re.I),
]

CONVERSATION_ROLES = {"user", "assistant"}
MAX_CONVERSATION_TURN_CHARS = 8000


@dataclass
class CandidateFile:
    path: Path
    relpath: str
    ext: str
    size: int
    mtime: float
    title: str
    sample: str
    tokens: set[str]
    role: str
    is_recent: bool
    sensitive: bool = False
    sensitive_reason: str = ""
    too_large: bool = False


@dataclass
class TaskGroup:
    files: list[CandidateFile] = field(default_factory=list)
    tokens: set[str] = field(default_factory=set)
    title: str = ""
    score: float = 0.0
    match_score: float = 0.0

    @property
    def latest_mtime(self) -> float:
        return max((f.mtime for f in self.files), default=0.0)


@dataclass
class ConversationTurn:
    source_path: Path
    source_kind: str
    timestamp: str
    role: str
    text: str
    index: int
    score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)
    truncated: bool = False


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M")


def human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def slugify(value: str, fallback: str = "task") -> str:
    value = value.strip()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-{2,}", "-", value).strip("-_")
    return (value or fallback)[:80]


def file_digest(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:10]


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def read_text_sample(path: Path, ext: str, max_chars: int = 12000) -> str:
    if ext == ".docx":
        return read_docx_text(path, max_chars=max_chars)
    if ext not in TEXT_EXTENSIONS:
        return ""
    try:
        data = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if ext in {".html", ".htm"}:
        data = strip_html(data)
    return data[:max_chars]


def read_docx_text(path: Path, max_chars: int = 12000) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception:
        return ""
    parts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml)
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", "", part)) for part in parts)
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def extract_title(path: Path, sample: str) -> str:
    if sample:
        heading = re.search(r"(?m)^\s{0,3}#\s+(.+?)\s*$", sample)
        if heading:
            return heading.group(1).strip()[:120]
        html_title = re.search(r"(?is)<title[^>]*>(.*?)</title>", sample)
        if html_title:
            return strip_html(html_title.group(1))[:120]
        for line in sample.splitlines():
            line = line.strip()
            if line and len(line) <= 120:
                return line
    return path.stem


def clean_token(token: str) -> str:
    token = token.strip(" ._-—–|｜丨:：,，、()（）[]【】{}《》\"'")
    token = re.sub(r"\d{4}[-_]\d{2}[-_]\d{2}$", "", token)
    token = re.sub(r"^\d+[\.-]?", "", token)
    for suffix in GENERIC_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix) + 1:
            token = token[: -len(suffix)]
            break
    return token.strip(" ._-—–|｜丨:：,，、")


def meaningful_token(token: str) -> bool:
    if not token:
        return False
    low = token.lower()
    if low in GENERIC_TOKENS or token in GENERIC_TOKENS:
        return False
    if "云厂商" in token:
        return False
    if re.fullmatch(r"\d+", token):
        return False
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", token))
    latin_count = len(re.findall(r"[A-Za-z]", token))
    if cjk_count >= 2 and len(token) <= 18:
        return True
    if latin_count >= 4 and len(token) <= 30:
        return True
    return False


def extract_tokens(path: Path, relpath: str, title: str, sample: str) -> set[str]:
    strong_sources = [
        path.stem,
        relpath,
        title,
    ]
    tokens: set[str] = set()
    split_re = re.compile(r"[\s/_\\.\-—–|｜丨×&+＋,，、:：;；()（）\[\]【】{}《》<>]+")
    for source in strong_sources:
        for part in split_re.split(source):
            token = clean_token(part)
            if meaningful_token(token):
                tokens.add(token)

    phrase_patterns = [
        r"[\u4e00-\u9fffA-Za-z0-9]{2,12}(?:医学|智家|网络|企服|财经|集团|公司|直播公司|科技|医疗|游戏|智能体)",
        r"(?:YOOZOO|Yoozoo|yoozoo)[A-Za-z0-9._-]*",
    ]
    for pattern in phrase_patterns:
        for match in re.findall(pattern, " ".join(strong_sources)):
            token = clean_token(match)
            if meaningful_token(token):
                tokens.add(token)
    return tokens


def classify_role(path: Path, title: str, sample: str) -> str:
    text = f"{path.name}\n{title}\n{sample[:3000]}".lower()
    name_title = f"{path.name}\n{title}".lower()
    ext = path.suffix.lower()
    if ext in MEDIA_EXTENSIONS:
        return "source_media"
    if re.search(r"速记|逐字稿|transcript|录音转文字|timecode|时间码", text):
        return "source_transcript"
    if re.search(r"参考文章|风格|style sample|三篇文章|reference", text):
        return "reference_style"
    if ext in {".html", ".htm"}:
        return "html_deliverable"
    if re.search(r"脚本|短视频|旁白|嘉宾原话|封标|script", name_title):
        return "script_or_draft"
    if re.search(r"deep research|深度研究|投前判断|判断报告|来源与可信度|事实核查|风险清单", name_title):
        return "research_report"
    if re.search(r"作战手册|采访提纲|人物档案|采访前|调研文档|视频结构|war-room", name_title):
        return "interview_brief"
    if re.search(r"deep research|深度研究|投前判断|判断报告|来源与可信度|事实核查|风险清单", text):
        return "research_report"
    if re.search(r"作战手册|采访提纲|人物档案|采访前|调研文档|视频结构|war-room", text):
        return "interview_brief"
    if re.search(r"脚本|短视频|旁白|嘉宾原话|封标|script", text):
        return "script_or_draft"
    if ext in {".docx", ".pptx", ".pdf"}:
        return "source_material"
    if ext in {".md", ".markdown", ".txt"}:
        return "content_note"
    return "supporting_file"


def is_sensitive_name(path: Path) -> str:
    name = path.name
    for pattern in SENSITIVE_NAME_PATTERNS:
        if pattern.search(name):
            return f"文件名疑似包含敏感信息: {pattern.pattern}"
    return ""


def is_sensitive_content(sample: str) -> str:
    if not sample:
        return ""
    for pattern in SENSITIVE_CONTENT_PATTERNS:
        if pattern.search(sample):
            return "内容疑似包含密钥、token 或密码"
    return ""


def should_skip_dir(name: str) -> bool:
    return name in EXCLUDED_DIRS or name.endswith(".app")


def looks_like_runtime_context(text: str) -> bool:
    stripped = text.strip()
    if stripped.startswith("# AGENTS.md instructions") and "<environment_context>" in stripped:
        return True
    runtime_markers = [
        "<permissions instructions>",
        "<app-context>",
        "<skills_instructions>",
        "<plugins_instructions>",
        "You are Codex, a coding agent",
    ]
    return any(marker in stripped for marker in runtime_markers)


def extract_message_text(payload: dict) -> str:
    content = payload.get("content", "")
    parts: list[str] = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
    text = "\n\n".join(part.strip() for part in parts if part and part.strip())
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def truncate_conversation_text(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_CONVERSATION_TURN_CHARS:
        return text, False
    suffix = "\n\n[已截断：单回合内容超过交接包限制，请回到原始会话查看完整内容。]"
    return text[:MAX_CONVERSATION_TURN_CHARS].rstrip() + suffix, True


def parse_codex_session(path: Path) -> list[ConversationTurn]:
    turns: list[ConversationTurn] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return turns
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        message = None
        if row.get("type") == "response_item" and payload.get("type") == "message":
            message = payload
        elif row.get("type") == "message":
            message = payload
        if not message:
            continue
        role = message.get("role")
        if role not in CONVERSATION_ROLES:
            continue
        text = extract_message_text(message)
        if not text or looks_like_runtime_context(text) or is_sensitive_content(text):
            continue
        text, truncated = truncate_conversation_text(text)
        turns.append(
            ConversationTurn(
                source_path=path,
                source_kind="codex_session",
                timestamp=str(row.get("timestamp", "")),
                role=role,
                text=text,
                index=len(turns),
                truncated=truncated,
            )
        )
    return turns


def resolve_conversation_path(workspace: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (workspace / path).resolve()


def read_explicit_conversation_file(path: Path) -> tuple[list[ConversationTurn], list[str]]:
    warnings: list[str] = []
    if not path.exists() or not path.is_file():
        return [], [f"显式对话文件不存在：{path}"]
    if is_sensitive_name(path):
        return [], [f"显式对话文件因文件名疑似敏感而跳过：{path}"]
    if path.suffix.lower() == ".jsonl":
        turns = parse_codex_session(path)
        if not turns:
            warnings.append(f"显式 Codex 会话文件没有可纳入的 user/assistant 自然语言回合：{path}")
        for turn in turns:
            turn.source_kind = "explicit_codex_session"
        return turns, warnings
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return [], [f"显式对话文件无法读取：{path} ({exc})"]
    if is_sensitive_content(raw):
        return [], [f"显式对话文件疑似包含密钥、token 或密码，已跳过：{path}"]
    text, truncated = truncate_conversation_text(raw.strip())
    if not text:
        return [], [f"显式对话文件为空：{path}"]
    stat = path.stat()
    return [
        ConversationTurn(
            source_path=path,
            source_kind="explicit_conversation_file",
            timestamp=dt.datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
            role="conversation_file",
            text=text,
            index=0,
            truncated=truncated,
        )
    ], warnings


def conversation_terms(group: TaskGroup, extra_query: str = "") -> list[str]:
    raw_terms: list[str] = [group.title]
    raw_terms.extend(group_common_tokens(group))
    raw_terms.extend(sorted(group.tokens, key=len, reverse=True))
    for file in priority_files(group)[:12]:
        raw_terms.extend(sorted(file.tokens, key=len, reverse=True))
    if extra_query:
        raw_terms.append(extra_query)
        raw_terms.extend(part for part in re.split(r"[\s,，、]+", extra_query) if part.strip())

    seen: set[str] = set()
    terms: list[str] = []
    for raw in raw_terms:
        raw_clean = clean_token(raw)
        raw_norm = normalize(raw_clean)
        if raw_norm and raw_norm not in seen and len(raw_clean) <= 80:
            parts = [clean_token(part) for part in re.split(r"[\s/_\\.\-—–|｜丨×xX&+＋,，、:：;；()（）\[\]【】{}《》<>]+", raw_clean)]
            has_meaningful_part = any(meaningful_token(part) for part in parts)
            is_explicit_query_phrase = bool(extra_query and raw_clean in extra_query and len(raw_norm) >= 4)
            if has_meaningful_part or is_explicit_query_phrase:
                seen.add(raw_norm)
                terms.append(raw_clean)
        for part in re.split(r"[\n/_\\.\-—–|｜丨×xX&+＋,，、:：;；()（）\[\]【】{}《》<>]+", raw):
            token = clean_token(part)
            norm = normalize(token)
            if not norm or norm in seen:
                continue
            if meaningful_token(token):
                seen.add(norm)
                terms.append(token)
    return sorted(terms, key=len, reverse=True)[:60]


def score_conversation_text(text: str, terms: list[str]) -> tuple[float, list[str]]:
    hay = normalize(text)
    score = 0.0
    matched: list[str] = []
    for term in terms:
        norm = normalize(term)
        if len(norm) < 2:
            continue
        if norm in hay:
            score += 1.0 + min(len(norm), 20) / 10
            matched.append(term)
    return score, matched[:12]


def select_relevant_turns(turns: list[ConversationTurn], terms: list[str], context_turns: int) -> tuple[list[ConversationTurn], float]:
    hit_indexes: set[int] = set()
    total_score = 0.0
    for idx, turn in enumerate(turns):
        score, matched = score_conversation_text(turn.text, terms)
        turn.score = score
        turn.matched_terms = matched
        if score > 0:
            hit_indexes.add(idx)
            total_score += score
    if not hit_indexes:
        return [], 0.0
    selected_indexes: set[int] = set()
    for idx in hit_indexes:
        start = max(0, idx - context_turns)
        end = min(len(turns), idx + context_turns + 1)
        selected_indexes.update(range(start, end))
    return [turns[idx] for idx in sorted(selected_indexes)], total_score


def find_codex_session_files(session_root: Path, days: int) -> tuple[list[Path], list[str]]:
    warnings: list[str] = []
    if not session_root.exists():
        return [], [f"Codex 会话目录不存在：{session_root}"]
    cutoff = dt.datetime.now().timestamp() - days * 86400
    files = []
    for path in session_root.rglob("*.jsonl"):
        try:
            if path.stat().st_mtime >= cutoff:
                files.append(path)
        except OSError:
            continue
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files, warnings


def collect_codex_conversation(
    session_root: Path,
    days: int,
    terms: list[str],
    context_turns: int,
    max_turns: int,
) -> tuple[list[ConversationTurn], list[dict], list[str]]:
    session_files, warnings = find_codex_session_files(session_root, days)
    scored_sources: list[dict] = []
    for path in session_files:
        turns = parse_codex_session(path)
        selected, score = select_relevant_turns(turns, terms, context_turns)
        if not selected:
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        scored_sources.append(
            {
                "path": path,
                "score": score,
                "mtime": mtime,
                "turns": selected,
                "matched_turns": sum(1 for turn in selected if turn.score > 0),
            }
        )

    scored_sources.sort(key=lambda item: (item["score"], item["mtime"]), reverse=True)
    included_turns: list[ConversationTurn] = []
    sources: list[dict] = []
    remaining = max_turns
    for source in scored_sources:
        if remaining <= 0:
            break
        selected = source["turns"][:remaining]
        if not selected:
            continue
        included_turns.extend(selected)
        remaining -= len(selected)
        sources.append(
            {
                "path": str(source["path"]),
                "kind": "codex_session",
                "score": round(float(source["score"]), 2),
                "included_turns": len(selected),
                "matched_turns": int(source["matched_turns"]),
                "mtime": dt.datetime.fromtimestamp(source["mtime"]).astimezone().isoformat(timespec="seconds")
                if source["mtime"]
                else "",
            }
        )
    return included_turns, sources, warnings


def collect_explicit_conversation(
    workspace: Path,
    files: list[str],
    terms: list[str],
    context_turns: int,
    max_turns: int,
) -> tuple[list[ConversationTurn], list[dict], list[str]]:
    included_turns: list[ConversationTurn] = []
    sources: list[dict] = []
    warnings: list[str] = []
    remaining = max_turns
    for value in files:
        if remaining <= 0:
            break
        path = resolve_conversation_path(workspace, value)
        turns, file_warnings = read_explicit_conversation_file(path)
        warnings.extend(file_warnings)
        if not turns:
            continue
        if path.suffix.lower() == ".jsonl":
            selected, score = select_relevant_turns(turns, terms, context_turns)
            if not selected:
                selected = turns
                score = 0.0
                warnings.append(f"显式 Codex 会话未命中任务关键词，按用户指定纳入自然语言回合：{path}")
        else:
            selected = turns
            score, matched = score_conversation_text(turns[0].text, terms)
            turns[0].score = score
            turns[0].matched_terms = matched
        selected = selected[:remaining]
        included_turns.extend(selected)
        remaining -= len(selected)
        sources.append(
            {
                "path": str(path),
                "kind": "explicit_conversation_file",
                "score": round(float(score), 2),
                "included_turns": len(selected),
                "matched_turns": sum(1 for turn in selected if turn.score > 0),
                "mtime": dt.datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
            }
        )
    return included_turns, sources, warnings


def safe_fenced_text(text: str) -> str:
    return text.replace("```", "` ` `").strip()


def write_conversation_pack(
    pack_dir: Path,
    workspace: Path,
    group: TaskGroup,
    conversation_files: list[str],
    include_codex: bool,
    session_root: Path,
    days: int,
    query: str,
    max_turns: int,
    context_turns: int,
) -> dict:
    enabled = bool(conversation_files or include_codex)
    if not enabled:
        return {
            "enabled": False,
            "included_turns": 0,
            "files": [],
            "sources": [],
            "warnings": [],
        }

    conv_dir = pack_dir / "conversation"
    conv_dir.mkdir(parents=True, exist_ok=True)
    terms = conversation_terms(group, query)
    warnings: list[str] = []
    turns: list[ConversationTurn] = []
    sources: list[dict] = []
    remaining = max_turns

    explicit_turns, explicit_sources, explicit_warnings = collect_explicit_conversation(
        workspace=workspace,
        files=conversation_files,
        terms=terms,
        context_turns=context_turns,
        max_turns=remaining,
    )
    turns.extend(explicit_turns)
    sources.extend(explicit_sources)
    warnings.extend(explicit_warnings)
    remaining = max(0, max_turns - len(turns))

    if include_codex and remaining > 0:
        codex_turns, codex_sources, codex_warnings = collect_codex_conversation(
            session_root=session_root,
            days=days,
            terms=terms,
            context_turns=context_turns,
            max_turns=remaining,
        )
        turns.extend(codex_turns)
        sources.extend(codex_sources)
        warnings.extend(codex_warnings)

    generated_at = now_iso()
    lines = [
        f"# Task Conversation: {group.title}",
        "",
        f"Generated: {generated_at}",
        "",
        "这些内容是围绕当前任务筛出来的对话片段，用于帮助下一个 AI 理解来龙去脉。",
        "对话不是事实来源；事实仍以 `sources/`、`artifacts/`、原始 transcript、公开来源和用户确认材料为准。",
        "",
        "## Selection",
        "",
        f"- 任务：{group.title}",
        f"- 关键词：{', '.join(terms[:20]) if terms else '未识别到关键词'}",
        f"- Codex 会话扫描：{'已启用' if include_codex else '未启用'}",
        f"- 显式对话文件：{len(conversation_files)} 个",
        f"- 纳入回合：{len(turns)}",
        "",
        "## Included Conversation",
        "",
    ]
    if not turns:
        lines.append("未找到可安全纳入的相关对话。")
    current_source = None
    for turn in turns:
        if current_source != turn.source_path:
            current_source = turn.source_path
            lines.extend(["", f"## Source: `{turn.source_path}`", ""])
        role = {"user": "用户", "assistant": "助手"}.get(turn.role, "对话文件")
        matched = f"；命中：{', '.join(turn.matched_terms)}" if turn.matched_terms else ""
        truncated = "；已截断" if turn.truncated else ""
        timestamp_text = turn.timestamp or "unknown time"
        lines.extend(
            [
                f"### {timestamp_text} · {role}{matched}{truncated}",
                "",
                "```text",
                safe_fenced_text(turn.text),
                "```",
                "",
            ]
        )

    readme = """# Conversation Folder

本目录只保存与当前任务相关的对话片段。

默认排除：

- system/developer 指令
- 工具调用与工具输出
- 环境上下文
- 疑似密钥、token、密码的内容

使用方式：

1. 先读 `HANDOFF.md`、`content_state.md`、`task_boundary.md` 和核心文件。
2. 再读 `conversation/task_conversation.md` 理解用户偏好、已做决策和争议点。
3. 不要把对话中的推断直接当事实写进正文。
"""

    manifest = {
        "enabled": True,
        "generated_at": generated_at,
        "task_title": group.title,
        "selection_terms": terms,
        "selection_policy": "只纳入显式对话文件，或从 Codex sessions 中按任务关键词筛选 user/assistant 自然语言回合；排除系统、开发者、工具和敏感内容。",
        "included_turns": len(turns),
        "max_turns": max_turns,
        "context_turns": context_turns,
        "sources": sources,
        "warnings": warnings,
    }
    (conv_dir / "task_conversation.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    (conv_dir / "README.md").write_text(readme, encoding="utf-8")
    (conv_dir / "conversation_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "enabled": True,
        "included_turns": len(turns),
        "files": [
            "conversation/task_conversation.md",
            "conversation/README.md",
            "conversation/conversation_manifest.json",
        ],
        "sources": sources,
        "warnings": warnings,
        "selection_terms": terms,
    }


def scan_workspace(workspace: Path, recent_days: int, max_size_mb: int) -> tuple[list[CandidateFile], list[dict]]:
    candidates: list[CandidateFile] = []
    excluded: list[dict] = []
    cutoff = dt.datetime.now().timestamp() - recent_days * 86400
    max_size = max_size_mb * 1024 * 1024

    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        root_path = Path(root)
        for filename in files:
            path = root_path / filename
            try:
                stat = path.stat()
            except OSError:
                continue
            relpath = str(path.relative_to(workspace))
            name_reason = is_sensitive_name(path)
            if name_reason:
                excluded.append(
                    {
                        "path": relpath,
                        "reason": name_reason,
                        "size": stat.st_size,
                    }
                )
                continue
            ext = path.suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            too_large = stat.st_size > max_size
            sample = "" if too_large else read_text_sample(path, ext)
            content_reason = "" if too_large else is_sensitive_content(sample)
            sensitive_reason = name_reason or content_reason
            if sensitive_reason or too_large:
                excluded.append(
                    {
                        "path": relpath,
                        "reason": sensitive_reason or f"文件过大，超过 {max_size_mb} MB",
                        "size": stat.st_size,
                    }
                )
                continue
            title = extract_title(path, sample)
            tokens = extract_tokens(path, relpath, title, sample)
            role = classify_role(path, title, sample)
            candidates.append(
                CandidateFile(
                    path=path,
                    relpath=relpath,
                    ext=ext,
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                    title=title,
                    sample=sample,
                    tokens=tokens,
                    role=role,
                    is_recent=stat.st_mtime >= cutoff,
                )
            )
    return candidates, excluded


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: int, b: int) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def cluster_files(files: list[CandidateFile], query: str = "") -> list[TaskGroup]:
    if not files:
        return []
    uf = UnionFind(len(files))
    token_map: dict[str, list[int]] = {}
    for idx, file in enumerate(files):
        for token in file.tokens:
            token_map.setdefault(token.lower(), []).append(idx)

    for token, indexes in token_map.items():
        if len(indexes) <= 1 or len(indexes) > 8:
            continue
        first = indexes[0]
        for idx in indexes[1:]:
            uf.union(first, idx)

    grouped: dict[int, TaskGroup] = {}
    for idx, file in enumerate(files):
        root = uf.find(idx)
        group = grouped.setdefault(root, TaskGroup())
        group.files.append(file)
        group.tokens.update(file.tokens)

    groups = list(grouped.values())
    for group in groups:
        group.title = choose_group_title(group)
        group.score = score_group(group)
        if query:
            group.match_score = score_query_match(group, query)
    groups.sort(key=lambda g: (g.match_score, g.score, g.latest_mtime), reverse=True)
    return groups


def choose_group_title(group: TaskGroup) -> str:
    titles = []
    for file in group.files:
        if file.title and file.title != file.path.stem:
            titles.append(file.title)
    if titles:
        titles.sort(key=lambda t: (len(t) > 8, -len(t)), reverse=True)
        title = titles[0]
    elif group.tokens:
        title = " / ".join(sorted(group.tokens, key=len, reverse=True)[:3])
    else:
        title = Path(group.files[0].relpath).stem
    return re.sub(r"\s+", " ", title).strip()[:100]


def score_group(group: TaskGroup) -> float:
    recent = sum(1 for f in group.files if f.is_recent)
    role_bonus = len({f.role for f in group.files}) * 0.5
    return len(group.files) * 2 + recent + role_bonus


def score_query_match(group: TaskGroup, query: str) -> float:
    query_norm = normalize(query)
    if not query_norm:
        return 0.0
    haystacks = [group.title, " ".join(group.tokens)]
    haystacks.extend(f.relpath for f in group.files)
    hay = normalize("\n".join(haystacks))
    score = 0.0
    if query_norm in hay:
        score += 10.0
    for term in split_query_terms(query):
        if term and term in hay:
            score += 2.0
    return score


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value.lower())


def split_query_terms(query: str) -> list[str]:
    parts = re.split(r"[\s/_\\\-—–|｜丨×xX&+＋,，、:：;；()（）\[\]【】{}《》<>]+", query)
    return [normalize(p) for p in parts if p.strip()]


def select_group(groups: list[TaskGroup], task: str = "", core_file: Path | None = None, workspace: Path | None = None) -> TaskGroup | None:
    if not groups:
        return None
    if core_file:
        core_resolved = core_file.resolve()
        for group in groups:
            for file in group.files:
                if file.path.resolve() == core_resolved:
                    return group
        if workspace and not core_file.is_absolute():
            maybe = (workspace / core_file).resolve()
            for group in groups:
                for file in group.files:
                    if file.path.resolve() == maybe:
                        return group
    if task:
        matched = sorted(groups, key=lambda g: (score_query_match(g, task), g.score), reverse=True)
        if score_query_match(matched[0], task) > 0:
            return matched[0]
    return groups[0]


def group_common_tokens(group: TaskGroup) -> list[str]:
    counts: dict[str, int] = {}
    for file in group.files:
        for token in file.tokens:
            counts[token] = counts.get(token, 0) + 1
    return [token for token, _ in sorted(counts.items(), key=lambda item: (item[1], len(item[0])), reverse=True)[:8]]


def priority_files(group: TaskGroup) -> list[CandidateFile]:
    role_priority = {
        "source_transcript": 0,
        "script_or_draft": 1,
        "interview_brief": 2,
        "research_report": 3,
        "html_deliverable": 4,
        "reference_style": 5,
        "source_material": 6,
    }
    return sorted(group.files, key=lambda f: (role_priority.get(f.role, 9), -f.mtime, f.relpath))


def role_label(role: str) -> str:
    labels = {
        "source_media": "原始媒体",
        "source_transcript": "采访速记/逐字稿",
        "reference_style": "参考风格/参考文章",
        "source_material": "输入材料",
        "html_deliverable": "HTML 成品",
        "script_or_draft": "脚本/草稿",
        "interview_brief": "采访前调研/作战手册",
        "research_report": "研究报告/判断报告",
        "content_note": "内容笔记",
        "supporting_file": "辅助文件",
    }
    return labels.get(role, role)


def infer_output_type(group: TaskGroup) -> str:
    roles = {f.role for f in group.files}
    if "source_transcript" in roles and "interview_brief" in roles:
        return "采访资料 + 采访后脚本"
    if "script_or_draft" in roles and "interview_brief" in roles:
        return "采访前调研 + 访谈/短视频脚本"
    if "source_transcript" in roles or "script_or_draft" in roles:
        return "采访后脚本/短视频脚本"
    if "interview_brief" in roles:
        return "采访前调研、视频结构或采访提纲"
    if "research_report" in roles and "html_deliverable" in roles:
        return "深度研究报告 + HTML 交付"
    if "research_report" in roles:
        return "研究报告/判断报告"
    if "html_deliverable" in roles:
        return "HTML 内容交付"
    return "内容生产任务"


def infer_background(group: TaskGroup) -> str:
    tokens = group_common_tokens(group)
    roles = sorted({role_label(f.role) for f in group.files})
    lines = [
        f"这是一个围绕 `{group.title}` 的内容任务交接包。",
        f"识别到的任务关键词：{', '.join(tokens) if tokens else '未明显识别'}。",
        f"文件角色覆盖：{', '.join(roles)}。",
    ]
    return "\n".join(lines)


def infer_next_action(group: TaskGroup) -> str:
    roles = {f.role for f in group.files}
    if "source_transcript" in roles:
        return "先读取 transcript/速记，再基于原话继续脚本、标题或剪辑结构，不要补写嘉宾原话。"
    if "script_or_draft" in roles:
        return "先读取当前脚本和相关调研，继续修改脚本结构、金句、长度或发布标题。"
    if "interview_brief" in roles:
        return "先读取作战手册和事实边界，继续完善视频结构、采访提纲或待确认问题。"
    if "research_report" in roles:
        return "先读取报告正文和来源分层，继续补充事实核查、建议或 HTML 版本。"
    if "html_deliverable" in roles:
        return "先确认 HTML 是否为最终可读成品，再继续内容或视觉修改。"
    return "先读取 HANDOFF.md 和优先文件，再根据用户的新指令继续。"


def build_markdown_list(files: Iterable[CandidateFile]) -> str:
    lines = []
    for file in files:
        lines.append(f"- `{file.relpath}`：{role_label(file.role)}，{human_size(file.size)}")
    return "\n".join(lines) if lines else "- 无"


def markdown_escape(value: str) -> str:
    return value.replace("\n", " ").strip()


def candidate_summary(groups: list[TaskGroup], recommended: TaskGroup | None, excluded: list[dict]) -> str:
    lines = []
    lines.append(f"识别到 {len(groups)} 个候选任务。")
    for idx, group in enumerate(groups, start=1):
        marker = "（推荐）" if recommended is group else ""
        tokens = ", ".join(group_common_tokens(group)[:5]) or "无明显关键词"
        lines.append("")
        lines.append(f"{idx}. {group.title}{marker}")
        lines.append(f"   - 文件数：{len(group.files)}")
        lines.append(f"   - 关键词：{tokens}")
        for file in priority_files(group)[:6]:
            lines.append(f"   - {file.relpath} [{role_label(file.role)}]")
        if len(group.files) > 6:
            lines.append(f"   - ... 另有 {len(group.files) - 6} 个文件")
    if excluded:
        lines.append("")
        lines.append(f"扫描时排除了 {len(excluded)} 个敏感或过大文件。")
    lines.append("")
    lines.append("下一步：确认要打包的任务后，用 `--task \"任务名\" --yes` 或 `--core-file \"核心文件\" --yes` 生成交接包。")
    return "\n".join(lines)


def copied_category(file: CandidateFile) -> str:
    if file.role in {"source_media", "source_transcript", "reference_style", "source_material"}:
        return "sources"
    return "artifacts"


def safe_relpath(relpath: str) -> Path:
    raw_parts = list(Path(relpath).parts)
    parts = []
    for idx, part in enumerate(raw_parts):
        p = Path(part)
        if idx == len(raw_parts) - 1 and p.suffix:
            parts.append(f"{slugify(p.stem, fallback='file')}{p.suffix}")
        else:
            parts.append(slugify(part, fallback="file"))
    return Path(*parts)


def copy_group_files(pack_dir: Path, group: TaskGroup) -> list[dict]:
    manifest_files = []
    for file in priority_files(group):
        category = copied_category(file)
        target_rel = Path(category) / safe_relpath(file.relpath)
        target = pack_dir / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target.with_name(f"{target.stem}-{file_digest(file.path)}{target.suffix}")
            target_rel = target.relative_to(pack_dir)
        shutil.copy2(file.path, target)
        shared = sorted(file.tokens & group.tokens, key=len, reverse=True)[:5]
        manifest_files.append(
            {
                "original_path": str(file.path),
                "copied_path": str(target_rel),
                "role": file.role,
                "role_label": role_label(file.role),
                "size": file.size,
                "mtime": dt.datetime.fromtimestamp(file.mtime).astimezone().isoformat(timespec="seconds"),
                "confidence": 0.85 if shared else 0.6,
                "inclusion_reason": f"与任务共享关键词: {', '.join(shared) if shared else '通过核心文件或候选聚类纳入'}",
                "title": file.title,
            }
        )
    return manifest_files


def excluded_unrelated(groups: list[TaskGroup], selected: TaskGroup) -> list[dict]:
    rows = []
    for group in groups:
        if group is selected:
            continue
        for file in priority_files(group):
            rows.append(
                {
                    "path": file.relpath,
                    "reason": f"疑似属于其他任务：{group.title}",
                    "size": file.size,
                }
            )
    return rows


def write_pack_docs(
    pack_dir: Path,
    workspace: Path,
    group: TaskGroup,
    groups: list[TaskGroup],
    manifest_files: list[dict],
    excluded_files: list[dict],
    target_ai: str,
    conversation_info: dict,
) -> dict:
    generated_at = now_iso()
    output_type = infer_output_type(group)
    next_action = infer_next_action(group)
    background = infer_background(group)
    priority = priority_files(group)
    top_files = "\n".join(f"{idx}. `{f.relpath}`：{role_label(f.role)}" for idx, f in enumerate(priority[:8], start=1))
    included_work = build_markdown_list(priority)
    common_tokens = group_common_tokens(group)
    unrelated = [item for item in excluded_files if item.get("reason", "").startswith("疑似属于其他任务")]
    if conversation_info.get("enabled") and conversation_info.get("included_turns", 0):
        conversation_note = (
            f"已纳入任务相关对话片段：{conversation_info.get('included_turns')} 个回合，"
            "见 `conversation/task_conversation.md`。"
        )
    elif conversation_info.get("enabled"):
        conversation_note = "已请求纳入对话，但没有找到可安全纳入的相关自然语言回合。"
    else:
        conversation_note = "本次未纳入聊天记录；如需加入同一任务对话，请重新运行时传入对话参数。"

    handoff = f"""# {group.title} Handoff

Generated: {generated_at}

Workspace: `{workspace}`

Target AI/tool: {target_ai}

## Background

{background}

## Current State

- Output type: {output_type}
- Included files: {len(group.files)}
- Conversation context: {conversation_note}
- Highest-priority files:
{top_files or "- 无"}

## Included Work

{included_work}

## Honest Layer

### 公开可核实事实

仅以包内文件已经列出的公开来源和事实核查区为准。本脚本没有重新联网核验。

### 输入材料口径

DOCX、PPTX、PDF、速记、用户提供材料和内部说明都应视为输入材料口径，除非包内文件已经给出公开来源。

### 编辑判断

调研报告、作战手册、脚本、视频结构和标题建议中的叙事主线、风险判断、表达方式，默认属于编辑判断。

### 对话上下文

{conversation_note}

对话只用于理解用户意图、已做决策、偏好和争议点；不能把对话里的推断直接当作公开事实或嘉宾原话。

### 待确认

嘉宾 title、指标口径、合作边界、是否可公开披露、采访中未核准的事实，都需要在继续写作前确认。

## Recommended Next Steps

{next_action}
"""

    resume_prompt = f"""# Resume Prompt

你将接手一个内容任务。请先读这个交接包，不要直接续写。

## 任务

{group.title}

## 你要先读

1. `HANDOFF.md`
2. `content_state.md`
3. `task_boundary.md`
4. `manifest.json`
5. 如存在，读取 `conversation/task_conversation.md`

然后按优先级读取这些文件：

{top_files or "- 暂无优先文件"}

## 当前下一步

{next_action}

## 必须遵守

- 区分公开可核实事实、输入材料口径、编辑判断和待确认内容。
- 如果有 transcript/速记，嘉宾原话只能来自 transcript，不能补写、代写或凭印象润色成新句子。
- 采访前提纲和调研材料只能辅助判断，不能覆盖 transcript。
- 如果是案例长文，先确认目标产物是文章、脚本还是报告，不要自动切换形态。
- 如果 Markdown 和 HTML 同时存在，先判断哪个是内容源，哪个是展示版本。
- 如果来源冲突，直接指出冲突，不要替用户抹平。
- 不要把 `excluded_files.md` 里的文件当成已经读过。
- 如果交接包包含 `conversation/`，对话只能作为任务背景和用户偏好线索，不能作为事实来源。
"""

    content_state = f"""# Content State

Task: {group.title}

Output type: {output_type}

Audience: 未自动识别；以下一轮用户说明和包内文件为准。

Style constraints: 保留用户原意，直接陈述，避免空泛营销腔。若包内存在参考文章或用户纠正记录，优先按那些材料执行。

Length or format constraints: 未自动识别；请检查原任务说明、脚本标题区、报告说明或用户后续指令。

Current version: 以 `manifest.json` 中的最高优先级文件和最新修改文件为准。

Conversation context: {conversation_note}

Next action: {next_action}

Forbidden or risky moves:
- 不要混入同一工作区里的其他任务。
- 不要把输入材料口径写成公开事实。
- 不要编造嘉宾原话或归因。
- 不要把对话里的推断直接当作事实或原话。
- 不要删除风险提示、来源分层、待确认事项。
"""

    task_boundary = f"""# Task Boundary

Selected task: {group.title}

Selection basis:

- 共同关键词：{', '.join(common_tokens) if common_tokens else '无明显共同关键词'}
- 文件数量：{len(group.files)}
- 角色覆盖：{', '.join(sorted({role_label(f.role) for f in group.files}))}

Included files belong to this task because:

{included_work}

Files excluded as likely unrelated:

{format_excluded(unrelated) if unrelated else "- 无明显无关任务文件"}

Conversation boundary:

{conversation_note}
"""

    excluded_md = f"""# Excluded Files

这些文件没有被放进交接包。原因可能是疑似其他任务、包含敏感信息、或文件过大。

{format_excluded(excluded_files)}
"""

    manifest = {
        "task_title": group.title,
        "generated_at": generated_at,
        "workspace": str(workspace),
        "target_ai": target_ai,
        "task_tokens": common_tokens,
        "files": manifest_files,
        "conversation": conversation_info,
        "excluded_files": excluded_files,
    }

    (pack_dir / "HANDOFF.md").write_text(handoff, encoding="utf-8")
    (pack_dir / "RESUME_PROMPT.md").write_text(resume_prompt, encoding="utf-8")
    (pack_dir / "content_state.md").write_text(content_state, encoding="utf-8")
    (pack_dir / "task_boundary.md").write_text(task_boundary, encoding="utf-8")
    (pack_dir / "excluded_files.md").write_text(excluded_md, encoding="utf-8")
    (pack_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def format_excluded(items: list[dict]) -> str:
    if not items:
        return "- 无"
    lines = []
    for item in items:
        size = f"，{human_size(int(item.get('size', 0)))}" if item.get("size") else ""
        lines.append(f"- `{item.get('path')}`：{item.get('reason')}{size}")
    return "\n".join(lines)


def make_zip(pack_dir: Path) -> Path:
    zip_path = pack_dir.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in pack_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(pack_dir.parent))
    return zip_path


def build_pack(
    workspace: Path,
    group: TaskGroup,
    groups: list[TaskGroup],
    scan_excluded: list[dict],
    output_dir: Path,
    target_ai: str,
    conversation_files: list[str],
    include_codex_conversation: bool,
    conversation_dir: Path,
    conversation_days: int,
    conversation_query: str,
    max_conversation_turns: int,
    conversation_context_turns: int,
) -> tuple[Path, Path, dict]:
    task_slug = slugify(group.title)
    pack_dir = output_dir / f"handoff-{timestamp()}-{task_slug}"
    counter = 2
    while pack_dir.exists():
        pack_dir = output_dir / f"handoff-{timestamp()}-{task_slug}-{counter}"
        counter += 1
    (pack_dir / "artifacts").mkdir(parents=True)
    (pack_dir / "sources").mkdir(parents=True)

    manifest_files = copy_group_files(pack_dir, group)
    excluded_files = excluded_unrelated(groups, group) + scan_excluded
    conversation_info = write_conversation_pack(
        pack_dir=pack_dir,
        workspace=workspace,
        group=group,
        conversation_files=conversation_files,
        include_codex=include_codex_conversation,
        session_root=conversation_dir,
        days=conversation_days,
        query=conversation_query,
        max_turns=max_conversation_turns,
        context_turns=conversation_context_turns,
    )
    manifest = write_pack_docs(
        pack_dir,
        workspace,
        group,
        groups,
        manifest_files,
        excluded_files,
        target_ai,
        conversation_info,
    )
    zip_path = make_zip(pack_dir)
    return pack_dir, zip_path, manifest


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an honest handoff pack for a content task.")
    parser.add_argument("--workspace", default=".", help="Workspace to scan. Default: current directory.")
    parser.add_argument("--task", default="", help="Task name or keyword to select a candidate task.")
    parser.add_argument("--core-file", default="", help="Core file path used to select the task cluster.")
    parser.add_argument("--target-ai", default="另一个 AI 工具", help="Target AI/tool name for RESUME_PROMPT.md.")
    parser.add_argument("--days", type=int, default=14, help="Recent-days signal for scoring only. Default: 14.")
    parser.add_argument("--max-size-mb", type=int, default=50, help="Skip individual files larger than this. Default: 50.")
    parser.add_argument("--output-dir", default="", help="Output directory. Default: <workspace>/handoffs.")
    parser.add_argument("--yes", action="store_true", help="Build the pack. Without --yes, only show candidate tasks.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown summary.")
    parser.add_argument(
        "--conversation-file",
        action="append",
        default=[],
        help="Explicit conversation file to include. Can be used more than once. Plain text/Markdown or Codex JSONL is supported.",
    )
    parser.add_argument(
        "--include-codex-conversation",
        action="store_true",
        help="Search ~/.codex/sessions for task-related user/assistant conversation snippets.",
    )
    parser.add_argument(
        "--conversation-dir",
        default=str(Path.home() / ".codex" / "sessions"),
        help="Codex sessions directory. Default: ~/.codex/sessions.",
    )
    parser.add_argument(
        "--conversation-days",
        type=int,
        default=14,
        help="Recent-days window for Codex conversation discovery. Default: 14.",
    )
    parser.add_argument(
        "--conversation-query",
        default="",
        help="Extra keywords for conversation matching, useful when the chat used a nickname or different task label.",
    )
    parser.add_argument(
        "--max-conversation-turns",
        type=int,
        default=80,
        help="Maximum conversation turns to include. Default: 80.",
    )
    parser.add_argument(
        "--conversation-context-turns",
        type=int,
        default=1,
        help="Neighbor turns to include around each matched conversation turn. Default: 1.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists() or not workspace.is_dir():
        print(f"Workspace not found: {workspace}", file=sys.stderr)
        return 2

    files, scan_excluded = scan_workspace(workspace, recent_days=args.days, max_size_mb=args.max_size_mb)
    query = args.task
    groups = cluster_files(files, query=query)

    core_file = None
    if args.core_file:
        core_file = Path(args.core_file).expanduser()
        if not core_file.is_absolute():
            core_file = workspace / core_file

    selected = select_group(groups, task=args.task, core_file=core_file, workspace=workspace)

    if args.json and not args.yes:
        print(json.dumps(discovery_json(groups, selected, scan_excluded), ensure_ascii=False, indent=2))
        return 0

    if not args.yes:
        print(candidate_summary(groups, selected, scan_excluded))
        return 0

    if not selected:
        print("No task candidate found.", file=sys.stderr)
        return 1

    if not args.task and not args.core_file:
        print(
            "Refusing to build without --task or --core-file. Run discovery first, confirm the task, then retry with --yes.",
            file=sys.stderr,
        )
        return 3

    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else workspace / "handoffs"
    output_dir.mkdir(parents=True, exist_ok=True)
    pack_dir, zip_path, manifest = build_pack(
        workspace=workspace,
        group=selected,
        groups=groups,
        scan_excluded=scan_excluded,
        output_dir=output_dir,
        target_ai=args.target_ai,
        conversation_files=args.conversation_file,
        include_codex_conversation=args.include_codex_conversation,
        conversation_dir=Path(args.conversation_dir).expanduser().resolve(),
        conversation_days=args.conversation_days,
        conversation_query=args.conversation_query,
        max_conversation_turns=args.max_conversation_turns,
        conversation_context_turns=args.conversation_context_turns,
    )

    result = {
        "task_title": selected.title,
        "pack_dir": str(pack_dir),
        "zip_path": str(zip_path),
        "included_files": len(manifest["files"]),
        "included_conversation_turns": manifest.get("conversation", {}).get("included_turns", 0),
        "excluded_files": len(manifest["excluded_files"]),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"已生成交接包：{pack_dir}")
        print(f"已生成 zip：{zip_path}")
        print(f"纳入文件：{result['included_files']} 个")
        if manifest.get("conversation", {}).get("enabled"):
            print(f"纳入对话回合：{result['included_conversation_turns']} 个")
        print(f"排除文件：{result['excluded_files']} 个")
    return 0


def discovery_json(groups: list[TaskGroup], selected: TaskGroup | None, excluded: list[dict]) -> dict:
    return {
        "recommended": selected.title if selected else None,
        "tasks": [
            {
                "title": group.title,
                "file_count": len(group.files),
                "tokens": group_common_tokens(group),
                "files": [
                    {
                        "path": file.relpath,
                        "role": file.role,
                        "role_label": role_label(file.role),
                        "title": file.title,
                        "size": file.size,
                    }
                    for file in priority_files(group)
                ],
            }
            for group in groups
        ],
        "excluded_files": excluded,
    }


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
