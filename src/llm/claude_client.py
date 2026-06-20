"""Claude API client — streaming, prompt caching, extended thinking.

수정 사항 (버그 수정):
  1. thinking={"type":"adaptive"} → 중앙 models.py의 thinking_config() 사용
  2. _stream() max_tokens 파라미터 누락 → 수정
  3. 여러 모듈의 dotenv 중복 로드 → src.config.env.bootstrap() 사용
  4. 모델명 하드코딩 → src.config.models.get_model() 사용
"""
from __future__ import annotations

import os
from typing import Dict, Iterator, List, Optional

from src.config.env import bootstrap
from src.config.logging_config import get_logger
from src.config.models import get_model, thinking_config

_log = get_logger(__name__)


def _ground_truth_block() -> str:
    """FIX-9 (2026-06-14): 로컬 PS1 훅이 prepend하던 ground-truth를 런타임에서 합성.

    PowerShell 훅 (.claude/hooks/preprompt_memory_inject.ps1) 은 로컬 VS Code 전용.
    HF Spaces 같은 웹 런타임은 PS1이 없어 CURRENT_STATE.json / CLAUDE.md 규칙을
    못 읽음 → 로컬 vs 웹 컨텍스트 불일치.

    이 함수가 파이썬으로 동일 ground-truth를 합성해 build_base_system에 주입.
    """
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent.parent
    parts = []

    # 1. CURRENT_STATE.json — verified_counts (진실원본)
    try:
        cs = json.loads((root / "CURRENT_STATE.json").read_text(encoding="utf-8"))
        vc = cs.get("verified_counts", {})
        if vc:
            kab = cs.get("key_assets_by_size", {})
            line = (
                f"# GROUND TRUTH (auto-injected, measured {vc.get('measured_at', '?')}):\n"
                f"- OA papers full-text: {vc.get('papers',{}).get('full_text_files','?')} "
                f"(>5KB: {vc.get('papers',{}).get('full_text_above_5kb','?')}, "
                f"{vc.get('papers',{}).get('full_text_completion_pct','?')}%)\n"
                f"- RAG chunks (ChromaDB): {vc.get('chromadb',{}).get('embeddings','?')} "
                f"+ queue {vc.get('chromadb',{}).get('queue_pending','?')}\n"
                f"- Knowledge graph: {vc.get('knowledge_graph',{}).get('nodes_total','?')} nodes / "
                f"{vc.get('knowledge_graph',{}).get('edges_total','?')} edges "
                f"(file: {vc.get('knowledge_graph',{}).get('file','?')})\n"
                f"- Medical ontology: {vc.get('ontology',{}).get('concept_count','?')} concepts\n"
                f"- Yoosun seed: {vc.get('yoosun_seed',{}).get('analyzed_papers','?')} papers analysed\n"
                f"- Per-user style profiles: {vc.get('style_profiles',{}).get('per_user_profiles','?')}\n"
                f"- Supabase live: {vc.get('supabase',{}).get('cloud_available', False)}\n"
            )
            parts.append(line)
    except Exception:
        pass

    # 2. CLAUDE.md core rules (압축 추출 — 핵심 12 규칙 요약만)
    rules = (
        "# PROJECT RULES (CLAUDE.md compressed):\n"
        "- RULE-7: NO placeholder words like '양식' in Korean output.\n"
        "- RULE-8: VIBE PAPER — user-driven, AI assists, no auto-pipeline unless user says '알아서 해'.\n"
        "- RULE-9: ONLINE-FIRST — all features must work from external URL.\n"
        "- RULE-11: NO LIES — if not done, report 'not done + reason'. No fake completion claims.\n"
        "- RULE-12: SINGLE CORE — persona/prompts/memory/events/router all share one backend.\n"
        "- Stats: LLM does NOT compute statistics. Use stat_bridge for OR/CI/p/n.\n"
        "- Citations: only PMIDs that exist in graph or RAG. Fabrication = reject.\n"
        "- Manuscript: English only. Chat: Korean OK.\n"
    )
    parts.append(rules)

    return "\n\n".join(parts) if parts else ""


def build_base_system(base_prompt: str, task: str = "general",
                        owner_email: str | None = None) -> str:
    """페르소나 + medical seed + 인사이트 + 리뷰어 패턴 + 자기개선 + base를 합친
    시스템 프롬프트 문자열. ClaudeClient와 GeminiClient/OpenAIClient가 공유해
    어떤 LLM으로 폴백돼도 페르소나 일관성을 유지한다 (규칙 9).

    FIX-1 (2026-06-13): owner_email 인자 추가. paper_write 계열은 StyleProfile 우선.
    FIX-9 (2026-06-14): 웹 런타임 ground-truth 주입 — CURRENT_STATE.json + CLAUDE.md
        핵심 규칙을 파이썬으로 합성해 로컬 PS1 훅과 동등화.
    """
    # 1. 페르소나 (항상 최우선) — per-user persona 우선
    persona_prompt = ""
    try:
        from src.agent.persona import get_system_prompt
        persona_prompt = get_system_prompt(task=task, owner_email=owner_email)
    except Exception:
        pass
    # 2. 의학 지식 프리앰블
    preamble = ""
    try:
        from src.knowledge.medical_seed import get_medical_preamble
        preamble = get_medical_preamble()
    except Exception:
        pass
    # 3. 축적 연구 인사이트 (research/paper 태스크)
    insight_block = ""
    _research_tasks = {"paper_writing", "paper_review", "topic_generation",
                       "novelty_check", "feasibility", "general"}
    if task in _research_tasks:
        try:
            from src.memory.agent_insight import build_self_context
            ctx = build_self_context()
            if ctx and len(ctx) > 20:
                insight_block = ctx
        except Exception:
            pass
    # 4. 실 리뷰어 피드백 패턴 (paper_writing)
    reviewer_block = ""
    if task in {"paper_writing", "paper_review"}:
        try:
            from src.memory.user_feedback_store import get_reviewer_patterns
            patterns = get_reviewer_patterns(top_n=5)
            if patterns and len(patterns) > 30:
                reviewer_block = patterns
        except Exception:
            pass
    # 5. 역량 자기개선 컨텍스트 (Phase C 루프)
    improvement_block = ""
    if task in {"paper_writing", "paper_review"}:
        try:
            from src.diagnostics.capability_bench import get_improvement_context
            imp = get_improvement_context()
            if imp and len(imp) > 30:
                improvement_block = imp
        except Exception:
            pass
    # 6. 연구 설계 패턴 주입 (논문 작성 시 — '논문 구조 라인' 학습)
    design_block = ""
    if task == "paper_writing":
        try:
            from src.library.design_template import DesignTemplate
            d = DesignTemplate().build_context("kyrbs_cross_sectional")
            if d and len(d) > 50:
                design_block = d
        except Exception:
            pass

    # 7. ★ Versioned prompts (medical_core + safety_constraints + task별 style) — ★최우선 task 정합
    #    `prompts/*.md` + `src/agent/prompt_loader.py`가 task→md 합성. paper_writing/paper_write는
    #    yoosun_style.md + raw_examples 3편이 자동 첨부. safety_constraints는 모든 task 필수.
    #    이 블록이 들어가면서 "환각 차단/임상키워드/truth hierarchy" 규약이 모든 LLM 호출에 강제됨.
    versioned_block = ""
    try:
        from src.agent.prompt_loader import load_prompt
        # paper_writing alias → paper_write composition. owner_email로 per-user style.
        _task_map = {"paper_writing": "paper_write", "paper_review": "paper_write"}
        pl_task = _task_map.get(task, task)
        versioned_block = load_prompt(pl_task, owner_email=owner_email) or ""
    except Exception as _e:
        # 안전망: prompt_loader 실패해도 페르소나/베이스는 그대로 살아있음
        pass

    # ── ★ 무의식 임프린트 (2026-05-30) — 현재 사용자 의도를 자동 픽업 ──
    # 사용자가 prompt 하나 입력하면 intent_sensor.set_current로 박혀, 이후 모든 LLM 호출이
    # 명시 전달 없이 자동으로 그 의도/뉘앙스/페르소나를 system_prompt에 임프린트.
    intent_block = ""
    try:
        from src.agent.intent_sensor import get_current as _intent_get
        sig = _intent_get()
        if sig is not None:
            intent_block = sig.to_system_block() or ""
    except Exception:
        pass

    # FIX-9: ground-truth (CURRENT_STATE.json + CLAUDE.md rules) — 항상 최상단
    ground_truth = ""
    try:
        ground_truth = _ground_truth_block()
    except Exception:
        pass

    parts = [p for p in [ground_truth, persona_prompt, versioned_block, preamble, intent_block,
                         insight_block, reviewer_block, improvement_block,
                         design_block, base_prompt or ""] if p]
    return "\n\n---\n\n".join(parts) if parts else "You are a helpful medical research assistant."


class ClaudeClient:
    """Anthropic Python SDK 래퍼.

    - 모델은 src.config.models에서 task 기반으로 자동 선택
    - Extended thinking: premium/standard task에서 자동 활성화
    - Prompt caching: 반복 컨텍스트를 ephemeral cache로 처리
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        task: str = "standard",
    ):
        bootstrap()  # .env 1회 로드 (이미 로드됐으면 무시)

        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "ANTHROPIC_API_KEY가 설정되지 않았습니다.\n"
                "Medical-Agent/.env 파일에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하세요."
            )

        import anthropic
        self._client = anthropic.Anthropic(api_key=resolved_key)

        # 모델: 명시 지정 > 환경변수 오버라이드 > task 기반 자동 선택
        if model:
            self.model = model
        else:
            _, self.model = get_model(task)

        self._task = task
        _log.debug(f"ClaudeClient 초기화: model={self.model}, task={task}")

    # ── Core generation ───────────────────────────────────────────────────────

    def generate(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        stream: bool = False,
        max_tokens: int = 4096,
        task: Optional[str] = None,
    ) -> str:
        """텍스트 생성.

        Args:
            user_message: 질문 또는 지시
            system_prompt: 역할/지시 프롬프트
            context_chunks: 검색된 논문 청크 (prompt cache 적용)
            stream: True면 streaming 사용
            max_tokens: 최대 출력 토큰
            task: thinking 레벨 결정용 task 이름 (기본: 초기화 시 task)
        """
        effective_task = task or self._task
        system = self._build_system(system_prompt, context_chunks, task=effective_task)
        messages = [{"role": "user", "content": user_message}]

        if stream:
            return self._stream(system, messages, max_tokens=max_tokens, task=effective_task)

        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        t_cfg = thinking_config(effective_task)
        if t_cfg and t_cfg.get("type") == "enabled":
            # budget_tokens must be strictly less than max_tokens
            if t_cfg.get("budget_tokens", 0) >= max_tokens:
                t_cfg = {"type": "disabled"}
        if t_cfg:
            kwargs["thinking"] = t_cfg

        # ── Tracing + Provenance: 한 호출의 span + fingerprint 자동 적재 ──
        # (실패해도 본 호출은 살아있어야 함 — 모두 graceful)
        try:
            from src.runtime.tracing import trace_span as _trace_span
            from src.runtime import provenance as _prov
        except Exception:
            _trace_span = None
            _prov = None

        if _trace_span is None:
            # tracing 로드 실패 — 원래 경로 그대로
            try:
                response = self._client.messages.create(**kwargs)
            except Exception as e:
                if "thinking" in str(e).lower() and "thinking" in kwargs:
                    _log.warning(f"thinking 파라미터 미지원, 재시도: {e}")
                    del kwargs["thinking"]
                    response = self._client.messages.create(**kwargs)
                else:
                    raise
            return self._extract_text(response)

        with _trace_span(
            "llm.anthropic.generate",
            provider="anthropic", model=self.model, task=effective_task,
            prompt_sha=_prov.text_hash(user_message),
            system_sha=_prov.text_hash(system),
        ) as _sp:
            try:
                response = self._client.messages.create(**kwargs)
            except Exception as e:
                if "thinking" in str(e).lower() and "thinking" in kwargs:
                    _log.warning(f"thinking 파라미터 미지원, 재시도: {e}")
                    del kwargs["thinking"]
                    response = self._client.messages.create(**kwargs)
                else:
                    raise

            text = self._extract_text(response)
            # usage 추출 — Anthropic SDK response.usage.{input,output}_tokens
            usage = getattr(response, "usage", None)
            t_in = int(getattr(usage, "input_tokens", 0) or 0)
            t_out = int(getattr(usage, "output_tokens", 0) or 0)
            _sp.update(tokens_in=t_in, tokens_out=t_out,
                       response_sha=_prov.text_hash(text),
                       response_len=len(text or ""))
            try:
                _prov.auto_record_llm_call(
                    provider="anthropic", model=self.model,
                    prompt=user_message, system_prompt=system,
                    response_sha=_prov.text_hash(text),
                    tokens_in=t_in, tokens_out=t_out, latency_ms=0,
                )
            except Exception:
                pass
            return text

    def generate_with_tools_streamed(
        self,
        user_message: str,
        tools: List[dict],
        tool_handler: callable,
        system_prompt: str = "",
        max_tokens: int = 4096,
        max_iters: int = 6,
        task: Optional[str] = None,
        prior_messages: Optional[List[dict]] = None,
    ):
        """★ Streaming + tools generator (2026-06-15).

        토큰 단위 yield → 사용자가 텍스트 한 글자씩 흘러나오는 효과 (Claude/VS Code 양식).
        tool_use 블록은 streaming 끝난 후 dispatch → tool_start/tool_result yield.

        Args:
            prior_messages: 이전 대화 누적 (project["messages"]). 양식 = [{"role": "user|assistant",
                "content": str}, ...]. ★ 2026-06-20: 이 인자가 누락되어 있어 ezhome agent가
                매 turn마다 직전 대화를 다 까먹는 양식 (VS Code Claude와 결정적 성능 차이 단일원인).

        Yields:
            {"type":"text_delta", "text": "..."} — 토큰 청크
            {"type":"tool_start", "tool": "...", "input": {...}}
            {"type":"tool_result", "tool": "...", "result_preview": "..."}
            {"type":"done", "text": "...전체...", "trace": [...]}
        """
        effective_task = task or self._task
        system = self._build_system(system_prompt, None, task=effective_task)
        messages: List[dict] = []
        # ★ prior_messages 누적 (사용자 정직 지적 2026-06-20: "동일 컨텍스트 100턴은 해야지")
        # 최근 100턴 · turn별 6K char 상한 → 합산 ~150K tokens (Anthropic 200K 안전 한도).
        if prior_messages:
            for m in prior_messages[-100:]:
                r = m.get("role")
                c = m.get("content")
                if r in ("user", "assistant") and isinstance(c, str) and c.strip():
                    messages.append({"role": r, "content": c[:6000]})
        messages.append({"role": "user", "content": user_message})
        trace: list = []
        full_text_parts: list = []

        for it in range(max_iters):
            tool_uses: list = []
            text_in_iter: list = []
            assistant_blocks: list = []
            current_text_block: list = []

            try:
                kwargs = dict(model=self.model, max_tokens=max_tokens,
                                system=system, messages=messages, tools=tools)
                with self._client.messages.stream(**kwargs) as stream:
                    for event in stream:
                        et = getattr(event, "type", None)
                        # input_json_delta는 tool_use 인자를 stream으로 보냄 → 무시
                        if et == "content_block_start":
                            block = getattr(event, "content_block", None)
                            btype = getattr(block, "type", None)
                            if btype == "tool_use":
                                tool_uses.append({"id": getattr(block, "id", ""),
                                                    "name": getattr(block, "name", ""),
                                                    "input": {}})
                                if current_text_block:
                                    assistant_blocks.append({
                                        "type": "text",
                                        "text": "".join(current_text_block)})
                                    current_text_block = []
                        elif et == "content_block_delta":
                            d = getattr(event, "delta", None)
                            dtype = getattr(d, "type", None)
                            if dtype == "text_delta":
                                txt = getattr(d, "text", "")
                                if txt:
                                    text_in_iter.append(txt)
                                    current_text_block.append(txt)
                                    yield {"type": "text_delta", "text": txt}
                            elif dtype == "input_json_delta":
                                # tool input 누적 (json delta)
                                pj = getattr(d, "partial_json", "")
                                if tool_uses and pj:
                                    tool_uses[-1].setdefault("_buf", "")
                                    tool_uses[-1]["_buf"] += pj
                        elif et == "content_block_stop":
                            # tool_use 마감 — buf → json
                            if tool_uses and tool_uses[-1].get("_buf") is not None:
                                try:
                                    import json as _j
                                    tool_uses[-1]["input"] = _j.loads(tool_uses[-1].pop("_buf"))
                                except Exception:
                                    tool_uses[-1]["input"] = {}
                    # Get final message for stop_reason
                    final = stream.get_final_message()
                    stop_reason = getattr(final, "stop_reason", "")
            except Exception as e:
                _log.warning("stream + tools fail iter %d: %s", it, e)
                yield {"type": "error", "msg": str(e)[:200]}
                break

            # Close out text in iter
            if current_text_block:
                assistant_blocks.append({"type": "text",
                                            "text": "".join(current_text_block)})

            full_text_parts.extend(text_in_iter)

            # No tools called → done
            if not tool_uses:
                yield {"type": "done", "text": "".join(full_text_parts),
                        "trace": trace, "stop_reason": stop_reason, "iters": it + 1}
                return

            # Append tool_use blocks to assistant + dispatch
            for tu in tool_uses:
                assistant_blocks.append({"type": "tool_use",
                                            "id": tu["id"], "name": tu["name"],
                                            "input": tu.get("input", {})})
            messages.append({"role": "assistant", "content": assistant_blocks})

            tool_results = []
            for tu in tool_uses:
                yield {"type": "tool_start", "tool": tu["name"],
                        "input": tu.get("input", {})}
                try:
                    result = tool_handler(tu["name"], tu.get("input", {}))
                except Exception as e:
                    result = f"ERROR: {e}"
                rs = result if isinstance(result, str) else str(result)
                trace.append({"tool": tu["name"], "input": tu.get("input", {}),
                                "result_preview": rs[:200]})
                yield {"type": "tool_result", "tool": tu["name"],
                        "result_preview": rs[:400]}
                tool_results.append({"type": "tool_result",
                                       "tool_use_id": tu["id"],
                                       "content": rs[:8000]})
            messages.append({"role": "user", "content": tool_results})

        # Hit max_iters
        yield {"type": "done", "text": "".join(full_text_parts),
                "trace": trace, "stop_reason": "max_iters", "iters": max_iters}


    def generate_with_tools(
        self,
        user_message: str,
        tools: List[dict],
        tool_handler: callable,
        system_prompt: str = "",
        max_tokens: int = 4096,
        max_iters: int = 6,
        task: Optional[str] = None,
    ) -> dict:
        """★ Agentic loop — Claude가 직접 tool을 호출하며 task 수행 (ReAct/Plan-Execute).

        Args:
            tools: Anthropic tool_use 스키마. 예:
                   [{"name": "search_pubmed", "description": "...",
                     "input_schema": {"type": "object", "properties": {...}}}]
            tool_handler: callable(name, input) → str. 도구 실행 결과 반환.
                          `src.tools.run_tool`을 그대로 넘기면 됨.
            max_iters: tool 호출-결과-재호출 사이클 최대 반복 (무한루프 방지).

        Returns:
            {"text": str (최종 응답), "trace": [{"tool": str, "input": dict, "result_preview": str}],
             "stop_reason": str, "iters": int}

        events.db에 각 step을 'tool_call' 타입으로 기록 → replay 가능.
        """
        effective_task = task or self._task
        system = self._build_system(system_prompt, None, task=effective_task)
        messages = [{"role": "user", "content": user_message}]
        trace: list = []
        stop_reason = "max_iters"

        try:
            from src.runtime.events import append as _events_append
        except Exception:
            _events_append = None

        for it in range(max_iters):
            kwargs = dict(model=self.model, max_tokens=max_tokens,
                          system=system, messages=messages, tools=tools)
            try:
                response = self._client.messages.create(**kwargs)
            except Exception as e:
                _log.warning("tool_use create 실패: %s", e)
                break

            stop_reason = response.stop_reason
            # tool_use 블록 수집
            tool_uses = []
            text_parts = []
            for block in response.content:
                btype = getattr(block, "type", None)
                if btype == "tool_use":
                    tool_uses.append(block)
                elif btype == "text":
                    text_parts.append(block.text)

            # 도구가 더 없으면 종료
            if not tool_uses:
                if _events_append:
                    try:
                        _events_append("tool_loop_end", {"iters": it + 1, "reason": stop_reason})
                    except Exception:
                        pass
                return {"text": "".join(text_parts), "trace": trace,
                        "stop_reason": stop_reason, "iters": it + 1}

            # 도구 실행
            assistant_blocks = []
            for block in response.content:
                btype = getattr(block, "type", None)
                if btype == "text":
                    assistant_blocks.append({"type": "text", "text": block.text})
                elif btype == "tool_use":
                    assistant_blocks.append({"type": "tool_use", "id": block.id,
                                             "name": block.name, "input": block.input})
            messages.append({"role": "assistant", "content": assistant_blocks})

            tool_results = []
            for tu in tool_uses:
                try:
                    result = tool_handler(tu.name, tu.input)
                except Exception as e:
                    result = f"ERROR: {e}"
                result_str = result if isinstance(result, str) else str(result)
                trace.append({"tool": tu.name, "input": tu.input,
                              "result_preview": result_str[:200]})
                if _events_append:
                    try:
                        _events_append("tool_call",
                                       {"tool": tu.name, "input_keys": list(tu.input.keys()),
                                        "result_len": len(result_str)})
                    except Exception:
                        pass
                tool_results.append({"type": "tool_result", "tool_use_id": tu.id,
                                     "content": result_str[:8000]})
            messages.append({"role": "user", "content": tool_results})

        return {"text": "", "trace": trace, "stop_reason": stop_reason, "iters": max_iters}


    def generate_streamed(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        max_tokens: int = 4096,
        task: Optional[str] = None,
    ) -> Iterator[str]:
        """토큰 단위 스트리밍 생성기."""
        effective_task = task or self._task
        system = self._build_system(system_prompt, context_chunks, task=effective_task)
        messages = [{"role": "user", "content": user_message}]

        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        t_cfg = thinking_config(effective_task)
        if t_cfg and t_cfg.get("type") == "enabled":
            if t_cfg.get("budget_tokens", 0) >= max_tokens:
                t_cfg = {"type": "disabled"}
        if t_cfg:
            kwargs["thinking"] = t_cfg

        try:
            with self._client.messages.stream(**kwargs) as s:
                for text in s.text_stream:
                    yield text
        except Exception as e:
            if "thinking" in str(e).lower() and "thinking" in kwargs:
                _log.warning(f"thinking 스트리밍 미지원, 폴백: {e}")
                del kwargs["thinking"]
                with self._client.messages.stream(**kwargs) as s:
                    for text in s.text_stream:
                        yield text
            else:
                raise

    # ── 전문 논문 작업 ────────────────────────────────────────────────────────

    def summarize_paper(self, paper_text: str) -> str:
        system = (
            "You are a medical research expert. "
            "Summarise the provided paper clearly and concisely. "
            "Structure your output as: Background, Objective, Methods, Results, Conclusion."
        )
        return self.generate(paper_text, system_prompt=system, task="summary")

    def answer_from_papers(
        self,
        question: str,
        context_chunks: List[str],
        context_prefix: str = "",
    ) -> str:
        base = (
            "You are a medical research assistant. "
            "Answer the question using ONLY the provided paper excerpts. "
            "If the answer is not in the excerpts, say so explicitly. "
            "Cite the source filename when available."
        )
        system = f"{context_prefix}\n\n{base}" if context_prefix else base
        return self.generate(
            question, system_prompt=system,
            context_chunks=context_chunks, task="qa",
        )

    def draft_abstract(
        self, background: str, objective: str, methods: str,
        results: str, conclusion: str,
    ) -> str:
        system = (
            "You are a professional medical writer. "
            "Write a concise, well-structured abstract (≤250 words) for a medical research paper. "
            "Follow the IMRAD format."
        )
        prompt = (
            f"Background: {background}\n"
            f"Objective: {objective}\n"
            f"Methods: {methods}\n"
            f"Results: {results}\n"
            f"Conclusion: {conclusion}\n\n"
            "Write the abstract."
        )
        return self.generate(prompt, system_prompt=system, task="abstract")

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _build_system(
        self,
        base_prompt: str,
        context_chunks: Optional[List[str]],
        task: str = "general",
    ):
        """시스템 프롬프트 구성. 페르소나 + medical seed + context 순서로 조립."""
        # 페르소나/seed/인사이트/리뷰어/자기개선 조립 — 공유 함수 사용 (전 LLM 일관)
        full_base = build_base_system(base_prompt, task)

        if not context_chunks:
            return full_base

        context_text = "\n\n---\n\n".join(context_chunks)
        return [
            {"type": "text", "text": full_base},
            {
                "type": "text",
                "text": f"<context>\n{context_text}\n</context>",
                "cache_control": {"type": "ephemeral"},
            },
        ]

    def _stream(
        self,
        system,
        messages: list,
        max_tokens: int = 4096,
        task: str = "standard",
    ) -> str:
        """스트리밍으로 완전한 응답 반환."""
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        t_cfg = thinking_config(task)
        if t_cfg and t_cfg.get("type") == "enabled":
            if t_cfg.get("budget_tokens", 0) >= max_tokens:
                t_cfg = {"type": "disabled"}
        if t_cfg:
            kwargs["thinking"] = t_cfg

        try:
            with self._client.messages.stream(**kwargs) as s:
                msg = s.get_final_message()
                return self._extract_text(msg)
        except Exception as e:
            if "thinking" in str(e).lower() and "thinking" in kwargs:
                del kwargs["thinking"]
                with self._client.messages.stream(**kwargs) as s:
                    msg = s.get_final_message()
                    return self._extract_text(msg)
            raise

    @classmethod
    def _extract_text(cls, response) -> str:
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                return block.text
        _log.warning(
            "API 응답에 text 블록이 없습니다. stop_reason=%s, blocks=%s",
            getattr(response, "stop_reason", "?"),
            [getattr(b, "type", "?") for b in response.content],
        )
        return ""
