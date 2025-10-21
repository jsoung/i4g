"""
LangChain RetrievalQA pipeline with Ollama as the local LLM.
"""

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_ollama.chat_models import ChatOllama


def build_qa_chain(vectorstore) -> RetrievalQA:
    """
    Build a simple RetrievalQA chain using Ollama as the LLM.
    """
    llm = ChatOllama(model="llama3.1")
    template = (
        "You are a scam detection assistant.\n"
        "Given the following chat or message context, "
        "decide if it shows signs of a scam. "
        "Focus on crypto and romance scams targeting seniors.\n\n"
        "Context:\n{context}\n\nQuestion: {question}\n"
        "Answer clearly and concisely:"
    )
    prompt = PromptTemplate(template=template, input_variables=["context", "question"])

    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=vectorstore.as_retriever(search_kwargs={"k": 4}),
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True,
    )
