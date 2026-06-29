import json
import os
from neo4j import GraphDatabase

# Neo4j 데이터베이스 설정 (강좌 텍스트에 언급된 기본 비밀번호 설정 적용)
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "neo4j1234"

# JSON 데이터 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
json_file_path = os.path.join(current_dir, "counsel_graph_data.json")
with open(json_file_path, "r", encoding="utf-8") as f:
    graph_data = json.load(f)

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

def import_graph(tx, data):
    # 1. 노드 삽입 (노드의 Type을 Label로 동적 바인딩)
    for node in data["nodes"]:
        label = node["type"]
        tx.run(f"MERGE (n:`{label}` {{id: $id}})", id=node["id"])
        
    # 2. 엣지 삽입 (엣지의 Relation 유형을 관계 타입으로 동적 바인딩)
    for edge in data["edges"]:
        relation = edge["relation"]
        tx.run(f"""
            MATCH (source {{id: $source_id}})
            MATCH (target {{id: $target_id}})
            MERGE (source)-[r:`{relation}`]->(target)
        """, source_id=edge["source"], target_id=edge["target"])

with driver.session() as session:
    # 기존 데이터 청소 (필요시 실행)
    session.run("MATCH (n) DETACH DELETE n")
    print("Database cleared.")
    
    # 데이터 삽입 수행
    session.execute_write(import_graph, graph_data)
    print("Graph insertion completed successfully!")

driver.close()
