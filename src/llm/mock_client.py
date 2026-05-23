class MockClient:
    """Simple local mock LLM for development and CI fallback.

    Methods mirror real clients enough for tests: `generate`, `generate_streamed`,
    `answer_from_papers`, `summarize_paper`, `draft_abstract`, `model` attr.
    """

    def __init__(self, api_key=None, model=None, task="standard"):
        self.model = model or "mock-model"
        self.task = task

    def generate(self, user_message: str, **kwargs) -> str:
        task = kwargs.get("task", self.task)
        return f"[MOCK {task}] 자동 생성된 응답 (개발용) — 원본 길이={len(user_message)}"

    def generate_streamed(self, user_message: str, **kwargs):
        text = self.generate(user_message, **kwargs)
        for ch in [text[i:i+80] for i in range(0, len(text), 80)]:
            yield ch

    def answer_from_papers(self, question: str, context_chunks, context_prefix="") -> str:
        return f"[MOCK ANSWER] 질문: {question[:120]} — 근거 청크 수={len(context_chunks)}"

    def summarize_paper(self, paper_text: str) -> str:
        return f"[MOCK SUMMARY] 요약 (원문 길이={len(paper_text)})"

    def draft_abstract(self, background: str, objective: str, methods: str, results: str, conclusion: str) -> str:
        return "Background: Mock. Objective: Mock. Methods: Mock. Results: Mock. Conclusion: Mock."
