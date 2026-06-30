# 정신 건강 상담 지식 그래프 기반 GraphRAG 프로젝트

정신 건강 상담 데이터셋(`Dataset_small.csv` 및 `Dataset_large.csv`)에서 심리 증상, 유발 사건, 치료 전략, 개념 간의 관계를 지식 그래프(Knowledge Graph) 형태로 추출하고, 이를 Neo4j 벡터 인덱스와 결합하여 전문적인 심리 상담 답변을 제공하는 **상담 GraphRAG 시스템**입니다.

이 프로젝트는 소규모 데이터셋(`dataset_small_neo4j`)과 대규모 데이터셋(`dataset_large_neo4j`) 두 가지 버전을 지원합니다.

---

## 📂 프로젝트 구조

```text
project-counsel-graphRAG/
├── dataset_small_neo4j/                # 소규모 데이터셋 (Small Dataset) 폴더
│   ├── Dataset_small.csv                 # 텍스트 원본 데이터 (Small)
│   ├── schema.json         # 지식 그래프 JSON 스키마 정의
│   ├── extraction_prompt.md  # 스키마 데이터 추출을 위한 프롬프트 정의
│   ├── graph_data.json           # 추출 완료된 노드 & 엣지 그래프 데이터
│   ├── load_graph.py    # 노드/엣지 데이터를 Neo4j에 로드하는 스키마 주입 스크립트
│   └── load_vector_chunks.py    # 텍스트를 청크 분할 및 임베딩 벡터화 후 인덱싱하는 스크립트
│
├── dataset_large_neo4j/                # 대규모 데이터셋 (Large Dataset) 폴더
│   ├── Dataset_large.csv                 # 텍스트 원본 데이터 (Large)
│   ├── schema.json         # 지식 그래프 JSON 스키마 정의
│   ├── extraction_prompt.md  # 스키마 데이터 추출을 위한 프롬프트 정의
│   ├── graph_data.json           # 추출 완료된 노드 & 엣지 그래프 데이터
│   ├── load_graph.py    # 노드/엣지 데이터를 Neo4j에 로드하는 스키마 주입 스크립트
│   └── load_vector_chunks.py    # 텍스트를 청크 분할 및 임베딩 벡터화 후 인덱싱하는 스크립트
│
├── run_chatbot.py             # 최종 통합 번역 기반 GraphRAG 실행 챗봇 스크립트
└── README.md                            # 프로젝트 설명서 (본 파일)
```

---

## ⚙️ RAG 파이프라인 수행 단계 및 실행 방법

### 1단계: 지식 그래프 스키마 스펙 정의
* `Dataset_xxx.csv` 파일의 형식을 참고하여 지식 그래프를 구성할 엔티티와 관계 정보 스펙인 `schema.json`을 정의합니다.

### 2단계: 그래프 데이터(Node/Edge) 추출
* `Dataset_xxx.csv` 와 `extraction_prompt.md` 프롬프트 문서를 참고해 AI 모델을 이용하여 그래프 형식에 맞게 노드와 엣지 목록을 가진 `graph_data.json` 데이터 파일을 생성합니다.
* Large 데이터의 경우 아래 스크립트를 실행하여 그래프 데이터를 추출할 수 있습니다:
  ```bash
  python ./dataset_large_neo4j/extract_graph.py
  ```

### 3단계: Neo4j 그래프 데이터베이스 적재
* 정의된 노드 및 엣지 데이터를 로컬 Neo4j 인스턴스에 주입합니다. **(실행 시 데이터베이스 내 기존의 모든 노드와 관계 데이터는 자동으로 초기화(`DETACH DELETE`)됩니다.)**
* 사용 예시에 따라 아래 스크립트 중 하나를 실행합니다.
  ```bash
  # Small 데이터 적재
  python ./dataset_small_neo4j/load_graph.py

  # Large 데이터 적재
  python ./dataset_large_neo4j/load_graph.py
  ```

### 4단계: 대화 청크 분할, 임베딩 벡터화 및 인덱스 빌드
* 각 상담 질문과 조언을 하나의 텍스트 `Chunk`로 병합하고, `nomic-embed-text` 임베딩 모델을 사용하여 768차원 벡터를 추출해 Neo4j에 로드합니다.
* 동시에 기존 그래프 노드들과 `MENTIONS` 관계로 연결하고 코사인 유사도 벡터 인덱스를 구축합니다. **(실행 시 기존에 저장되어 있던 모든 `Chunk` 노드와 `chunk_embedding_index` 벡터 인덱스는 자동으로 삭제 후 재생성됩니다.)**
  ```bash
  # Small 데이터 청킹 및 임베딩 설정
  python ./dataset_small_neo4j/load_vector_chunks.py

  # Large 데이터 청킹 및 임베딩 설정
  python ./dataset_large_neo4j/load_vector_chunks.py
  ```

### 5단계: GraphRAG 인터랙티브 챗 실행 및 답변 평가
* [run_chatbot.py](file:///d:/workspace/smart-counsel/run_chatbot.py) 파일을 실행하여 실시간으로 상담 시스템을 구동합니다.
* 내담자가 한국어로 질문하면, 파이프라인이 자동으로 다음과 같이 작동합니다.
  1. **한국어 질문 번역**: 한국어 질문을 LLM(`gemma4`)을 이용해 자연스러운 영어 질문으로 번역합니다.
  2. **벡터 검색**: 번역된 영어 벡터로 가장 유사한 상담 문서 조각(`Chunk`)을 매칭합니다.
  3. **지식 그래프 확장**: 매칭된 청크 주변의 증상(Emotion), 치료전략(Intervention), 유발 요인(Trigger), 관련 심리 개념(Concept) 사실들을 탐색합니다.
  4. **최종 한국어 생성**: 수집된 영어 컨텍스트를 다국어 LLM(`gemma4`)이 추론하여 한국어로 정교하게 정리한 상담 답변을 출력합니다.
  ```bash
  python ./run_chatbot.py
  ```

---

## 💡 데이터셋 중복 처리 및 노드 매핑 구조

본 프로젝트에서 사용하는 `Dataset_large.csv` 데이터셋은 동일한 내담자 질문(Context)에 대해 여러 상담사의 답변(Response)이 개별 행(Row)으로 매칭되어 있는 **1:N 구조**를 가지고 있습니다. (총 3,512개 행 존재)

중복 검색 방지 및 고유 시나리오 중심의 색인을 위해 시스템은 다음과 같이 중복을 처리하고 노드를 구성합니다:

1. **질문 기준 중복 필터링 (`seen_contexts` 적용)**:
   - 그래프 추출(`extract_graph.py`) 및 청크 로드(`load_vector_chunks.py`) 스크립트 실행 시, 동일한 질문에 대해서는 **가장 첫 번째 등장하는 행(첫 번째 상담사 답변)만 샘플링**하여 로드하고, 이후 등장하는 동일 질문의 행은 자동으로 스킵 처리됩니다.
   - 이를 통해 대규모 데이터셋(3,512개 행) 내에서 최종적으로 **995개의 고유한 대화 및 질문**만을 대상으로 파이프라인이 구축됩니다.

2. **노드 생성 및 연결 구조 (`MATCH` 매핑)**:
   - 지식 그래프 데이터 추출 단계에서는 시간 소요를 고려하여 **상위 50개의 고유 대화**만 LLM을 통해 지식 그래프(엔티티 및 관계)로 추출하여 생성합니다. (Document_001 ~ Document_050)
   - 이후 벡터 청크 로더(`load_vector_chunks.py`) 실행 시 `MATCH` 쿼리를 사용하여, 이미 지식 그래프가 추출된 1~50번 문서 노드에 대해서만 청크 노드를 연결(`IS_CHUNK_OF` 관계 설정)하고 복사 쿼리를 통해 지식 그래프의 엔티티와 청크 노드를 연결(`MENTIONS` 관계 설정)합니다.
   - 지식 그래프가 존재하지 않는 51~995번까지의 고유 대화들은 청크 노드(`Chunk`)만 단독 생성되며 문서 노드나 지식 그래프와 연결되지 않습니다.

결과적으로 데이터베이스 내에는 실제 추출이 이루어진 50개의 고유 `Document/Interaction` 노드만 존재하며, 해당 노드들에 연계된 1~50번 청크들만 하이브리드 GraphRAG 검색으로 동작하고, 나머지 청크들은 일반적인 Vector RAG 검색으로 안전하게 격리되어 동작합니다.

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
