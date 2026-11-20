"""LANE 설정 파일. 게임에 영향을 주는 숫자는 전부 여기서 바꾼다.

읽는 법
- "프레임"은 게임 한 칸이다. FPS가 45라서 45프레임 = 1초, 20프레임 ≈ 0.44초.
- "px"는 화면 픽셀이다. 화면은 900 x 600.
- 값을 바꾼 뒤 게임을 다시 실행하면 적용된다.
"""
import os
import sys

# ============================================================
# 경로 (보통 건드릴 필요 없음)
# ============================================================

HERE = os.path.dirname(os.path.abspath(__file__))

# PyInstaller로 exe를 만들면 실행 중 코드는 임시 폴더에 풀리기 때문에,
# 분석 결과(cache)는 exe가 있는 폴더에 저장해야 사라지지 않는다.
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else HERE
CACHE_DIR = os.path.join(APP_DIR, "cache")


def resource_path(relative_path):
    """아이콘 같은 포함 파일의 위치. .py 실행과 PyInstaller --onefile 모두 지원."""
    base = getattr(sys, "_MEIPASS", HERE)
    return os.path.join(base, relative_path)


# ============================================================
# 창 / 문구
# ============================================================

WIDTH, HEIGHT = 900, 600   # 창 크기(px)
FPS = 45                   # 초당 프레임 수. 이 값을 바꾸면 "프레임" 단위로 적힌 모든 값의
                           # 실제 시간이 달라져 게임 속도가 변한다(올리면 전부 빨라짐).
                           # 속도를 유지하려면 프레임 단위 값도 같은 비율로 같이 바꿔야 한다.

WINDOW_TITLE = "lane"                 # 창 제목줄에 표시되는 이름
TITLE_TEXT = "LANE"                   # 시작 화면 가운데 큰 제목
ICON_FILE = "lane.ico"                # 창/작업표시줄 아이콘 (main.py와 같은 폴더)
APP_ID = "NeonGauntlet.Game"          # Windows 작업표시줄 앱 식별자

# ============================================================
# 색 (#RRGGBB)
# ============================================================

BG = "#07070b"            # 배경
CYAN = "#00f5d4"          # 플레이어, 강조
DANGER = "#ff2a5f"        # 위험 표시(게임오버, 대시 충전 중)
TEXT = "#e8e8f0"          # 일반 글자
MUTED = "#4a4a5e"         # 흐린 글자
FONT = "Consolas"         # 글꼴

LASER = "#ff5575"         # 일반 레이저 색
LASER_MINT = "#00d9bd"    # 레이저 경고 중 깜빡이는 보조색

# ============================================================
# 전투 상자 (플레이어가 움직일 수 있는 영역)
# ============================================================

BOX_WIDTH = 620           # 상자 가로(px). 크면 피할 공간이 넓어져 쉬워짐
BOX_HEIGHT = 360          # 상자 세로(px)
BOX_LEFT = (WIDTH - BOX_WIDTH) // 2     # 아래 4개는 위 두 값으로 자동 계산
BOX_RIGHT = BOX_LEFT + BOX_WIDTH
BOX_TOP = (HEIGHT - BOX_HEIGHT) // 2
BOX_BOTTOM = BOX_TOP + BOX_HEIGHT
BOX_BORDER_COLOR = "#ffffff"            # 상자 테두리 색

# ============================================================
# 플레이어
# ============================================================

PLAYER_VISUAL_R = 10      # 화면에 그려지는 반지름(px). 벽 충돌 기준이기도 함
PLAYER_HIT_R = 8          # 레이저에 맞는 반지름(px). 작을수록 피하기 쉬움

PLAYER_ACCELERATION = 0.75   # 방향키를 누를 때 프레임마다 붙는 가속(px/프레임).
                             # 클수록 출발이 빠름
PLAYER_FRICTION = 0.25       # 키를 놓았을 때 프레임마다 속도에 곱해지는 비율.
                             # 작을수록 빨리 멈춤(0.25 = 거의 바로 멈춤),
                             # 클수록 미끄러짐(0.75 = 오래 미끄러짐), 1.0이면 안 멈춤
PLAYER_MAX_SPEED = 3.9       # 최고 속도(px/프레임) = 초당 약 175px. 공정성 검사 기준이기도 함

# ---------------- 대시 ----------------
DASH_SPEED = 16              # 대시 시작 속도(px/프레임)
DASH_DECAY = 0.8             # 프레임마다 속도에 곱해지는 비율. 작을수록 대시 거리가 짧음
DASH_COOLDOWN = 45           # 대시 재사용 대기(프레임). 45 = 1초
DASH_GRACE_AFTER_START = 9   # 대시 시작 후 무적 시간(프레임)
DASH_GRACE_AFTER_END = 5     # 대시가 끝난 뒤 추가 무적 시간(프레임)
DASH_BUFFER = 8              # 대기가 끝나기 이 프레임 전에 눌러도 끝나자마자 대시가 나감
DASH_GHOST_LIFE = 10         # 대시 청록 잔상이 남는 시간(프레임, 보이는 효과만)
DASH_TRAIL_LIFE = 18         # 대시 붉은 궤적이 남는 시간(프레임, 보이는 효과만)

# ============================================================
# 난이도 상승 (시간이 지날수록 레이저가 자주 나오는 정도)
# ============================================================
# 점수는 1프레임마다 1 오른다. "점수 ÷ STEP_FRAMES"의 몫이 단계가 되고,
# 단계가 1 오를 때마다 아래 각 REDUCTION만큼 생성 간격이 줄어든다(MIN_INTERVAL까지).

INTERVAL_STEP_FRAMES = 200       # 생성 간격이 한 단계 줄어드는 데 걸리는 프레임.
                               # 지금 1이라서 시작하자마자 최대 난이도다(테스트용 값으로 보임).
                               # 천천히 어려워지게 하려면 500(약 11초마다 한 단계) 등으로.
RAM_WARNING_STEP_FRAMES = 500  # 발사형 경고 시간이 한 단계 줄어드는 데 걸리는 프레임

# ============================================================
# 일반 레이저 (가로/세로 줄)
# ============================================================

MAX_LASERS = 24            # 화면에 동시에 있을 수 있는 최대 개수. 넘으면 오래된 것부터 사라짐
STARTUP_DELAY = 32         # 시작 키를 누른 뒤 첫 레이저가 나오기까지(프레임)

LASER_WARNING_TIME = 20    # 경고선이 떠 있다가 실제 레이저가 되기까지(프레임). 20 ≈ 0.44초.
                           # 크면 쉬워짐(피할 시간이 길어짐)
LASER_HIT_GRACE = 5        # 레이저가 켜진 직후 맞아도 안 죽는 시간(프레임)
TRIPLE_WALL_MARGIN = 55    # 3연/위치 지정 레이저가 상자 벽에서 최소한 떨어지는 거리(px)
LASER_OFFSET_MIN = 15      # 랜덤 레이저 위치의 편차 최소(px)
LASER_OFFSET_MAX = 75      # 랜덤 레이저 위치의 편차 최대(px)

# ---------------- 단일 레이저: 플레이어 위치를 노리고 한 줄씩 ----------------
SINGLE_START_INTERVAL = 114   # 다음 단일 레이저까지의 시작 간격(프레임)
SINGLE_MIN_INTERVAL = 42      # 간격이 줄어드는 하한(프레임). 작을수록 어려움
SINGLE_REDUCTION = 6          # 단계마다 줄어드는 양(프레임)
SINGLE_LIFETIME = 50          # 레이저가 화면에 남는 총 시간(경고 포함, 프레임)
SINGLE_WARNING_WIDTH = 2      # 경고선 굵기(px, 보이는 것만)
SINGLE_ACTIVE_WIDTH = 5       # 켜진 레이저 굵기(px, 보이는 것만)
SINGLE_GLOW_WIDTH = 7         # 번짐 굵기(px, 보이는 것만)

# ---------------- 3연 레이저: 가로/세로 3줄이 한 번에 ----------------
TRIPLE_START_INTERVAL = 220   # 시작 간격(프레임)
TRIPLE_MIN_INTERVAL = 85      # 하한(프레임)
TRIPLE_REDUCTION = 10         # 단계마다 줄어드는 양(프레임)
TRIPLE_LIFETIME = 34          # 한 줄이 남는 시간(프레임)
TRIPLE_REMOVE_DELAY = 14      # 다음 3연이 나온 뒤 이전 3연이 사라지기까지(프레임)
TRIPLE_WARNING_WIDTH = 1      # 보이는 것만
TRIPLE_ACTIVE_WIDTH = 2
TRIPLE_GLOW_WIDTH = 5

# ============================================================
# 발사형 레이저 (경고 경로를 따라 날아오는 굵은 빔)
# ============================================================

RAM_START_INTERVAL = 350      # 시작 간격(프레임)
RAM_MIN_INTERVAL = 160        # 하한(프레임)
RAM_REDUCTION = 12            # 단계마다 줄어드는 양(프레임)

RAM_WARNING_TIME = 50         # 경로 표시 시간(프레임). 50 ≈ 1.1초. 나중에 바꿀 값
RAM_WARNING_MIN_TIME = 30     # 경로 표시 시간의 하한(프레임)
RAM_WARNING_REDUCTION = 3     # 단계마다 줄어드는 양(프레임)

RAM_THICKNESS = 28            # 빔 굵기(px). 굵을수록 피하기 어려움
RAM_LENGTH = 190              # 빔 길이(px)
RAM_SPEED = 34                # 날아가는 속도(px/프레임) = 초당 약 1530px
RAM_HIT_GRACE = 5             # 발사 직후 맞아도 안 죽는 시간(프레임)
RAM_SPAWN_DISTANCE = 350      # 화면 밖 몇 px에서 출발하는지
RAM_SPAWN_MARGIN = 40         # 출발 위치를 화면 모서리에서 최소 이만큼 띄움(px)

RAM_WARNING_COLOR = "#d99aa8" # 경고 경로 색
RAM_BEAM_COLOR = "#ff4568"    # 빔 색
RAM_GLOW_WIDTH = 8            # 번짐(px, 보이는 것만)
RAM_GLOW_EXTENSION = 8
RAM_TRAIL_LIFETIME = 9        # 빔 잔상이 남는 시간(프레임, 보이는 것만)
RAM_TRAIL_ALPHA = 65          # 잔상 진하기 0~255(보이는 것만)

# ============================================================
# 사망 연출 (게임 규칙에는 영향 없음)
# ============================================================

HITSTOP_FRAMES = 4            # 맞는 순간 화면이 멈추는 시간(프레임)
RESTART_DELAY = 25            # 사망 후 GAME OVER 문구가 뜨고 Enter가 먹히기까지(프레임)
DEATH_FRAGMENTS = 10          # 플레이어가 부서지는 조각 수
DEATH_SPARKS = 24             # 튀는 불꽃 수
DEATH_SHAKE = 10              # 화면 흔들림 세기(px)

# ============================================================
# 공정성 검사용 값 (위 값에서 자동 계산. 직접 바꾸지 말 것)
# ============================================================

WALK_SPEED_PX_S = PLAYER_MAX_SPEED * FPS                # 걷기 속도 (px/초)
LASER_WARNING_SEC = LASER_WARNING_TIME / FPS            # 경고 시간 (초)
RAM_SPEED_PX_S = RAM_SPEED * FPS                        # 발사형 속도 (px/초)
REACH_PX = WALK_SPEED_PX_S * LASER_WARNING_SEC          # 경고 동안 걸을 수 있는 거리 (px)

# ============================================================
# 음원 분석 (분석 결과가 달라지므로 함부로 바꾸지 말 것)
# ============================================================

ANALYZER_VERSION = 1          # 분석 방식을 바꾸면 올린다. 올리면 저장된 분석 결과가 무효가 되어 다시 분석됨
ANALYSIS_SR = 22050           # 분석용 샘플레이트
ANALYSIS_FRAME = 1024
ANALYSIS_HOP = 512
ANALYSIS_CHUNK_SEC = 30       # 긴 곡을 이 길이씩 나눠서 읽음(메모리 절약)