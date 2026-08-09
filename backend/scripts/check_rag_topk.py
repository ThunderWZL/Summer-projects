"""Print manually reviewable Top-K citations for the five PPE categories."""

from __future__ import annotations

import sys
from pathlib import Path

from app.api.deps import get_requirement_retriever
from app.config import get_settings
from app.domain.requirements_rag import RequirementQuery
from app.modules.requirements_rag.service import CorpusNotReady


QUESTIONS = {
    "helmet": "建筑施工现场安全帽的配备和佩戴要求是什么？",
    "goggles": "建筑施工现场护目镜或眼部防护的配备要求是什么？",
    "gloves": "建筑施工现场手部防护和防护手套的配备要求是什么？",
    "boots": "建筑施工现场足部防护和安全鞋的配备要求是什么？",
    "vest": "建筑施工现场高可视背心或反光背心的配置要求是什么？",
}


def main() -> int:
    settings = get_settings()
    if not settings.embedding_api_key:
        print("SKIP: EMBEDDING_API_KEY is not configured; real RAG was not run.")
        return 2
    retriever = get_requirement_retriever()
    manifest_path = Path(__file__).parents[1] / "app/modules/requirements_rag/manifests/authoritative_sources.json"
    try:
        retriever.index_documents(manifest_path)
    except CorpusNotReady as exc:
        print(f"NOT RUN: verified corpus is not ready ({exc}).")
        for category in QUESTIONS:
            print(f"[{category}] NOT RUN")
        return 2
    failed = False
    for category, question in QUESTIONS.items():
        print(f"\n[{category}] {question}")
        citations = retriever.search(RequirementQuery(q=question, top_k=settings.rag_top_k))
        if not citations:
            failed = True
            print("NOT RUN: no citation returned")
        for index, citation in enumerate(citations, start=1):
            print(f"{index}. {citation.document_title} | {citation.section}")
            print(f"   {citation.source_url}\n   {citation.excerpt}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
