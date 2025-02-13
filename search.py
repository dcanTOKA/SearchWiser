import json
import os

from dotenv import load_dotenv
from duckduckgo_search import DDGS

from langchain import hub
from langchain.agents import create_react_agent, AgentExecutor, Tool
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI


load_dotenv()


class DuckDuckGoSearch:
    def __init__(self):
        self.ddgs = DDGS()

    def search(self, query: str, max_results: int = 5) -> str:
        results = self.ddgs.text(query, max_results=max_results)
        parsed_results = []
        for item in results:
            title = item.get("title", "")
            snippet = (
                item.get("body")
                or item.get("snippet")
                or item.get("description")
                or ""
            )
            href = item.get("href", "")

            parsed_results.append({
                "title": title,
                "href": href,
                "snippet": snippet
            })
        return json.dumps(parsed_results, ensure_ascii=False)


class NegativeFilter:
    def __init__(self):
        self.negative_keywords = [
            "vefat", "ceza", "dava", "haciz", "usulsüzlük", "baskın",
            "tutuklama", "soruşturma", "mühürlendi", "yangın", "iflas",
            "dolandırıcılık", "fetö", "işçi kıyımı", "yolsuzluk",
            "hapis cezası", "para cezası", "ihaleye fesat karıştırma",
            "operasyon", "mafya", "kara para aklama", "patlama", "soruşturma"
        ]
        self.llm = ChatOpenAI(
            temperature=0.0,
            model_name="gpt-4o-mini",
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )

    @staticmethod
    def _build_negative_filter_prompt() -> PromptTemplate:
        template = """
Aşağıda DuckDuckGo'dan elde edilen bazı haber sonuçları var (JSON formatında):
{search_results_json}

Negatif anahtar kelimeler: {{neg_keywords}}

Görev:
1. Her bir sonuçtaki "title", "snippet" ve "href" alanlarını kontrol et.
2. Aşağıdaki negatif kelimelerden (veya benzer semantik ifade) herhangi biri geçiyorsa, o haberi negatif olarak işaretle.
3. Bulduğun haberleri yalnızca şu JSON formatında döndür (dışında bir şey ekleme):
[
  {{
    "title": "...",
    "href": "...",
    "snippet": "...",
    "keywords_found": ["..."],
    "reason": "kısa açıklama"
  }}
]

Eğer hiçbir negatif içerik yoksa boş bir liste [] döndür.
Sadece geçerli JSON döndür; başka açıklama veya "Thought" ekleme.
"""
        return PromptTemplate(
            template=template,
            input_variables=["search_results_json"]
        )

    def filter_negative_news(self, search_results_json: str) -> str:
        prompt_template = self._build_negative_filter_prompt()
        prompt_filled = prompt_template.format(
            search_results_json=search_results_json
        ).replace("{{neg_keywords}}", str(self.negative_keywords))

        response = self.llm.invoke(prompt_filled)
        return response


class SummarizeNegativeNews:
    def __init__(self):
        self.llm = ChatOpenAI(
            temperature=0.2,  # Özetleme için hafif yaratıcılık
            model_name="gpt-4o-mini",
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )

    def summarize(self, negative_json_str: str) -> str:
        prompt = f"""
Aşağıda negatif haberlerin JSON formatında bir listesi bulunuyor:
{negative_json_str}

Lütfen bu haberleri kısa ve öz bir şekilde özetle.
- Her haberi madde işaretiyle göster.
- 'title' ve 'reason' kısımlarını kullan.
- Kısa, insan tarafından okunabilir bir metin döndür.
"""
        response = self.llm.invoke(prompt)
        return response


class AgentManager:
    def __init__(self):
        self.search_instance = DuckDuckGoSearch()
        self.filter_instance = NegativeFilter()
        self.summarize_tool = SummarizeNegativeNews()

        # Ajanın temel LLM'i
        self.llm = ChatOpenAI(
            temperature=0.7,
            model_name="gpt-4o-mini",
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )

        self.tools_for_agent = self._initialize_tools()

    def _initialize_tools(self) -> list:
        return [
            Tool(
                name="DuckDuckGoSearch",
                func=lambda query: self.search_instance.search(query),
                description="DuckDuckGo'da arama yapar, sonuçları JSON formatında döndürür."
            ),
            Tool(
                name="NegativeFilter",
                func=lambda search_results: self.filter_instance.filter_negative_news(search_results),
                description="Arama sonuçlarından negatif haberleri filtreler ve JSON formatında döndürür."
            ),
            Tool(
                name="SummarizeNegativeNews",
                func=lambda negative_json_str: self.summarize_tool.summarize(negative_json_str),
                description="NegativeFilter tarafından dönen JSON'u özetler, daha okunabilir bir formatta Türkçe dilinde çıktı verir."
            ),
        ]

    def execute(self, prompt_input: str) -> str:
        react_prompt = hub.pull("hwchase17/react")

        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools_for_agent,
            prompt=react_prompt
        )

        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools_for_agent,
            verbose=True,
            handle_parsing_errors=True
        )

        result = agent_executor.invoke({"input": prompt_input})

        final_answer = result.get("output", "")
        return final_answer


if __name__ == "__main__":
    manager = AgentManager()
    query_text = (
        "DuckDuckGoSearch ile 'Ümit ÖZDAĞ' ile ilgili haberleri ara, "
        "NegativeFilter ile olumsuz olanları ayıkla ve SummarizeNegativeNews aracıyla özetini bana sun."
    )
    response = manager.execute(query_text)
    print("=== Nihai Yanıt (Final Answer) ===\n", response)
