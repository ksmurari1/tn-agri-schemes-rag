from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from src.ingestion import get_vector_store
from src.retrieval import retrieve_documents


SYSTEM_PROMPT = """You are a careful Tamil Nadu agriculture schemes information assistant.

STRICT EVIDENCE RULES:
1. Answer exclusively from the supplied RETRIEVED CONTEXT. Never use outside knowledge, assumptions, memory, or live web search.
2. Treat retrieved passages as the only evidence available. A source title or page number alone does not prove a claim.
3. Include a factual claim only when the retrieved text explicitly supports it. This applies to scheme names, amounts, dates, eligibility, beneficiary counts, acreage, targets, deadlines, and Government Order numbers.
4. Never invent missing details or combine separate facts to create an unsupported conclusion.
5. If a passage is truncated, unclear, or insufficient to support a detail, omit that detail or clearly state that the retrieved evidence is insufficient. Do not complete missing text from memory.
6. Cite each major factual claim inline using the exact source title and page number supplied in the context, for example [Source title, page 20]. Do not invent citations or cite a page that does not support the claim.
7. If the retrieved passages do not answer the question adequately, clearly explain what can and cannot be confirmed from the indexed evidence. Recommend checking the relevant official department for missing information.

SOURCE AND YEAR RESTRICTIONS:
8. Respect explicit source, document, and financial-year restrictions in the farmer's question.
9. If a question specifies a budget year or document, use only passages from that matching source. Never mix facts from other years or documents to fill gaps.
10. If the matching source does not provide enough evidence, say so rather than using another source.
11. Distinguish historical measures and Government Orders from currently applicable rules. Do not describe an older announcement as a current benefit unless the retrieved evidence establishes that it remains applicable.

RESPONSE STYLE:
12. Use simple, clear language and answer in the language used by the farmer when feasible.
13. Organize the answer into concise points when appropriate.
14. Do not claim that a farmer is eligible, that funding is currently available, or that an application is open unless the retrieved context explicitly establishes it.
15. Do not claim that you verified a fact independently.

Before responding, check internally that every factual claim is supported by a retrieved passage and that each citation matches the claim. If not, remove the claim or explain the evidence gap.
"""

def answer_question(
    question: str, embeddings, chat_model: str = "gpt-4o-mini", k: int = 5,
    retrieval_mode: str = "vector",
) -> dict:
    question = question.strip()
    if not question:
        raise ValueError("Enter a question first.")
    store = get_vector_store(embeddings)
    if store is None:
        return {"answer": "The knowledge base is empty. Please ingest approved sources first.", "sources": []}

    docs = retrieve_documents(store, question, mode=retrieval_mode, k=k)
    if not docs:
        return {"answer": "I could not find relevant information in the indexed sources.", "sources": []}

    context_parts, sources = [], []
    for doc in docs:
        title = doc.metadata.get("source_title", "Unknown source")
        url = doc.metadata.get("source_url", "")
        page = doc.metadata.get("page")
        cite = f"[{title}, page {page}]" if page else f"[{title}, {url}]"
        context_parts.append(f"SOURCE: {cite}\nCONTENT:\n{doc.page_content}")
        sources.append({
            "title": title, "url": url, "page": page,
            "source_type": doc.metadata.get("source_type", ""),
            "excerpt": doc.page_content,
        })

    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model=chat_model, temperature=0)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"FARMER QUESTION:\n{question}\n\nRETRIEVED CONTEXT:\n" + "\n\n---\n\n".join(context_parts)),
    ]
    response = llm.invoke(messages)
    return {"answer": response.content, "sources": sources}
