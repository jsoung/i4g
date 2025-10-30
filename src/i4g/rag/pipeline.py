"""
Scam Detection RAG Pipeline (LangChain v0.2+)

This module constructs a LangChain Expression Language (LCEL)-based pipeline
that uses an Ollama chat model as the reasoning component. It retrieves
relevant documents from a vector store and evaluates whether the provided
context exhibits signs of fraud.

The design is modular and composable:
- Retriever → Prompt → LLM → Output Parser
"""

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser


def build_scam_detection_chain(vectorstore):
    """
    Build a RAG pipeline for scam detection using the LangChain LCEL API.

    Args:
        vectorstore: A LangChain-compatible vector store instance (e.g., FAISS, Chroma).

    Returns:
        Runnable: A composable LCEL chain that accepts {"question": str} and returns
        a scam assessment string.
    """
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    llm = ChatOllama(model="llama3.1")
    template = (
        "You are a scam detection assistant.\n"
        "Given the following chat or message context, "
        "decide if it shows signs of a scam. "
        "Focus on crypto and romance scams targeting seniors.\n\n"
        "Context:\n{context}\n\nQuestion: {question}\n"
        "Answer clearly and concisely:"
    )

    prompt = ChatPromptTemplate.from_template(template=template)

    # LCEL chain composition
    chain = (
        {
            "context": RunnablePassthrough() | (lambda inp: retriever.invoke(inp["question"]))
            | (lambda docs: "\n\n".join(d.page_content for d in docs)),
            "question": RunnablePassthrough() | (lambda inp: inp["question"]),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain
