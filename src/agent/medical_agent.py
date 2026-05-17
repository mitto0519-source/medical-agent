"""Self-learning Medical Research Agent

This agent accumulates knowledge from papers over time.
Each session builds on the previous: new papers expand the index,
Q&A history informs future responses, and cross-paper insights
are synthesised automatically whenever new papers are added.

Architecture
------------
    PDFs → RAGPipeline (ingest + retrieve) → ClaudeClient (generate)
                                ↘
                            AgentMemory (persist everything to disk)

The agent never forgets what it has learned. The vector DB (ChromaDB)
stores all embeddings persistently; the JSON memory stores all interactions.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

from src.rag.pipeline import RAGPipeline
from src.llm import get_llm_client
from src.agent.memory import AgentMemory


class MedicalAgent:
    """Continually-learning medical research agent.

    Usage
    -----
        agent = MedicalAgent()

        # Learn from a new paper
        agent.learn("data/papers/nature_medicine_2024.pdf")

        # Ask a question — answered from everything learned so far
        result = agent.ask("What are the main side effects of drug X?")
        print(result["answer"])

        # Summarise a specific paper
        summary = agent.summarize("nature_medicine_2024.pdf")

        # Discover cross-paper insights
        insights = agent.synthesize_insights()
    """

    def __init__(
        self,
        persist_dir: str = "data/chromadb",
        papers_dir: str = "data/papers",
        memory_path: str = "data/agent_memory.json",
        api_key: Optional[str] = None,
    ):
        self._llm = get_llm_client(api_key=api_key)
        self._rag = RAGPipeline(
            persist_dir=persist_dir,
            papers_dir=papers_dir,
            api_key=api_key,
            llm_client=self._llm,
        )
        self._memory = AgentMemory(memory_path=memory_path)

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------

    def learn(self, file_path: str) -> Dict:
        """Ingest any supported file and update long-term memory.

        Supports PDF, Word, PowerPoint, Excel, text, images.
        After ingestion the agent automatically generates a summary.

        Args:
            file_path: Path to the file

        Returns:
            Ingest result dict with chunks_added, title, file_type, etc.
        """
        result = self._rag.ingest_file(file_path)
        self._memory.log_ingest(result)

        # Auto-summarise newly added papers (skip if already summarised)
        filename = result["filename"]
        if result["chunks_added"] > 0 and not self._memory.get_summary(filename):
            print(f"[Agent] Summarising '{filename}'...")
            summary = self._rag.summarize(filename)
            self._memory.save_summary(filename, summary)
            result["summary"] = summary

        return result

    def learn_url(self, url: str) -> Dict:
        """Fetch a URL and learn from its content.

        Supports: web pages, arXiv, PubMed, direct PDF links.
        The page is crawled, chunked, stored in ChromaDB, and auto-summarised.

        Args:
            url: Full URL, arXiv ID (e.g. "2401.12345"), or PMID

        Returns:
            Ingest result dict
        """
        result = self._rag.ingest_url(url)
        self._memory.log_ingest(result)

        filename = result["filename"]
        if result["chunks_added"] > 0 and not self._memory.get_summary(filename):
            print(f"[Agent] Summarising '{result['title']}'...")
            summary = self._rag.summarize(filename)
            self._memory.save_summary(filename, summary)
            result["summary"] = summary

        return result

    def learn_directory(self, directory: Optional[str] = None, recursive: bool = False) -> List[Dict]:
        """Ingest all supported files in a directory.

        Supports PDF, Word, PowerPoint, Excel, text, images.
        """
        target = directory or self._rag.papers_dir
        if recursive:
            docs = self._rag._reader.read_directory_recursive(target)
        else:
            docs = self._rag._reader.read_directory(target)
        results = []
        for doc in docs:
            try:
                result = self.learn(doc["path"])
                results.append(result)
            except Exception as exc:
                print(f"[Agent] Failed to learn '{doc['filename']}': {exc}")
        return results

    # ------------------------------------------------------------------
    # Q&A
    # ------------------------------------------------------------------

    def ask(self, question: str, filename_filter: Optional[str] = None) -> Dict:
        """Answer a question from all indexed papers.

        The answer and sources are saved to memory for continuity.

        Args:
            question: Natural-language question
            filename_filter: Limit to a specific paper filename (optional)

        Returns:
            {answer, sources}
        """
        result = self._rag.ask(question, filename_filter=filename_filter)
        self._memory.log_qa(question, result["answer"], result["sources"])

        # Suggest follow-up questions by examining unanswered aspects
        if "not found" not in result["answer"].lower():
            self._suggest_follow_ups(question, result["answer"])

        return result

    # ------------------------------------------------------------------
    # Summarisation
    # ------------------------------------------------------------------

    def summarize(self, filename: str, force: bool = False) -> str:
        """Return or generate a structured paper summary.

        Uses cached summary if available unless force=True.
        """
        if not force:
            cached = self._memory.get_summary(filename)
            if cached:
                return cached

        summary = self._rag.summarize(filename)
        self._memory.save_summary(filename, summary)
        return summary

    # ------------------------------------------------------------------
    # Cross-paper synthesis
    # ------------------------------------------------------------------

    def synthesize_insights(self) -> str:
        """Ask Claude to find patterns across ALL indexed papers.

        Retrieves one representative chunk per paper and asks Claude to
        identify shared themes, contradictions, and research gaps.
        The resulting insight is saved to memory.

        Returns:
            Insight text from Claude
        """
        papers = self._memory.get_ingested_papers()
        if len(papers) < 2:
            return "Need at least 2 papers indexed to synthesise cross-paper insights."

        # Build a mini-corpus: one summary paragraph per paper
        summaries = []
        for p in papers:
            s = self._memory.get_summary(p["filename"])
            if s:
                summaries.append(f"### {p['title']} ({p['filename']})\n{s[:800]}")

        if not summaries:
            return "No summaries available yet. Run summarize() on each paper first."

        context = "\n\n".join(summaries)
        prompt = (
            "You are reviewing a collection of medical research papers. "
            "Identify: (1) shared themes, (2) contradictions between papers, "
            "(3) open research gaps, and (4) the most impactful finding overall. "
            "Be specific and cite paper titles."
        )
        insight = self._llm.generate(context, system_prompt=prompt)
        self._memory.add_insight(insight, [p["filename"] for p in papers])
        return insight

    # ------------------------------------------------------------------
    # Memory inspection
    # ------------------------------------------------------------------

    def status(self) -> Dict:
        """Full agent status: index + memory."""
        rag_status = self._rag.status()
        return {
            **rag_status,
            "qa_interactions": len(self._memory.get_qa_log()),
            "summaries_cached": len(self._memory.get_qa_log()),
            "cross_paper_insights": len(self._memory.get_insights()),
            "open_follow_ups": len(self._memory.get_open_follow_ups()),
        }

    def get_follow_ups(self) -> List[Dict]:
        """Return open follow-up questions generated from past interactions."""
        return self._memory.get_open_follow_ups()

    def get_history(self) -> List[Dict]:
        """Return the full Q&A interaction history."""
        return self._memory.get_qa_log()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _suggest_follow_ups(self, question: str, answer: str):
        """Ask Claude to generate follow-up questions from the current Q&A."""
        prompt = (
            f"Question: {question}\n\nAnswer: {answer[:600]}\n\n"
            "List 2 specific follow-up research questions that naturally arise "
            "from this answer. Output one question per line, no numbering."
        )
        system = "You are a medical researcher generating precise follow-up questions."
        try:
            raw = self._llm.generate(prompt, system_prompt=system, stream=False)
            for line in raw.strip().splitlines():
                line = line.strip()
                if line:
                    self._memory.add_follow_up(line, reason=f"Derived from: {question[:80]}")
        except Exception:
            pass  # Follow-up generation is best-effort
