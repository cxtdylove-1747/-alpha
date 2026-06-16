from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from django.db import transaction

from .models import CaseLibraryDocument
from .pdf_utils import parse_pdf
from .utils import digest_text, mask_text

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx"}

INDUSTRY_KEYWORDS = {
	"AI科技": ["ai", "算法", "智能", "机器学习", "大模型", "芯片"],
	"教育创新": ["教育", "教学", "课堂", "学习", "校园"],
	"环保公益": ["环保", "低碳", "公益", "绿色", "节能", "减排"],
	"医疗健康": ["医疗", "健康", "诊断", "医生", "药", "病"],
	"工业制造": ["制造", "工业", "装备", "机器人", "工艺"],
	"农业发展": ["农业", "农", "种植", "养殖", "乡村"],
	"政务管理": ["政务", "治理", "公共服务", "政府"],
	"交通运输": ["交通", "运输", "物流", "出行"],
	"文化旅游": ["文旅", "文化", "旅游", "景区"],
}

SCORE_TAG_RULES = {
	"innovation": ["创新", "差异", "首创", "独特"],
	"logic": ["痛点", "方案", "路径", "闭环"],
	"feasibility": ["成本", "资源", "风险", "实施", "里程碑"],
	"completeness": ["市场", "团队", "财务", "计划"],
	"competition": ["大赛", "评审", "评分", "奖项"],
}


def _strip_noise(text: str) -> str:
	text = text or ""
	text = re.sub(r"\s+", " ", text)
	text = re.sub(r"(目录|封面|版权声明|致谢){2,}", "", text)
	return text.strip()


def _extract_key_sentences(text: str, keywords: list[str], limit: int = 3) -> list[str]:
	if not text:
		return []
	segments = re.split(r"[。！？\n]", text)
	hits = []
	for seg in segments:
		s = seg.strip()
		if len(s) < 8:
			continue
		if any(k in s for k in keywords):
			hits.append(s[:120])
		if len(hits) >= limit:
			break
	return hits


def _classify_industry(title: str, text: str) -> str:
	haystack = f"{title} {text}".lower()
	for name, keys in INDUSTRY_KEYWORDS.items():
		if any(k in haystack for k in keys):
			return name
	return "其他"


def _classify_score_tags(text: str) -> list[str]:
	tags = []
	for code, keys in SCORE_TAG_RULES.items():
		if any(k in text for k in keys):
			tags.append(code)
	return tags or ["completeness"]


def _extract_core_facts(title: str, text: str) -> dict[str, Any]:
	return {
		"basic": {"case_name": title},
		"innovation": _extract_key_sentences(text, ["创新", "差异", "独特", "首创"]),
		"logic": _extract_key_sentences(text, ["痛点", "解决", "盈利", "实施", "计划"]),
		"feasibility": _extract_key_sentences(text, ["成本", "资源", "风险", "验证"]),
		"competition_fit": _extract_key_sentences(text, ["大赛", "评审", "评分", "示范"]),
	}


def _run_office_to_pdf(source_path: str, target_dir: str) -> str:
	soffice = shutil.which("soffice")
	if not soffice:
		return ""
	try:
		subprocess.run(
			[soffice, "--headless", "--convert-to", "pdf", "--outdir", target_dir, source_path],
			check=True,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			timeout=120,
		)
	except Exception:
		return ""
	base_name = Path(source_path).stem + ".pdf"
	out = Path(target_dir) / base_name
	return str(out) if out.exists() else ""


def _normalize_to_pdf(source_path: str, normalized_root: str) -> str:
	ext = Path(source_path).suffix.lower()
	Path(normalized_root).mkdir(parents=True, exist_ok=True)
	if ext == ".pdf":
		target = Path(normalized_root) / Path(source_path).name
		if Path(source_path).resolve() != target.resolve():
			shutil.copyfile(source_path, target)
		return str(target)
	return _run_office_to_pdf(source_path, normalized_root)


def _iter_case_files(root: str):
	for current, dirs, files in os.walk(root):
		dirs[:] = [d for d in dirs if d != "__MACOSX"]
		for file_name in files:
			path = os.path.join(current, file_name)
			if Path(path).suffix.lower() in SUPPORTED_EXTENSIONS:
				yield path


def _relative_source_path(file_path: str, project_root: str) -> str:
	try:
		return str(Path(file_path).resolve().relative_to(Path(project_root).resolve()))
	except Exception:
		return str(Path(file_path).resolve())


def _build_synthetic_cases(real_cases: list[CaseLibraryDocument], max_ratio: float = 0.3) -> list[dict[str, Any]]:
	if not real_cases:
		return []
	target_count = int(len(real_cases) * max_ratio)
	synthetic_payload = []
	for idx, case in enumerate(real_cases[:target_count], start=1):
		facts = case.core_facts or {}
		synthetic_payload.append(
			{
				"title": f"补充案例{idx}-{case.industry_category}",
				"industry_category": case.industry_category,
				"score_tags": case.score_tags,
				"core_facts": {
					"basic": {"case_name": f"阶段化演练案例{idx}"},
					"innovation": (facts.get("innovation") or [])[:1] + ["在原案例基础上增加细分场景验证"],
					"logic": (facts.get("logic") or [])[:1] + ["强调从痛点到验证结果的可追踪闭环"],
					"feasibility": (facts.get("feasibility") or [])[:1] + ["补充低成本试点与风险预案"],
					"competition_fit": ["用于课堂反例对比与阶段优化训练"],
				},
				"source_case_id": case.id,
			}
		)
	return synthetic_payload


@transaction.atomic
def ingest_case_library(
	data_root: str,
	project_root: str,
	normalized_dir: str,
	include_synthetic: bool = True,
) -> dict[str, Any]:
	scanned = 0
	imported = 0
	skipped = 0
	errors = []
	imported_ids = []

	for source in _iter_case_files(data_root):
		scanned += 1
		source_rel = _relative_source_path(source, project_root)
		ext = Path(source).suffix.lower().lstrip(".")

		normalized_pdf = _normalize_to_pdf(source, normalized_dir)
		extracted_text = ""
		page_count = 0
		if normalized_pdf and Path(normalized_pdf).exists():
			try:
				parsed = parse_pdf(normalized_pdf)
				extracted_text = parsed.get("text", "")
				page_count = parsed.get("page_count", 0)
			except Exception as exc:
				errors.append(f"parse_failed:{source_rel}:{exc}")
		else:
			extracted_text = Path(source).stem

		cleaned = _strip_noise(extracted_text)
		title = Path(source).stem[:255]
		industry = _classify_industry(title, cleaned)
		score_tags = _classify_score_tags(cleaned)
		core_facts = _extract_core_facts(title, cleaned)

		fingerprint = digest_text(f"{source_rel}:{cleaned[:2000]}")
		defaults = {
			"title": title,
			"source_format": ext if ext in {"pdf", "docx", "pptx"} else "pdf",
			"normalized_pdf_path": _relative_source_path(normalized_pdf, project_root) if normalized_pdf else "",
			"extracted_text": mask_text(cleaned),
			"page_count": page_count,
			"industry_category": industry,
			"score_tags": score_tags,
			"core_facts": core_facts,
			"is_synthetic": False,
			"clean_status": CaseLibraryDocument.CLEAN_DONE,
			"privacy_masked": True,
			"fingerprint": fingerprint,
		}
		obj, created = CaseLibraryDocument.objects.update_or_create(source_path=source_rel, defaults=defaults)
		if created:
			imported += 1
		else:
			skipped += 1
		imported_ids.append(obj.id)

	synthetic_created = 0
	if include_synthetic:
		real_cases = list(CaseLibraryDocument.objects.filter(id__in=imported_ids, is_synthetic=False))
		for payload in _build_synthetic_cases(real_cases):
			source_marker = f"synthetic:{payload['source_case_id']}:{payload['title']}"
			_, created = CaseLibraryDocument.objects.get_or_create(
				source_path=source_marker,
				defaults={
					"title": payload["title"],
					"source_format": "pdf",
					"normalized_pdf_path": "",
					"extracted_text": "",
					"page_count": 0,
					"industry_category": payload["industry_category"],
					"score_tags": payload["score_tags"],
					"core_facts": payload["core_facts"],
					"is_synthetic": True,
					"source_case_id": payload["source_case_id"],
					"clean_status": CaseLibraryDocument.CLEAN_DONE,
					"privacy_masked": True,
					"fingerprint": digest_text(source_marker),
				},
			)
			if created:
				synthetic_created += 1

	return {
		"scanned": scanned,
		"imported": imported,
		"skipped": skipped,
		"synthetic_created": synthetic_created,
		"errors": errors[:100],
	}


def export_case_core_table(output_path: str) -> str:
	rows = []
	for item in CaseLibraryDocument.objects.filter(clean_status=CaseLibraryDocument.CLEAN_DONE).order_by("-updated_at"):
		facts = item.core_facts or {}
		rows.append(
			{
				"case_name": item.title,
				"industry": item.industry_category,
				"innovation": (facts.get("innovation") or [])[:2],
				"logic": (facts.get("logic") or [])[:2],
				"feasibility": (facts.get("feasibility") or [])[:2],
				"competition_fit": (facts.get("competition_fit") or [])[:2],
				"score_tags": item.score_tags,
				"is_synthetic": item.is_synthetic,
			}
		)
	out = Path(output_path)
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
	return str(out)


