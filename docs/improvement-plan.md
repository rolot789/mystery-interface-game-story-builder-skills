# 스킬 묶음 분석 및 개선 계획안

- 대상: `mystery-interface-game-story-builder-skills` v1.0.0 (커밋 `c2bcdca`)
- 초점: **Mystery World Builder**를 주변 세계관까지 세밀하되 모순 없이 설계하는 전문가 수준 스킬로 강화하고, 나머지 스킬·도구·패키지의 개선점을 함께 정리한다.
- 작성일: 2026-09-24

> **진행 상황**
>
> - Phase 0: 완료
> - Phase 1: 완료
> - Phase 2: 완료. 계획과 달라진 점이 있다.
>   - 이동 시간 경고를 SPACE-003으로 분리했다.
>   - knows 링크 경고를 LINK-001로 추가했다.
>   - Trace에 state_at_present와 retention_exception을 추가했다.
> - Phase 3: 완료. 인물·사건·감사·진행자 스킬이 v2 필드와 규칙 ID를 쓰도록 바꿨다.
>   - 인물 스킬에 프로필과 말투 참조 문서를 추가했다.
>   - validate_suite가 문서의 필드명을 데이터 계약과 양방향으로 대조한다.
> - Phase 4~5: 남음. 정확한 규칙 목록은 `skills/notion-canon-manager/references/data-contract.md`를 따른다.

---

## 0. 요약

- 현재 묶음은 **역할 분리, 상태 축 분리, Notion 동기화 안전장치**가 탄탄하다. 반면 세계관 영역은 참조 문서 21줄과 객체 종류 3개(WorldRule·Organization·Service)뿐이다. "세세하게"와 "꼬임 없이"를 동시에 받쳐 줄 **구조(고정점)와 검사**가 없다.
- 세부가 늘어날수록 모순이 생길 수 있는 지점도 늘어난다. 따라서 강화의 핵심은 더 많이 쓰는 것이 아니다. 다음 세 가지를 갖추는 것이다.
  1. 세부를 **고정점**(구조화 필드)에 묶는다.
  2. 서술은 고정점에서 **파생**한다.
  3. 고정점끼리 **자동 검사**한다.
- 제안하는 내용:
  - 8가지 꼬임 방지 원칙
  - 6층 설계 방법론: 헌장 → 기반 → 제도 → 정보 환경 → 생활 → 사건 접점
  - 설정 밀도 계층: CORE / SUPPORTING / MENTION
  - Canon schema v2: Location·HistoryEvent·Term 추가, 불확실 시각(TimeSpec) 표현
  - 규칙 ID가 붙은 자동 검사 20종
  - 세계 바이블 렌더링
- 분석 중 코드를 실행해 **결함 8건**을 재현했다. 영향 추적 방향 누락, 시간 순서·순환 미검사, 문서와 데이터 계약의 불일치 등이다. 이를 먼저 고치는 Phase 0부터 시작하는 6단계(Phase 0~5) 로드맵을 제안한다.

---

## 1. 현재 구조 분석

### 1.1 구성

| 스킬 | 소유 객체 | 참조 문서 | 분량(SKILL + 참조) |
|---|---|---|---|
| Mystery Production Orchestrator | 질문·라우팅·Session 흐름 | workshop.md, completion.md | 47 + 43줄 |
| Mystery Plot Builder | Event·Fact·Trace·Choice·Ending | plot-and-branches.md | 31 + 21줄 |
| **Mystery World Builder** | WorldRule·Organization·Service | world.md | **27 + 21줄** |
| Character Knowledge Builder | Character·Knowledge·Claim | knowledge.md | 26 + 13줄 |
| Mystery Continuity Auditor | QA Issue | audit.md | 27 + 21줄 |
| Notion Canon Manager | 기록·관계·동기화·기획서 조립 | data-contract, notion-template, sync, `canon.py`, `notion_plan.py` | 39줄 + 스크립트 390줄 |

작업 흐름은 다음과 같다.

1. Orchestrator가 쟁점 하나를 질문한다.
2. 답변에 따라 담당 도메인 스킬이 변경안을 만든다.
3. Auditor가 검토한다.
4. Canon Manager가 Notion에 동기화한다.

### 1.2 강점 (유지할 것)

- 내용·검토·저장 상태를 서로 다른 축으로 분리했다. CONFIRMED 객체는 사용자 결정 출처를 반드시 갖는다.
- 과거 진상은 고정하고 결말은 상태 변수로 표현한다. 선택의 effects가 Fact를 덮어쓸 수 없다.
- Fact / Claim / Knowledge를 분리했다. 거짓말은 지식 상태가 아니라 주장과 지식의 차이로 표현한다.
- Notion 동기화가 견고하다.
  - Change Set, 해시·리비전 비교, 부분 실패 복구, 사용자 메모 보존을 갖췄다.
  - Notion의 원자성을 가정하지 않는다.
- 워크숍 규칙이 정교하다. 한 번에 한 쟁점만 묻고, 선택지별 영향을 비교하며, explicit / entailed / proposed를 구분한다.
- "무한 확장 금지"와 "모든 배경을 단서로 만들지 말라" 같은 좋은 원칙이 이미 있다.

### 1.3 세계관 영역의 한계

1. **분량과 깊이.**
   - world.md는 조직에 대해 10가지 항목(목적, 재원, 평판, 부서·의사결정, 평가·보상, 실제 관행, 내부 갈등, 평범한 업무, 역사, 관계 기관)을 쓰라고 한다.
   - 하지만 데이터 필드는 5개(purpose, economy, operations, culture, daily_life)뿐이다.
   - 나머지는 자유 서술에 섞여 검사할 수 없다. SKILL.md가 요구하는 "공식 규정·금기"도 필드가 없다.
2. **시간 축 부재.**
   - WorldRule에 "유효 시점"을 적으라고 하지만 필드가 없다.
   - 조직 설립, 과거 스캔들, 제도 개정 같은 세계 역사를 담을 종류가 없다. Event는 Plot Builder 소유이고 사건용이다.
   - 시각은 시간대가 포함된 ISO 문자열만 허용한다. 그래서 "약 3년 전", "2019년 가을"을 표현할 수 없다.
   - 결국 가짜 정밀 시각을 만들거나(기존 원칙 위반) 역사를 기록하지 않게 된다.
3. **공간 축 부재.** Location이 없다. Auditor는 "행위자의 위치·접근이 양립하는가"를 검사하라고 하지만 위치 데이터 자체가 없다.
4. **소속 관계 부재.**
   - 인물의 조직 소속·직위·재직 기간이 `relationships` 자유 서술에 섞여 있다.
   - 그래서 "그 시점에 그 인물에게 그 권한이 있었나"를 검사할 수 없다.
5. **정보 환경의 해상도 부족.**
   - 휴대폰·문서·검색·메신저형 게임에서 가장 꼬이기 쉬운 것은 기록의 존재·보존·권한·메타데이터다. 여기에는 읽음 표시, 수정 이력, 삭제 흔적이 포함된다.
   - 그런데 이 모든 것이 `data_lifecycle`와 `permissions` 자유 서술 두 칸에 들어간다.
6. **용어·명칭 관리 부재.** 같은 기관이나 서비스가 대화가 길어지며 여러 이름으로 불리는 표류를 막을 장치가 없다.
7. **방법론 부재.** 다음과 같은 전문 절차가 없다.
   - 무엇을 어떤 순서로, 어느 깊이까지 정할지(층·밀도)
   - 2차 파급 기록
   - 허점 정당화
   - 편의 설정 탐지
   - 서술 속 암묵 설정 회수
8. **공개도 부재.**
   - 세계 사실을 주민 상식, 내부자 지식, 비밀로 구분하지 않는다.
   - 그래서 플레이어의 출발 지식과 공정성(fair play)을 판단할 근거가 약하다.

### 1.4 코드 실행으로 재현한 결함

재현 방법: `tests/test_contracts.py`의 `sample()` fixture를 변형해 `canon.validate` / `canon.impact`를 호출했다.

| # | 결함 | 재현 결과 | 영향 |
|---|---|---|---|
| B1 | `impact`가 근거 링크를 한 방향으로만 추적한다 | F1 변경 → `needs_review=['K1']`. F1을 supports하는 T1은 빠진다 | 진상을 수정해도 이를 뒷받침하던 기록이 재검토되지 않는다 |
| B2 | 원인 Event보다 이른 `Trace.created_at`을 허용한다 | 오류 0건 | 사건 이전에 생성된 기록 |
| B3 | 획득 경로(Trace)가 생기기 전의 `Knowledge.from`을 허용한다 | 오류 0건 | 알 수 없는 시점에 이미 알고 있는 인물 |
| B4 | `preconditions` 순환을 허용한다 | EV1 ↔ EV2 순환, 오류 0건 | 인과 순환 |
| B5 | 선행 사건이 후행 사건보다 늦은 시각을 허용한다 | 오류 0건 | 시간 역전 |
| B6 | 불확실한 시각을 표현할 수 없다 | `'2026-01-01'`, `'2019'` 모두 거부 | 가짜 정밀 시각 강요. plot-and-branches.md 원칙과 충돌 |
| B7 | 문서와 데이터 계약이 불일치한다 | 아래 목록 참고 | 스킬이 쓰라고 한 정보가 저장·검사되지 않는다 |
| B8 | `knows` 링크의 위치가 모호하다 | 코드(`LINKS`)와 blueprint Relation 선택지에는 있지만 계약 문서에 없다. Knowledge 객체와 표현이 중복된다 | 지식이 두 곳에 기록되어 불일치한다 |

B7의 불일치 항목. 모두 data-contract와 `canon.py`에 없다.

- knowledge.md의 `cannot_know`
- knowledge.md의 "Claim의 관련 Fact"
- world.md의 WorldRule 유효 시점
- world.md의 조직 10항목

경미한 문제:

- `agents/openai.yaml`의 `default_prompt`가 5개 스킬에서 동일하다("담당 영역을 설계하고 기록해줘"). Auditor와 Canon Manager에는 맞지 않는다.
- `validate_suite.py`의 TODO 검사는 SKILL.md만 대상으로 한다.
- 5개 스킬에 복사된 "공통 계약" 블록은 현재 모두 동일하지만 drift 검사가 없다.
- `canon.py`는 밀집된 한 줄 코드라서 규칙을 추가할 때 유지보수 부담이 크다.

---

## 2. 핵심 강화: Mystery World Builder v2

### 2.1 목표 정의

전문가 수준의 세계관은 다음 세 가지를 만족한다.

1. **어느 세부를 찔러도 답이 있다.** 정한 범위 안에서 "그 조직 예산은 어디서 나오나?", "그 메시지는 지워졌다면 어디에 흔적이 남나?"에 Canon으로 답할 수 있다.
2. **사건보다 먼저 있었던 것처럼 보인다.** 사건이 이용하는 허점과 규칙이 역사·경제·기술로 독립적으로 설명된다.
3. **세부가 늘어도 꼬이지 않는다.** 시간·공간·소속·보존·명칭이 구조화된 고정점에 묶여 자동으로 검사된다.

### 2.2 꼬임 방지 8원칙

이 원칙은 SKILL.md 상단에 둔다.

1. **단일 출처, 파생 서술.**
   - 날짜·기간·수치·명칭은 한 곳(구조화 필드)에만 적는다.
   - 요일, "n일 전", 경과 기간은 도구가 계산해 보여준다.
   - 서술문에 계산한 값을 직접 적지 않는다.
2. **모든 규칙에 한계·비용·집행자.**
   - 제도나 기술을 정할 때 다음을 함께 정한다.
     - 무엇을 못 하는가
     - 어기면 누가 어떻게 제재하는가
     - 유지 비용은 누가 내는가
   - 퍼즐을 만드는 것은 강력한 규칙보다 규칙의 한계다.
3. **2차 파급 기록.** HARD 규칙마다 "이것이 참이면 반드시 함께 존재할 것"(관행·산업·법·사용자 습관)을 `entails`로 남긴다.
   - 예: 메신저가 30일 뒤 자동 삭제된다면 스크린샷 습관, 백업 업체, 보존 의무 법 조항이 생긴다.
4. **허점 정당화.** 사건이 이용하는 모든 허점에 다음을 기록한다.
   - 존재 이유(비용·정치·무지·최근 변경)
   - 왜 아직 막히지 않았는가
   - 그 밖에 누가 아는가
5. **편의 설정 표시.**
   - 플롯에 필요해서 나중에 추가한 설정은 `origin=PLOT_NEED`로 표시한다.
   - 이런 설정에는 세계 내부의 독립 근거와 플레이어 사전 노출 경로를 요구한다.
6. **공개도 계층.**
   - 모든 세계 사실은 PUBLIC(주민 상식) / INSIDER(해당 조직·직군) / SECRET 중 하나다.
   - 이 구분이 플레이어 출발 지식과 공정성 판단의 기준이 된다.
7. **밀도 계층.**
   - 모든 설정을 같은 깊이로 쓰지 않는다.
   - CORE(사건 접점) / SUPPORTING(배경 운영) / MENTION(이름만 등장)마다 필수 항목이 다르다.
   - **주변 설정도 고정점(시간·장소·명칭·공개도)은 반드시 갖는다.** 계층에 따라 달라지는 것은 서술 분량뿐이다.
   - 그래서 주변 세계가 세밀해져도 무한 확장되거나 모순이 생기지 않는다.
8. **서술 속 암묵 설정 회수.**
   - 세부 묘사는 조용히 Canon을 만든다(예: "3층 건물", "직원 40명", "개업 10년").
   - 서술을 작성한 뒤에는 새로 생긴 이름·수치·날짜·관계를 목록으로 뽑는다.
   - 각 항목은 PROPOSED 고정점으로 등록하거나, 모호한 표현으로 되돌린다.

### 2.3 설계 방법론: 6층 진행

각 층은 결정할 쟁점, 산출 객체, 층 완료 조건을 갖는다. 순서는 권장 사항이며, Orchestrator가 사용자의 현재 관심에 따라 조정한다. 사건이 먼저 정해진 기획이면 역방향 모드(2.3.7)를 사용한다.

#### W0 세계 헌장 (Charter)

- 쟁점:
  - 장르와 톤
  - 현실 거리
  - 핵심 전제(what-if 한 문장)
  - 세계 범위(포함 / 제외)
  - 기본 시간대
  - 조사 현재 시점(`present_at`)
  - 표현 금기
- 현실 거리가 검증 의무를 결정한다.

  | 현실 거리 | 의미 | 검증 의무 |
  |---|---|---|
  | REAL | 현실 그대로 | 현실 법·기술 사실은 출처 URL과 확인일을 기록한다(기존 원칙 유지) |
  | REAL_PLUS | 현실 + 가상 기관·서비스 | 현실 부분은 REAL과 같다. 가상 부분에는 fictional을 표시한다 |
  | ALTERNATE | 대체 현실 | 분기점(divergence point)과 그 이후 달라진 것을 명시한다 |
  | INVENTED | 완전 가상 | 물리·기술·사회의 기본 규칙을 WorldRule로 모두 선언한다 |

- 산출: `snapshot.charter`
- 완료 조건: 현실 거리와 세계 범위가 CONFIRMED다.

#### W1 기반 (Foundation)

- 쟁점:
  - 역사 연표(현재에 흔적을 남긴 사건 위주)
  - 지리와 장소 계층, 장소 간 이동 시간
  - 기술 수준(존재하는 기술, 존재하지 않는 기술, 보급률)
  - 경제의 큰 흐름
- 산출: HistoryEvent, Location, WorldRule(TECHNICAL / ECONOMIC)
- 완료 조건: 범위 안의 CORE 장소와 역사가 시각·계층을 가진다.

#### W2 제도 (Institutions)

- 쟁점:
  - 법·규범
  - 조직의 구조, 의사결정, 재원, 인센티브, 평판, 내부 갈등, 역사
  - **공식 규정과 실제 관행의 차이**
  - 권력 지도: 누가 기록을 바꿀 수 있고, 누가 그것을 감시하는가
- 산출: WorldRule(LEGAL / ORGANIZATIONAL / SOCIAL_NORM), Organization
- 완료 조건: CORE 조직마다 돈의 흐름과 권한 구조가 설명된다.

#### W3 정보 환경 (Information Environment)

인터페이스형 미스터리 전용 층이다. 게임 UI에 나오는 매체마다 **기록 의미론**을 정한다.

| 매체 | 반드시 정할 것 |
|---|---|
| 메신저 | 타임스탬프 기준(기기·서버·시간대), 읽음·전달 표시, 수정·삭제 흔적, 보존 기간, 백업·기기 동기화, 알림 미리보기 |
| 메일 | 발신·수신 시각 차이, 전달·참조 기록, 첨부 보존, 삭제함 보존 기간, 관리자 열람 |
| 문서 | 버전 기록, 작성자·수정자 메타데이터, 공유 권한 변경 이력, 오프라인 편집 충돌 |
| 검색 | 색인 지연, 캐시·스냅샷, 자동완성·검색 기록, 삭제 요청 반영 속도 |
| 사진·파일 | 촬영 메타데이터(시각·위치), 클라우드 동기화, 편집 이력 |
| 계정 | 인증·복구 경로, 2단계 인증, 공유 기기, 로그인 기록, 관리자 접근과 감사 로그 |

- 산출: Service(구조화된 retention·access_policy·artifacts), Term
- 완료 조건: 게임에 등장하는 모든 Trace 유형이 어떤 Service의 artifacts에 선언되어 있다.

#### W4 생활 (Daily Life)

- 쟁점:
  - 계층·직군별 평범한 하루
  - 생활 리듬(영업시간, 교대, 휴일, 계절 행사)
  - 언어·호칭·은어
  - 공개 상식
- 산출: Location.rhythm, Organization.daily_life, Term, WorldRule(SOCIAL_NORM)
- 완료 조건: "평범한 하루 워크스루"(2.6-2)를 통과한다.

#### W5 사건 접점 (Incident Interface)

- 쟁점:
  - 사건이 가능해지는 조건과 불가능해지는 조건
  - 사건이 이용한 허점 목록과 그 정당화
  - 사건이 남길 수밖에 없는 기록
  - 인물에게 가해지는 압박
- 산출:
  - `exploits` / `generates` 링크
  - QA Issue
  - 타 영역 변경 요청: Plot Builder에는 기록, Character Builder에는 압박
- 완료 조건: 모든 `exploits` 링크가 정당화를 가진다.

#### 2.3.7 역방향(backfill) 모드

사건이 먼저 정해진 경우에 사용한다.

1. 사건이 요구하는 세계 조건을 목록으로 만든다.
2. 각 조건을 W1~W4 층의 독립 원인에 뿌리내린다.
3. 해당 객체에 `origin=PLOT_NEED`를 표시한다.
4. 뿌리내리지 못한 조건은 MAJOR QA Issue로 남긴다.

### 2.4 데이터 모델 확장 (Canon schema v2)

설계 원칙:

- 필수 필드는 최소로 둔다.
- 구조화 필드는 선택이지만, 값이 있으면 반드시 검사한다.
- 기존 v1 snapshot은 `canon.py migrate`로 무손실 변환한다.

#### (1) snapshot 최상위

```json
{
  "schema_version": 2,
  "charter": {
    "genre_tone": "…",
    "reality_distance": "REAL_PLUS",
    "premise": "…",
    "scope_in": ["LOC-harbor-district", "ORG-archive-bureau"],
    "scope_out": "…",
    "timezone": "Asia/Seoul",
    "present_at": "2026-03-14T21:00:00+09:00"
  }
}
```

#### (2) 시간 표현 TimeSpec (B6 해결)

기존 ISO 문자열은 그대로 허용하고, 불확실한 구간 표현을 추가한다.

```json
"at": "2026-03-01T09:10:00+09:00"
"at": {"earliest": "2019-09-01T00:00:00+09:00", "latest": "2019-11-30T23:59:59+09:00", "label": "2019년 가을"}
"at": null
```

- 첫째 줄은 정확한 시각이다.
- 둘째 줄은 불확실한 구간이다. `label`은 읽기용 표기다.
- 셋째 줄은 미정이다. 순서는 preconditions로만 표현한다.

비교는 보수적으로 한다.

- `A.earliest > B.latest`처럼 역전이 **확실할 때만** 오류로 판정한다.
- 구간이 겹치면 통과시킨다.
- 이렇게 하면 "가짜 정밀 시각을 만들지 않는다"는 기존 원칙과 양립한다.

#### (3) 새 종류 (소유: mystery-world-builder)

| kind | 필수 텍스트 | 구조화 필드 | 용도 |
|---|---|---|---|
| Location | description, access, rhythm | parent_id, place_type, connections `[{to, minutes, mode}]` | 장소 계층, 출입 조건, 이동 시간, 생활 리듬 |
| HistoryEvent | summary, consequences, public_account | at(TimeSpec), preconditions, legacy_ids | 세계 역사. 실제(summary)와 통념(public_account)의 차이 |
| Term | definition, register | aliases, forbidden_aliases, refers_to | 용어집, 명칭 표류 방지 |

경계 규칙:

- **Event와 HistoryEvent.**
  - 사건의 인과 사슬에 직접 들어가는 과거 행동은 Event다(Plot Builder 소유).
  - 배경 역사는 HistoryEvent다(World Builder 소유).
  - Event.preconditions는 HistoryEvent를 참조할 수 있다.
- **HistoryEvent의 두 서술.**
  - `summary`는 실제로 일어난 일이다.
  - `public_account`는 통념이다.
  - 두 서술의 차이가 플롯에 중요해지면 Fact + Claim으로 승격한다.
- **물리 공간과 온라인 공간.** Location은 물리 공간이다. 온라인 커뮤니티나 앱 안의 공간은 Service로 표현한다.

#### (4) 기존 종류 확장

공통 메타데이터는 엔티티 최상위에 두며, status·review와 같은 층이다.

| 필드 | 값 | 적용 |
|---|---|---|
| `depth` | CORE / SUPPORTING / MENTION | 세계 소유 종류는 필수, 나머지는 선택 |
| `visibility` | PUBLIC / INSIDER / SECRET | 세계 소유 종류는 필수, Fact는 선택 |
| `origin` | FOUNDATION / PLOT_NEED (+ `in_world_reason`) | 세계 소유 종류는 필수 |

종류별 확장 필드는 모두 선택이다.

| kind | 추가 필드 |
|---|---|
| WorldRule | `rule_type`(PHYSICAL / TECHNICAL / LEGAL / ORGANIZATIONAL / SOCIAL_NORM / ECONOMIC / BELIEF), `strength`(HARD / SOFT), `valid_from` / `valid_until`(TimeSpec), `enforced_by`[Org], `violation_cost` |
| Organization | `founded_at`, `parent_id`, `hq_location_id`, `structure`, `incentives`, `reputation`, `conflicts`, `formal_vs_actual` |
| Service | `launched_at`, `changes[{at, summary}]`, `retention[{data, keep_days, after: HARD_DELETE/SOFT_DELETE/ARCHIVE, exceptions}]`, `access_policy[{role, data, ops[], condition}]`, `artifacts[{type, timestamp_source, edit_trace, delete_trace, read_receipt}]` |
| Character (Character Builder) | `affiliations[{org_id, role, from, until}]`, `home_location_id`, `routine`, `voice` |
| Event (Plot Builder) | `location_id`, `duration_minutes` |
| Trace (Plot Builder) | `service_id`, `artifact_type` |
| Claim (Character Builder) | `fact_ids` (B7 해소) |
| Knowledge (Character Builder) | `cannot_know` (B7 해소) |

#### (5) 링크 종류

- 추가: `entails`. WorldRule에서 WorldRule·Organization·Service·Term으로 향한다. 2차 파급을 기록한다.
- 추가: `exploits`. Event에서 WorldRule·Service로 향한다. 사건이 이용한 허점이며, reason에 정당화를 반드시 적는다.
- 정리: `knows` 링크를 폐지하고 Knowledge 객체로 일원화한다(B8). migrate는 기존 `knows` 링크를 Knowledge 초안과 QA Issue로 변환한다.

### 2.5 자동 검사 목록 (규칙 ID)

출력 형식:

- 기존 `errors` / `warnings` 문자열 배열은 호환을 위해 유지한다.
- `findings: [{rule, level, ids, message}]`를 추가한다.
- Auditor는 QA Issue의 `violated_rule`에 규칙 ID를 그대로 사용한다.

수준 표기: E = 오류, W = 경고.

| ID | 수준 | 검사 내용 | 해결 결함 |
|---|---|---|---|
| TIME-001 | E | 과거 Event와 HistoryEvent는 `charter.present_at` 이전이다 | |
| TIME-002 | E | 선행 조건(Event·HistoryEvent)의 시각은 후행 Event 시각보다 늦지 않다 | B5 |
| TIME-003 | E | `Trace.created_at`은 원인 Event의 가장 이른 시각보다 이르지 않다 | B2 |
| TIME-004 | E | `Knowledge.from`은 획득 경로(Event·Trace·Claim)의 시각보다 이르지 않다 | B3 |
| TIME-005 | E | `Service.launched_at`은 그 서비스의 Trace 생성 시각보다 이르다. `Organization.founded_at`은 그 조직이 행위자인 Event보다 이르다 | |
| TIME-006 | E | Event가 선행 조건으로 쓴 WorldRule의 유효 구간이 그 Event 시각을 포함한다 | |
| TIME-007 | W | Character가 조직 서비스를 이용해 행동할 때 소속 기간이 그 시각을 포함한다 | |
| GRAPH-001 | E | preconditions·depends_on·parent_id에 순환이 없다 | B4 |
| SPACE-001 | E | Location 계층의 참조가 유효하고 순환이 없다 | |
| SPACE-002 | E/W | 같은 행위자가 같은 시간에 두 장소에 있으면 오류, 이동 시간이 부족하면 경고 | |
| DATA-001 | E | 예외 사유 없이 보존 기간이 지난 Trace가 `present_at`에 존재하면 안 된다 | |
| DATA-002 | W | `Trace.artifact_type`이 해당 Service.artifacts에 선언되어 있다 | |
| TERM-001 | W | `forbidden_aliases`가 활성 객체의 텍스트에 등장하지 않는다 | |
| TERM-002 | W | 같은 kind 안에서 제목이 중복되지 않고, Term 간 별칭이 충돌하지 않는다 | |
| WORLD-001 | E (complete) | `charter.scope_in`의 객체가 존재하고 활성 상태다 | |
| WORLD-002 | E (complete) | depth=CORE 객체가 종류별 구조화 필드를 충족한다 | |
| WORLD-003 | E | `origin=PLOT_NEED`이면 `in_world_reason`이 있다 | |
| WORLD-004 | W | exploits 대상 규칙이 SOFT이거나 예외 서술을 가진다 | |
| FAIR-001 | W | 해답에 쓰인 SECRET·INSIDER 규칙에 플레이어가 볼 수 있는 Trace가 연결되어 있다 | |
| CLAIM-001 | W | intent=lie인 Claim의 `stated_at` 시점에 화자가 `fact_ids`에 대한 KNOWS/BELIEVES 지식을 갖고 있다 | |
| (impact) | — | 근거 링크를 양방향으로 전파한다. Fact가 바뀌면 이를 supports/contradicts하는 Trace도 재검토 대상이 된다 | B1 |

기존의 "구조 검증은 공정성·개연성을 증명하지 않는다" 원칙은 유지한다. 경고는 검토 목록을 만드는 용도다.

### 2.6 의미 검토 (자동화 불가)

새 문서 `references/world-review.md`에 둔다. World Builder가 자가 점검에 쓰고 Auditor가 검토에 쓴다.

1. **사건 제거 테스트** (기존 유지): 사건을 빼도 일상 운영과 사용자 가치가 설명되는가?
2. **평범한 하루 워크스루**: 일반 사용자, 현장 직원, 관리자 세 사람의 하루를 따라간다. 모든 접점에 해당하는 Canon 객체가 있는가?
3. **돈의 흐름**: 누가 누구에게 돈을 내는가? 그 인센티브가 실제 관행을 설명하는가?
4. **2차 파급**: HARD 규칙마다 `entails`가 2개 이상 있거나, 없는 이유가 기록되어 있는가?
5. **허점 감사**: `exploits`마다 존재 이유, 방치 이유, 아는 사람이 기록되어 있는가?
6. **외부 시선**: 언론, 규제기관, 경쟁자, 사용자 커뮤니티가 이 조직·서비스를 어떻게 보는가?
7. **규모 감각(Fermi 점검)**: 인원, 사용자 수, 예산, 거리, 소요 시간의 자릿수가 서로 맞는가?
8. **공식과 실제**: 공식 규정과 실제 관행의 차이는 누구에게 이득인가?
9. **편의 설정 감사**: PLOT_NEED 객체에 독립 근거와 사전 노출 경로가 있는가?
10. **명칭과 어조**: 용어집을 지켰는가? 인물 register가 일관되는가?

### 2.7 파일 구성 변경

```
skills/mystery-world-builder/
  SKILL.md                         # 8원칙, 6층 라우팅 표, 소유·경계, 출력 형식 (약 80줄)
  references/
    charter.md                     # W0 헌장, 현실 거리별 검증 의무
    foundation.md                  # W1 연표·장소·기술·경제, TimeSpec 사용법
    institutions.md                # W2 규칙 유형, 조직 프로필, 권력 지도
    information-environment.md     # W3 매체별 기록 의미론 체크리스트
    daily-life-and-language.md     # W4 생활 리듬, 공개 상식, 용어집
    incident-interface.md          # W5 허점 정당화, backfill 모드
    depth-tiers.md                 # CORE / SUPPORTING / MENTION별 필수 항목
    world-review.md                # 10가지 의미 검토
```

SKILL.md는 지금 작업 중인 층에 해당하는 참조 문서만 읽도록 라우팅한다. 참조 문서는 필요한 작업에서만 읽는다는 기존 원칙을 유지한다.

### 2.8 SKILL.md 개정 뼈대

```markdown
---
name: mystery-world-builder
description: "미스터리 게임의 독립 세계를 헌장·연표·장소·기술·법과 제도·가상 조직·앱과
  서비스의 기록 보존 규칙·용어집·일상생활까지 층별로 설계·수정·검토할 때 사용한다.
  세계 설정 간 연표·장소·소속·보존 기간·명칭 모순 점검과 사건이 이용하는 허점의 정당화를 포함한다."
---

# Mystery World Builder

## 꼬임 방지 원칙 (8)
## 작업 층 라우팅 (W0~W5 → 읽을 참조 문서)
## 밀도 계층 (CORE / SUPPORTING / MENTION)
## 세부 서술 프로토콜 (작성 전 고정점 확인 → 작성 → 암묵 설정 회수)
## 소유와 경계 (HistoryEvent와 Event, Location과 Service, Character 소속)
## 출력 형식
  1. 변경안: 객체 ID, 층, depth, visibility, origin
  2. 고정점 변경: 시간·장소·소속·보존·명칭을 따로 표시
  3. 2차 파급: explicit / entailed / proposed
  4. 영향: canon.py impact 결과와 의미적 영향
  5. 검사 결과: 규칙 ID별
  6. 미정 항목과 다음 질문 후보
## 공통 계약 (기존 블록 유지)
```

---

## 3. 다른 스킬 개선점

### 3.1 Mystery Continuity Auditor

- **규칙 카탈로그.**
  - audit.md의 11개 검사를 규칙 ID 체계(TIME / SPACE / DATA / TERM / WORLD / FAIR / CLAIM …)로 재정리한다.
  - 각 규칙을 자동 검사와 의미 검토로 구분해 표시한다.
- **세계 이슈 심각도 기준 예시.**

  | 상황 | 심각도 |
  |---|---|
  | 보존 기간 모순으로 핵심 Trace가 존재할 수 없다 | BLOCKER |
  | CORE 조직의 재원을 알 수 없다 | MAJOR |
  | 용어 별칭이 표류한다 | MINOR |

- **변경 검토 모드.** HARD 규칙, 보존 기간, 권한, 소속이 바뀌면 impact와 관련 규칙 재검사를 반드시 실행한다.
- **보고 형식 고정.** 범위 → 사용 리비전 → 규칙 ID별 자동 결과 → 의미 검토 → 이슈 표 → 판정 순서로 쓴다.

### 3.2 Character Knowledge Builder

- **소속·일과·거주 장소.** `affiliations`·`routine`·`home_location_id`로 "그때 거기 있었나", "그 권한이 있었나"를 검사할 수 있게 한다.
- **voice 프로필.**
  - 메신저·메일 중심 게임에서 말투는 단서이자 일관성 지점이다.
  - 다음 항목을 기록한다.
    - 관계별 존댓말·반말
    - 호칭
    - 이모지·오타·줄바꿈 습관
    - 활동 시간대
  - 대필·사칭 트릭을 설계하는 근거가 된다.
- **계약 반영.** `cannot_know`와 `Claim.fact_ids`를 데이터 계약에 반영하고(B7) CLAIM-001 경고를 활용한다.
- **인물별 시간선 렌더.** `canon.py timeline --character`로 위치, 행동, 알게 된 것을 시간순으로 보여준다. 특정 인물 시점의 문서 개요를 작성할 때 참조한다.

### 3.3 Mystery Plot Builder

- **조사 시작 경계의 데이터화.** "조사 시작 시점과 과거 사건의 경계"를 `charter.present_at`과 `Event.location_id`로 표현한다.
- **허점 연결.** `exploits` 링크로 사건이 이용한 세계 허점을 명시하고, World Builder의 정당화 의무와 연결한다.
- **공정성 절 추가.**
  - 해답에 필요한 규칙과 사실은 공개 전에 플레이어가 볼 수 있는 Trace로 노출되어야 한다(FAIR-001).
  - 레드 헤링 Trace도 routine / system 기원의 세계 내 원인을 가져야 한다.
- **범위 유지.** README가 후속 범위로 둔 전체 해금 그래프는 이번에도 제외한다. 이번에는 Trace와 노출의 연결만 다룬다.

### 3.4 Mystery Production Orchestrator

- **세계 질문 사다리.** 기존 우선순위 (1)~(5)에 세계 영역의 세부 순서를 추가한다.
  1. 현실 거리·톤
  2. 핵심 전제
  3. 권력·기록 통제 구조
  4. 정보 환경(매체와 기록 규칙)
  5. 주요 조직의 돈과 인센티브
  6. 생활권·장소
  7. 흔적을 남긴 역사
  8. 명칭
- **모드 판단.**
  - 첫 아이디어가 세계 중심인지 사건 중심인지로 세계 우선 모드 또는 사건 우선(backfill) 모드를 고른다.
  - 사용자에게 모드 선택을 강요하지 않는다.
- **정합성 체크포인트.**
  - 고정점(시간·장소·소속·보존·HARD 규칙)을 바꾸는 결정 직후, 다음 질문 전에 impact와 관련 규칙 검사를 실행한다.
  - 새 모순이 생기면 그것을 다음 쟁점으로 우선한다.
- **completion.md 세계 완료 조건 추가.**
  - 헌장이 확정되었다.
  - `scope_in`의 CORE 객체가 구조화 필드를 충족한다.
  - W3 매체별 기록 의미론이 정해졌다.
  - PLOT_NEED 객체가 정당화되었다.
  - TERM 경고가 처리되었다.

### 3.5 Notion Canon Manager

- **blueprint 1.1.0 (추가형 변경만).**
  - Kind 선택지에 Location, HistoryEvent, Term을 추가한다.
  - 속성을 추가한다: Depth·Visibility·Origin(SELECT), Valid From / Valid Until(DATE).
  - Relation 선택지에 `entails`와 `exploits`를 추가한다.
  - `knows` 선택지는 남겨 두되 신규 사용을 금지한다. 선택지 삭제는 손실 가능 변경이므로 자동 적용하지 않는다는 기존 원칙을 따른다.
- **세계관 페이지 뷰.**
  - 연표: Event Time 기준 timeline 뷰. 커넥터가 지원하지 않으면 시각 정렬 table로 대체한다.
  - 장소, 용어집, 정보 환경(Service) 뷰를 추가한다.
- **migrate 요청 생성.** `notion_plan.py migrate --from 1.0.0 --to 1.1.0`을 추가한다. fetch한 현재 schema를 입력받아, 없는 속성과 선택지만 추가하는 요청을 생성한다.
- **page-templates 세계관 본문 재구성.** 다음 절로 나눈다.
  - 세계 헌장
  - 연표
  - 장소와 생활 리듬
  - 제도와 조직
  - 정보 환경과 기록 규칙
  - 용어집
  - 공개 상식과 비밀의 경계
  - 세계의 경계
- **`canon.py bible`.**
  - 세계 바이블 Markdown을 렌더링한다. 세계관 페이지와 기획서 "독립 세계관" 절의 원천이 된다.
  - 포함 내용:
    - 연표: 요일과 present_at 기준 D-n을 자동으로 표시한다(원칙 1).
    - 장소 트리
    - 조직도
    - 서비스 × 데이터 보존·권한 매트릭스
    - 용어집
- **design-document.md.** "독립 세계관" 절을 위 구성에 맞춰 하위 절로 나눈다.

### 3.6 패키지와 품질

- **공통 계약 drift 검사.**
  - `validate_suite.py`가 5개 스킬의 "## 공통 계약" 블록 해시가 같은지 확인한다.
  - 스킬별 단독 설치 가능성은 그대로 유지한다.
- **스킬별 `default_prompt`.**

  | 스킬 | default_prompt 예시 |
  |---|---|
  | Auditor | "…모순과 변경 영향을 검토하고 QA 이슈로 정리해줘" |
  | Canon Manager | "…Notion 기록을 조회·동기화해줘" |
  | World Builder | "…세계관을 층별로 설계하고 정합성을 점검해줘" |

- **`validate_suite.py` 강화.**
  - references·assets 문서도 TODO를 검사한다.
  - SKILL.md에서 링크되지 않은 고아 참조 문서를 탐지한다.
  - description 길이 상한을 검사한다.
  - 참조 문서가 언급한 필드명이 data-contract 표에 있는지 대조한다(B7 재발 방지).
- **`canon.py` 구조 정리.**
  - 규칙 ID → 함수 등록 방식으로 재구성하고, 읽을 수 있는 포맷으로 정리한다.
  - 이식성을 위해 `notion-canon-manager/scripts` 안에 유지한다.
- **테스트.**
  - fixture를 `tests/fixtures/*.json`으로 분리한다.
  - 규칙마다 통과 사례와 실패 사례를 한 쌍씩 둔다.
  - v1 → v2 migrate 왕복을 검증한다.
  - bible 렌더링 결과를 스냅샷으로 검증한다.
- **행동 평가(evals).** 스킬 지시 준수를 확인하는 시나리오 묶음을 만든다.

  | 시나리오 | 기대 행동 |
  |---|---|
  | 메신저 보존 기간을 30일에서 7일로 변경 | 영향받는 Trace를 나열하고 DATA-001을 보고한다. 사용자 확인 없이 CONFIRMED로 만들지 않는다 |
  | "사건에 필요하니 관리자 백도어를 추가해줘" | PLOT_NEED로 표시하고, 세계 내 근거를 질문한다 |
  | 현실 법 조항을 설정에 인용 | 출처와 확인일을 기록하도록 요구한다 |

- **버전.**
  - suite 1.1.0으로 올린다. schema v2 전환에는 migrate를 제공한다.
  - notion_template 1.1.0으로 올린다.
  - `CHANGELOG.md`를 추가한다.

---

## 4. 로드맵

| Phase | 내용 | 주요 변경 파일 | 위험 |
|---|---|---|---|
| 0. 즉시 수정 | B1~B5 수정, B8 정리, openai.yaml 개선, 공통 계약 drift 검사 | canon.py, tests, validate_suite.py | 낮음 (스키마 불변) |
| 1. 방법론 문서 | World Builder SKILL.md와 참조 문서 8종(원칙·층·밀도·검토) | skills/mystery-world-builder/** | 낮음. **사용자 리뷰 지점** |
| 2. 스키마 v2 | TimeSpec, 새 kind 3종, 확장 필드, migrate, 규칙 ID findings, bible·timeline 렌더 | canon.py, data-contract.md, tests | 중간 |
| 3. 스킬 연동 | Character·Plot·Auditor·Orchestrator 문서, completion 기준 | 각 SKILL.md와 참조 문서 | 낮음 |
| 4. Notion 1.1.0 | blueprint, page templates, migrate 요청, design-document | notion_plan.py, assets/** | 중간 (실제 Notion 검증 필요) |
| 5. 평가·문서 | evals, README, CHANGELOG | evals/**, README.md | 낮음 |

권장 순서는 0 → 1 → 2 → 3 → 4 → 5다.

- 방법론(Phase 1)을 스키마(Phase 2)보다 먼저 합의해야 필드가 과잉되거나 부족하지 않게 정해진다.
- Phase 1 문서는 v2 필드명을 미리 사용한다. 다만 "Phase 2 적용 전에는 서술로 기록한다"고 명시한다.

## 5. 결정이 필요한 사항

1. **새 kind 추가**(권장) 또는 기존 kind 확장만 할지
2. **World Builder 단일 스킬 + 참조 문서 분할**(권장) 또는 정보 환경(W3)을 별도 스킬로 분리할지
3. **FAIR-001 수준**: 경고(권장) 또는 `--complete`에서 오류로 처리할지
4. **새 객체의 기본 depth**: SUPPORTING(권장) 또는 CORE
5. **대상 런타임**: 현재 openai.yaml(Codex·ChatGPT) 외에 Claude Code 플러그인 형태도 지원할지

## 6. 위험과 대응

| 위험 | 대응 |
|---|---|
| 필드가 많아져 "해당 없음" 채우기가 늘어난다 | 필수 필드는 최소로 둔다. 구조화 필드는 depth=CORE에서만 필수다 |
| 모델이 구조화 필드를 부정확하게 채운다 | 자동 검사로 잡는다. 불확실 TimeSpec을 허용해 가짜 정밀성을 만들 유인을 없앤다 |
| Notion 스키마 변경이 실패하거나 손실을 낸다 | 추가형 변경만 한다. 먼저 fetch한 뒤 계획을 만든다. 파괴적 변경은 자동 적용하지 않는다 |
| 기존 v1 프로젝트가 깨진다 | migrate로 무손실 변환한다. `knows` 링크는 Knowledge 초안과 QA Issue로 옮긴다 |
| 문서가 늘어 컨텍스트 부담이 커진다 | SKILL.md는 라우팅만 한다. 참조 문서는 층별로 필요할 때만 읽는다 |
| 시간대 계산 환경 차이 (zoneinfo·tzdata 부재) | ISO 문자열의 오프셋을 기준으로 계산하고, 시간대 이름은 표시용으로만 쓴다 |
