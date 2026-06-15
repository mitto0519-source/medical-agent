"""RESEARCH_STATE_SPEC §9 — checkpoint → 변경 → restore=원복 / branch=독립 검증.

실 사용자 시나리오 시뮬레이션:
  1. 새 프로젝트
  2. RQ + dataset(KNHANES) 설정 후 cp1
  3. 변경(섹션 추가 + cp2)
  4. restore(cp1) → cp1 시점으로 돌아가 sections 비어있어야
  5. branch(cp2, "분석 A") → 새 state_id + parent_checkpoint=cp2
  6. 두 갈래 독립 변경 → diff 차이 표시
  7. resume(state_id) → load 정상
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from src.research.research_state import (
        new_project, project_save, project_load,
        from_project_dict, to_project_dict,
        checkpoint, list_checkpoints, restore, branch, resume, diff
    )

    print("=" * 60)
    print("RESEARCH_STATE end-to-end smoke")
    print("=" * 60)

    # 1. new project
    rp = new_project(owner_email="test@local",
                        title="MASLD 2023 신정의 KNHANES")
    print(f"1. new state: {rp.id} '{rp.title}'")

    # 2. RQ + dataset
    rp.rq = {"pico": {"P": "성인 19+", "I": "UPF", "O": "MASLD",
                        "year_range": [2019, 2024]}}
    rp.dataset = {"name": "KNHANES", "year_range": [2019, 2024],
                    "dataset_version": "HN24_2024.10",
                    "registry_version": "0.1.0"}
    project_save(rp, cloud=False)
    cp1 = checkpoint(rp, label="RQ_dataset_set")
    print(f"2. cp1: {cp1} (RQ + dataset)")
    assert cp1.startswith("cp_"), "checkpoint format fail"

    # 3. sections 추가 + cp2
    rp.sections["Abstract"] = "Background: KNHANES 2019-2024..."
    rp.sections["Methods"] = "We used FLI ≥ 60 as steatosis proxy..."
    rp.results["estimates"] = {"aOR": 1.23, "ci_low": 1.05, "ci_high": 1.44, "p": 0.01}
    project_save(rp, cloud=False)
    cp2 = checkpoint(rp, label="draft_v1")
    print(f"3. cp2: {cp2} (Abstract+Methods+estimates)")
    print(f"   manuscript_text derived: {len(rp.manuscript_text)} chars")
    assert len(rp.manuscript_text) > 0, "derived getter fail"

    # 4. restore(cp1)
    rp_back = restore(cp1)
    print(f"4. restore(cp1): {rp_back.id if rp_back else 'FAIL'}")
    assert rp_back is not None, "restore returned None"
    assert not rp_back.sections.get("Abstract"), \
        f"restore should have empty Abstract, got {rp_back.sections.get('Abstract')!r}"
    print(f"   ✓ sections cleared after restore (cp1=RQ-only)")

    # 5. branch
    rp_branch = branch(cp2, new_title="분석 A: UPF×MetALD")
    print(f"5. branch(cp2): new id={rp_branch.id if rp_branch else 'FAIL'}")
    assert rp_branch is not None, "branch failed"
    assert rp_branch.id != rp.id, "branch did not create new id"
    assert rp_branch.parent_checkpoint == cp2, \
        f"parent_checkpoint should be cp2, got {rp_branch.parent_checkpoint!r}"
    print(f"   parent_checkpoint correctly set to cp2")

    # 6. 두 갈래 독립 변경
    rp_branch.sections["Results"] = "분석 A 결과: aOR=1.45 (MetALD subgroup)"
    project_save(rp_branch, cloud=False)
    cp_a = checkpoint(rp_branch, label="branch_A_results")

    # 다시 rp (메인) 진행
    rp_main = project_load(rp.id)
    assert rp_main is not None, "main state load fail"
    rp_main.sections["Results"] = "메인 분석 결과: aOR=1.23 (전체 MASLD)"
    project_save(rp_main, cloud=False)
    cp_m = checkpoint(rp_main, label="main_results")

    # diff
    d = diff(cp_a, cp_m)
    print(f"6. diff(cp_a, cp_m): changed={list(d.get('changed_fields') or {})[:5]}")
    assert "manuscript" in d.get("changed_fields", {}), \
        "manuscript should differ between A and main"

    # 7. resume
    rp_resumed = resume(rp.id)
    print(f"7. resume(rp.id): {rp_resumed.id if rp_resumed else 'FAIL'}")
    assert rp_resumed is not None, "resume fail"
    assert rp_resumed.id == rp.id

    # 8. checkpoints listing
    cps = list_checkpoints(rp.id, limit=10)
    print(f"8. list_checkpoints({rp.id}): {len(cps)} checkpoints")
    for cp in cps[:5]:
        print(f"   • {cp.get('cp_id')[:18]} '{cp.get('label')}'")

    # 9. provenance v2 (dataset/registry version)
    from src.runtime.provenance import build_fingerprint
    fp = build_fingerprint(
        scope="test_rerun",
        dataset_version="HN24_2024.10",
        registry_version="0.1.0",
        seed=42,
    )
    assert fp["dataset_version"] == "HN24_2024.10"
    assert fp["registry_version"] == "0.1.0"
    print(f"9. provenance v2: dataset={fp['dataset_version']} registry={fp['registry_version']} seed={fp['seed']}")

    print("\n" + "=" * 60)
    print("✓ ALL 9 stages PASS — RESEARCH_STATE end-to-end OK")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
