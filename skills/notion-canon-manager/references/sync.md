# Notion 조회·동기화·복구

## 목차

1. 읽기와 기준 상태
2. 변경 묶음과 쓰기
3. 부분 실패와 충돌
4. 문서 조립과 완료

## 1. 읽기와 기준 상태

Hub와 Registry를 fetch해 실제 프로젝트·버전·리비전을 확인한다. 페이지가 잘렸거나 unknown 블록이 있으면 해당 내용을 덮어쓰지 말고 필요한 부분을 추가로 읽는다. 데이터 소스를 fetch해 정확한 schema와 collection:// ID를 확보한다.

조회는 현재 Notion 접근 상태에 맞는 도구를 사용한다. 키 조회는 지원되는 exact 필터나 매개변수 SQL을 사용하고, 사용자 문자열을 SQL 문법에 직접 합치지 않는다. 행 rich text는 rows 모드 또는 페이지 fetch로 확인한다. 결과 100개를 전체로 간주하지 않는다. 제한된 rows 결과는 키별로 조회하거나 pagination이 있는 뷰를 끝까지 읽는다. 쓰기 대상 모든 Key에 대한 조회가 완료되었을 때만 remote.complete=true로 표시한다.

로컬 remote.json의 형식은 {"complete":true,"records":[{"page_id":"반환 UUID","properties":{...},"body":"fetch한 본문"}]}다. properties는 MCP 읽기 결과를 생성·갱신 형식의 스칼라·배열 값으로 정규화한다. relation URL/ID, 날짜, checkbox의 문법을 실제 schema에 맞춘다. 새 레코드라면 조회 결과가 없는 것을 확인한다. 기존 레코드는 본문 관리 JSON을 추출하고 snapshot을 구성한다.

Registry.bases[Key]에 읽은 {revision,hash}를 저장한다. Notion의 Revision 속성만으로 사람의 편집을 감지할 수 없으므로 본문과 Content Hash 및 읽기용 내용을 함께 확인한다. direct edit와 canonical JSON이 다르면 자동으로 어느 쪽이 옳다고 선택하지 않는다.

## 2. 변경 묶음과 쓰기

1. 변경 ID를 생성하고 Change Sets에 PREPARED 행을 기록한다. 본문에는 대상 Key, 기준 리비전/해시, 목표 데이터/해시, 예정 operation_key와 성공·실패 목록을 둔다. 동일 변경 ID를 재시도할 때 재사용한다.
2. 사용자 선택·위임 범위 안에서 snapshot을 수정한다. AI 제안은 PROPOSED로 유지한다. 변경된 객체와 행의 revision을 증가시킨다. snapshot.revision은 묶음의 목표 리비전이다.
3. validate와 도메인 검토를 수행한다. 변경할 객체의 explicit 의존 폐쇄와 의미적 영향 범위를 확인한다.
4. 쓰기 직전에 대상 행을 다시 fetch해 기준과 충돌하지 않는지 확인한다. Notion의 서버 측 CAS나 트랜잭션을 가정하지 않는다. 짧은 경합 가능성은 남으므로 쓰기 후 검증한다.
5. Change Sets를 APPLYING으로 바꾼다. entities를 먼저 반영하고 반환된 페이지 ID를 entity_pages에 기록한다. 이어 links, decisions, issues를 반영한다. 각 operation의 결과를 즉시 기록한다.
6. 모든 도메인 행이 확인되면 Versions의 initial_state·pending_decisions와 현재 리비전을 갱신한다. Session을 저장하고 읽기용 요약·기획서를 갱신한다.
7. 결과와 대상 본문·속성을 확인한 뒤 Change Sets를 COMMITTED로 바꾸고 Hub 리비전·Registry.bases를 갱신한다. Session의 SYNCED는 해당 저장 범위가 완료된 경우에만 기록한다.

요청 생성:

```bash
python3 scripts/notion_plan.py upsert snapshot.json registry.json remote.json --collection entities
```

collection은 entities / links / decisions / issues / versions / sessions다. collection별 remote 조회 결과를 새로 준비한다. 각 요청은 도구에서 실제 실행해야 한다. 도구명의 접두사는 환경마다 다를 수 있으므로 의미에 맞는 현재 callable tool을 선택한다. Change Sets와 Hub·Registry 관리 페이지의 좁은 본문 갱신은 이 절차에 따라 직접 수행한다.

새 객체를 만들고 관계 ID가 확보되기 전에는 관계 payload를 만들지 않는다. changed record의 revision은 기존보다 커야 한다. 내용이 같으면 요청을 만들지 않는다. Key가 중복되면 어느 행이 정본인지 해결하기 전 쓰기를 중단한다. 알려진 행이 조회에서 사라졌으면 삭제·권한·범위를 확인하고 자동 재생성하지 않는다.

## 3. 부분 실패와 충돌

- 일부 성공 후 실패: PARTIAL로 기록하고 성공한 operation은 재실행하지 않는다. 전체를 성공으로 보고하지 않는다.
- 타임아웃으로 생성 성공 여부 불명: Key를 조회해 반환 ID를 복구한 뒤 후속 작업을 한다. 무조건 create 재시도하지 않는다.
- content 갱신 성공, properties 갱신 실패: fetch한 관리 JSON이 Change Set의 목표 해시와 같고 메모가 보존됐는지 확인한다. 기존 속성이 기준 상태와 일치하는 경우에만 저장된 property operation을 재개한다. 이를 확인할 수 없으면 CONFLICT다. 평상시 upsert planner는 이런 불일치를 거절하도록 설계되어 있다.
- 사람이 메모 영역을 편집: 관리 영역만 좁게 갱신해 메모를 유지한다.
- 사람이 읽기용 설정·JSON·속성을 편집: CONFLICT로 기록하고 양쪽 차이를 비교한다. 사람의 새 결정을 반영한 병합본과 새 리비전을 만든다. 동시 수정이 충돌하지 않는 범위는 자동 병합할 수 있다.
- 외부 변경 실패: API 오류에 맞춘 재시도는 최대 3회. 권한·도구 부재는 무한 반복하지 않는다. 저장 대기 데이터와 구체적인 미반영 항목을 보존한다.

update_page가 async task를 반환하면 성공 상태까지 조회한 뒤 종속 작업을 실행한다. 도구에 allow_async=false를 보내도 지연 응답이 나올 수 있으므로 결과를 확인한다. Notion 원자성을 가정하지 않는다.

삭제 요청이 없으면 객체를 지우지 않고 SUPERSEDED 또는 REJECTED로 기록한다. 기존 child page/database 태그를 제거하거나 allow_deleting_content로 보호를 우회하지 않는다. 전체 페이지 replacement보다 fetch한 유일한 old_str에 대한 targeted update를 사용한다.

## 4. 문서 조립과 완료

각 작업 페이지의 `## Canon 요약`은 `notion_plan.py pages`로 다시 쓰고, `## 해설`은 에이전트가 정본을 바탕으로 새로 쓴 서술을 같은 명령의 --narratives로 넘긴다. 영역 구성과 충돌 판단은 [Notion 템플릿](notion-template.md)의 작업 페이지 구성을 따른다. User Notes와 기존 링크·자식 블록은 보존한다. 도메인 행을 모두 반영한 뒤에 페이지 요약을 갱신한다. 최종 기획서는 design-document.md를 사용하고 실제 Notion에 만들 때 문서 제목은 properties.title에만 둔다.

자동 재생성 중 새로운 설정을 추가하지 않는다. 확정되지 않은 제안, 관련 객체의 리비전, 남은 이슈를 표시한다. Hub에 마지막 성공 리비전과 다음 질문을 남긴다. Notion 미연결이면 로컬 초안과 저장 대기 상태를 전달하고 연결 성공을 주장하지 않는다.

GitHub 저장소에는 스킬·템플릿·검증 코드만 저장한다. 게임별 snapshot, Notion UUID·사용자 답변·접속 정보는 사용자 요청 없이 그 공개 저장소로 내보내지 않는다.
