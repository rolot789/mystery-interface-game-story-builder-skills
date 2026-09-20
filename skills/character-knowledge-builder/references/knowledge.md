# 정보 비대칭 계약

Knowledge는 character_id, fact_id, state, from, until, acquired_via를 갖는다. state는 KNOWS / BELIEVES / SUSPECTS / UNKNOWN이다. BELIEVES는 대상 Fact에 대한 믿음을 belief_text로 설명한다. 잘못된 믿음은 참인 Fact 자체를 거짓으로 바꾸지 않는다.

Claim은 speaker_id, statement, stated_at, audience, intent와 관련 Fact를 가진다. intent는 truthful / lie / mistaken / uncertain 중 해당하는 설명을 기록한다. LIE는 지식 상태가 아니다. 고의적 거짓말은 당시의 믿음·지식과 주장 간 차이로 설명해야 한다.

acquired_via는 정보가 전달된 Event·Trace·Claim의 ID다. 초기부터 아는 사실은 initial_basis로 근거를 설명할 수 있다. 관계가 있다는 사실만으로 서로의 모든 비밀을 안다고 가정하지 않는다.

cannot_know는 특정 시간·경로·권한에서의 제한이다. 규칙과 예외를 함께 적는다. 기관의 비공개 정책은 별개의 사적 정보 경로까지 금지하지 않는다.

시점별 표를 만들 때 행은 Fact, 열은 인물이며 해당 시각을 명시한다. 현재 시점 표를 과거 보고서 작성 검증에 사용하지 않는다. 동일 인물·사실의 기간이 겹치고 상태가 다르면 의도적 복합 믿음인지 충돌인지 확인한다.

인물의 매력을 비밀의 수로 대체하지 않는다. 사건과 무관한 관계·생활·목표가 행동에 실질적인 무게를 갖도록 설계한다.
