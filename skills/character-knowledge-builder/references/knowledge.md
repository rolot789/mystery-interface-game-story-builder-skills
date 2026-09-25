# 정보 비대칭 계약

## Knowledge

Knowledge는 character_id, fact_id, state, from, until, acquired_via를 갖는다. state는 KNOWS / BELIEVES / SUSPECTS / UNKNOWN이다. BELIEVES는 대상 Fact에 대한 믿음을 belief_text로 설명한다. 잘못된 믿음은 참인 Fact 자체를 거짓으로 바꾸지 않는다.

acquired_via는 정보가 전달된 Event·Trace·Claim의 ID다. from은 모든 획득 경로보다 앞설 수 없다(TIME-004). 초기부터 아는 사실은 initial_basis로 근거를 설명할 수 있다. 관계가 있다는 사실만으로 서로의 모든 비밀을 안다고 가정하지 않는다. 인물의 앎은 Knowledge로만 기록하고 knows 링크를 쓰지 않는다(LINK-001).

from과 until은 TimeSpec이다. "그 주 어느 날 알게 됐다"처럼 정확한 시각이 없으면 구간으로 적는다. 알게 된 시각을 모르는데 정밀한 시각을 꾸며 넣지 않는다.

## 지식의 한계

cannot_know(Knowledge의 선택 필드)는 특정 시간·경로·권한에서의 제한이다. 규칙과 예외를 함께 적는다. 기관의 비공개 정책은 별개의 사적 정보 경로까지 금지하지 않는다.

권한에서 오는 한계는 World Builder의 Service.access_policy와 인물의 affiliations로 판단한다. "관리자만 볼 수 있다"면 그 인물이 그 시점에 관리자 역할이었는지 확인한다. 공개도가 INSIDER나 SECRET인 세계 사실을 인물이 알고 있다면, 그 인물의 소속이나 획득 경로가 설명해야 한다.

## Claim

Claim은 speaker_id, statement, stated_at, audience, intent와 관련 Fact(fact_ids)를 가진다. intent는 truthful / lie / mistaken / uncertain 중 하나다. LIE는 지식 상태가 아니다. 고의적 거짓말은 당시의 믿음·지식과 주장 간 차이로 설명해야 한다.

| intent | 필요한 연결 |
|---|---|
| truthful | 화자가 그 시점에 KNOWS 또는 BELIEVES인 Knowledge |
| lie | fact_ids로 숨기는 진실을 가리키고, 화자가 stated_at에 그 진실을 KNOWS·BELIEVES·SUSPECTS (CLAIM-001) |
| mistaken | 화자의 BELIEVES Knowledge와 belief_text. 믿음이 틀린 이유 |
| uncertain | 화자가 SUSPECTS이거나 모른다는 것을 스스로 표현한 주장 |

거짓말마다 대상(audience), 이유, 들킬 위험을 정한다. 같은 사람에게 한 두 거짓말이 서로 모순되면 의도인지 확인한다.

## 시점별 표

시점별 표를 만들 때 행은 Fact, 열은 인물이며 해당 시각을 명시한다. 현재 시점 표를 과거 보고서 작성 검증에 사용하지 않는다. 동일 인물·사실의 기간이 겹치고 상태가 다르면 의도적 복합 믿음인지 충돌인지 확인한다.

인물 한 명의 흐름은 `canon.py timeline snapshot.json --character 인물ID`로 본다. 소속 시작, 사건, 작성한 기록, 앎의 시작, 발언이 시간순으로 나오므로 "그때 이 사람이 이걸 알았나"를 한 번에 확인할 수 있다.

## 문서 작성자의 시점

인물이 작성한 기록(Trace.author_id)의 개요에는 작성 시점에 그 인물이 알 수 있었던 것만 넣는다. 작성 시각 이후에 얻은 지식이 문서에 섞이면 모순이다. 자동 검사는 문서 개요의 내용까지 읽지 못하므로, 개요가 기대는 Fact마다 작성자의 Knowledge.from이 Trace.created_at보다 이른지 직접 확인한다. 우연히 맞힌 추측은 추측으로 표시한다.
