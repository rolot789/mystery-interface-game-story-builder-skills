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
| [Mystery Plot Builder](skills/mystery-plot-builder/SKILL.md) | 진상·시간선·조사 개요·선택과 결말 |
| [Mystery World Builder](skills/mystery-world-builder/SKILL.md) | 헌장·연표·장소·제도·정보 환경·생활을 층별로 설계하고 설정 간 모순 점검 |
| [Character Knowledge Builder](skills/character-knowledge-builder/SKILL.md) | 인물·관계·동기·시점별 지식과 주장 |
| [Mystery Continuity Auditor](skills/mystery-continuity-auditor/SKILL.md) | 인과·정보·세계 규칙·근거·결말 검토 |
| [Notion Canon Manager](skills/notion-canon-manager/SKILL.md) | 템플릿 적용·Canon 동기화·기획서 조립 |

각 폴더는 SKILL.md와 agents/openai.yaml을 포함한다. 참조 문서는 필요한 작업에서만 읽는다. 다른 스킬은 이름으로 찾으므로 설치 시 생성되는 내부 경로에 의존하지 않는다. 일반 Codex 환경에서는 6개 폴더를 해당 환경의 스킬 설치 방식으로 함께 설치한다. ChatGPT에서는 Skills에서 제공된 스킬을 사용한다.

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
python3 skills/notion-canon-manager/scripts/notion_plan.py --help
```

`canon.py`는 구조·ID·참조·결정 출처·결말 도달 경로·변경 영향과 함께, 규칙 ID가 붙은 시간·공간·보존·명칭·세계관 정합성 규칙을 검사한다. `bible`과 `timeline`은 요일과 경과 기간을 계산한 세계 바이블과 시간선을 출력하고, `migrate`는 v1 스냅샷을 v2로 옮긴다. `notion_plan.py`는 현재 Notion MCP용 생성·갱신 요청을 출력한다. 요청 실행은 연결된 도구를 사용하는 에이전트가 담당한다. 이 스크립트는 토큰을 저장하거나 직접 네트워크를 호출하지 않는다.

테스트는 구조 검증, 결말 조건, 변경 파급, 템플릿 요청, 중복 방지, 충돌 감지, 메모 보존을 확인한다. 실제 Notion 쓰기와 사용자 창작 워크숍의 품질 검증은 사용자가 연결 후 진행한다. 데모 게임은 포함하지 않는다. `tests/fixtures`의 작은 세계는 검사기 테스트용이다.

## 완료 범위

첫 버전은 실제 사용할 기획서 제작 워크플로 전체를 제공한다. 메시지·보고서 본문 대량 생성, 실행 가능한 검색·해금 전체 그래프, 게임 UI·코드와 실제 플레이 검증은 후속 제작 범위다.

사용자 게임의 snapshot, 답변, Notion 연결 ID, 토큰은 이 공개 저장소에 자동 저장하지 않는다.
