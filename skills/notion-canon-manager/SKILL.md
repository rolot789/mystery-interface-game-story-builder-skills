---
name: notion-canon-manager
description: "미스터리 게임별 Notion Project Hub·데이터베이스·필터 뷰 템플릿을 구성하고 Canon·결정·세션·검토 이슈를 조회·동기화하며 최종 기획서를 조립할 때 사용한다."
---

# Notion Canon Manager

Notion을 확정 기록의 기준으로 사용하라. 로컬 snapshot은 읽어 온 리비전의 작업본이다. [데이터 계약](references/data-contract.md), 작업에 맞는 [Notion 템플릿](references/notion-template.md) 또는 [동기화 절차](references/sync.md)를 읽어라.

## 새 프로젝트

연결된 Notion의 현재 도구를 확인하라. 현재 커넥터에 `fetch id=self`가 있으면 먼저 확인하고, 콘텐츠 검색은 반환된 접근 상태에 맞는 검색 도구를 사용하라. 페이지 생성 전에 enhanced Markdown 문서를, 뷰 구성 전에 view DSL 문서를 읽어라. 기존 페이지의 부모·소유 범위를 확인하고 같은 프로젝트를 중복 생성하지 마라.

`assets/notion-blueprint.json`과 `scripts/notion_plan.py`로 Project Hub, 하위 페이지, 7개 데이터베이스, 관계 속성, 활성 버전별 필터 뷰를 단계적으로 생성하라. 실제 반환 ID를 기록하고 다음 단계에 사용하라. 부모가 지정되지 않았으면 창작을 먼저 진행할 수 있지만 Notion의 임의 기존 페이지에 저장하지 마라. 최상위 새 페이지를 원하는지 또는 사용할 부모를 정하는 질문은 실제 생성이 필요할 때 한 번만 하라.

## 조회·변경

1. Hub의 프로젝트 ID·활성 버전·리비전과 Sync Registry를 읽어라.
2. 관련 데이터 소스 schema와 필요한 행·본문을 fetch하라. 일부 결과를 전체 결과로 간주하지 말고 pagination을 완료하라.
3. Canon의 관리 JSON 영역과 속성을 교차 확인해 snapshot을 구성하라. 사용자 메모는 보존하고 새 설정 제안으로 별도 기록하라.
4. `scripts/canon.py validate snapshot.json`으로 구조를 검사하고 해당 도메인과 Auditor로 의미를 검토하라.
5. [동기화 절차](references/sync.md)에 따라 변경 묶음을 기록하고 단계적으로 반영하라. 일괄 갱신이 원자적이라고 가정하지 마라.
6. 저장·재개 상태를 갱신하고 실제 성공·실패를 보고하라.

## 기획서 조립

세계관 페이지와 기획서의 세계관 절은 `canon.py bible` 출력을 바탕으로 서술한다. `assets/design-document.md`의 목차로 버전의 세계·인물·진상·조사·분기·미정을 통합하라. 목록을 붙여 넣는 것으로 끝내지 말고 관계와 인과를 읽기 쉬운 문장으로 설명하라. 출처 객체 ID와 리비전을 남기고 새 설정은 추가하지 마라. 완성 판정은 Auditor가 맡는다.

## 도구의 역할

`canon.py`는 snapshot 생성·검증·영향 추적·관리 본문 렌더링·v1 이관(`migrate`)·세계 바이블(`bible`)·시간선(`timeline`) 출력을 한다. 검증 결과의 findings는 규칙 ID와 대상 ID를 가지므로 QA Issue로 그대로 옮길 수 있다. `notion_plan.py`는 현재 MCP용 요청 계획(최초 구성, 행 생성·갱신, 템플릿 1.0.0 → 1.1.0 추가형 전환)을 생성하며 직접 네트워크 요청을 하지 않는다. 기존 프로젝트의 Registry에 template_version이 없거나 1.0.0이면 schema v2 객체를 기록하기 전에 [Notion 템플릿](references/notion-template.md)의 전환 절차를 먼저 수행하라. 계획을 출력한 것과 Notion 실행을 혼동하지 마라. 현재 도구의 schema가 다르면 최신 도구 설명을 읽고 같은 계약에 맞게 조정하라. 네트워크용 토큰을 요구하거나 저장하지 마라.

본문 템플릿은 `assets/page-templates.json`에 있다. 데이터베이스 템플릿 버튼 API가 있다고 가정하지 않고 페이지 생성 시 해당 본문을 넣어라. 템플릿 자체를 실제 세계 설정으로 확정하지 마라.

## 상태·소유권

내용 상태는 DRAFT / PROPOSED / CONFIRMED / SUPERSEDED / REJECTED, 검토 상태는 NOT_CHECKED / VALID / NEEDS_REVIEW / BLOCKED, 저장 상태는 LOCAL_DRAFT / PENDING_SYNC / SYNCED / SYNC_FAILED다. 서로 다른 축을 섞지 마라. 도메인의 의미 변경은 담당 스킬에 요청하고, 기록·관계·동기화·문서 조립만 소유하라.

묶음 설치 시 다른 스킬은 이름으로 찾아라. 본문에 다른 설치의 절대 경로를 남기지 마라. 이 스킬 단독으로도 템플릿과 기록 관리를 할 수 있지만 부족한 사건·인물 설정을 임의로 채우지 마라.
