# Mystery Interface Game Story Builder Skills

짧은 아이디어를 핵심 쟁점별 대화로 발전시켜, 게임마다 독립 세계관·사건·인물·분기 결말을 갖춘 기획서를 완성하는 실사용 스킬 묶음이다.

## 시작

6개 스킬을 함께 사용할 수 있는 환경에서 다음과 같이 요청한다.

> @Mystery Production Orchestrator 새 미스터리 게임을 기획하자. 아이디어는 …이다. 질문 하나씩 선택지와 주요 영향을 비교해줘.

Notion 연결은 사용자가 제공한다. 연결과 대상 페이지가 주어지면 Canon Manager가 프로젝트 템플릿을 적용한다. 연결 전에는 초안을 진행하고 미동기화 상태를 유지한다. 연결 정보를 저장소에 넣지 않는다.

## 포함된 스킬

| 스킬 | 역할 |
|---|---|
| [Mystery Production Orchestrator](skills/mystery-production-orchestrator/SKILL.md) | 질문·라우팅·결정·재개·기획 완료 진행 |
| [Mystery Plot Builder](skills/mystery-plot-builder/SKILL.md) | 진상·시간선·사건 장소·기록 설계·공정한 단서 노출·선택과 결말 |
| [Mystery World Builder](skills/mystery-world-builder/SKILL.md) | 헌장·연표·장소·제도·정보 환경·생활을 층별로 설계하고 설정 간 모순 점검 |
| [Character Knowledge Builder](skills/character-knowledge-builder/SKILL.md) | 인물·관계·동기·소속과 동선·말투·시점별 지식과 주장 |
| [Mystery Continuity Auditor](skills/mystery-continuity-auditor/SKILL.md) | 변경 검토·전체 검토·완료 판정, 규칙 ID별 이슈 정리 |
| [Notion Canon Manager](skills/notion-canon-manager/SKILL.md) | 템플릿 적용·Canon 동기화·기획서 조립 |

각 폴더는 SKILL.md와 agents/openai.yaml을 포함한다. 참조 문서는 필요한 작업에서만 읽는다. 다른 스킬은 이름으로 찾으므로 설치 시 생성되는 내부 경로에 의존하지 않는다. 일반 Codex 환경에서는 6개 폴더를 해당 환경의 스킬 설치 방식으로 함께 설치한다. ChatGPT에서는 Skills에서 제공된 스킬을 사용한다.

## 세계관을 모순 없이 설계하는 방식

세부가 늘어날수록 모순이 생길 자리도 늘어난다. 그래서 세계관은 분량보다 **고정점**을 먼저 정한다.

- **구조화 필드에 적는 고정점:** 시각, 장소, 소속, 보존 기간, 권한, 명칭.
- **서술은 고정점에서 파생한다:** 요일이나 경과 기간을 직접 쓰지 않고 `canon.py bible`의 계산값을 인용한다.
- **자동 검사:** 고정점끼리의 모순은 규칙 ID가 붙은 검사가 잡는다.

World Builder는 세계를 헌장 → 기반(연표·장소·기술·경제) → 제도 → 정보 환경 → 생활 → 사건 접점의 6층으로 설계한다. 설정마다 밀도(CORE / SUPPORTING / MENTION), 공개도(PUBLIC / INSIDER / SECRET), 출처(FOUNDATION / PLOT_NEED)를 붙인다. 주변 설정도 고정점은 반드시 갖고, 밀도에 따라 달라지는 것은 서술 분량뿐이다.

- [World Builder 원칙과 층](skills/mystery-world-builder/SKILL.md)
- [데이터 계약과 자동 검사 규칙 목록](skills/notion-canon-manager/references/data-contract.md)

## Notion 구성

게임마다 Project Hub와 다음 8개 하위 페이지를 구성한다.

- 워크숍 · 다음 결정
- 세계관 · 조직과 서비스
- 인물 · 관계와 지식
- 사건 · 실제 진상
- 조사 · 선택과 결말
- 최종 기획서
- 관리 데이터
- 동기화 상태

관리 데이터 아래에 **Story Versions / Canon Entities / Canon Links / Decision Log / QA Issues / Workshop Sessions / Change Sets** 7개 데이터베이스를 둔다. 작업 페이지는 활성 버전별 필터 뷰와 서술형 설명을 보여준다. 같은 게임의 대안 버전과 결말 분기는 분리한다. 새 게임은 새로운 세계·페이지·데이터베이스를 사용한다.

- [페이지·속성·관계·뷰 템플릿](skills/notion-canon-manager/references/notion-template.md)
- [정확한 데이터베이스 스키마와 뷰 정의](skills/notion-canon-manager/assets/notion-blueprint.json)
- [페이지 본문 템플릿](skills/notion-canon-manager/assets/page-templates.json)
- [동기화·충돌·부분 실패 복구](skills/notion-canon-manager/references/sync.md)
- [최종 기획서 템플릿](skills/notion-canon-manager/assets/design-document.md)

현재 템플릿은 1.2.0이다. Hub와 5개 작업 페이지는 같은 영역 순서를 갖는다.

| 영역 | 쓰는 쪽 |
|---|---|
| 안내 | 템플릿 |
| 해설 | AI의 서술 |
| Canon 요약 | `canon.py`가 동기화 때마다 다시 만드는 표·목록 |
| User Notes | 사람. 자동으로 고치지 않는다 |
| 데이터 뷰 | Notion 필터 뷰 |

`notion_plan.py pages`가 해설과 Canon 요약 영역만 좁게 교체하는 요청을 만든다. 사람이 그 영역을 고쳤으면 덮어쓰지 않고 충돌로 보고한다. 세계관 페이지에는 연표·장소·정보 환경·용어집 뷰가 있고, Canon Entities에 Depth·Visibility·Origin 속성이 있다. 이전 템플릿으로 만든 프로젝트는 [전환 절차](skills/notion-canon-manager/references/notion-template.md)를 따른다. 1.0.0에서는 `notion_plan.py upgrade`로 속성과 선택지를 추가만 하고, 1.1.0에서는 첫 동기화 때 요약 영역이 추가된다.

템플릿은 실제 페이지 생성 요청에 본문과 스키마를 적용하는 방식이다. Notion의 템플릿 버튼이나 외부 백그라운드 서비스가 자동 설치되는 것은 아니다.

## 동작 원칙

질문은 하나씩 제시하고, 선택지의 설명과 설정에 미칠 영향을 비교한다. 선택이 어려우면 이유를 확인해 대안을 다시 만든다. 사용자 결정과 AI 제안을 구별한다. 조직·서비스는 사건 밖의 운영·문화·일상까지 갖는다. 과거 진상은 고정하고 플레이어 선택이 이후 결과를 바꾼다.

Notion이 정본이며 로컬 snapshot은 작업본이다. 사용자 메모는 보존한다. 해시·리비전·정확한 Key 조회로 중복과 충돌을 감지하고, 부분 실패는 Change Set에서 재개한다. Notion API의 원자적 트랜잭션이나 서버 측 CAS를 가정하지 않는다.

## 도구와 검증

Python 3 표준 라이브러리만 사용한다.

```bash
python3 scripts/validate_suite.py
python3 -m unittest discover -s tests -v
python3 skills/notion-canon-manager/scripts/canon.py --help
python3 skills/notion-canon-manager/scripts/canon.py bible tests/fixtures/world_v2.json
python3 skills/notion-canon-manager/scripts/canon.py timeline tests/fixtures/world_v2.json --character C1
python3 skills/notion-canon-manager/scripts/canon.py page tests/fixtures/world_v2.json world
python3 skills/notion-canon-manager/scripts/notion_plan.py --help
```

`canon.py`는 구조·ID·참조·결정 출처·결말 도달 경로·변경 영향과 함께, 규칙 ID가 붙은 시간·공간·보존·명칭·세계관 정합성 규칙을 검사한다. `bible`과 `timeline`은 요일과 경과 기간을 계산한 세계 바이블과 시간선을 출력하고, `migrate`는 v1 스냅샷을 v2로 옮긴다. `canon.py page`는 Notion 작업 페이지에 들어갈 Canon 요약을 Notion 문법으로 미리 보여 준다. `notion_plan.py`는 현재 Notion MCP용 생성·갱신 요청, 템플릿 추가형 전환 요청(`upgrade`), 작업 페이지 영역 교체 요청(`pages`)을 출력한다. 요청 실행은 연결된 도구를 사용하는 에이전트가 담당한다. 이 스크립트는 토큰을 저장하거나 직접 네트워크를 호출하지 않는다.

테스트는 다음을 확인한다: 구조 검증, 결말 조건, 변경 파급, 규칙별 통과·실패 사례, v1 이관, 세계 바이블 출력, 템플릿 요청과 추가형 전환, 중복 방지, 충돌 감지, 메모 보존, 잘못된 입력에서의 안정성. `scripts/validate_suite.py`는 스킬 문서가 쓰는 필드명과 코드의 필드가 데이터 계약과 일치하는지도 검사한다. 실제 Notion 쓰기와 사용자 창작 워크숍의 품질 검증은 사용자가 연결 후 진행한다. 데모 게임은 포함하지 않는다. `tests/fixtures`의 작은 세계는 검사기 테스트용이다.

[행동 평가 시나리오](evals/README.md)는 모델이 스킬을 읽고 올바르게 행동하는지를 채점하는 묶음이다. 예를 들어 모순을 알리는지, 사용자 대신 확정하지 않는지 본다. 시나리오의 정답 규칙은 테스트가 검사기와 대조한다.

## 완료 범위

현재 버전(1.2.0)은 실제 사용할 기획서 제작 워크플로 전체를 제공한다. 변경 내역은 [CHANGELOG](CHANGELOG.md)에 있다. 메시지·보고서 본문 대량 생성, 실행 가능한 검색·해금 전체 그래프, 게임 UI·코드와 실제 플레이 검증은 후속 제작 범위다.

사용자 게임의 snapshot, 답변, Notion 연결 ID, 토큰은 이 공개 저장소에 자동 저장하지 않는다.
