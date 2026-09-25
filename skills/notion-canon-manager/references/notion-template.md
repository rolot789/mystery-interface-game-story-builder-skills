# Notion 프로젝트 템플릿 v1.0.0

## 목차

1. 페이지와 사용 흐름
2. 데이터베이스와 관계
3. 단계별 생성
4. 템플릿 적용과 버전

## 1. 페이지와 사용 흐름

게임마다 독립 Project Hub를 생성한다. 다른 게임의 데이터베이스를 공유하지 않는다. 같은 게임의 대안 버전은 Version 관계로 분리한다. 부모는 사용자가 지정한 페이지를 사용하며, 신규 워크스페이스 최상위 생성은 그 위치가 요청된 경우에만 한다.

| 페이지 | 사용자가 하는 일 | 연결할 뷰 |
|---|---|---|
| Project Hub | 목표·세계 범위·활성 버전·현재 쟁점을 확인 | 각 하위 페이지의 실제 링크 |
| 워크숍 · 다음 결정 | 질문에 답하고 결정·미정을 확인 | Decision Log, 열린 QA, Sessions |
| 세계관 · 조직과 서비스 | 사회·역사·생활·운영·문화 읽기 | WorldRule, Organization, Service |
| 인물 · 관계와 지식 | 인물 일상·동기·관계·시점별 앎 확인 | Character, Knowledge, Claim |
| 사건 · 실제 진상 | 실제 사건·원인·결과 검토 | Event, Fact |
| 조사 · 선택과 결말 | 기록·추론·선택·분기 검토 | Trace, Choice, Ending, Canon Links |
| 최종 기획서 | 연결된 전체 기획서 읽기 | 서술형 통합 문서 |
| 관리 데이터 | 버전과 원본 데이터 접근 | Story Versions와 원본 DB 7개 |
| 동기화 상태 | 현재 연결·미반영 변경·충돌 확인 | Change Sets, Sync Registry |

하위 페이지는 요약 서술과 필터 뷰를 함께 갖는다. JSON만 노출하는 데이터 창고로 끝내지 않는다. 원본 데이터베이스는 관리 데이터 아래에 두고 일반 작업 페이지에는 linked view를 만든다.

## 2. 데이터베이스와 관계

정확한 생성 타입·선택값은 assets/notion-blueprint.json이 기준이다. 모든 DB의 공통 속성은 Name(TITLE), Key(RICH_TEXT), Revision(NUMBER), Content Hash(RICH_TEXT), Updated(LAST_EDITED_TIME)다.

| DB | 추가 속성 | Relation |
|---|---|---|
| Story Versions | Version ID, Status, Current Revision, Parent Version ID | 없음 |
| Canon Entities | Entity ID, Kind, Canon, Review, Owner, Summary, Event Time | Version → Versions |
| Canon Links | Relation, Reason | Version → Versions; Source·Target → Entities |
| Decision Log | Status, Question, Answer, Rationale | Version → Versions; Affected → Entities |
| QA Issues | Severity, Status | Version → Versions; Affected → Entities |
| Workshop Sessions | Phase, Next Question, Sync | Version → Versions |
| Change Sets | Base Revision, Target Revision, Status | Version → Versions; Affected → Entities |

Relation 생성에는 data source ID를 사용한다. 행 Relation 값에는 대상 페이지 ID/URL을 사용한다. 데이터베이스 ID, data source ID, 행 페이지 ID는 서로 대체할 수 없다. Key는 프로젝트/버전/객체ID다. Notion이 UNIQUE를 강제한다고 가정하지 말고 쓰기 전 중복 조회를 한다.

Entity 종류별 세부 정보는 본문의 읽기용 설정과 관리 JSON에 둔다. 관리 JSON 뒤에는 User Notes를 두어 사용자 메모를 보존한다. 다른 페이지를 참조할 때 mention을 사용하고 기존 page/database 태그를 제거하거나 이동시키지 않는다.

## 3. 단계별 생성

Notion MCP의 실제 설명에서 fetch, create_pages, create_database, update_data_source, create_view, update_page, query_data_sources를 확인한다. enhanced-markdown-spec, view-dsl-spec을 먼저 읽는다. 현재 커넥터가 다른 문법이면 임의 요청을 보내지 않고 설명에 맞게 변환한다.

Registry JSON을 로컬 작업본과 동기화 상태 페이지에 보관한다. 기본 필드는 project_id, version_id, title, parent_page_id 또는 workspace_root_requested, hub_page_id, pages, data_sources, database_ids, version_page_id, relations_applied, views, entity_pages, bases다. 아직 반환되지 않은 ID 필드는 비워 둔다. Notion ID는 실제 응답의 UUID를 복사한다.

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

네트워크 중단으로 성공 여부가 모호하면 재생성 전에 부모의 자식·스키마·뷰 또는 Key를 조회한다. 같은 이름만으로 임의 기존 객체를 연결하지 말고 프로젝트 범위와 생성 기록을 비교한다.

Hub에 실제 하위 페이지 링크를 연결한다. 관계를 언급하려고 기존 page 태그를 다른 페이지에 삽입하면 이동이 일어날 수 있으므로 mention-page 또는 일반 링크를 목적에 맞게 사용한다. User Notes와 기존 자식 블록을 보존하고 좁은 영역만 수정한다.

## 4. 템플릿 적용과 버전

본문은 assets/page-templates.json, 최종 문서는 assets/design-document.md를 사용한다. 템플릿 버튼이 자동 설치된다고 주장하지 않는다. 페이지 생성 시 content를 주입하는 재사용 템플릿이다. 기본 Notion 템플릿 버튼을 요구하면 현재 도구 지원을 따로 확인한다.

게임 대안 버전을 추가할 때 Versions 행과 해당 버전의 필터 뷰를 만든다. 기존 뷰의 버전 필터를 몰래 바꾸지 않는다. Hub에서 활성 버전을 표시하고 다른 버전 뷰에는 버전명을 노출한다. 독립 게임은 새로운 Hub와 DB를 생성한다.

현재 템플릿 1.0.0의 Kind 선택지에는 Location·HistoryEvent·Term이 없다. schema v2 객체를 기록하기 전에 Kind 선택지에 세 값을 추가하는 속성 갱신을 먼저 실행하고, 추가가 확인된 뒤 행을 만든다. 새 선택지를 여는 템플릿 1.1.0 전환 절차는 후속 버전에서 제공한다.

템플릿 변경은 template_version을 올리고 기존 스키마를 먼저 조회한다. 속성 삭제·이름 변경 등 손실 가능 변경은 자동 적용하지 않는다. 현재 버전은 최초 설치를 위한 계약이며 파괴적 migration 도구를 포함하지 않는다.

확인한 인터페이스: Notion MCP create_database의 SQL DDL, create_pages의 data_source_id 부모, create_view의 filter DSL (2026-09-20). 문법은 실행 시 노출된 도구 설명으로 다시 확인한다.
