"""Self-Auditor — 의학 박사 관점 Medical-Agent 자가 진단 엔진.

실행 주기: 12시간마다 백그라운드 데몬 (mcp_server.py)
수동 실행: python scripts/self_evolution.py

진단 범위:
  1. 코드 품질 정적 분석 — CLAUDE.md 규칙 위반 자동 감지
  2. RAG 품질 — 도메인 관련성 점수 샘플링 (5개 쿼리)
  3. 파이프라인 상태 — 데이터셋 라이브러리 / 모듈 체인
  4. LLM 연결 + 응답 속도
  5. LLM 자기평가 — 궁극의 Medical Agent 관점 아키텍처 갭 분석

결과 저장:
  data/diagnostics/audit_log.json  — 최근 30회 진단 이력
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_AUDIT_LOG = Path("data/diagnostics/audit_log.json")
_MAX_LOG = 30

_SAMPLE_QUERIES = [
    "adolescent obesity Korea BMI KYRBS",
    "sleep quality smartphone Korean youth",
    "physical activity mental health adolescent Korea",
    "KNHANES cardiovascular metabolic syndrome",
    "depression suicidal ideation Korean adolescent survey",
]

_RULE_VIOLATIONS = [
    # (pattern_in_line, exclude_files, severity, type_name, description)
    ("except: pass",    [""],             "high",   "bare_except_pass",   "except: pass — 최소 _log.warning() 추가"),
    ("load_dotenv()",   ["config/env"],   "medium", "direct_load_dotenv", "load_dotenv() 직접 호출 — bootstrap() 사용"),
    ("getLogger(",      ["logging_config"], "low",  "direct_getLogger",   "logging.getLogger 직접 사용 — get_logger() 사용"),
]

_HARDCODED_MODELS = [
    "claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5",
    "gpt-4o", "gpt-4-turbo", "gpt-3.5",
]


class AuditResult:
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.code_issues: List[Dict] = []
        self.rag_health: Dict = {}
        self.pipeline_health: Dict = {}
        self.llm_health: Dict = {}
        self.llm_gaps: List[Dict] = []
        self.auto_fixes_applied: List[str] = []
        self.needs_approval: List[Dict] = []
        self.overall_score: int = 0
        self.duration_sec: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "overall_score": self.overall_score,
            "duration_sec": round(self.duration_sec, 1),
            "code_issues": self.code_issues,
            "rag_health": self.rag_health,
            "pipeline_health": self.pipeline_health,
            "llm_health": self.llm_health,
            "llm_gaps": self.llm_gaps,
            "auto_fixes_applied": self.auto_fixes_applied,
            "needs_approval": self.needs_approval,
        }


class SelfAuditor:
    """Medical-Agent 자가 진단 엔진."""

    def run_full_audit(self, with_llm_eval: bool = True) -> AuditResult:
        """전체 진단 실행.

        Args:
            with_llm_eval: LLM 아키텍처 갭 평가 포함 여부 (약 30초 추가 소요)
        """
        t0 = time.time()
        result = AuditResult()
        _log.info("자가 진단 시작 (llm_eval=%s)...", with_llm_eval)

        result.code_issues = self._scan_code_quality()
        result.rag_health = self._check_rag_health()
        result.pipeline_health = self._check_pipeline_health()
        result.llm_health = self._check_llm_health()

        if with_llm_eval:
            result.llm_gaps = self._llm_evaluate_gaps()

        result.overall_score = self._compute_score(result)
        result.duration_sec = time.time() - t0

        _save_audit(result)
        _log.info(
            "자가 진단 완료: score=%d, issues=%d, gaps=%d, %.1fs",
            result.overall_score, len(result.code_issues),
            len(result.llm_gaps), result.duration_sec,
        )
        return result

    def run_quick_audit(self) -> AuditResult:
        """빠른 진단 (LLM 갭 평가 제외) — 약 30초."""
        return self.run_full_audit(with_llm_eval=False)

    # ── 1. 코드 품질 정적 분석 ────────────────────────────────────────────

    def _scan_code_quality(self) -> List[Dict]:
        issues = []
        src = Path("src")
        if not src.exists():
            return issues

        for py_file in src.rglob("*.py"):
            rel = str(py_file).replace("\\", "/")
            try:
                lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue

            for i, line in enumerate(lines, 1):
                stripped = line.strip()

                # 규칙 위반 패턴 체크
                for pattern, excludes, severity, vtype, desc in _RULE_VIOLATIONS:
                    if pattern in stripped and not any(ex in rel for ex in excludes if ex):
                        # bare except: pass는 두 줄 패턴
                        if vtype == "bare_except_pass":
                            if stripped == "except:" and i < len(lines):
                                next_stripped = lines[i].strip() if i < len(lines) else ""
                                if next_stripped == "pass":
                                    issues.append(_issue(rel, i, severity, vtype, desc))
                            elif stripped == "except: pass":
                                issues.append(_issue(rel, i, severity, vtype, desc))
                        else:
                            issues.append(_issue(rel, i, severity, vtype, desc))

                # 하드코딩 모델명 (models.py, test 파일 제외)
                if "models.py" not in rel and "test_" not in rel and "self_auditor" not in rel:
                    for model_name in _HARDCODED_MODELS:
                        if f'"{model_name}"' in line or f"'{model_name}'" in line:
                            issues.append(_issue(rel, i, "medium", "hardcoded_model",
                                                 f"하드코딩 모델명: {model_name} — get_model() 사용"))
        return issues

    # ── 2. RAG 품질 샘플링 ───────────────────────────────────────────────

    def _check_rag_health(self) -> Dict:
        result: Dict = {"status": "unknown", "avg_score": None, "doc_count": 0, "issues": []}
        try:
            from src.vectordb.store import get_vector_store
            store = get_vector_store()
            count = store.count()
            result["doc_count"] = count

            if count == 0:
                result["status"] = "empty"
                result["issues"].append("RAG 스토어 비어있음 — 논문 인제스트 필요")
                return result

            scores = []
            for query in _SAMPLE_QUERIES[:3]:
                try:
                    hits = store.search(query, top_k=3)
                    scores.extend(h.get("score", 1.0) for h in (hits or []))
                except Exception as e:
                    _log.warning("RAG 샘플 쿼리 실패 '%s': %s", query, e)

            if scores:
                avg = sum(scores) / len(scores)
                result["avg_score"] = round(avg, 4)
                # cosine distance: 낮을수록 관련성 높음
                if avg < 0.3:
                    result["status"] = "excellent"
                elif avg < 0.5:
                    result["status"] = "good"
                elif avg < 0.7:
                    result["status"] = "fair"
                    result["issues"].append(f"RAG 관련성 보통 (avg_dist={avg:.3f}) — 도메인 논문 추가 권장")
                else:
                    result["status"] = "poor"
                    result["issues"].append(f"RAG 관련성 낮음 (avg_dist={avg:.3f}) — 재인제스트 필요")
            else:
                result["status"] = "no_results"
                result["issues"].append("RAG 검색 결과 없음 — 인덱스 이상")
        except Exception as e:
            result["status"] = "error"
            result["issues"].append(f"RAG 체크 오류: {str(e)[:120]}")
        return result

    # ── 3. 파이프라인 상태 ───────────────────────────────────────────────

    def _check_pipeline_health(self) -> Dict:
        result: Dict = {"status": "ok", "checks": {}, "issues": []}
        checks = {
            "dataset_library": ("src.library.dataset_library", "DatasetLibrary"),
            "methods_library": ("src.library.methods_library", "MethodsLibrary"),
            "novelty_checker": ("src.research.novelty_checker", "NoveltyChecker"),
            "paper_writer": ("src.research.paper_writer", "PaperWriter"),
            "rag_pipeline": ("src.rag.pipeline", "RAGPipeline"),
            "persona": ("src.agent.persona", "get_persona"),
            "conversation_memory": ("src.memory.conversation_memory", "record"),
            "medical_ontology": ("src.knowledge.medical_ontology", "MedicalOntology"),
            "medical_graph": ("src.knowledge.medical_graph", "get_graph"),
        }
        for name, (mod, attr) in checks.items():
            try:
                m = __import__(mod, fromlist=[attr])
                getattr(m, attr)
                result["checks"][name] = "ok"
            except Exception as e:
                result["checks"][name] = "fail"
                result["issues"].append(f"{name}: {str(e)[:80]}")

        # 데이터셋 라이브러리 실제 데이터 확인
        try:
            from src.library.dataset_library import DatasetLibrary
            lib = DatasetLibrary("data/libraries")
            for ds in ["KYRBS", "KNHANES"]:
                ctx = lib.get_context(ds)
                if not ctx or len(ctx) < 100:
                    result["issues"].append(f"{ds} 데이터셋 컨텍스트 부족 — seed 필요")
        except Exception as e:
            result["issues"].append(f"데이터셋 라이브러리 오류: {str(e)[:80]}")

        if result["issues"]:
            result["status"] = "degraded" if len(result["issues"]) < 3 else "failing"
        return result

    # ── 4. LLM 연결 + 응답 속도 ──────────────────────────────────────────

    def _check_llm_health(self) -> Dict:
        result: Dict = {"status": "unknown", "response_ms": None, "model": "", "issues": []}
        try:
            from src.llm import get_llm_client
            from src.config.models import get_model
            _, model_id = get_model("fast")
            result["model"] = model_id

            client = get_llm_client(task="fast")
            t0 = time.time()
            resp = client.generate("Reply with exactly one word: OK", max_tokens=10, task="fast")
            ms = int((time.time() - t0) * 1000)
            result["response_ms"] = ms

            if resp and len(resp) > 0:
                result["status"] = "ok"
            else:
                result["status"] = "empty_response"
                result["issues"].append("LLM 응답이 비어있음")

            if ms > 15000:
                result["issues"].append(f"LLM 응답 느림: {ms}ms (15초 초과)")
        except Exception as e:
            result["status"] = "error"
            result["issues"].append(f"LLM 연결 오류: {str(e)[:120]}")
        return result

    # ── 5. LLM 아키텍처 갭 평가 ──────────────────────────────────────────

    def _llm_evaluate_gaps(self) -> List[Dict]:
        """Claude가 의학 박사 관점에서 현재 아키텍처 갭을 평가."""
        try:
            from src.llm import get_llm_client
            client = get_llm_client(task="standard")

            arch = _build_arch_summary()
            prompt = f"""You are a senior medical informatics researcher and AI architect.
Evaluate this Medical Research Agent system that generates Korean public health papers (KYRBS/KNHANES datasets).

SYSTEM ARCHITECTURE:
{arch}

GOAL: Become the ULTIMATE Medical Research Agent — autonomous, publication-quality, PhD-level reasoning about Korean public health, continuous self-improvement.

Identify the 5 most critical gaps or improvement opportunities. For each:
- What is missing or suboptimal
- Why it matters for research quality
- A concrete, implementable solution
- Whether it can be applied automatically (no code review needed) or needs manual approval

Return JSON array only:
[
  {{
    "priority": 1,
    "gap": "description",
    "impact": "why this matters",
    "solution": "concrete implementable solution",
    "auto": true,
    "category": "rag|pipeline|persona|code_quality|ux|data|reasoning"
  }}
]"""

            raw = client.generate(prompt, max_tokens=2000, task="standard")
            raw = raw.strip()
            # JSON 추출
            if "```" in raw:
                parts = raw.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("["):
                        raw = part
                        break
            if raw.startswith("["):
                gaps = json.loads(raw)
                return [g for g in gaps if isinstance(g, dict)]
        except Exception as e:
            _log.warning("LLM 갭 평가 오류: %s", e)
        return []

    # ── 점수 계산 ─────────────────────────────────────────────────────────

    def _compute_score(self, result: AuditResult) -> int:
        score = 100

        high = sum(1 for i in result.code_issues if i.get("severity") == "high")
        med = sum(1 for i in result.code_issues if i.get("severity") == "medium")
        score -= high * 8
        score -= med * 3

        rag_status = result.rag_health.get("status", "unknown")
        rag_penalty = {"excellent": 0, "good": -5, "fair": -15, "poor": -25,
                       "empty": -30, "error": -20, "no_results": -15, "unknown": -10}
        score += rag_penalty.get(rag_status, -10)

        if result.llm_health.get("status") not in ("ok",):
            score -= 20

        failing_checks = sum(1 for v in result.pipeline_health.get("checks", {}).values() if v == "fail")
        score -= failing_checks * 5

        score -= len(result.llm_gaps) * 2

        return max(0, min(100, score))


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _issue(file: str, line: int, severity: str, vtype: str, desc: str) -> Dict:
    return {"file": file, "line": line, "severity": severity, "type": vtype, "text": desc}


def _build_arch_summary() -> str:
    lines = ["=== Medical-Agent Architecture ==="]
    src = Path("src")
    for subdir in sorted(src.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("_"):
            py_files = [f.stem for f in subdir.glob("*.py") if f.stem != "__init__"]
            if py_files:
                lines.append(f"src/{subdir.name}/: {', '.join(py_files)}")

    for d in ["data/agent_self", "data/libraries", "data/diagnostics"]:
        p = Path(d)
        if p.exists():
            files = [f.name for f in p.glob("*.json")]
            if files:
                lines.append(f"{d}/: {', '.join(files)}")

    try:
        from src.vectordb.store import get_vector_store
        count = get_vector_store().count()
        lines.append(f"RAG chunks: {count}")
    except Exception:
        pass

    try:
        from src.memory.agent_insight import get_all
        lines.append(f"Agent insights: {len(get_all(n=500))}")
    except Exception:
        pass

    try:
        from src.knowledge.medical_graph import get_graph
        stats = get_graph().stats()
        lines.append(f"Knowledge graph: {stats.get('nodes', 0)} nodes, {stats.get('edges', 0)} edges")
    except Exception:
        pass

    try:
        from src.agent.persona import get_persona
        pstatus = get_persona().status()
        lines.append(f"Persona perspectives: {pstatus.get('perspectives_count', 0)}, evolutions: {pstatus.get('evolution_count', 0)}")
    except Exception:
        pass

    return "\n".join(lines)


def _load_audit_log() -> List[Dict]:
    if not _AUDIT_LOG.exists():
        return []
    try:
        return json.loads(_AUDIT_LOG.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_audit(result: AuditResult) -> None:
    _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = _load_audit_log()
    log.insert(0, result.to_dict())
    _AUDIT_LOG.write_text(
        json.dumps(log[:_MAX_LOG], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_last_audit() -> Optional[Dict]:
    log = _load_audit_log()
    return log[0] if log else None


def get_audit_history(n: int = 10) -> List[Dict]:
    return _load_audit_log()[:n]
