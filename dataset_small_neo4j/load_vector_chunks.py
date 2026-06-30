import csv
import json
import os
from neo4j import GraphDatabase
from langchain_ollama import OllamaEmbeddings

# Neo4j connection details
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "neo4j1234"
NEO4J_DATABASE = "neo4j"

# Initialize Ollama Embeddings for nomic-embed-text
embedding_model = OllamaEmbeddings(model="nomic-embed-text")

# Step 1: Read the CSV and extract the first 5 unique conversations
current_dir = os.path.dirname(os.path.abspath(__file__))
csv_file_path = os.path.join(current_dir, "Dataset_small.csv")

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

# Step 2: Write chunks to Neo4j, link relations, generate embeddings, and build vector index
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

def setup_chunks_and_index(session):
    # 1. Clean existing Chunk nodes and drop vector index if exists
    session.run("MATCH (c:Chunk) DETACH DELETE c")
    session.run("DROP INDEX chunk_embedding_index IF EXISTS")
    print("Cleaned existing Chunk nodes and dropped 'chunk_embedding_index' vector index.")
    
    # 2. Create chunks, link to documents, and copy MENTIONS to entities
    for conv in unique_conversations:
        doc_id = conv["doc_id"]
        chunk_id = conv["chunk_id"]
        text = conv["text"]
        
        # Generate nomic-embed-text embedding
        print(f"Generating embedding for {chunk_id}...")
        embedding = embedding_model.embed_query(text)
        
        # Merge Chunk node
        session.run("""
            MERGE (c:Chunk {id: $chunk_id})
            SET c.text = $text,
                c.embedding = $embedding,
                c.source = "Dataset_small.csv"
        """, chunk_id=chunk_id, text=text, embedding=embedding)
        
        # Link Chunk to Document/Interaction
        session.run("""
            MATCH (d:`Document/Interaction` {id: $doc_id})
            MATCH (c:Chunk {id: $chunk_id})
            MERGE (c)-[:IS_CHUNK_OF]->(d)
        """, doc_id=doc_id, chunk_id=chunk_id)
        
        # Traverse existing relationships from Document to Entities and create (Chunk)-[:MENTIONS]->(Entity)
        session.run("""
            MATCH (d:`Document/Interaction` {id: $doc_id})
            MATCH (c:Chunk {id: $chunk_id})
            MATCH (d)-[:HAS_CONTEXT|SUGGESTS]->(e)
            MERGE (c)-[:MENTIONS]->(e)
        """, doc_id=doc_id, chunk_id=chunk_id)
        
        print(f"Chunk {chunk_id} created, embedded (dim={len(embedding)}), and linked to {doc_id} & mentioned entities.")
        
    # 3. Create Vector Index on Chunk nodes
    print("Creating Vector Index on Chunk nodes...")
    session.run("""
        CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS
        FOR (c:Chunk)
        ON c.embedding
        OPTIONS {
          indexConfig: {
            `vector.dimensions`: 768,
            `vector.similarity_function`: 'cosine'
          }
        }
    """)
    print("Vector Index 'chunk_embedding_index' created/verified.")

try:
    with driver.session(database=NEO4J_DATABASE) as session:
        setup_chunks_and_index(session)
        print("\nNeo4j Chunk and Vector Index setup complete!")
finally:
    driver.close()
