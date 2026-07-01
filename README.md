# 정신 건강 상담 지식 그래프 기반 GraphRAG 프로젝트

정신 건강 상담 데이터셋에서 심리 증상, 유발 사건, 치료 전략, 개념 간의 관계를 지식 그래프(Knowledge Graph) 형태로 추출하고, 이를 다양한 그래프 데이터베이스(Neo4j, Kùzu, Memgraph) 및 벡터 인덱스와 결합하여 전문적인 심리 상담 답변을 제공하는 **상담 GraphRAG 시스템**입니다.

이 프로젝트는 Neo4j 파이프라인(LangChain 활용)과 Kùzu 파이프라인(LlamaIndex 활용), 그리고 Memgraph 컨테이너 환경을 지원합니다.

---

## 📂 프로젝트 구조

```text
smart-counsel/
├── data/
│   ├── raw/
│   │   ├── Dataset_large.csv         # 대규모 원본 상담 데이터셋 (CSV)
│   │   └── Dataset_small.csv         # 소규모 원본 상담 데이터셋 (CSV)
│   └── extraction/
│       ├── schema.json               # 지식 그래프 JSON 스키마 정의
│       ├── extraction_prompt.md      # LLM 지식 그래프 추출을 위한 프롬프트 가이드
│       ├── graph_data_small.json     # 소규모 데이터셋 기반 추출된 그래프 데이터 (노드/엣지)
│       ├── graph_data_large.json     # 대규모 데이터셋 기반 추출된 그래프 데이터 (노드/엣지)
│       └── extract_graph_large.py    # 대규모 데이터셋으로부터 LLM을 사용하여 지식 그래프 데이터를 추출하는 스크립트
│
├── documents/
│   ├── 21_llamaindex_graphrag.html   # LlamaIndex GraphRAG 기술 분석/학습 노트
│   └── 22_graph_db_for_llamaindex_comparison.html # LlamaIndex 지원 그래프 DB 비교 및 테스트 문서
│
├── pipeline_kuzu/
│   ├── kuzu_db/                      # 로컬 Kùzu 내장 DB 파일 저장소 (자동 생성)
│   ├── load_graph.py                 # 스키마, 그래프 데이터(JSON), 텍스트 임베딩(Vector)을 Kùzu DB에 적재하는 스크립트
│   └── run_chatbot.py                # Kùzu + LlamaIndex 기반 GraphRAG 한-영 번역 하이브리드 상담 챗봇 실행 스크립트
│
├── pipeline_memgraph/
│   └── docker-compose.yml            # Memgraph DB 및 Memgraph Lab GUI 컨테이너 실행을 위한 Docker Compose 설정 파일
│
├── pipeline_neo4j/
│   ├── load_graph.py                 # 추출된 그래프 데이터(JSON)를 Neo4j에 로드 및 관계 매핑하는 스크립트
│   ├── load_vector_chunks.py         # 상담 질문/조언 텍스트 청킹, nomic-embed-text 벡터화 및 Neo4j 벡터 인덱스 생성 스크립트
│   └── run_chatbot.py                # Neo4j + LangChain 기반 GraphRAG 한-영 번역 하이브리드 상담 챗봇 실행 스크립트
│
└── README.md                         # 프로젝트 설명서 (본 파일)
```

---

## ⚙️ RAG 파이프라인 수행 단계 및 실행 방법

### 0단계: 지식 그래프 데이터 추출 (공통)
* `data/raw/Dataset_xxx.csv` 파일의 형식을 참고하여 지식 그래프를 구성할 엔티티와 관계 정보 스펙인 `schema.json`을 정의합니다.
* `data/raw/Dataset_xxx.csv` 와 `extraction_prompt.md` 프롬프트 문서를 참고해 AI 모델을 이용하여 그래프 형식에 맞게 노드와 엣지 목록을 가진 `graph_data.json` 데이터 파일을 생성합니다.
* (`graph_data_small.json` 및 `graph_data_large.json`은 이미 추출 완료된 데이터로 포함되어 있어 바로 로드하여 사용할 수 있습니다.)
* 필요시 아래 스크립트를 실행하여 대규모 데이터셋에서 새로운 그래프 데이터를 추출할 수 있습니다:
  ```bash
  python ./data/extraction/extract_graph_large.py
  ```

---

### [Option A] Neo4j 파이프라인 실행 방법 (LangChain 활용)

Neo4j 데이터베이스를 기반으로 GraphRAG 시스템을 구축하는 단계입니다. (로컬에 Neo4j가 기동되어 있어야 하며, 기본 접속 정보는 `bolt://localhost:7687`, ID/PW: `neo4j/neo4j1234`로 설정되어 있습니다.)

#### 1. Neo4j 그래프 데이터 적재
* 정의된 노드 및 엣지 데이터를 로컬 Neo4j 인스턴스에 주입합니다. **(실행 시 데이터베이스 내 기존의 모든 노드와 관계 데이터는 자동으로 초기화(`DETACH DELETE`)됩니다.)**
  ```bash
  python ./pipeline_neo4j/load_graph.py
  ```

#### 2. 대화 청크 분할, 임베딩 벡터화 및 인덱스 빌드
* 각 상담 질문과 조언을 하나의 텍스트 `Chunk`로 병합하고, `nomic-embed-text` 임베딩 모델을 사용하여 768차원 벡터를 추출해 Neo4j에 로드합니다.
* 동시에 기존 그래프 노드들과 `MENTIONS` 관계로 연결하고 코사인 유사도 벡터 인덱스를 구축합니다. **(실행 시 기존에 저장되어 있던 모든 `Chunk` 노드와 `chunk_embedding_index` 벡터 인덱스는 자동으로 삭제 후 재생성됩니다.)**
  ```bash
  python ./pipeline_neo4j/load_vector_chunks.py
  ```

#### 3. GraphRAG 인터랙티브 챗 실행
* [run_chatbot.py](file:///d:/workspace/smart-ai/smart-counsel/pipeline_neo4j/run_chatbot.py) 파일을 실행하여 실시간으로 상담 시스템을 구동합니다.
* 내담자가 한국어로 질문하면, 파이프라인이 자동으로 다음과 같이 작동합니다:
  1. **한국어 질문 번역**: 한국어 질문을 LLM(`gemma4`)을 이용해 자연스러운 영어 질문으로 번역합니다.
  2. **벡터 검색**: 번역된 영어 벡터로 가장 유사한 상담 문서 조각(`Chunk`)을 매칭합니다.
  3. **지식 그래프 확장**: 매칭된 청크 주변의 증상(Emotion/Symptom), 치료전략(Intervention/Strategy), 유발 요인(Trigger/Event), 관련 심리 개념(Concept) 사실들을 탐색합니다.
  4. **최종 한국어 생성**: 수집된 영어 컨텍스트를 다국어 LLM(`gemma4`)이 추론하여 한국어로 정교하게 정리한 상담 답변을 출력합니다.
  ```bash
  python ./pipeline_neo4j/run_chatbot.py
  ```

---

### [Option B] Kùzu 파이프라인 실행 방법 (LlamaIndex 활용)

Kùzu는 로컬 파일 기반의 내장형(Embedded) 그래프 데이터베이스로, 별도의 DB 서버 설치 및 실행 없이 경량 파일 형태로 GraphRAG를 구축할 수 있습니다.

#### 1. 그래프 데이터 및 벡터 임베딩 일괄 적재
* 스키마 테이블 생성, 그래프 노드/엣지 주입, CSV 파일 로드 및 청킹/임베딩 설정, `Document_Interaction`과의 `IS_CHUNK_OF` 및 `MENTIONS` 관계 연결을 한 번에 진행합니다. **(실행 시 기존의 `pipeline_kuzu/kuzu_db/` 폴더는 자동으로 삭제 후 다시 생성됩니다.)**
  ```bash
  python ./pipeline_kuzu/load_graph.py
  ```

#### 2. Kùzu 기반 GraphRAG 인터랙티브 챗 실행
* [run_chatbot.py](file:///d:/workspace/smart-ai/smart-counsel/pipeline_kuzu/run_chatbot.py) 파일을 실행하여 실시간으로 상담 시스템을 구동합니다.
* LlamaIndex 프레임워크와 Kùzu DB가 결합되어 한-영 번역 및 하이브리드 RAG 검색(Cosine Similarity 계산 후 그래프 관계 정보 확장 탐색)을 지원합니다.
  ```bash
  python ./pipeline_kuzu/run_chatbot.py
  ```

---

### [Option C] Memgraph 파이프라인 실행 방법

Memgraph는 Neo4j와 호환되는 고성능 인메모리 그래프 데이터베이스입니다. 제공된 Docker Compose 설정을 활용하여 간편하게 로컬 환경에 띄우고 테스트할 수 있습니다.

#### 1. Memgraph 컨테이너 실행
* Memgraph 및 시각화 웹 도구인 Memgraph Lab 컨테이너를 함께 실행합니다.
  ```bash
  cd pipeline_memgraph
  docker compose up -d
  ```
* 컨테이너가 정상 실행되면 `http://localhost:3000` 접속을 통해 웹 GUI 환경(Memgraph Lab)에서 지식 그래프와 쿼리 수행 결과를 시각적으로 확인하고 관리할 수 있습니다.

---

## 💡 데이터셋 중복 처리 및 노드 매핑 구조

본 프로젝트에서 사용하는 `Dataset_large.csv` 및 `Dataset_small.csv` 데이터셋은 동일한 내담자 질문(Context)에 대해 여러 상담사의 답변(Response)이 개별 행(Row)으로 매칭되어 있는 **1:N 구조**를 가지고 있습니다.

중복 검색 방지 및 고유 시나리오 중심의 색인을 위해 시스템은 다음과 같이 중복을 처리하고 노드를 구성합니다:

1. **질문 기준 중복 필터링 (`seen_contexts` 적용)**:
   - 그래프 추출(`extract_graph_large.py`) 및 청크 로더 스크립트 실행 시, 동일한 질문에 대해서는 **가장 첫 번째 등장하는 행(첫 번째 상담사 답변)만 샘플링**하여 로드하고, 이후 등장하는 동일 질문의 행은 자동으로 스킵 처리됩니다.
   
2. **노드 생성 및 연결 구조 (`MATCH` 매핑)**:
   - 지식 그래프 데이터 추출 단계에서는 시간 소요 및 LLM API 처리량을 고려하여 데이터셋의 상위 고유 대화만 LLM을 통해 지식 그래프(엔티티 및 관계)로 추출하여 생성합니다.
   - 이후 벡터 청크 로더 실행 시, 이미 지식 그래프가 추출된 문서 노드에 대해서만 청크 노드를 연결(`IS_CHUNK_OF` 관계 설정)하고 지식 그래프의 엔티티와 청크 노드를 연결(`MENTIONS` 관계 설정)합니다.
   - 지식 그래프가 존재하지 않는 대화들은 청크 노드(`Chunk`)만 단독 생성되며 문서 노드나 지식 그래프와 연결되지 않고, 일반적인 Vector RAG 검색 대상으로 격리되어 동작합니다.

---

## 🛠️ 필수 요구사항 및 환경 구성

* **Python 3.10+**
* **OpenJDK 21** 및 로컬 **Neo4j Community Edition** (Neo4j 파이프라인 사용 시)
* **Docker / Docker Compose** (Memgraph 파이프라인 사용 시)
* 로컬 **Ollama** 실행 및 필수 모델 다운로드:
  ```bash
  ollama pull nomic-embed-text
  ollama pull gemma4
  ```
* 필수 파이썬 패키지 설치:
  ```bash
  # Neo4j 및 LangChain 관련 패키지
  pip install neo4j langchain-core langchain-ollama
  
  # Kùzu 및 LlamaIndex 관련 패키지
  pip install kuzu numpy llama-index llama-index-embeddings-ollama llama-index-llms-ollama llama-index-core
  ```
  