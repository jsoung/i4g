"""
Scam Detection RAG Pipeline (LangChain v0.2+)

This module constructs a LangChain Expression Language (LCEL)-based pipeline
that uses an Ollama chat model as the reasoning component. It retrieves
relevant documents from a vector store and evaluates whether the provided
context exhibits signs of fraud.

The design is modular and composable:
- Retriever → Prompt → LLM → Output Parser
"""

from langchain_community.chat_models import ChatOllama
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

    prompt = ChatPromptTemplate.from_template(
        """You are a scam detection assistant.
Your task is to determine whether the following conversation or message
shows signs of fraudulent or deceptive behavior.

Focus specifically on crypto-related or romance scams that target
senior citizens.

Context:
{context}

Question:
{question}

Answer briefly, clearly, and objectively:"""
    )

    # LCEL chain composition
    chain = (
        {
            "context": retriever | (lambda docs: "\n\n".join(d.page_content for d in docs)),
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain
