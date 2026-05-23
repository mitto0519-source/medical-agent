"""Code Knowledge Graph — 코드 구조 자산화 (medical_graph와 같은 NetworkX 엔진).

의학 지식을 medical_graph로 자산화하듯, 코드 구조를 그래프 자산으로 만들어
같은 자가진단·자가발전 루프에 넣는다. (사용자 철학: 그래프 자산화 + 자가발전 + 규칙10 완전성)

- ast 기반 100% 로컬 (tree-sitter/외부 의존 없음, LLM 무관 — 크레딧 0이어도 작동)
- 노드: module / function / class
- 엣지: DEFINES(module→symbol), IMPORTS(module→module)
- 자가진단: 고아 심볼(아무도 안 부름), 끊긴 import, ARCHITECTURE.md 누락 탐지

저장: data/knowledge_graph/code_graph.json
"""
from __future__ import annotations

import ast
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

try:
    import networkx as nx
    _NX_OK = True
except ImportError:
    _NX_OK = False
    _log.warning("networkx 없음 — code_graph 비활성. pip install networkx")

_GRAPH_DIR = Path("data/knowledge_graph")
_GRAPH_FILE = _GRAPH_DIR / "code_graph.json"

NODE_TYPES = {"module", "function", "class"}


def _path_to_module(py: Path, root: Path) -> str:
    """src/foo/bar.py → src.foo.bar"""
    rel = py.relative_to(root.parent) if root.parent in py.parents else py
    return str(rel.with_suffix("")).replace("\\", "/").replace("/", ".")


class CodeGraph:
    """코드 구조 그래프 — medical_graph와 동일 패턴 (NetworkX DiGraph + JSON 저장)."""

    def __init__(self):
        if not _NX_OK:
            self._G = None
            return
        self._G = nx.DiGraph()
        self._name_refs: Counter = Counter()  # 전체 코드에서 이름 참조 횟수 (고아 탐지)
        self._imports: Dict[str, set] = {}     # module → import한 src 모듈 집합

    # ── 빌드 ────────────────────────────────────────────────────────────────
    def build(self, src_dir: str = "src",
              ref_dirs: tuple = ("app", "scripts")) -> "CodeGraph":
        """src_dir 전체를 ast 파싱해 그래프 구성.

        ref_dirs: 정의 노드는 만들지 않되 '참조'만 수집할 디렉토리(app/scripts 등).
                  Streamlit/스크립트의 호출까지 참조에 포함해야 고아 오탐을 줄인다.
        """
        if self._G is None:
            return self
        root = Path(src_dir)
        if not root.exists():
            _log.warning("code_graph: %s 없음", src_dir)
            return self

        for py in sorted(root.rglob("*.py")):
            if "__pycache__" in py.parts:
                continue
            module = _path_to_module(py, root)
            try:
                src = py.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(src)
            except Exception as e:
                _log.debug("code_graph 파싱 실패 %s: %s", py, e)
                continue

            self._G.add_node(module, type="module", path=str(py).replace("\\", "/"))
            self._imports.setdefault(module, set())

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sym = f"{module}.{node.name}"
                    self._G.add_node(sym, type="function", module=module, line=node.lineno)
                    self._G.add_edge(module, sym, relation="DEFINES")
                elif isinstance(node, ast.ClassDef):
                    sym = f"{module}.{node.name}"
                    self._G.add_node(sym, type="class", module=module, line=node.lineno)
                    self._G.add_edge(module, sym, relation="DEFINES")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("src"):
                        self._imports[module].add(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("src"):
                            self._imports[module].add(alias.name)
                # 이름 참조 수집 (고아 탐지용)
                elif isinstance(node, ast.Name):
                    self._name_refs[node.id] += 1
                elif isinstance(node, ast.Attribute):
                    self._name_refs[node.attr] += 1

        # IMPORTS 엣지 연결
        for module, imps in self._imports.items():
            for imp in imps:
                self._G.add_edge(module, imp, relation="IMPORTS")

        # 참조 전용 디렉토리(app/scripts) 스캔 — 정의 노드는 안 만들고 이름 참조만 수집
        for rd in ref_dirs:
            rdp = Path(rd)
            if not rdp.exists():
                continue
            targets = rdp.rglob("*.py") if rdp.is_dir() else [rdp]
            for py in targets:
                if "__pycache__" in py.parts:
                    continue
                try:
                    rtree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
                except Exception:
                    continue
                for node in ast.walk(rtree):
                    if isinstance(node, ast.Name):
                        self._name_refs[node.id] += 1
                    elif isinstance(node, ast.Attribute):
                        self._name_refs[node.attr] += 1

        _log.info("code_graph 빌드: %d노드 / %d엣지", self._G.number_of_nodes(), self._G.number_of_edges())
        return self

    # ── 자가진단 ────────────────────────────────────────────────────────────
    def find_orphan_symbols(self) -> List[str]:
        """정의됐으나 코드베이스 어디서도 참조 안 되는 public 함수/클래스.

        근사(ast 정적 분석) — Streamlit 콜백/동적호출은 false positive 가능하므로
        '확정'이 아니라 '점검 후보'로 다룬다. 규칙10(고아코드 금지) 자동 신호.
        """
        if self._G is None:
            return []
        orphans = []
        for node, d in self._G.nodes(data=True):
            if d.get("type") not in ("function", "class"):
                continue
            name = node.split(".")[-1]
            if name.startswith("_"):          # private/dunder 제외
                continue
            if name in ("main",):
                continue
            # 이름 참조 횟수 (정의 자신 1회는 Name으로 안 잡힘 → 0이면 아무도 안 씀)
            if self._name_refs.get(name, 0) == 0:
                orphans.append(node)
        return sorted(orphans)

    def find_broken_imports(self) -> List[str]:
        """src 모듈을 import하는데 그 모듈 노드가 그래프에 없는 경우 (끊긴 연결)."""
        if self._G is None:
            return []
        modules = {n for n, d in self._G.nodes(data=True) if d.get("type") == "module"}
        broken = []
        for module, imps in self._imports.items():
            for imp in imps:
                # src.foo.bar 또는 src.foo (패키지) — 둘 다 허용
                if imp not in modules and not any(m.startswith(imp + ".") or imp.startswith(m + ".") for m in modules):
                    broken.append(f"{module} → {imp}")
        return sorted(broken)

    def check_architecture(self, arch_file: str = "ARCHITECTURE.md") -> Dict:
        """ARCHITECTURE.md에 적힌 모듈 경로가 실제 코드에 존재하는지 대조 (누락 검증)."""
        p = Path(arch_file)
        if not p.exists() or self._G is None:
            return {"checked": 0, "missing": []}
        import re
        text = p.read_text(encoding="utf-8", errors="ignore")
        # "삭제된 모듈" 이력 섹션은 제외 (이미 지운 모듈 경로라 누락이 정상)
        for marker in ("삭제된 모듈", "## 삭제", "deleted"):
            if marker in text:
                text = text.split(marker)[0]
                break
        # `src/foo/bar.py` 형태 추출
        cited = set(re.findall(r"`(src/[\w/]+\.py)`", text))
        actual = {d.get("path") for _, d in self._G.nodes(data=True) if d.get("path")}
        missing = sorted(c for c in cited if c not in actual)
        return {"checked": len(cited), "missing": missing}

    def stats(self) -> Dict:
        if self._G is None:
            return {"nodes": 0, "edges": 0}
        types = Counter(d.get("type") for _, d in self._G.nodes(data=True))
        return {
            "nodes": self._G.number_of_nodes(),
            "edges": self._G.number_of_edges(),
            "modules": types.get("module", 0),
            "functions": types.get("function", 0),
            "classes": types.get("class", 0),
        }

    # ── 저장/로드 ────────────────────────────────────────────────────────────
    def save(self) -> None:
        if self._G is None:
            return
        _GRAPH_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now().isoformat(),
            "nodes": [{"id": n, **d} for n, d in self._G.nodes(data=True)],
            "edges": [{"src": u, "dst": v, **d} for u, v, d in self._G.edges(data=True)],
            "stats": self.stats(),
        }
        _GRAPH_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _log.info("code_graph 저장: %s", _GRAPH_FILE)


def build_code_graph(src_dir: str = "src", save: bool = True) -> CodeGraph:
    """편의 함수 — 빌드 + 저장."""
    cg = CodeGraph().build(src_dir)
    if save:
        cg.save()
    return cg
