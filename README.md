# 정신 건강 상담 지식 그래프 기반 GraphRAG 프로젝트

정신 건강 상담 데이터셋(`Dataset_small.csv` 및 `Dataset_large.csv`)에서 심리 증상, 유발 사건, 치료 전략, 개념 간의 관계를 지식 그래프(Knowledge Graph) 형태로 추출하고, 이를 Neo4j 벡터 인덱스와 결합하여 전문적인 심리 상담 답변을 제공하는 **상담 GraphRAG 시스템**입니다.

이 프로젝트는 소규모 데이터셋(`1_dataset_small_neo4j`)과 대규모 데이터셋(`2_dataset_large_neo4j`) 두 가지 버전을 지원합니다.

---

## 📂 프로젝트 구조

```text
project-counsel-graphRAG/
├── 1_dataset_small_neo4j/                # 소규모 데이터셋 (Small Dataset) 폴더
│   ├── Dataset_small.csv                 # 텍스트 원본 데이터 (Small)
│   ├── counsel_graph_schema.json         # 지식 그래프 JSON 스키마 정의
│   ├── counsel_graph_schema_create_prompt.md  # 스키마 데이터 추출을 위한 프롬프트 정의
│   ├── counsel_graph_data.json           # 추출 완료된 노드 & 엣지 그래프 데이터
│   ├── counsel_graph_schema_insert.py    # 노드/엣지 데이터를 Neo4j에 로드하는 스키마 주입 스크립트
│   └── counsel_graph_vector_insert.py    # 텍스트를 청크 분할 및 임베딩 벡터화 후 인덱싱하는 스크립트
│
├── 2_dataset_large_neo4j/                # 대규모 데이터셋 (Large Dataset) 폴더
│   ├── Dataset_large.csv                 # 텍스트 원본 데이터 (Large)
│   ├── counsel_graph_schema.json         # 지식 그래프 JSON 스키마 정의
│   ├── counsel_graph_schema_create_prompt.md  # 스키마 데이터 추출을 위한 프롬프트 정의
│   ├── counsel_graph_data.json           # 추출 완료된 노드 & 엣지 그래프 데이터
│   ├── counsel_graph_schema_insert.py    # 노드/엣지 데이터를 Neo4j에 로드하는 스키마 주입 스크립트
│   └── counsel_graph_vector_insert.py    # 텍스트를 청크 분할 및 임베딩 벡터화 후 인덱싱하는 스크립트
│
├── counsel_graphrag_neo4j.py             # 최종 통합 번역 기반 GraphRAG 실행 챗봇 스크립트
└── READEME.md                            # 프로젝트 설명서 (본 파일)
```

---

## ⚙️ RAG 파이프라인 수행 단계 및 실행 방법

### 1단계: 지식 그래프 스키마 스펙 정의
* `Dataset_xxx.csv` 파일의 형식을 참고하여 지식 그래프를 구성할 엔티티와 관계 정보 스펙인 `counsel_graph_schema.json`을 정의합니다.

### 2단계: 그래프 데이터(Node/Edge) 추출
* `Dataset_xxx.csv` 와 `counsel_graph_schema_create_prompt.md` 프롬프트 문서를 참고해 AI 모델을 이용하여 그래프 형식에 맞게 노드와 엣지 목록을 가진 `counsel_graph_data.json` 데이터 파일을 생성합니다.

### 3단계: Neo4j 그래프 데이터베이스 적재
* 정의된 노드 및 엣지 데이터를 로컬 Neo4j 인스턴스에 주입합니다. **(실행 시 데이터베이스 내 기존의 모든 노드와 관계 데이터는 자동으로 초기화(`DETACH DELETE`)됩니다.)**
* 사용 예시에 따라 아래 스크립트 중 하나를 실행합니다.
  ```bash
  # Small 데이터 적재
  python ./1_dataset_small_neo4j/counsel_graph_schema_insert.py

  # Large 데이터 적재
  python ./2_dataset_large_neo4j/counsel_graph_schema_insert.py
  ```

### 4단계: 대화 청크 분할, 임베딩 벡터화 및 인덱스 빌드
* 각 상담 질문과 조언을 하나의 텍스트 `Chunk`로 병합하고, `nomic-embed-text` 임베딩 모델을 사용하여 768차원 벡터를 추출해 Neo4j에 로드합니다.
* 동시에 기존 그래프 노드들과 `MENTIONS` 관계로 연결하고 코사인 유사도 벡터 인덱스를 구축합니다. **(실행 시 기존에 저장되어 있던 모든 `Chunk` 노드와 `chunk_embedding_index` 벡터 인덱스는 자동으로 삭제 후 재생성됩니다.)**
  ```bash
  # Small 데이터 청킹 및 임베딩 설정
  python ./1_dataset_small_neo4j/counsel_graph_vector_insert.py

  # Large 데이터 청킹 및 임베딩 설정
  python ./2_dataset_large_neo4j/counsel_graph_vector_insert.py
  ```

### 5단계: GraphRAG 인터랙티브 챗 실행 및 답변 평가
* [counsel_graphrag_neo4j.py](file:///d:/workspace/smart-ai/project-counsel-graphRAG/counsel_graphrag_neo4j.py) 파일을 실행하여 실시간으로 상담 시스템을 구동합니다.
* 내담자가 한국어로 질문하면, 파이프라인이 자동으로 다음과 같이 작동합니다.
  1. **한국어 질문 번역**: 한국어 질문을 LLM(`gemma4`)을 이용해 자연스러운 영어 질문으로 번역합니다.
  2. **벡터 검색**: 번역된 영어 벡터로 가장 유사한 상담 문서 조각(`Chunk`)을 매칭합니다.
  3. **지식 그래프 확장**: 매칭된 청크 주변의 증상(Emotion), 치료전략(Intervention), 유발 요인(Trigger), 관련 심리 개념(Concept) 사실들을 탐색합니다.
  4. **최종 한국어 생성**: 수집된 영어 컨텍스트를 다국어 LLM(`gemma4`)이 추론하여 한국어로 정교하게 정리한 상담 답변을 출력합니다.
  ```bash
  python ./counsel_graphrag_neo4j.py
  ```

---

## 🛠️ 필수 요구사항 및 환경 구성
* **OpenJDK 21** 및 **Neo4j Community Edition** 설치 및 환경 변수 등록
* 로컬 **Ollama** 실행 및 필수 모델 다운로드:
  ```bash
  ollama pull nomic-embed-text
  ollama pull gemma4
  ```
* 필수 파이썬 패키지 설치:
  ```bash
  pip install neo4j langchain-core langchain-ollama
  ```
