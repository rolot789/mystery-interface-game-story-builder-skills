# Canon 데이터 계약 v2

## 목차

1. 스냅샷과 객체
2. 헌장과 시간 표현
3. 종류별 데이터
4. 관계와 결정
5. 리비전과 검사
6. 규칙 목록
7. v1 스냅샷 이관

## 1. 스냅샷과 객체

JSON을 사용한다. Python 3 표준 라이브러리만 필요하다. 초기 파일은 다음 명령으로 만들며 기존 파일을 덮어쓰지 않는다. 새 파일은 schema_version 2다.

```bash
python3 scripts/canon.py new --project-id PRJ-식별자 --version-id VER-001 --title '프로젝트 제목' --output snapshot.json
```

project_id는 새 게임마다 고유하게 생성한다. version_id는 게임 내 스토리 대안이다. 결말은 버전이 아니다. 스냅샷의 키는 schema_version=2, project_id, version_id, title, revision, charter, initial_state, entities, links, decisions, issues, pending_decisions, session이다. initial_state는 선언된 상태 변수와 초기 스칼라 값이다. 미정 수치는 임의 생성하지 않는다. schema_version 1 스냅샷도 계속 검증되지만 charter와 v2 전용 종류를 쓸 수 없다.

각 entity는 id, project_id, version_id, title, kind, revision, owner, status, review, depends_on, decision_refs, data를 갖는다. id는 영문·숫자·밑줄·하이픈으로 구성한다. 식별 키는 project/version/id다. 리비전은 0부터 증가하는 정수다. 모든 참조는 같은 스냅샷의 ID를 사용한다. 대안 버전은 명시적 복제와 source version 기록으로 만들며 이후 자동 상속하지 않는다.

status는 DRAFT / PROPOSED / CONFIRMED / SUPERSEDED / REJECTED, review는 NOT_CHECKED / VALID / NEEDS_REVIEW / BLOCKED다. 확인되지 않은 의미는 PROPOSED로 남긴다. CONFIRMED는 원문 답변이 있는 확정 Decision의 근거를 갖는다. 객체의 일부만 선택된 경우 확정 부분을 별도 객체로 나누거나 전체는 PROPOSED로 유지하고 부분 결정의 범위를 기록한다.

세계 소유 종류(WorldRule, Organization, Service, Location, HistoryEvent, Term)는 v2에서 entity 최상위에 다음 메타데이터를 반드시 갖는다. 다른 종류는 선택이다.

| 필드 | 값 | 의미 |
|---|---|---|
| depth | CORE / SUPPORTING / MENTION | 설정 밀도 |
| visibility | PUBLIC / INSIDER / SECRET | 공개도 |
| origin | FOUNDATION / PLOT_NEED | 출처. PLOT_NEED는 in_world_reason(세계 내 근거)을 함께 적는다 |

## 2. 헌장과 시간 표현

charter는 genre_tone, reality_distance(REAL / REAL_PLUS / ALTERNATE / INVENTED 또는 null), premise, scope_in(entity ID 배열), scope_out, timezone, present_at(조사 현재 시점)을 갖는다. timezone은 표시용이며 계산은 각 시각의 오프셋을 따른다.

시각 필드는 TimeSpec이다.

```json
"at": "2026-03-01T22:00:00+09:00"
"at": {"earliest": "2019-09-01T00:00:00+09:00", "latest": "2019-11-30T23:59:59+09:00", "label": "2019년 가을"}
"at": null
```

- 첫째 줄은 정확한 시각이다. 시간대 오프셋이 필수다.
- 둘째 줄은 불확실한 구간이다. earliest와 latest 중 하나만 있으면 열린 구간이다.
- 셋째 줄은 미정이다. 순서는 preconditions로만 표현한다.

모르는 시각을 그럴듯한 정밀 시각으로 채우지 않는다. 시간 규칙은 역전이 **확실할 때만** 오류를 낸다. 구간이 겹치면 통과한다.

## 3. 종류별 data

아래 텍스트 필드는 비어 있지 않아야 한다. 적용되지 않으면 해당 없음과 이유를 적는다. 미정은 미정이라고 적고 pending_decisions에 연결한다. 이는 최종 기획에서 미정을 숨기는 수단이 아니다.

| kind | 필수 data 필드 | owner |
|---|---|---|
| WorldRule | statement, scope, exceptions, grounding | mystery-world-builder |
| Organization | purpose, economy, operations, culture, daily_life | mystery-world-builder |
| Service | purpose, provider_id, users, normal_use, data_lifecycle, permissions, failures | mystery-world-builder |
| Location (v2) | description, access, rhythm | mystery-world-builder |
| HistoryEvent (v2) | summary(실제로 일어난 일), consequences(현재에 남은 흔적), public_account(통념) | mystery-world-builder |
| Term (v2) | definition, register(사용 집단과 어조) | mystery-world-builder |
| Character | identity, motive, daily_life, relationships | character-knowledge-builder |
| Event | at, actors(ID 배열), preconditions(ID 배열), action, result | mystery-plot-builder |
| Fact | statement, basis, 선택적 event_id 또는 world_rule_id | mystery-plot-builder |
| Claim | statement, speaker_id, audience, stated_at, intent | character-knowledge-builder |
| Knowledge | character_id, fact_id, state, from, until, acquired_via(ID 배열), 필요 시 initial_basis | character-knowledge-builder |
| Trace | origin_type, origin_ids(ID 배열), summary, access, distortion, created_at | mystery-plot-builder |
| Choice | prompt, known_information, available_when, options | mystery-plot-builder |
| Ending | condition, consequences, witness, exclusive | mystery-plot-builder |

선택 필드는 값이 있을 때만 형식과 규칙을 검사한다. depth=CORE인 세계 설정은 완료 판정에서 ★ 표시 필드를 채워야 한다(WORLD-002).

| kind | 선택 필드 |
|---|---|
| WorldRule | rule_type★(PHYSICAL / TECHNICAL / LEGAL / ORGANIZATIONAL / SOCIAL_NORM / ECONOMIC / BELIEF), strength★(HARD / SOFT), valid_from, valid_until, enforced_by(Organization ID 배열), violation_cost |
| Organization | founded_at★, parent_id, hq_location_id, structure★, incentives★, reputation, conflicts, formal_vs_actual |
| Service | launched_at★, changes[{at, summary}], retention★[{data, keep_days(정수 일수, 영구면 null), after(HARD_DELETE / SOFT_DELETE / ARCHIVE, 영구면 null), exceptions}], access_policy★[{role, data, ops(read / edit / delete / restore / export), condition}], artifacts★[{type, timestamp_source, edit_trace, delete_trace, read_receipt}] |
| Location | place_type★, parent_id, connections★[{to, minutes, mode}] (빈 배열 허용) |
| HistoryEvent | at★, preconditions(HistoryEvent·WorldRule ID 배열), legacy_ids(흔적이 남은 세계 설정 ID 배열) |
| Term | aliases★, forbidden_aliases★ (빈 배열 허용), refers_to |
| Character | affiliations[{org_id, role, from, until}], home_location_id, routine, voice |
| Event | location_id, duration_minutes; preconditions에 HistoryEvent 허용 |
| Claim | fact_ids(관련 Fact ID 배열) |
| Knowledge | cannot_know(시간·경로·권한 제한과 예외), belief_text |
| Trace | author_id, service_id, artifact_type, state_at_present(PRESENT / DELETED / ALTERED, 기본 PRESENT), retention_exception; origin_ids에 HistoryEvent 허용 |

Knowledge state는 KNOWS / BELIEVES / SUSPECTS / UNKNOWN이다. BELIEVES의 구체적 인식은 belief_text로 보충한다. 진실과 다른 믿음은 Claim과 연결한다. intent는 truthful / lie / mistaken / uncertain이다. Trace origin_type은 event / routine / system이다. 일상 기록은 주요 사건 외의 활동에서 생길 수 있다.

Choice options는 각 id, label, condition, effects를 갖는다. effects는 선언된 변수에 같은 자료형의 값을 설정한다. 조건은 불리언 또는 all / any / not / var+eq 구조다. 자세한 의미는 Plot Builder의 분기 참조 문서 및 canon.py condition을 따른다. Ending witness는 choice_id와 option_id 쌍의 순서 있는 배열이다. 단일 선택은 한 경로에서 한 번만 실행한다.

## 4. 관계와 결정

Link는 id, kind, source, target, reason을 갖는다. 이유 없이 링크만 연결하지 않는다.

| kind | 방향 | 변경 영향 |
|---|---|---|
| supports / contradicts | Trace → Fact·Claim | 양쪽. 대상이 바뀌면 근거 Trace도 재검토한다 |
| generates | Event·Service → Trace | 원인 → 기록 |
| depends_on | 의존하는 객체 → 필요한 객체 | 필요한 객체 → 의존하는 객체 |
| related | 임의 | 설명용 |
| entails (v2) | WorldRule → WorldRule·Organization·Service·Location·Term | 규칙 → 2차 파급 |
| exploits (v2) | Event → WorldRule·Service | 양쪽. reason에 허점의 정당화를 적는다 |
| knows | Character → Fact | 폐지 예정, 경고만 낸다. 인물의 앎은 Knowledge 하나로 기록한다 |

Decision은 id, question, answer, status, rationale, affected_ids를 갖는다. 확정된 사용자 원문 답변과 선택의 범위를 보존한다. 도출 제약은 entailed, 추가 가정은 proposed로 본문에 구별한다. 선택 한 번을 근거로 관계없는 설정까지 확정하지 않는다.

QA Issue는 id, title, severity(BLOCKER / MAJOR / MINOR), affected_ids, evidence, violated_rule, suggested_fix, status(OPEN / RESOLVED / ACCEPTED)를 갖는다. 자동 검사에서 나온 이슈는 violated_rule에 규칙 ID를 적는다. BLOCKER를 ACCEPTED로 바꿔 완료 검사를 우회하지 않는다.

Session은 id, title, phase, last_question, options, answer, pending_decisions, next_question, next_question_reason, canon_revision, sync_state와 선택적 last_check(검토한 리비전과 남은 ERROR 규칙 ID)를 갖는다. 전체 응답이나 식별 가능한 개인정보를 공개 GitHub에 자동 저장하지 않는다. 게임 데이터는 해당 사용자의 Notion에 저장한다.

## 5. 리비전과 검사

본문의 사용자 메모를 유지한다. JSON 구조화 원본과 읽기용 설정, Notion 속성은 같은 변경 묶음에서 갱신한다. 사용자가 관리 영역이나 속성을 직접 수정했으면 충돌로 발견해 의미를 비교하고 병합한다. 사람의 수정 내용을 조용히 제거하지 않는다.

```bash
python3 scripts/canon.py validate snapshot.json
python3 scripts/canon.py validate snapshot.json --complete
python3 scripts/canon.py impact snapshot.json ENTITY-ID
python3 scripts/canon.py render snapshot.json ENTITY-ID
python3 scripts/canon.py bible snapshot.json
python3 scripts/canon.py timeline snapshot.json --character CHARACTER-ID
python3 scripts/canon.py migrate old.json --output new.json
```

- validate는 errors, warnings, findings를 출력한다. findings는 `{rule, level, ids, message}` 목록이며 ids는 QA Issue의 affected_ids로 그대로 쓸 수 있다.
- bible은 세계 헌장, 연표, 장소 트리, 조직, 규칙, 서비스별 보존·권한·기록 유형, 용어집, 공개도별 목록을 Markdown으로 출력한다.
- timeline은 사건·기록·발언·앎·소속을 시간순으로 출력한다.
- bible과 timeline은 요일과 조사 현재 시점 기준 경과 기간을 계산해 보여 준다. 서술에는 계산한 값을 직접 적지 말고 이 출력을 인용한다.

--complete는 필수 종류, 확정·검토 상태, 결말 witness, 열린 차단 이슈와 미정 목록, 헌장 확정(WORLD-001), CORE 세계 설정의 구조화 필드(WORLD-002)를 검사한다. 주변 미정은 명시적으로 보류 목록으로 분리할 수 있다. 스키마 검증과 서사 검토를 함께 해야 완료로 판정할 수 있다. 별도 시뮬레이터 없이 모든 경로를 검증했다고 보고하지 않는다.

## 6. 규칙 목록

시각이 null인 객체는 시간 규칙에서 비교하지 않는다. ERROR는 validate 실패, WARNING은 검토 목록이다.

| 규칙 | 수준 | 내용 |
|---|---|---|
| TIME-001 | ERROR | Event·HistoryEvent는 charter.present_at보다 늦을 수 없다 |
| TIME-002 | ERROR | 선행 조건(Event·HistoryEvent)은 후행 사건보다 늦을 수 없다 |
| TIME-003 | ERROR | Trace.created_at은 모든 원인 사건보다 이를 수 없다 |
| TIME-004 | ERROR | Knowledge.from은 모든 획득 경로(Event·Trace·Claim)보다 이를 수 없다 |
| TIME-005 | ERROR | 서비스 출시 전의 기록, 설립 전 조직의 행동, 제공 조직 설립 전의 서비스 출시 |
| TIME-006 | ERROR | Event가 선행 조건으로 쓴 WorldRule은 그 시각에 유효해야 한다 |
| TIME-007 | WARNING | 조직과 함께 행동한 인물의 소속 기간이 사건 시각을 포함하지 않는다 |
| GRAPH-001 | ERROR | depends_on·preconditions 순환, 조직 상하 관계 순환 |
| SPACE-001 | ERROR | 장소 상하 관계 순환 |
| SPACE-002 | ERROR | 같은 인물이 같은 시각에 서로 다른 장소에 있다 (상하 관계인 장소는 제외) |
| SPACE-003 | WARNING | 연속된 두 사건 사이의 시간이 알려진 이동 시간보다 짧다 |
| DATA-001 | ERROR | 조사 현재 시점에 HARD_DELETE 보존 기간이 지난 기록이 PRESENT로 존재하고 retention_exception이 없다 |
| DATA-002 | WARNING | Trace.artifact_type이 해당 Service.artifacts에 선언되지 않았다 |
| TERM-001 | WARNING | 금지 별칭이 다른 설정의 제목·본문에 등장한다 |
| TERM-002 | WARNING | 같은 종류의 제목 중복, 두 용어가 같은 이름을 쓰거나 금지 별칭이 다른 용어의 이름이다 |
| WORLD-001 | ERROR | scope_in이 없는 ID를 가리킨다. 완료 시 헌장의 reality_distance·premise·present_at과 scope_in 활성 상태 |
| WORLD-002 | ERROR | 완료 시 CORE 세계 설정의 ★ 필드 누락 |
| WORLD-003 | ERROR | PLOT_NEED 설정에 in_world_reason이 없다 |
| WORLD-004 | WARNING | HARD 규칙이 exploits 대상이다. 허점을 exceptions에 적거나 SOFT로 바꾼다 |
| FAIR-001 | WARNING | 해답에 쓰인 SECRET·INSIDER 규칙에 연결된 Trace가 없다 |
| CLAIM-001 | WARNING | 거짓말(lie)에 fact_ids가 없거나, 발언 시점에 화자가 그 사실을 알거나 믿지 않았다 |
| LINK-001 | WARNING | knows 링크 사용 |

## 7. v1 스냅샷 이관

```bash
python3 scripts/canon.py migrate old.json --output new.json
```

migrate는 schema_version 1만 받는다. 출력 파일을 덮어쓰지 않고, 결과를 검증해 출력한다. mystery-world-builder가 정한 v1 고정 형식을 읽는다.

- 제목 `헌장:`, `장소:`, `용어:`
- 첫 줄 `[밀도·공개도·출처]` 태그와 `세계 내 근거:` 줄
- `보존:`, `권한:`, `[연표]` 줄

변환 방식:

- 장소·용어 규칙은 같은 ID의 Location·Term으로 바꾼다.
- 헌장 규칙은 charter를 채우고 규칙 자체는 남긴다.
- 연표 줄은 HistoryEvent로 만든다.
- knows 링크는 Knowledge 초안으로 옮긴다.
- 변경한 객체와 스냅샷의 리비전을 올린다.
- 원래 텍스트는 지우지 않는다.

정확히 옮기지 못한 부분(해석하지 못한 줄, 근사한 보존 기간, 기본값을 넣은 메타데이터, 제거한 참조)은 violated_rule이 MIGRATION인 OPEN MINOR QA Issue로 남긴다. 기본값을 넣은 객체는 NEEDS_REVIEW가 된다. 이관 후 이 이슈들을 사용자와 확인한다.
