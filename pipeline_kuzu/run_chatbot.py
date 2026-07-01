import sys
import os
import numpy as np
import kuzu
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings, PromptTemplate
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.core.query_engine import RetrieverQueryEngine

# Reconfigure stdout for UTF-8 (Windows compatibility)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Setup LlamaIndex models via Settings
Settings.llm = Ollama(model="gemma4:latest", temperature=0, request_timeout=1200.0)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text", request_timeout=1200.0)

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
db_dir = os.path.join(current_dir, "kuzu_db")

# Initialize Kùzu DB connection
db = kuzu.Database(db_dir)
conn = kuzu.Connection(db)

def translate_korean_to_english(query: str) -> str:
    """
    Translate the user's Korean query to English using gemma4 via LlamaIndex.
    """
    print("[Pipeline] Translating Korean query to English...")
    system_prompt = (
        "You are a professional medical and psychological translator. "
        "Translate the user's Korean mental health question/query into natural English. "
        "Provide ONLY the English translation. Do not include any greeting, explanation, "
        "or extra commentary. Return only the pure translation."
    )
    prompt = f"{system_prompt}\n\nKorean query: {query}\n\nEnglish translation:"
    response = Settings.llm.complete(prompt)
    english_query = response.text.strip()
    print(f" -> English Query: '{english_query}'")
    return english_query

class KuzuGraphRAGRetriever(BaseRetriever):
    """
    Custom LlamaIndex retriever for Kùzu.
    Performs python-side cosine similarity search over Chunk embeddings,
    then expands to entities and relationship facts via Cypher queries.
    """
    def __init__(self, kuzu_conn, embed_model, top_k=2):
        super().__init__()
        self.conn = kuzu_conn
        self.embed_model = embed_model
        self.top_k = top_k
        
    def _retrieve(self, query_bundle):
        query_str = query_bundle.query_str
        print(f"[Pipeline] Performing Vector Search and Graph Expansion in Kùzu...")
        
        # 1. Generate query embedding
        query_embedding = self.embed_model.get_text_embedding(query_str)
        
        # 2. Retrieve all Chunks from Kùzu
        res = self.conn.execute("MATCH (c:Chunk) RETURN c.id, c.text, c.embedding")
        chunks = []
        while res.has_next():
            row = res.get_next()
            chunks.append({
                "id": row[0],
                "text": row[1],
                "embedding": np.array(row[2])
            })
            
        if not chunks:
            print("Warning: No chunks found in Kùzu DB.")
            return []
            
        # 3. Calculate cosine similarity
        query_emb_np = np.array(query_embedding)
        for chunk in chunks:
            dot_product = np.dot(chunk["embedding"], query_emb_np)
            norm_a = np.linalg.norm(chunk["embedding"])
            norm_b = np.linalg.norm(query_emb_np)
            similarity = dot_product / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0
            chunk["similarity"] = similarity
            
        # 4. Sort and select top_k
        sorted_chunks = sorted(chunks, key=lambda x: x["similarity"], reverse=True)
        top_chunks = sorted_chunks[:self.top_k]
        
        # 5. Graph expansion for each top chunk
        retrieved_nodes = []
        for chunk in top_chunks:
            chunk_id = chunk["id"]
            chunk_text = chunk["text"]
            score = chunk["similarity"]
            
            # Fetch entities mentioned by this Chunk
            entity_res = self.conn.execute(
                "MATCH (c:Chunk {id: $chunk_id})-[:MENTIONS]->(e) RETURN e.id, label(e)",
                {"chunk_id": chunk_id}
            )
            entities = []
            while entity_res.has_next():
                r = entity_res.get_next()
                entities.append({"id": r[0], "label": r[1]})
                
            # For each entity, fetch adjacent relations (facts)
            relationships = []
            for entity in entities:
                entity_id = entity["id"]
                entity_label = entity["label"]
                
                # Outgoing relations
                rel_res_out = self.conn.execute(
                    f"MATCH (e:{entity_label} {{id: $entity_id}})-[r]->(other) RETURN label(r), other.id",
                    {"entity_id": entity_id}
                )
                while rel_res_out.has_next():
                    r = rel_res_out.get_next()
                    relationships.append(f"- {entity_id} -[{r[0]}]-> {r[1]}")
                    
                # Incoming relations (skip Chunk relationships like IS_CHUNK_OF and MENTIONS)
                rel_res_in = self.conn.execute(
                    f"MATCH (e:{entity_label} {{id: $entity_id}})<-[r]-(other) RETURN label(r), other.id",
                    {"entity_id": entity_id}
                )
                while rel_res_in.has_next():
                    r = rel_res_in.get_next()
                    rel_name = r[0]
                    if rel_name not in ["IS_CHUNK_OF", "MENTIONS"]:
                        relationships.append(f"- {r[1]} -[{rel_name}]-> {entity_id}")
            
            # Formatting the retrieved context block for this chunk
            context_block = (
                f"[문서 조각 (Document Chunk)]\n"
                f"Chunk ID: {chunk_id}\n"
                f"Search Score: {score:.4f}\n"
                f"{chunk_text}\n\n"
                f"[언급된 심리 엔티티 (Entities)]\n"
                f"{', '.join([e['id'] for e in entities]) if entities else '없음'}\n\n"
                f"[심리 지식 그래프 관계 (Graph Facts)]\n"
                f"{chr(10).join(list(set(relationships))) if relationships else '없음'}\n"
            )
            
            node = TextNode(text=context_block, id_=chunk_id)
            retrieved_nodes.append(NodeWithScore(node=node, score=score))
            
        return retrieved_nodes

# Define Custom Prompt Template for Response Synthesis
qa_prompt_tmpl = (
    "당신은 정신 건강 상담을 지원하는 전문 AI 상담사입니다. (GraphRAG 시스템)\n\n"
    "반드시 제공된 [Context] 정보만을 바탕으로 답변해야 합니다.\n"
    "[Context]에 명확하게 언급되지 않은 사실이나 치료법은 절대로 추측하여 답변하지 마십시오.\n"
    "답변할 수 없는 경우, \"제공된 상담 기록에서는 관련 내용을 찾을 수 없습니다.\"라고 답변하십시오.\n\n"
    "답변 지침:\n"
    "1. 반드시 한국어로 답변하십시오.\n"
    "2. 내담자의 질문에 공감하되, [Context]에 기술된 검증된 상담사 조언과 치료법(Intervention), 그리고 원인(Trigger), 증상(Emotion/Symptom) 및 관련 심리학적 개념(Concept) 사이의 관계를 기반으로 논리적으로 답변하십시오.\n"
    "3. [Context] 내의 문서 조각(Chunk)과 지식 그래프의 관계 사실(Graph Facts)을 결합하여 구체적인 해결책을 제시하십시오.\n\n"
    "[Context]\n"
    "{context_str}\n\n"
    "[Client's Question]\n"
    "{query_str}\n\n"
    "[Answer]\n"
)
qa_prompt = PromptTemplate(qa_prompt_tmpl)

# Initialize Retriever and Query Engine
retriever = KuzuGraphRAGRetriever(conn, Settings.embed_model, top_k=2)
query_engine = RetrieverQueryEngine.from_args(
    retriever=retriever,
    text_qa_template=qa_prompt,
    llm=Settings.llm
)

def ask(question):
    try:
        # 1. Translate question
        english_question = translate_korean_to_english(question)
        
        # 2. Query the engine (this automatically runs retriever and response synthesizer)
        print("[Pipeline] Retrieving context and generating answer...")
        response = query_engine.query(english_question)
        
        # 3. Print details to console
        # We manually print the retrieved context from response.source_nodes to show log output
        retrieved_context = "\n---\n".join([node.node.text for node in response.source_nodes])
        
        print("=" * 80)
        print(f"Q: {question}")
        print("-" * 80)
        print(f"GraphRAG Context:\n{retrieved_context}")
        print("-" * 80)
        print(f"A:\n{response.response}")
        print("=" * 80)
        
    except Exception as e:
        print("Error during ask execution:", e)

if __name__ == "__main__":
    print("=== Counseling GraphRAG CLI Interface (Kùzu & LlamaIndex) ===")
    print("Type 'exit' or 'quit' to end the session.\n")
    try:
        while True:
            question = input("\n[질문 입력] > ")
            if question.strip().lower() in ["exit", "quit"]:
                print("Session closed.")
                break
            if not question.strip():
                continue
            ask(question)
    finally:
        # Close connection is not needed for Kùzu connection explicitly, but good practice
        pass
