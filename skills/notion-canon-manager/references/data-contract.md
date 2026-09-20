# Canon 데이터 계약 v1

## 목차

1. 스냅샷과 객체
2. 종류별 데이터
3. 관계와 결정
4. 리비전과 검사

## 1. 스냅샷과 객체

JSON을 사용한다. Python 3 표준 라이브러리만 필요하다. 초기 파일은 다음 명령으로 만들며 기존 파일을 덮어쓰지 않는다.

```bash
python3 scripts/canon.py new --project-id PRJ-식별자 --version-id VER-001 --title '프로젝트 제목' --output snapshot.json
```

project_id는 새 게임마다 고유하게 생성한다. version_id는 게임 내 스토리 대안이다. 결말은 버전이 아니다. 스냅샷의 키는 schema_version=1, project_id, version_id, title, revision, initial_state, entities, links, decisions, issues, pending_decisions, session이다. initial_state는 선언된 상태 변수와 초기 스칼라 값이다. 미정 수치는 임의 생성하지 않는다.

각 entity는 id, project_id, version_id, title, kind, revision, owner, status, review, depends_on, decision_refs, data를 갖는다. id는 영문·숫자·밑줄·하이픈으로 구성한다. 식별 키는 project/version/id다. 리비전은 0부터 증가하는 정수다. 모든 참조는 같은 스냅샷의 ID를 사용한다. 대안 버전은 명시적 복제와 source version 기록으로 만들며 이후 자동 상속하지 않는다.

status는 DRAFT / PROPOSED / CONFIRMED / SUPERSEDED / REJECTED, review는 NOT_CHECKED / VALID / NEEDS_REVIEW / BLOCKED다. 확인되지 않은 의미는 PROPOSED로 남긴다. CONFIRMED는 원문 답변이 있는 확정 Decision의 근거를 갖는다. 객체의 일부만 선택된 경우 확정 부분을 별도 객체로 나누거나 전체는 PROPOSED로 유지하고 부분 결정의 범위를 기록한다.

## 2. 종류별 data

아래 텍스트 필드는 비어 있지 않아야 한다. 적용되지 않으면 해당 없음과 이유를 적는다. 미정은 미정이라고 적고 pending_decisions에 연결한다. 이는 최종 기획에서 미정을 숨기는 수단이 아니다.

| kind | data 필드 | owner |
|---|---|---|
| WorldRule | statement, scope, exceptions, grounding | mystery-world-builder |
| Organization | purpose, economy, operations, culture, daily_life | mystery-world-builder |
| Service | purpose, provider_id, users, normal_use, data_lifecycle, permissions, failures | mystery-world-builder |
| Character | identity, motive, daily_life, relationships | character-knowledge-builder |
| Event | at(null 또는 시간대 포함 ISO 시각), actors(ID 배열), preconditions(ID 배열), action, result | mystery-plot-builder |
| Fact | statement, basis, 선택적 event_id 또는 world_rule_id | mystery-plot-builder |
| Claim | statement, speaker_id, audience, stated_at, intent | character-knowledge-builder |
| Knowledge | character_id, fact_id, state, from, until, acquired_via(ID 배열), 필요 시 initial_basis | character-knowledge-builder |
| Trace | origin_type, origin_ids(ID 배열), summary, access, distortion, created_at, 선택적 author_id | mystery-plot-builder |
| Choice | prompt, known_information, available_when, options | mystery-plot-builder |
| Ending | condition, consequences, witness, exclusive | mystery-plot-builder |

Knowledge state는 KNOWS / BELIEVES / SUSPECTS / UNKNOWN이다. BELIEVES의 구체적 인식은 belief_text로 보충한다. 진실과 다른 믿음은 Claim과 연결한다. intent는 truthful / lie / mistaken / uncertain이다. Trace origin_type은 event / routine / system이다. 일상 기록은 주요 사건 외의 활동에서 생길 수 있다.

Choice options는 각 id, label, condition, effects를 갖는다. effects는 선언된 변수에 같은 자료형의 값을 설정한다. 조건은 불리언 또는 all / any / not / var+eq 구조다. 자세한 의미는 Plot Builder의 분기 참조 문서 및 canon.py condition을 따른다. Ending witness는 choice_id와 option_id 쌍의 순서 있는 배열이다. 단일 선택은 한 경로에서 한 번만 실행한다.

## 3. 관계와 결정

Link는 id, kind, source, target, reason을 갖는다. supports / contradicts는 Trace에서 Fact·Claim으로 향한다. generates는 Event·Service에서 Trace로 향한다. depends_on은 의존하는 객체에서 필요한 객체로 향한다. related는 관련 설명용이다. 이유 없이 링크만 연결하지 않는다.

Decision은 id, question, answer, status, rationale, affected_ids를 갖는다. 확정된 사용자 원문 답변과 선택의 범위를 보존한다. 도출 제약은 entailed, 추가 가정은 proposed로 본문에 구별한다. 선택 한 번을 근거로 관계없는 설정까지 확정하지 않는다.

QA Issue는 id, title, severity(BLOCKER / MAJOR / MINOR), affected_ids, evidence, violated_rule, suggested_fix, status(OPEN / RESOLVED / ACCEPTED)를 갖는다. BLOCKER를 ACCEPTED로 바꿔 완료 검사를 우회하지 않는다.

Session은 id, title, phase, last_question, options, answer, pending_decisions, next_question, next_question_reason, canon_revision, sync_state를 갖는다. 전체 응답이나 식별 가능한 개인정보를 공개 GitHub에 자동 저장하지 않는다. 게임 데이터는 해당 사용자의 Notion에 저장한다.

## 4. 리비전과 검사

본문의 사용자 메모를 유지한다. JSON 구조화 원본과 읽기용 설정, Notion 속성은 같은 변경 묶음에서 갱신한다. 사용자가 관리 영역이나 속성을 직접 수정했으면 충돌로 발견해 의미를 비교하고 병합한다. 사람의 수정 내용을 조용히 제거하지 않는다.

```bash
python3 scripts/canon.py validate snapshot.json
python3 scripts/canon.py impact snapshot.json ENTITY-ID
python3 scripts/canon.py render snapshot.json ENTITY-ID
python3 scripts/canon.py validate snapshot.json --complete
```

--complete는 필수 종류, 확정·검토 상태, 결말 witness, 열린 차단 이슈와 미정 목록을 검사한다. 주변 미정은 명시적으로 보류 목록으로 분리할 수 있다. 스키마 검증과 서사 검토를 함께 해야 완료로 판정할 수 있다. 별도 시뮬레이터 없이 모든 경로를 검증했다고 보고하지 않는다.
