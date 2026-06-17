"""E2E 체계 진단 — 11 chain 실측 (한 번에 끝장).

- 옛 데이터/새 코드 mismatch 모두 잡아낸다.
- 빌드-푸시 사이클 멈추고 실측 보고서 1장으로 판정.
"""
from __future__ import annotations

import json
import sys
import urllib.request
import ssl
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config.env import bootstrap
bootstrap()

R: list[tuple[str, str, str]] = []


def add(chain: str, status: str, detail: str) -> None:
    R.append((chain[:48], status, detail[:100]))


# ── 1. Supabase DDL ────────────────────────────────────────────────────────
try:
    from src.cloud.db import get_engine
    from sqlalchemy import text as _sql
    with get_engine().begin() as conn:
        wp_cols = set(r[0] for r in conn.execute(_sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name='ma_working_papers'")).all())
        rs_cols = set(r[0] for r in conn.execute(_sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name='ma_research_state'")).all())
    add("1.Supabase ma_working_papers DDL",
        "BROKEN" if 'data_json' not in wp_cols else "OK",
        f"cols={','.join(sorted(wp_cols))[:80]}")
    add("1.Supabase ma_research_state DDL",
        "OK" if 'data_json' in rs_cols else "BROKEN",
        f"cols={','.join(sorted(rs_cols))[:80]}")
except Exception as e:
    add("1.Supabase DDL", "ERROR", str(e)[:80])


# ── 2. HF Datasets 영속화 ──────────────────────────────────────────────────
try:
    ctx = ssl._create_unverified_context()
    t = os.environ.get('HF_TOKEN', '')
    h = {'User-Agent': 'Mozilla/5.0', 'Authorization': f'Bearer {t}'}
    req = urllib.request.Request(
        'https://huggingface.co/api/datasets/cave87/medical-agent-runtime', headers=h)
    d = json.loads(urllib.request.urlopen(req, timeout=10, context=ctx).read().decode('utf-8'))
    sibs = d.get('siblings', [])
    wp = [s.get('rfilename', '') for s in sibs if 'working_paper' in s.get('rfilename', '').lower()]
    rs = [s.get('rfilename', '') for s in sibs if 'research_state' in s.get('rfilename', '').lower()]
    add("2.HF Datasets working_papers",
        "BROKEN" if not wp else f"{len(wp)} files",
        "컨테이너 restart 시 RECENT 데이터 사라짐")
    add("2.HF Datasets research_states",
        "BROKEN" if not rs else f"{len(rs)} files",
        "ResearchProject 영속화 누락")
except Exception as e:
    add("2.HF Datasets", "ERROR", str(e)[:80])


# ── 3. 로그인 chain ────────────────────────────────────────────────────────
try:
    src_app = Path('app/streamlit_app.py').read_text(encoding='utf-8')
    src_ez = Path('app/pages/ez_home.py').read_text(encoding='utf-8')
    # ★ ez_home도 query_params 자체 처리하므로 양쪽 어디든 있으면 OK (이전 streamlit_app만 검사 false-positive)
    have_qp = ('st.query_params' in src_app or 'st.query_params' in src_ez) \
                 and ('auto=1' in src_app or 'auto=1' in src_ez or 'autologin' in src_ez)
    have_gate = '_ensure_logged_in' in src_ez
    add("3.Login query_params 영속", "OK" if have_qp else "BROKEN",
        "streamlit_app 또는 ez_home에서 처리")
    add("3.Login ez_home gate", "OK" if have_gate else "BROKEN", "_ensure_logged_in")
    add("3.Login HF iframe RISK", "RISK",
        "wrapper iframe에서 query_params 변경이 부모 URL에 반영 안 될 수 있음")
except Exception as e:
    add("3.Login", "ERROR", str(e)[:80])


# ── 4. 채팅 turn chain ─────────────────────────────────────────────────────
try:
    from src.service.chat import stream_turn, build_full_system  # noqa
    from app.agentic_loop import TOOL_SCHEMAS
    from src.llm.claude_client import ClaudeClient
    has_streamed = hasattr(ClaudeClient, 'generate_with_tools_streamed')
    add("4.Chat stream_turn", "OK", "정의됨")
    add("4.Chat tools 18종", "OK" if len(TOOL_SCHEMAS) >= 18 else "WARN",
        f"{len(TOOL_SCHEMAS)} tools")
    add("4.Chat streaming + tools", "OK" if has_streamed else "BROKEN",
        "generate_with_tools_streamed (토큰 단위)")
except Exception as e:
    add("4.Chat", "ERROR", str(e)[:80])


# ── 5. 첨부 chain ──────────────────────────────────────────────────────────
try:
    from src.ingestion.universal_loader import load, render_for_llm
    tp = Path('test_attach_smoke.txt')
    tp.write_text("테스트 첨부. caffeine과 우울증 가설.", encoding='utf-8')
    result = load(tp)
    tp.unlink()
    has_text = bool(result.get('text'))
    inject = render_for_llm([result], max_text_per_file=500)
    add("5.Attach universal_loader.load", "OK" if has_text else "BROKEN",
        f"text {len(result.get('text',''))} chars")
    add("5.Attach render_for_llm", "OK" if inject else "BROKEN",
        f"{len(inject)} chars")
    src_chat = Path('src/service/chat.py').read_text(encoding='utf-8')
    add("5.Attach build_full_system inject",
        "OK" if ('render_for_llm' in src_chat and 'attachments' in src_chat) else "BROKEN",
        "service.chat이 project.attachments를 inject")
except Exception as e:
    add("5.Attach", "ERROR", str(e)[:80])


# ── 6. RECENT chain ────────────────────────────────────────────────────────
try:
    src_ez = Path('app/pages/ez_home.py').read_text(encoding='utf-8')
    has_local_fb = 'startswith("chat_")' in src_ez
    has_sb_fb = 'data_json' in src_ez and 'fallback_used' in src_ez
    add("6.RECENT Supabase fallback",
        "OK" if has_sb_fb else "BROKEN",
        "Supabase 분기 title이 chat_xxx면 첫 user msg 대체")
    add("6.RECENT local fallback",
        "OK" if has_local_fb else "BROKEN",
        "로컬 .json fallback")
    # ★ DDL 실측 (data_json 컬럼 추가됐는지 판정 — 이전 하드코딩 BROKEN false-positive)
    try:
        from src.cloud.db import get_engine
        from sqlalchemy import text as _sql2
        with get_engine().begin() as conn:
            cols = set(r[0] for r in conn.execute(_sql2(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='ma_working_papers'")).all())
        has_dj = "data_json" in cols
        add("6.RECENT DDL data_json",
            "OK" if has_dj else "BROKEN",
            "data_json 컬럼 추가됨" if has_dj else "ALTER TABLE 필요")
    except Exception as e:
        add("6.RECENT DDL data_json", "ERROR", str(e)[:80])
except Exception as e:
    add("6.RECENT", "ERROR", str(e)[:80])


# ── 7. autopilot ───────────────────────────────────────────────────────────
try:
    from src.service.paper import autopilot_run  # noqa
    src_paper = Path('src/service/paper.py').read_text(encoding='utf-8')
    has_pw = 'PaperWriter' in src_paper
    add("7.Autopilot generator", "OK", "")
    add("7.Autopilot PaperWriter call",
        "OK" if has_pw else "BROKEN",
        "writer wired")
except Exception as e:
    add("7.Autopilot", "ERROR", str(e)[:80])


# ── 8. RAG ─────────────────────────────────────────────────────────────────
try:
    from src.service.rag import retrieve
    hits = retrieve("caffeine adolescent depression Korea", top_k=3)
    add("8.RAG retrieve",
        "OK" if hits else "BROKEN",
        f"{len(hits)} hits, PMID:{hits[0].get('metadata',{}).get('pmid','?') if hits else 'N/A'}")
except Exception as e:
    add("8.RAG", "ERROR", str(e)[:80])


# ── 9. ChromaDB / 인제스트 ─────────────────────────────────────────────────
# ★ ChromaDB singleton instance 재사용 (운영 인스턴스 충돌 방지 — service.rag 경유)
try:
    from src.service.rag import _get_pipeline
    pipe = _get_pipeline()
    cnt = 0
    if pipe and hasattr(pipe, 'vector_store') and hasattr(pipe.vector_store, 'count'):
        cnt = pipe.vector_store.count()
    elif pipe and hasattr(pipe, 'collection'):
        cnt = pipe.collection.count()
    else:
        # fallback: 운영 chromadb를 우회한 count
        import chromadb
        try:
            c = chromadb.PersistentClient(path='data/chromadb')
            for col in c.list_collections():
                if '768' in col.name:
                    cnt = col.count()
                    break
        except Exception:
            pass
    add("9.ChromaDB 768d (service)",
        "OK" if cnt > 40000 else "WARN",
        f"{cnt:,} chunks (~{cnt//13} papers)")
    add("9.Ingest 12,625 목표 대비",
        "PARTIAL",
        f"chromadb {cnt:,}+ / oa_papers 4,997")
except Exception as e:
    add("9.ChromaDB", "ERROR", str(e)[:80])


# ── 10. SELF_EVOLUTION ─────────────────────────────────────────────────────
try:
    from src.evolution.anchor import run as anchor_run
    rep = anchor_run()
    add("10.SELF_EVOLUTION anchor",
        f"{rep['axes_evaluated']}/6 axes",
        f"overall={rep['overall']}. 골드셋 0/3")
except Exception as e:
    add("10.SELF_EVOLUTION", "ERROR", str(e)[:80])


# ── 11. ResearchProject roundtrip ──────────────────────────────────────────
try:
    from src.research.research_state import new_project, project_save, project_load
    rp = new_project(owner_email="test@local", title="E2E smoke")
    rp.sections["Abstract"] = "smoke test"
    project_save(rp, cloud=True)
    loaded = project_load(rp.id)
    ok = loaded is not None and loaded.sections.get("Abstract") == "smoke test"
    add("11.ResearchProject roundtrip",
        "OK" if ok else "BROKEN",
        "new→save(cloud=True)→load")
except Exception as e:
    add("11.ResearchProject", "ERROR", str(e)[:80])


# ── 보고서 ─────────────────────────────────────────────────────────────────
print()
print("=" * 90)
print("E2E 체계 진단 결과 (실측)")
print("=" * 90)

ok = broken = warn = 0
for chain, status, detail in R:
    s = status.upper()
    if s == "OK" or s.endswith("FILES") or "AXES" in s or s.endswith("EDIT"):
        icon = "✅"; ok += 1
    elif s == "BROKEN":
        icon = "❌"; broken += 1
    elif s in ("ERROR",):
        icon = "🔴"; broken += 1
    elif s in ("WARN", "PARTIAL", "RISK"):
        icon = "🟡"; warn += 1
    else:
        icon = "🟡"; warn += 1
    print(f"{icon} {chain:50s} {status:14s} {detail}")

print()
print(f"요약: OK={ok}  BROKEN={broken}  WARN/RISK={warn}  Total={len(R)}")
print()
if broken:
    print("★ BROKEN 우선 fix 대상:")
    for chain, status, detail in R:
        if status.upper() in ("BROKEN", "ERROR"):
            print(f"  • {chain}")
