"use client";

import { useMemo } from "react";
// @ts-expect-error — diff 패키지는 @types/diff 별도 필요. 단순 type 선언으로 해결.
import { diffWords } from "diff";

type DiffPart = { added?: boolean; removed?: boolean; value: string };

// FRONTEND_NEXTJS_SPEC §6.2: compare 모드 — 위 Before / 아래 After + diff 하이라이트.
// DESIGN-LANGUAGE §1 단일 강조 sapphire · §2 정보 위계 · §3 흰 카드 + 미세 그림자.
// 톤: 캔버스 = white-paper (sapphire glass 톤과 의도적 대비).

type Props = {
  section: string;
  before: string;
  after?: string;
  onAccept?: () => void;
  onReject?: () => void;
};

export default function BeforeAfter({ section, before, after, onAccept, onReject }: Props) {
  // diff 계산 — 단어 단위, 추가/삭제만 하이라이트
  const diff = useMemo<DiffPart[] | null>(() => {
    if (!after || !before) return null;
    return diffWords(before, after) as DiffPart[];
  }, [before, after]);

  const hasContent = before || after;

  return (
    <div className="px-6 py-5 space-y-4">
      {/* 섹션 헤더 — 작고 절제된 라벨 (DESIGN-LANGUAGE §6 타이포 3단) */}
      <div className="flex items-baseline justify-between">
        <h2 className="text-[0.7rem] font-semibold tracking-[0.15em] uppercase text-ink-muted">
          {section}
        </h2>
        {diff && (
          <span className="text-[0.68rem] text-ink-muted tabular-nums">
            {countChanges(diff)} 변경 제안
          </span>
        )}
      </div>

      {/* 빈 상태 — DESIGN-LANGUAGE §4 4-피드백 (empty) */}
      {!hasContent && (
        <div className="rounded-2xl border border-dashed border-ink/10 bg-white/60 px-6 py-12 text-center">
          <div className="text-sm text-ink-subtle">아직 본문이 없습니다.</div>
          <div className="mt-1 text-xs text-ink-muted">
            채팅에서 분석/작성을 요청하면 이 섹션에 채워집니다.
          </div>
        </div>
      )}

      {/* Before 카드 */}
      {hasContent && (
        <Card label="Before" tone="neutral">
          <div className="prose-paper">
            {before ? (
              <p className="whitespace-pre-wrap">{before}</p>
            ) : (
              <p className="text-ink-muted italic">(비어 있음 — 새로 작성될 섹션)</p>
            )}
          </div>
        </Card>
      )}

      {/* 화살표 — 흐름 표시 (DESIGN-LANGUAGE §7 8px 그리드) */}
      {hasContent && (
        <div className="flex justify-center -my-1.5">
          <div className="w-px h-4 bg-ink/15" />
        </div>
      )}

      {/* After 카드 — diff 하이라이트 */}
      {hasContent && (
        <Card label="After" tone="accent">
          <div className="prose-paper">
            {diff ? (
              <p className="whitespace-pre-wrap">
                {diff.map((part: DiffPart, i: number) => {
                  if (part.added) {
                    return (
                      <span
                        key={i}
                        className="bg-success/10 text-success rounded px-0.5 mx-px"
                        style={{ textDecoration: "none" }}
                      >
                        {part.value}
                      </span>
                    );
                  }
                  if (part.removed) {
                    return (
                      <span
                        key={i}
                        className="bg-danger/8 text-danger/70 rounded px-0.5 mx-px line-through decoration-danger/40"
                      >
                        {part.value}
                      </span>
                    );
                  }
                  return <span key={i}>{part.value}</span>;
                })}
              </p>
            ) : after ? (
              <p className="whitespace-pre-wrap">{after}</p>
            ) : (
              <p className="text-ink-muted italic">AI 수정안이 아직 없습니다.</p>
            )}
          </div>

          {/* Accept / Reject — 카드 하단 우측 정렬, 큰 강조 없이 */}
          {after && (
            <div className="mt-5 pt-4 border-t border-ink/5 flex items-center justify-end gap-2">
              <button
                onClick={onReject}
                className="px-3 py-1.5 text-xs text-ink-subtle hover:text-ink
                             rounded-md transition-colors"
              >
                되돌리기
              </button>
              <button
                onClick={onAccept}
                className="px-3.5 py-1.5 text-xs font-medium text-white bg-sapphire
                             rounded-md shadow-sm shadow-sapphire/15
                             hover:shadow-md hover:shadow-sapphire/25 hover:-translate-y-0.5
                             transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]"
              >
                수락
              </button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

function Card({
  label,
  tone,
  children,
}: {
  label: string;
  tone: "neutral" | "accent";
  children: React.ReactNode;
}) {
  return (
    <article
      className={
        "rounded-2xl bg-white px-6 py-5 " +
        "shadow-[0_1px_2px_rgba(34,34,34,0.04),0_8px_24px_rgba(34,34,34,0.04)] " +
        "border border-ink/5 " +
        (tone === "accent" ? "ring-1 ring-sapphire/15" : "")
      }
    >
      <div className="flex items-center gap-2 mb-3 -mt-1">
        <span
          className={
            "text-[0.62rem] font-semibold tracking-[0.18em] uppercase " +
            (tone === "accent" ? "text-sapphire" : "text-ink-muted")
          }
        >
          {label}
        </span>
        {tone === "accent" && (
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-sapphire/60 animate-pulse" />
        )}
      </div>
      {children}
    </article>
  );
}

function countChanges(parts: DiffPart[]): number {
  return parts.reduce((n, p) => n + (p.added || p.removed ? 1 : 0), 0);
}
