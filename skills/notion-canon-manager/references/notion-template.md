# Notion 프로젝트 템플릿 v1.2.0

## 목차

1. 페이지와 사용 흐름
2. 작업 페이지 구성과 자동 반영
3. 데이터베이스와 관계
4. 단계별 생성
5. 템플릿 적용과 버전
6. 이전 템플릿에서 전환

## 1. 페이지와 사용 흐름

게임마다 독립 Project Hub를 생성한다. 다른 게임의 데이터베이스를 공유하지 않는다. 같은 게임의 대안 버전은 Version 관계로 분리한다. 부모는 사용자가 지정한 페이지를 사용하며, 신규 워크스페이스 최상위 생성은 그 위치가 요청된 경우에만 한다.

| 페이지 | 사용자가 하는 일 | 연결할 뷰 |
|---|---|---|
| Project Hub | 목표·세계 범위·활성 버전·현재 쟁점을 확인 | 각 하위 페이지의 실제 링크 |
| 워크숍 · 다음 결정 | 질문에 답하고 결정·미정을 확인 | Decision Log, 열린 QA, Sessions |
| 세계관 · 조직과 서비스 | 헌장·연표·장소·제도·정보 환경·용어 읽기 | 설정 목록, 연표, 장소, 정보 환경, 용어집 |
| 인물 · 관계와 지식 | 인물 일상·동기·관계·소속과 동선·말투·시점별 앎 확인 | Character, Knowledge, Claim |
| 사건 · 실제 진상 | 실제 사건·원인·결과 검토 | Event, Fact |
| 조사 · 선택과 결말 | 기록·추론·공정성·선택·분기 검토 | Trace, Choice, Ending, Canon Links |
| 최종 기획서 | 연결된 전체 기획서 읽기 | 서술형 통합 문서 |
| 관리 데이터 | 버전과 원본 데이터 접근 | Story Versions와 원본 DB 7개 |
| 동기화 상태 | 현재 연결·미반영 변경·충돌 확인 | Change Sets, Sync Registry |

하위 페이지는 요약 서술과 필터 뷰를 함께 갖는다. JSON만 노출하는 데이터 창고로 끝내지 않는다. 원본 데이터베이스는 관리 데이터 아래에 두고 일반 작업 페이지에는 linked view를 만든다.

## 2. 작업 페이지 구성과 자동 반영

### 영역

Project Hub와 5개 작업 페이지(워크숍, 세계관, 인물, 사건, 조사)는 같은 순서의 영역을 갖는다. 영역의 경계는 `##` 제목이며, 제목 문구가 곧 표지다. 제목을 바꾸거나 지우면 자동 반영이 멈춘다.

| 순서 | 영역 | 쓰는 쪽 | 갱신 |
|---|---|---|---|
| 1 | 안내 callout | 템플릿 | 바뀌지 않는다 |
| 2 | `## 해설` | AI 에이전트의 서술 | 에이전트가 Canon을 바탕으로 다시 쓴다. `notion_plan.py pages --narratives`가 교체 요청을 만든다 |
| 3 | `## Canon 요약` | `canon.py` | 동기화 때마다 Canon에서 전부 다시 만든다 |
| 4 | `## User Notes` | 사람 | 자동으로 절대 고치지 않는다 |
| 5 | `## 데이터 뷰` (Hub는 `## 작업 페이지`) | Notion | 필터 뷰와 하위 페이지가 이 제목 아래에 붙는다 |

이 순서에는 이유가 있다.

- create_view와 create_pages는 새 뷰와 하위 페이지를 페이지 **맨 끝**에 붙인다. 그래서 뷰와 하위 페이지를 받는 제목을 맨 뒤에 둔다.
- 자동 영역은 User Notes 앞에서 끝난다. 자동 갱신은 User Notes, 뷰, 하위 페이지 블록을 건드리지 않는다.

### 페이지별 Canon 요약

| 페이지 | 자동 요약 내용 |
|---|---|
| Project Hub | 진행 현황: 버전·리비전, 현실 거리, 핵심 전제, 조사 현재 시점, 종류별 설정 수, 확정 비율, 자동 검사 오류·경고 수, 심각도별 열린 이슈, 미정 결정 수, 다음 질문 |
| 워크숍 | 미정 결정, 심각도순 열린 이슈, 규칙 ID별 자동 검사 결과, 다음 질문과 이유 |
| 세계관 | 세계 바이블과 같은 내용: 헌장, 연표, 장소 트리, 조직, 규칙, 서비스별 보존·권한·기록 유형, 용어집, 공개도별 설정 |
| 인물 | 인물(정체성·소속과 기간·거주지·말투), 시점별 지식, 발언(의도·관련 사실) |
| 사건 | 사건 시간선(시각·현재 기준 경과·장소·행위자·결과), 사실, 사건이 이용한 허점 |
| 조사 | 기록(생성 시각·서비스·작성자·현재 상태·접근), 근거 링크, 해답에 쓰인 규칙과 이를 드러내는 기록, 선택, 결말과 도달 경로 예 |

최종 기획서, 관리 데이터, 동기화 상태 페이지는 자동 요약이 없다. 최종 기획서는 design-document.md로 에이전트가 조립한다.

요약은 Notion 문법으로 만든다. 표는 `<table>` 블록이고, 들여쓰기는 탭이며, 역슬래시·별표·물결·백틱·달러·대괄호·꺾쇠·중괄호·세로선·캐럿은 역슬래시로 이스케이프한다. 요일과 조사 현재 시점 기준 경과 기간은 계산한 값이다. Notion에 연결하기 전에 `canon.py page snapshot.json world`로 결과를 볼 수 있다.

### 반영 절차

1. 6개 페이지를 fetch해 본문을 `{"hub": "본문", "workshop": "본문", ...}` JSON으로 저장한다.
2. `python3 scripts/notion_plan.py pages snapshot.json registry.json bodies.json`을 실행한다. 해설도 바꾸려면 `--narratives narratives.json`에 `{"world": "### 세계의 정체성\n…"}` 형식으로 넘긴다.
3. 출력의 operations(update_page의 update_content 요청)를 실행한다.
4. 성공하면 출력의 record를 Registry의 page_regions에 기록한다.
5. conflicts가 있으면 그 영역은 요청을 만들지 않았다는 뜻이다. 사용자와 병합한다.

### 충돌 판단

영역마다 마지막으로 쓴 내용의 지문(fingerprint)을 page_regions에 둔다. Notion은 저장할 때 공백·빈 줄·이스케이프·표 표기를 정규화한다. 그래서 지문은 이런 표기를 뺀 **글자만** 비교한다.

- 현재 내용이 새 내용과 같으면 요청을 만들지 않는다.
- 현재 내용이 마지막 기록과 같거나, 기록이 없고 영역이 템플릿 그대로(“아직 작성되지 않음.”)면 교체한다.
- 그 밖의 경우는 사람이 영역을 고친 것이다. 교체하지 않고 conflicts로 보고한다.
- 교체는 제목부터 다음 제목 직전까지의 원문을 old_str로 쓰는 좁은 갱신이다. 제목이 없거나 두 번 나오면 요청을 만들지 않고 멈춘다.

## 3. 데이터베이스와 관계

정확한 생성 타입·선택값은 assets/notion-blueprint.json이 기준이다. 모든 DB의 공통 속성은 Name(TITLE), Key(RICH_TEXT), Revision(NUMBER), Content Hash(RICH_TEXT), Updated(LAST_EDITED_TIME)다.

| DB | 추가 속성 | Relation |
|---|---|---|
| Story Versions | Version ID, Status, Current Revision, Parent Version ID | 없음 |
| Canon Entities | Entity ID, Kind, Canon, Review, Owner, Summary, Event Time, Depth, Visibility, Origin | Version → Versions |
| Canon Links | Relation, Reason | Version → Versions; Source·Target → Entities |
| Decision Log | Status, Question, Answer, Rationale | Version → Versions; Affected → Entities |
| QA Issues | Severity, Status | Version → Versions; Affected → Entities |
| Workshop Sessions | Phase, Next Question, Sync | Version → Versions |
| Change Sets | Base Revision, Target Revision, Status | Version → Versions; Affected → Entities |

Relation 생성에는 data source ID를 사용한다. 행 Relation 값에는 대상 페이지 ID/URL을 사용한다. 데이터베이스 ID, data source ID, 행 페이지 ID는 서로 대체할 수 없다. Key는 프로젝트/버전/객체ID다. Notion이 UNIQUE를 강제한다고 가정하지 말고 쓰기 전 중복 조회를 한다.

Kind 선택지는 Canon 종류 14개(schema v2의 Location·HistoryEvent·Term 포함)다. Relation 선택지에는 entails·exploits가 있다. knows는 기존 행을 위해 선택지로 남지만 새로 쓰지 않는다.

Event Time은 연표 뷰의 기준 날짜다. 종류별로 다음 값을 넣는다. 불확실 구간은 시작과 끝을 가진 날짜 범위가 된다.

| 종류 | Event Time |
|---|---|
| Event, HistoryEvent | at |
| Organization | founded_at |
| Service | launched_at |
| WorldRule | valid_from부터 valid_until까지 |

Depth·Visibility·Origin은 해당 필드가 있는 객체에만 넣는다. v1 객체의 속성은 바뀌지 않는다.

Entity 종류별 세부 정보는 본문의 읽기용 설정과 관리 JSON에 둔다. 관리 JSON 뒤에는 User Notes를 두어 사용자 메모를 보존한다. 다른 페이지를 참조할 때 mention을 사용하고 기존 page/database 태그를 제거하거나 이동시키지 않는다.

## 4. 단계별 생성

Notion MCP의 실제 설명에서 fetch, create_pages, create_database, update_data_source, create_view, update_page, query_data_sources를 확인한다. enhanced-markdown-spec, view-dsl-spec을 먼저 읽는다. 현재 커넥터가 다른 문법이면 임의 요청을 보내지 않고 설명에 맞게 변환한다.

Registry JSON을 로컬 작업본과 동기화 상태 페이지에 보관한다. 기본 필드는 project_id, version_id, title, parent_page_id 또는 workspace_root_requested, hub_page_id, pages, data_sources, database_ids, version_page_id, relations_applied, views, entity_pages, bases, template_version, page_regions다. databases 단계가 끝나면 template_version에 blueprint의 버전을 기록한다. schema v2 객체(Location·HistoryEvent·Term 또는 밀도·공개도·출처)를 쓰는 upsert는 template_version이 1.1.0 이상이 아니면 요청을 만들지 않는다. 아직 반환되지 않은 ID 필드는 비워 둔다. Notion ID는 실제 응답의 UUID를 복사한다.

```bash
python3 scripts/notion_plan.py bootstrap registry.json --phase root
python3 scripts/notion_plan.py bootstrap registry.json --phase pages
python3 scripts/notion_plan.py bootstrap registry.json --phase databases
python3 scripts/notion_plan.py bootstrap registry.json --phase relations
python3 scripts/notion_plan.py bootstrap registry.json --phase version
python3 scripts/notion_plan.py bootstrap registry.json --phase views
```

각 명령은 실행할 tool과 arguments를 출력한다. 계획의 executed=false는 아직 실행되지 않았다는 뜻이다. 단계별로 실제 도구를 호출하고 성공 응답의 ID를 Registry에 기록한 다음 후속 단계를 생성한다. 독립 생성도 기록 순서가 유지되도록 처리한다. 이미 Registry에 있는 항목은 fetch로 존재를 확인하고 재사용한다.

- root → hub_page_id
- pages → pages[논리 이름]
- databases → database_ids[이름], data_sources[이름]; fetch로 schema 확인
- relations → fetch로 속성 확인 후 relations_applied에 DB/속성 기록
- version → version_page_id와 VERSION 행의 base hash/revision
- views → views[version_id/뷰 이름]에 반환된 view ID

세계관 페이지에는 설정 목록 외에 연표(Event Time 순서의 표), 장소, 정보 환경, 용어집 뷰가 생긴다. 연표를 timeline 뷰로 바꾸고 싶으면 커넥터의 view DSL 설명에서 `TIMELINE BY` 문법과 날짜 범위 속성 지원을 확인한 뒤 새 뷰로 추가한다. 기존 표 뷰를 바꾸지 않는다.

네트워크 중단으로 성공 여부가 모호하면 재생성 전에 부모의 자식·스키마·뷰 또는 Key를 조회한다. 같은 이름만으로 임의 기존 객체를 연결하지 말고 프로젝트 범위와 생성 기록을 비교한다.

Hub에 실제 하위 페이지 링크를 연결한다. 관계를 언급하려고 기존 page 태그를 다른 페이지에 삽입하면 이동이 일어날 수 있으므로 mention-page 또는 일반 링크를 목적에 맞게 사용한다. User Notes와 기존 자식 블록을 보존하고 좁은 영역만 수정한다.

## 5. 템플릿 적용과 버전

본문은 assets/page-templates.json, 최종 문서는 assets/design-document.md를 사용한다. 템플릿 버튼이 자동 설치된다고 주장하지 않는다. 페이지 생성 시 content를 주입하는 재사용 템플릿이다. 기본 Notion 템플릿 버튼을 요구하면 현재 도구 지원을 따로 확인한다.

게임 대안 버전을 추가할 때 Versions 행과 해당 버전의 필터 뷰를 만든다. 기존 뷰의 버전 필터를 몰래 바꾸지 않는다. Hub에서 활성 버전을 표시하고 다른 버전 뷰에는 버전명을 노출한다. 독립 게임은 새로운 Hub와 DB를 생성한다.

템플릿 변경은 template_version을 올리고 기존 스키마를 먼저 조회한다. 속성 삭제·이름 변경 등 손실 가능 변경은 자동 적용하지 않는다. 파괴적 migration 도구는 포함하지 않는다. 새로 만드는 페이지만 새 본문 템플릿을 쓴다. 기존 페이지 본문은 템플릿 변경으로 다시 쓰지 않는다.

## 6. 이전 템플릿에서 전환

### 1.1.0 → 1.2.0

스키마 변경은 없다. 바뀌는 것은 새로 만드는 작업 페이지의 본문 구성뿐이다.

- `upgrade`를 실행해도 요청이 없다. Registry의 template_version만 1.2.0으로 기록한다.
- 기존 페이지는 다시 만들지 않는다. 첫 `pages` 실행 때 `## Canon 요약` 영역이 User Notes 바로 앞에 **추가**된다. 기존 절(“## 세계 헌장” 등)은 그대로 남는다.
- 기존 페이지에는 `## 해설` 제목이 없다. 그래서 해설 교체는 conflicts로 보고되고 건너뛴다. 해설을 자동 관리하려면 기존 절들 앞에 `## 해설` 제목을 직접 한 줄 넣는다.

### 1.0.0 → 1.1.0

1.0.0으로 만든 프로젝트는 속성과 선택지를 **추가만** 해서 1.1.0으로 옮긴다. schema v2 객체(Location·HistoryEvent·Term, Depth·Visibility·Origin)를 기록하기 전에 전환을 마친다.

1. 7개 데이터 소스를 fetch해 현재 속성과 타입을 읽는다.
2. 읽은 스키마를 `{"entities": {"속성 이름": "타입"}, "links": {...}, ...}` 형식의 JSON으로 적는다. 타입은 blueprint와 같은 DDL 표기다(예: `SELECT('WorldRule':default, 'Organization')`, `RICH_TEXT`). 선택지는 이름과 색을 fetch 결과 그대로 옮긴다.
3. `python3 scripts/notion_plan.py upgrade registry.json schema.json`으로 요청을 만든다.
4. 출력된 update_data_source 요청을 실행하고, 다시 fetch해 새 속성과 선택지를 확인한다.
5. Registry에 template_version 1.1.0을 기록한다.
6. `bootstrap registry.json --phase views`로 새 뷰만 추가한다. 이미 Registry에 있는 뷰는 건너뛴다.

전환 규칙:

- 없는 속성은 `ADD COLUMN`으로 추가한다.
- 선택지가 빠진 SELECT는 `ALTER COLUMN … SET`으로 갱신한다. 이 문장은 선택지 목록 전체를 **교체**하므로, 요청에는 fetch한 기존 선택지(사용자가 직접 추가한 선택지와 색 포함)를 모두 넣고 빠진 값만 뒤에 붙인다. 그래서 2단계의 스키마는 반드시 방금 fetch한 것이어야 한다.
- 템플릿에 없는 속성(사용자가 추가한 속성, Relation)은 건드리지 않는다.
- 같은 이름의 속성이 다른 타입이면 요청을 만들지 않고 멈춘다. 사람이 직접 판단한다.
- DROP·RENAME 문장은 만들지 않는다.

기존 페이지 본문은 새 템플릿으로 다시 쓰지 않는다. 세계관 페이지에 새 절(연표, 장소와 생활 리듬 등)이 필요하면 User Notes 앞에 절을 추가하는 좁은 갱신으로 넣는다.

확인한 인터페이스:

- create_database의 SQL DDL
- create_pages의 data_source_id 부모
- create_view의 filter DSL (2026-09-20)
- update_data_source의 `ADD COLUMN`, `ALTER COLUMN … SET` 문법 (2026-09-25)
- create_view의 `SORT BY`, `TIMELINE BY` 지시어 (2026-09-25)

문법은 실행 시 노출된 도구 설명으로 다시 확인한다.
