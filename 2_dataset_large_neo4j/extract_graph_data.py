import csv
import json
import os
import sys
from langchain_ollama import ChatOllama

# Setup stdout for utf-8 encoding to avoid Windows cp949 encoding errors
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# File paths
current_dir = os.path.dirname(os.path.abspath(__file__))
csv_file_path = os.path.join(current_dir, "Dataset_large.csv")
prompt_file_path = os.path.join(current_dir, "counsel_graph_schema_create_prompt.md")
output_json_path = os.path.join(current_dir, "counsel_graph_data.json")

# Define Enums for validation/normalization
VALID_NODE_TYPES = {
    "emotion/symptom": "Emotion/Symptom",
    "trigger/event": "Trigger/Event",
    "intervention/strategy": "Intervention/Strategy",
    "concept": "Concept",
    "document/interaction": "Document/Interaction"
}

VALID_RELATIONS = {
    "causes": "CAUSES",
    "co-occurs_with": "CO-OCCURS_WITH",
    "alleviates": "ALLEVIATES",
    "explains": "EXPLAINS",
    "has_context": "HAS_CONTEXT",
    "suggests": "SUGGESTS"
}

# Load the prompt instructions
with open(prompt_file_path, "r", encoding="utf-8") as f:
    prompt_instructions = f.read()

# Initialize ChatOllama with JSON mode
llm = ChatOllama(model="gemma4:latest", format="json", temperature=0)

# Step 1: Read the first 50 unique conversations from the CSV
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
                unique_conversations.append({
                    "doc_id": doc_id,
                    "context": ctx,
                    "response": resp
                })
                if len(unique_conversations) >= 50:
                    break

print(f"Loaded {len(unique_conversations)} unique conversations for graph extraction.")

# Master graph collections
all_nodes = {}
all_edges = set()

# Process each conversation
for idx, conv in enumerate(unique_conversations):
    doc_id = conv["doc_id"]
    ctx = conv["context"]
    resp = conv["response"]
    
    print(f"[{idx+1}/50] Extracting graph data for {doc_id}...")
    
    # Construct input text for LLM
    input_text = f"""
    [대화 원본]
    상담 문서 번호: {doc_id}
    내담자 질문 (Context): {ctx}
    상담사 답변 (Response): {resp}
    """
    
    try:
        # Call the LLM
        response = llm.invoke([
            ("system", prompt_instructions),
            ("human", input_text)
        ])
        
        # Parse the JSON response
        data = json.loads(response.content.strip())
        
        # Add Document node explicitly
        all_nodes[doc_id] = {
            "id": doc_id,
            "type": "Document/Interaction"
        }
        
        # Process extracted nodes
        for node in data.get("nodes", []):
            node_id = node.get("id", "").strip()
            node_type = node.get("type", "").strip()
            
            # Skip if ID or Type is empty
            if not node_id or not node_type:
                continue
                
            # Normalize Document IDs (e.g. if LLM returned "Document_001" or placeholder)
            if node_type.lower() == "document/interaction" or node_id.startswith("Document_"):
                # Always map document nodes back to the current doc_id being processed
                node_id = doc_id
                
            # Normalize type
            norm_type = VALID_NODE_TYPES.get(node_type.lower(), "Concept")
            
            all_nodes[node_id] = {
                "id": node_id,
                "type": norm_type
            }
            
        # Process extracted edges
        for edge in data.get("edges", []):
            source = edge.get("source", "").strip()
            target = edge.get("target", "").strip()
            relation = edge.get("relation", "").strip()
            
            if not source or not target or not relation:
                continue
                
            # Normalize Document references in edges
            if source.startswith("Document_") or source.lower() == "document/interaction":
                source = doc_id
            if target.startswith("Document_") or target.lower() == "document/interaction":
                target = doc_id
                
            # Normalize relation
            norm_rel = VALID_RELATIONS.get(relation.lower(), "CO-OCCURS_WITH")
            
            # Prevent self-loop relationships
            if source == target:
                continue
                
            all_edges.add((source, target, norm_rel))
            
    except Exception as e:
        print(f"Error extracting for {doc_id}: {e}")
        # Add minimal fallback document connections to avoid leaving it orphaned
        all_nodes[doc_id] = {
            "id": doc_id,
            "type": "Document/Interaction"
        }

# Convert sets and dicts to final lists format
output_nodes = list(all_nodes.values())
output_edges = []
for edge in all_edges:
    # Ensure source and target exist in our final nodes list
    source_id, target_id, relation = edge
    if source_id in all_nodes and target_id in all_nodes:
        output_edges.append({
            "source": source_id,
            "target": target_id,
            "relation": relation
        })

# Compile final JSON structure
final_graph_data = {
    "nodes": output_nodes,
    "edges": output_edges
}

# Save output
with open(output_json_path, "w", encoding="utf-8") as f:
    json.dump(final_graph_data, f, ensure_ascii=False, indent=4)

print(f"\nExtraction complete! Saved {len(output_nodes)} nodes and {len(output_edges)} edges to {output_json_path}")
