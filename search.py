import json
import os
from dotenv import load_dotenv
from langchain_community.tools import DuckDuckGoSearchRun
from langchain import hub
from langchain.agents import create_react_agent, AgentExecutor, Tool
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

load_dotenv()

ddg_search = DuckDuckGoSearchRun()


class NegativeFilter:
    NEGATIVE_KEYWORDS = [
        "vefat", "ceza", "dava", "haciz", "usulsüzlük", "baskın",
        "tutuklama", "soruşturma", "mühürlendi", "yangın", "iflas",
        "dolandırıcılık", "fetö", "işçi kıyımı", "yolsuzluk",
        "hapis cezası", "para cezası", "ihaleye fesat karıştırma",
        "operasyon", "mafya", "kara para aklama", "patlama"
    ]

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    @staticmethod
    def _create_negative_filter_prompt() -> PromptTemplate:
        template = """
    Aşağıda DuckDuckGo'dan elde edilen bazı haber sonuçları var (JSON formatında):
    {search_results_json}

    Aranan terim: "{search_query}"

    Negatif anahtar kelimeler: {neg_keywords}

    Görev:
    1. Her bir sonucu (title, href, snippet) incele.
    2. Eğer hem "{search_query}" ifadesiyle doğrudan ilişkiliyse **ve** aşağıdaki negatif kelimelerden (veya benzer semantik ifadelerden) biri geçiyorsa, o haberi negatif olarak işaretle.
    3. Bulduğun negatif haberleri tek bir Markdown metninde sırayla döndür:
       - **Title**: ...
       - **URL**: ...
       - **Snippet**: ...
       - **Keywords Found**: ...
       - **Reason**: (Bu haber neden negatif olarak işaretlendi?)  

    4. Eğer hiçbir negatif içerik yoksa sadece `"No negative content found."` döndür.
    5. Haberlerin gerçekten aranan terimle ilgili olup olmadığına özellikle dikkat et. **Eğer sadece negatif kelime geçiyorsa ama haber doğrudan "{search_query}" ile ilgili değilse, bu haberi dahil etme.**  
    6. Markdown formatı dışında başka açıklama veya "Thought" ekleme.
    """
        return PromptTemplate(template=template,
                              input_variables=["search_results_json", "neg_keywords", "search_query"])

    def filter_negative_news(self, search_results_json: str) -> str:
        try:
            prompt_template = self._create_negative_filter_prompt()
            neg_keywords_json = json.dumps(self.NEGATIVE_KEYWORDS, ensure_ascii=False)
            prompt_filled = prompt_template.format(
                search_results_json=search_results_json,
                neg_keywords=neg_keywords_json
            )
            response = self.llm.invoke(prompt_filled)
            return response.content.strip()
        except Exception as e:
            return f"Error during filtering: {str(e)}"


class SummarizeNegativeNews:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def summarize(self, negative_news_markdown: str) -> str:
        try:
            prompt = f"""
Aşağıda negatif haberlerin listesi (Markdown formatında) bulunuyor:
{negative_news_markdown}

Görev:
1. Bu haberleri kısa ve öz bir şekilde özetle.
2. Negatif haber yoksa "No negative content found." metnini yaz.
3. Markdown dışı açıklama ekleme.
"""
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            return f"Error during summarization: {str(e)}"


class AgentManager:
    def __init__(self):
        self.llm = ChatOpenAI(
            temperature=0.0,
            model_name="gpt-4o-mini",
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            streaming=True
        )
        self.filter_instance = NegativeFilter(self.llm)
        self.summarize_instance = SummarizeNegativeNews(self.llm)
        self.tools_for_agent = [
            Tool(
                name="DuckDuckGoSearch",
                func=ddg_search.run,
                description="DuckDuckGo'da arama yapar ve sonuçları döndürür."
            ),
            Tool(
                name="NegativeFilter",
                func=self.filter_instance.filter_negative_news,
                description="Arama sonuçlarından negatif haberleri filtreler (Markdown formatında)."
            ),
            Tool(
                name="SummarizeNegativeNews",
                func=self.summarize_instance.summarize,
                description="Negatif haberleri kısa ve anlaşılır bir şekilde özetler."
            ),
        ]
        react_prompt = hub.pull("hwchase17/react")
        self.agent = create_react_agent(llm=self.llm, tools=self.tools_for_agent, prompt=react_prompt)
        self.agent_executor = AgentExecutor(agent=self.agent, tools=self.tools_for_agent, verbose=True)

    def execute(self, user_prompt: str, st_callback=None):
        try:
            if st_callback:
                return self.agent_executor.invoke({"input": user_prompt}, {"callbacks": [st_callback]})
            else:
                return self.agent_executor.invoke({"input": user_prompt})
        except Exception as e:
            return f"Error during agent execution: {str(e)}"
