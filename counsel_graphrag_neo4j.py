import sys
from neo4j import GraphDatabase
from langchain_ollama import OllamaEmbeddings, ChatOllama

# Setup stdout for utf-8 encoding (to support Windows console characters without cp949 encoding errors)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Neo4j configuration
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "neo4j1234"
NEO4J_DATABASE = "neo4j"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

# Initialize Ollama Models
embedding_model = OllamaEmbeddings(model="nomic-embed-text")
llm = ChatOllama(model="gemma4:latest", temperature=0)

def translate_korean_to_english(query: str) -> str:
    """
    Translate the user's Korean query to English using gemma4.
    """
    print("[Pipeline] Translating Korean query to English...")
    system_prompt = (
        "You are a professional medical and psychological translator. "
        "Translate the user's Korean mental health question/query into natural English. "
        "Provide ONLY the English translation. Do not include any greeting, explanation, "
        "or extra commentary. Return only the pure translation."
    )
    response = llm.invoke([
        ("system", system_prompt),
        ("human", query)
    ])
    english_query = response.content.strip()
    print(f" -> English Query: '{english_query}'")
    return english_query

def retrieve_graphrag_context(tx, query_embedding, top_k=2):
    """
    Search vector index for similar Chunk nodes, then expand to matching entities
    and adjacent relationships (facts) from the knowledge graph.
    """
    print("[Pipeline] Performing Vector Search and Graph Expansion in Neo4j...")
    
    # queryNodes finds similar Chunk nodes.
    # From those Chunk nodes, we match (node)-[:MENTIONS]->(entity)
    # and then matching (entity)-[r]-(related) for graph context.
    result = tx.run("""
        CALL db.index.vector.queryNodes(
          'chunk_embedding_index',
          $top_k,
          $query_embedding
        )
        YIELD node, score
        
        OPTIONAL MATCH (node)-[:MENTIONS]->(entity)
        OPTIONAL MATCH (entity)-[r]-(related)
        
        RETURN node.id AS chunk_id,
               node.text AS chunk_text,
               score,
               collect(DISTINCT entity.id) AS entities,
               collect(DISTINCT {
                 entity: entity.id,
                 relation: type(r),
                 related: related.id
               }) AS relationships
        ORDER BY score DESC
    """, query_embedding=query_embedding, top_k=top_k)
    
    rows = [dict(row) for row in result]
    context_parts = []
    
    for row in rows:
        context_parts.append("[문서 조각 (Document Chunk)]")
        context_parts.append(f"Chunk ID: {row['chunk_id']}")
        context_parts.append(f"Search Score: {row['score']:.4f}")
        context_parts.append(row["chunk_text"])
        
        context_parts.append("[언급된 심리 엔티티 (Entities)]")
        entities = [e for e in row["entities"] if e is not None]
        if entities:
            context_parts.append(", ".join(entities))
        else:
            context_parts.append("없음")
            
        context_parts.append("[심리 지식 그래프 관계 (Graph Facts)]")
        has_relationship = False
        for rel in row["relationships"]:
            if (
                rel["entity"] is not None
                and rel["relation"] is not None
                and rel["related"] is not None
            ):
                context_parts.append(
                    f"- {rel['entity']} -[{rel['relation']}]-> {rel['related']}"
                )
                has_relationship = True
        if not has_relationship:
            context_parts.append("없음")
            
        context_parts.append("") # Spacer
        
    return "\n".join(context_parts)

def generate_answer(question, english_question, context):
    """
    Generate final counseling response in Korean based on context using gemma4.
    """
    print("[Pipeline] Generating final counseling response...")
    
    system_prompt = """
당신은 정신 건강 상담을 지원하는 전문 AI 상담사입니다. (GraphRAG 시스템)

반드시 제공된 [Context] 정보만을 바탕으로 답변해야 합니다.
[Context]에 명확하게 언급되지 않은 사실이나 치료법은 절대로 추측하여 답변하지 마십시오.
답변할 수 없는 경우, "제공된 상담 기록에서는 관련 내용을 찾을 수 없습니다."라고 답변하십시오.

답변 지침:
1. 반드시 한국어로 답변하십시오.
2. 내담자의 질문에 공감하되, [Context]에 기술된 검증된 상담사 조언과 치료법(Intervention), 그리고 원인(Trigger), 증상(Emotion/Symptom) 및 관련 심리학적 개념(Concept) 사이의 관계를 기반으로 논리적으로 답변하십시오.
3. [Context] 내의 문서 조각(Chunk)과 지식 그래프의 관계 사실(Graph Facts)을 결합하여 구체적인 해결책을 제시하십시오.
"""
    
    user_prompt = f"""
[Context]
{context}

[Client's Question]
{question}
(English Translation: {english_question})

[Answer]
"""
    response = llm.invoke([
        ("system", system_prompt),
        ("human", user_prompt)
    ])
    return response.content

def ask(question):
    """
    Run the full translation-based GraphRAG pipeline.
    """
    try:
        # 1. Translate Korean to English
        english_question = translate_korean_to_english(question)
        
        # 2. Get embedding of English question
        query_embedding = embedding_model.embed_query(english_question)
        
        # 3. Retrieve Context from Neo4j
        with driver.session(database=NEO4J_DATABASE) as session:
            context = session.execute_read(
                retrieve_graphrag_context,
                query_embedding,
                2 # top_k
            )
            
        # 4. Generate Answer using LLM
        answer = generate_answer(question, english_question, context)
        
        print("=" * 80)
        print(f"Q: {question}")
        print("-" * 80)
        print(f"GraphRAG Context:\n{context}")
        print("-" * 80)
        print(f"A:\n{answer}")
        print("=" * 80)
    except Exception as e:
        print("Error during ask execution:", e)

if __name__ == "__main__":
    print("=== Counseling GraphRAG CLI Interface ===")
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
        driver.close()
