"use client";

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect } from "react";

// FRONTEND_NEXTJS_SPEC §6/§7 + AGENT_OUTPUT_UX_SPEC §3.
// 섹션별 SSE token append + 인라인 편집. 우측 라이브 프리뷰.
type Props = {
  sections: Record<string, string>;     // {Abstract, Introduction, Methods, Results, Discussion}
  onChange?: (sections: Record<string, string>) => void;
  readOnly?: boolean;
};

export default function TipTapManuscript({ sections, onChange, readOnly = false }: Props) {
  const initialHtml = renderSectionsAsHtml(sections);

  const editor = useEditor({
    extensions: [StarterKit],
    content: initialHtml,
    editable: !readOnly,
    onUpdate: ({ editor }) => {
      if (!onChange) return;
      // HTML → sections 파싱은 다음 사이클 (간단히 raw HTML 유지)
      onChange({ ...sections, _html: editor.getHTML() });
    },
  });

  useEffect(() => {
    if (!editor) return;
    editor.commands.setContent(renderSectionsAsHtml(sections), false);
  }, [editor, sections]);

  if (!editor) {
    return (
      <div className="p-4 text-sm text-ink-muted">
        프리뷰 로딩 중…
      </div>
    );
  }

  return (
    <div className="prose prose-sm max-w-none p-4">
      <EditorContent editor={editor} />
    </div>
  );
}

function renderSectionsAsHtml(sections: Record<string, string>): string {
  const order = ["Abstract", "Introduction", "Methods", "Results", "Discussion", "Conclusion"];
  const parts: string[] = [];
  for (const key of order) {
    const v = sections[key];
    if (!v) continue;
    parts.push(`<h2>${key}</h2>`);
    parts.push(`<p>${escapeHtml(v).replace(/\n+/g, "</p><p>")}</p>`);
  }
  return parts.join("\n") || "<p><em>섹션이 채워지면 여기에 표시됩니다.</em></p>";
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
