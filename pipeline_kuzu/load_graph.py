import json
import os
import csv
import shutil
import kuzu
import sys
from llama_index.embeddings.ollama import OllamaEmbedding

# Setup stdout for utf-8 encoding (to support Windows console characters without cp949 encoding errors)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
db_dir = os.path.join(current_dir, "kuzu_db")
json_file_path = os.path.join(current_dir, "..", "data", "extraction", "graph_data_small.json")
csv_file_path = os.path.join(current_dir, "..", "data", "raw", "Dataset_small.csv")

# Initialize LlamaIndex Ollama Embeddings
embedding_model = OllamaEmbedding(model_name="nomic-embed-text")

# 1. Clean and recreate Kùzu DB folder
if os.path.exists(db_dir):
    print(f"Cleaning existing Kùzu DB at {db_dir}...")
    shutil.rmtree(db_dir)

print(f"Initializing Kùzu Database at {db_dir}...")
db = kuzu.Database(db_dir)
conn = kuzu.Connection(db)

# 2. Define Node Tables
print("Creating Node Tables...")
node_tables = [
    "CREATE NODE TABLE Emotion_Symptom(id STRING, PRIMARY KEY(id))",
    "CREATE NODE TABLE Trigger_Event(id STRING, PRIMARY KEY(id))",
    "CREATE NODE TABLE Intervention_Strategy(id STRING, PRIMARY KEY(id))",
    "CREATE NODE TABLE Concept(id STRING, PRIMARY KEY(id))",
    "CREATE NODE TABLE Document_Interaction(id STRING, PRIMARY KEY(id))",
    "CREATE NODE TABLE Condition_Disorder(id STRING, PRIMARY KEY(id))",
    "CREATE NODE TABLE Medication(id STRING, PRIMARY KEY(id))",
    "CREATE NODE TABLE Provider_Professional(id STRING, PRIMARY KEY(id))",
    "CREATE NODE TABLE Chunk(id STRING, text STRING, embedding FLOAT[], source STRING, PRIMARY KEY(id))"
]
for query in node_tables:
    conn.execute(query)

# 3. Define Relationship Tables
print("Creating Relationship Tables...")
rel_tables = [
    "CREATE REL TABLE CAUSES(FROM Trigger_Event TO Emotion_Symptom, FROM Emotion_Symptom TO Emotion_Symptom)",
    "CREATE REL TABLE HAS_CONTEXT(FROM Document_Interaction TO Trigger_Event, FROM Document_Interaction TO Emotion_Symptom)",
    "CREATE REL TABLE CO_OCCURS_WITH(FROM Emotion_Symptom TO Emotion_Symptom)",
    "CREATE REL TABLE SUGGESTS(FROM Document_Interaction TO Intervention_Strategy)",
    "CREATE REL TABLE ALLEVIATES(FROM Intervention_Strategy TO Emotion_Symptom)",
    "CREATE REL TABLE EXPLAINS(FROM Concept TO Emotion_Symptom)",
    "CREATE REL TABLE TREATS(FROM Intervention_Strategy TO Condition_Disorder, FROM Provider_Professional TO Condition_Disorder)",
    "CREATE REL TABLE PRESCRIBES(FROM Provider_Professional TO Medication)",
    "CREATE REL TABLE IS_CHUNK_OF(FROM Chunk TO Document_Interaction)",
    "CREATE REL TABLE MENTIONS("
    "    FROM Chunk TO Emotion_Symptom, "
    "    FROM Chunk TO Trigger_Event, "
    "    FROM Chunk TO Intervention_Strategy, "
    "    FROM Chunk TO Concept, "
    "    FROM Chunk TO Condition_Disorder, "
    "    FROM Chunk TO Medication, "
    "    FROM Chunk TO Provider_Professional"
    ")"
]
for query in rel_tables:
    conn.execute(query)

# 4. Load graph_data.json
print(f"Loading graph data from {json_file_path}...")
with open(json_file_path, "r", encoding="utf-8") as f:
    graph_data = json.load(f)

# Insert Nodes
print("Inserting nodes from graph_data.json...")
node_type_map = {}
for node in graph_data["nodes"]:
    node_id = node["id"]
    node_type = node["type"].replace("/", "_")
    node_type_map[node_id] = node_type
    
    conn.execute(f"CREATE (n:{node_type} {{id: $id}})", {"id": node_id})

# Insert Edges
print("Inserting edges from graph_data.json...")
for edge in graph_data["edges"]:
    source_id = edge["source"]
    target_id = edge["target"]
    relation = edge["relation"].replace("-", "_")  # Map CO-OCCURS_WITH to CO_OCCURS_WITH
    
    source_type = node_type_map.get(source_id)
    target_type = node_type_map.get(target_id)
    
    if not source_type or not target_type:
        print(f"Warning: Missing node type for source '{source_id}' or target '{target_id}'")
        continue
        
    conn.execute(f"""
        MATCH (s:{source_type} {{id: $source_id}}), (t:{target_type} {{id: $target_id}})
        CREATE (s)-[:{relation}]->(t)
    """, {"source_id": source_id, "target_id": target_id})

# 5. Load Dataset_small.csv and extract 5 unique conversations for chunking
print(f"Processing conversations from {csv_file_path}...")
unique_conversations = []
seen_contexts = set()

with open(csv_file_path, "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    
    for row in reader:
        if len(row) >= 2:
            ctx = row[0].strip()
            resp = row[1].strip()
            if ctx not in seen_contexts:
                seen_contexts.add(ctx)
                idx = len(unique_conversations) + 1
                doc_id = f"Document_{idx:03d}"
                chunk_text = f"[Context]\n{ctx}\n\n[Response]\n{resp}"
                unique_conversations.append({
                    "doc_id": doc_id,
                    "chunk_id": f"chunk_{idx:03d}",
                    "text": chunk_text
                })
                if len(unique_conversations) >= 5:
                    break

print(f"Loaded {len(unique_conversations)} unique conversations for chunking.")

# 6. Insert Chunk nodes, link to documents, and create MENTIONS relations
for conv in unique_conversations:
    doc_id = conv["doc_id"]
    chunk_id = conv["chunk_id"]
    text = conv["text"]
    
    print(f"Generating embedding for {chunk_id}...")
    embedding = embedding_model.get_text_embedding(text)
    
    # Create Chunk Node
    conn.execute("""
        CREATE (c:Chunk {id: $chunk_id, text: $text, embedding: $embedding, source: 'Dataset_small.csv'})
    """, {"chunk_id": chunk_id, "text": text, "embedding": embedding})
    
    # Link Chunk to Document/Interaction
    conn.execute("""
        MATCH (d:Document_Interaction {id: $doc_id}), (c:Chunk {id: $chunk_id})
        CREATE (c)-[:IS_CHUNK_OF]->(d)
    """, {"doc_id": doc_id, "chunk_id": chunk_id})
    
    # Establish MENTIONS relations
    conn.execute("""
        MATCH (d:Document_Interaction {id: $doc_id})-[:HAS_CONTEXT]->(e:Emotion_Symptom), (c:Chunk {id: $chunk_id})
        CREATE (c)-[:MENTIONS]->(e)
    """, {"doc_id": doc_id, "chunk_id": chunk_id})
    
    conn.execute("""
        MATCH (d:Document_Interaction {id: $doc_id})-[:HAS_CONTEXT]->(e:Trigger_Event), (c:Chunk {id: $chunk_id})
        CREATE (c)-[:MENTIONS]->(e)
    """, {"doc_id": doc_id, "chunk_id": chunk_id})
    
    conn.execute("""
        MATCH (d:Document_Interaction {id: $doc_id})-[:SUGGESTS]->(e:Intervention_Strategy), (c:Chunk {id: $chunk_id})
        CREATE (c)-[:MENTIONS]->(e)
    """, {"doc_id": doc_id, "chunk_id": chunk_id})
    
    print(f"Chunk {chunk_id} created and linked to {doc_id} & mentioned entities.")

print("\nKùzu Graph and Vector Embeddings ingestion completed successfully!")
