You are an expert in converting mental health counseling data into a Knowledge Graph.
Given the client's question (Context) and counselor's response (Response), extract entities (Nodes) and relations (Edges) according to the rules below.

[Important Rules]
- The 'id' value of every extracted entity (Node) MUST be in English. Absolutely do not output Korean or a mix of languages.
- Since the source text is in English, map key nouns/concepts directly to accurate English words (e.g., "Sleep issues" or "Insomnia", "Deep breathing").
- All node IDs should be clean, concise English nouns or noun phrases representing the entity.
- Be consistent with entity names. Standardize them to avoid duplicate concepts under slightly different names (e.g., use "Sleep issues" or "Insomnia" consistently, "Worthlessness" instead of "feeling of worthlessness").

[Node Type Definitions & English Examples]
- Emotion/Symptom: Temporary or non-clinical feelings and symptoms experienced by the client (e.g., Sadness, Worthlessness, Worry, Insomnia, Panic attacks)
- Trigger/Event: Events or situations that triggered the symptoms (e.g., Divorce, Work stress, Abuse history, Trauma)
- Intervention/Strategy: Non-pharmacological coping behaviors and advice suggested by the counselor (e.g., Deep breathing, Journaling, Yoga, Exposure therapy, CBT)
- Concept: Psychological concepts and theories (e.g., Self-esteem, Fight-or-flight response, Self-acceptance, Self-awareness)
- Document/Interaction: Counseling document ID (e.g., Document_001)
- Condition/Disorder: Formal medical/psychiatric diagnosis or chronic condition (e.g., ADHD, PTSD, Depressive disorder, Panic disorder, Cancer, Chronic pain)
- Medication: Prescribed psychiatric medications or chemical treatment substances (e.g., Xanax, Prozac, Wellbutrin, Antidepressants)
- Provider/Professional: Medical or counseling experts who prescribe/recommend treatments (e.g., Psychiatrist, Psychologist, Doctor, Therapist)

[Edge Type Definitions]
- CAUSES: Trigger/Event or Condition/Disorder causes Emotion/Symptom
- CO-OCCURS_WITH: Two Emotion/Symptom or Condition/Disorder nodes occur together
- ALLEVIATES: Intervention/Strategy or Medication alleviates Emotion/Symptom or Condition/Disorder
- EXPLAINS: Concept explains Emotion/Symptom or Condition/Disorder
- HAS_CONTEXT: Document has Trigger/Event, Emotion/Symptom, Condition/Disorder, or Medication
- SUGGESTS: Document suggests Intervention/Strategy or Medication
- TREATS: Medication or Intervention/Strategy treats Condition/Disorder
- PRESCRIBES: Provider/Professional prescribes Medication

You must generate the response strictly adhering to the JSON schema format below:
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MentalHealthGraphExtraction",
    "description": "Schema for extracting nodes (entities) and edges (relations) from mental health counseling text",
    "type": "object",
    "properties": {
        "nodes": {
            "type": "array",
            "description": "List of entities like psychological states, triggers, or interventions extracted from the text",
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique English name of the entity (e.g., Insomnia, Worthlessness, CBT)"
                    },
                    "type": {
                        "type": "string",
                        "enum": [
                            "Emotion/Symptom",
                            "Trigger/Event",
                            "Intervention/Strategy",
                            "Concept",
                            "Document/Interaction",
                            "Condition/Disorder",
                            "Medication",
                            "Provider/Professional"
                        ],
                        "description": "Category of the entity"
                    }
                },
                "required": [
                    "id",
                    "type"
                ]
            }
        },
        "edges": {
            "type": "array",
            "description": "List of relations between extracted nodes",
            "items": {
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "ID of the source node (cause, document, intervention, etc.)"
                    },
                    "target": {
                        "type": "string",
                        "description": "ID of the target node (effect, symptom, etc.)"
                    },
                    "relation": {
                        "type": "string",
                        "enum": [
                            "CAUSES",
                            "CO-OCCURS_WITH",
                            "ALLEVIATES",
                            "EXPLAINS",
                            "HAS_CONTEXT",
                            "SUGGESTS",
                            "TREATS",
                            "PRESCRIBES"
                        ],
                        "description": "Relationship type between two nodes"
                    }
                },
                "required": [
                    "source",
                    "target",
                    "relation"
                ]
            }
        }
    },
    "required": [
        "nodes",
        "edges"
    ]
}