import math
import random
import pygame
import ctypes
import sys
import os

# ============================================================
# 기본 설정
# ============================================================

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

WIDTH, HEIGHT = 900, 600
FPS = 45

BG = "#07070b"
CYAN = "#00f5d4"
DANGER = "#ff2a5f"
TEXT = "#e8e8f0"
MUTED = "#4a4a5e"
FONT = "Consolas"

LASER = "#ff5575"
LASER_MINT = "#00d9bd"
TRAIL_COLOR = "#ff3366"

MAX_LASERS = 24
STARTUP_DELAY = 32

# 단일 레이저 생성 간격
SINGLE_START_INTERVAL = 114
SINGLE_MIN_INTERVAL = 42
SINGLE_REDUCTION = 6

# 3개 레이저 생성 간격
TRIPLE_START_INTERVAL = 220
TRIPLE_MIN_INTERVAL = 85
TRIPLE_REDUCTION = 10
TRIPLE_LIFETIME = 34

# 발사형 레이저 생성 간격
RAM_START_INTERVAL = 350
RAM_MIN_INTERVAL = 160
RAM_REDUCTION = 12

SINGLE_LIFETIME = 50

# 3개 레이저는 다음 3개 생성 후 제거
TRIPLE_REMOVE_DELAY = 14

LASER_WARNING_TIME = 20
TRIPLE_WALL_MARGIN = 55

# 단일 레이저 굵기
SINGLE_WARNING_WIDTH = 2
SINGLE_ACTIVE_WIDTH = 5
SINGLE_GLOW_WIDTH = 7

# 3개 레이저 굵기
TRIPLE_WARNING_WIDTH = 1
TRIPLE_ACTIVE_WIDTH = 2
TRIPLE_GLOW_WIDTH = 5

# 발사형 레이저 경로 표시 시간
RAM_WARNING_TIME = 50
RAM_WARNING_MIN_TIME = 30
RAM_WARNING_REDUCTION = 3

RAM_THICKNESS = 28
RAM_LENGTH = 190
RAM_SPEED = 34

RAM_WARNING_COLOR = "#d99aa8"
RAM_BEAM_COLOR = "#ff4568"

RAM_GLOW_WIDTH = 8
RAM_GLOW_EXTENSION = 8
RAM_SPAWN_DISTANCE = 350

RAM_TRAIL_LIFETIME = 9
RAM_TRAIL_ALPHA = 65

# 플레이어 관성 설정
PLAYER_ACCELERATION = 0.75
PLAYER_FRICTION = 0.25
PLAYER_MAX_SPEED = 3.9

# ============================================================
# 전투 상자 설정
# ============================================================

# 기존 520 × 300에서 620 × 360으로 확대
BOX_WIDTH = 620
BOX_HEIGHT = 360

BOX_LEFT = (WIDTH - BOX_WIDTH) // 2
BOX_RIGHT = BOX_LEFT + BOX_WIDTH

BOX_TOP = (HEIGHT - BOX_HEIGHT) // 2
BOX_BOTTOM = BOX_TOP + BOX_HEIGHT

BOX_BORDER_COLOR = "#ffffff"

# ============================================================
# 레이저 피격 보정
# ============================================================

LASER_HIT_GRACE = 5
RAM_HIT_GRACE = 5


# ============================================================
# 색상 변환 함수
# ============================================================

def rgb(color):
    return pygame.Color(color)


def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    a, b = rgb(c1), rgb(c2)

    return (
        int(a.r + (b.r - a.r) * t),
        int(a.g + (b.g - a.g) * t),
        int(a.b + (b.b - a.b) * t)
    )


def alpha_color(color, alpha):
    c = rgb(color)

    return (
        c.r,
        c.g,
        c.b,
        max(0, min(255, int(alpha)))
    )


# ============================================================
# 글로우 색상 미리 계산
# ============================================================

LASER_GLOW = lerp_color(LASER, BG, 0.58)
MINT_GLOW = lerp_color(LASER_MINT, BG, 0.65)
BORDER_COLOR = lerp_color(BG, CYAN, 0.35)

RAM_GLOW_OUTER = lerp_color(RAM_BEAM_COLOR, BG, 0.78)
RAM_GLOW_INNER = lerp_color(RAM_BEAM_COLOR, BG, 0.55)


# ============================================================
# 게임 클래스
# ============================================================

class NeonGauntletGame:

    def __init__(self):
        pygame.init()

        # Windows 작업 표시줄 앱 식별자
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "NeonGauntlet.Game"
        )

        pygame.display.set_caption("lane")

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))

        # 사용자 지정 아이콘
        # .py 실행과 PyInstaller --onefile 실행 모두 지원
        icon_path = resource_path("lane.ico")

        icon = pygame.image.load(icon_path).convert_alpha()
        pygame.display.set_icon(icon)

        # Windows 창 및 작업 표시줄 아이콘 설정
        # WM_SETICON: 0x0080 / ICON_SMALL: 0 / ICON_BIG: 1
        hwnd = pygame.display.get_wm_info()["window"]
        user32 = ctypes.WinDLL("user32", use_last_error=True)

        user32.LoadImageW.restype = ctypes.c_void_p
        user32.LoadImageW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint
        ]

        user32.SendMessageW.restype = ctypes.c_ssize_t
        user32.SendMessageW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_void_p
        ]

        self.icon_handle = user32.LoadImageW(
            None,
            icon_path,
            1,      # IMAGE_ICON
            0,
            0,
            0x10    # LR_LOADFROMFILE
        )

        if self.icon_handle:
            user32.SendMessageW(hwnd, 0x0080, 0, self.icon_handle)
            user32.SendMessageW(hwnd, 0x0080, 1, self.icon_handle)
        self.scene = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()

        # 폰트 설정
        self.font_small = pygame.font.SysFont(FONT, 14, bold=True)
        self.font_medium = pygame.font.SysFont(FONT, 15, bold=True)
        self.font_large = pygame.font.SysFont(FONT, 36, bold=True)
        self.font_score = pygame.font.SysFont(FONT, 17, bold=True)

        self.running = True

        self.reset_game(initial=True)

    # ========================================================
    # 게임 초기화
    # ========================================================

    def reset_game(self, initial=False):

        # 플레이어 위치
        self.px = WIDTH / 2
        self.py = HEIGHT / 2

        self.visual_r = 10
        self.pr = 8

        # 플레이어 관성 속도
        self.move_vx = 0.0
        self.move_vy = 0.0

        self.score = 0
        self.game_over = False
        self.game_started = False

        # 방향키 상태
        self.keys = {
            "Up": False,
            "Down": False,
            "Left": False,
            "Right": False
        }

        # 키보드 입력 연결
        self.key_aliases = {
            pygame.K_UP: "Up",
            pygame.K_KP8: "Up",

            pygame.K_DOWN: "Down",
            pygame.K_KP2: "Down",

            pygame.K_LEFT: "Left",
            pygame.K_KP4: "Left",

            pygame.K_RIGHT: "Right",
            pygame.K_KP6: "Right",

            pygame.K_w: "Up",
            pygame.K_s: "Down",
            pygame.K_a: "Left",
            pygame.K_d: "Right"
        }

        # 대시 상태
        self.dash_cooldown = 0
        self.is_dashing = False

        self.dx_dash = 0
        self.dy_dash = 0

        self.dash_grace = 0
        self.dash_buffer = 0

        self.last_dir = (0, -1)

        # 레이저 목록
        self.lasers = []

        self.single_laser_timer = 0
        self.triple_laser_timer = 0

        self.single_laser_last_axis = None
        self.single_laser_streak = 0

        # 3개 레이저 묶음 번호
        self.triple_batch_id = 0

        # 발사형 레이저
        self.ram_timer = 0
        self.ram_attack = None
        self.ram_trails = []

        self.startup_delay = STARTUP_DELAY

        # 시작 공격 순서
        self.initial_triple_delay = None
        self.initial_ram_delay = None

        # 플레이어 잔상
        self.ghosts = []
        self.move_trails = []

        # 사망 이펙트
        self.fragments = []
        self.sparks = []
        self.ring = None

        # 화면 흔들림
        self.shake = 0.0

        self.hitstop = 0
        self.death_timer = 0
        self.can_restart = False

    # ========================================================
    # 배경 그리기
    # ========================================================

    def draw_background(self, surface):

        surface.fill(rgb(BG))

        pygame.draw.rect(
            surface,
            lerp_color(BG, CYAN, 0.12),
            (3, 3, WIDTH - 6, HEIGHT - 6),
            1
        )

        L = 22

        corners = (
            (3, 3, 1, 1),
            (WIDTH - 3, 3, -1, 1),
            (3, HEIGHT - 3, 1, -1),
            (WIDTH - 3, HEIGHT - 3, -1, -1)
        )

        for cx, cy, sx, sy in corners:

            pygame.draw.line(
                surface,
                BORDER_COLOR,
                (cx, cy),
                (cx + L * sx, cy),
                2
            )

            pygame.draw.line(
                surface,
                BORDER_COLOR,
                (cx, cy),
                (cx, cy + L * sy),
                2
            )

    # ========================================================
    # 원형 글로우 효과
    # ========================================================

    def draw_glow_circle(
        self, surface, x, y, radius, color, strength=1.0
    ):

        glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        layers = [
            (radius + 9, 13),
            (radius + 6, 22),
            (radius + 3, 38),
            (radius, 65)
        ]

        for r, alpha in layers:

            pygame.draw.circle(
                glow,
                alpha_color(color, alpha * strength),
                (int(x), int(y)),
                int(r)
            )

        surface.blit(glow, (0, 0))

    # ========================================================
    # 선형 글로우 효과
    # ========================================================

    def draw_glow_line(
        self, surface, start, end, color,
        core_width, strength=1.0, glow_width=None
    ):

        if glow_width is None:
            glow_width = core_width + 7

        glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        layers = [
            (glow_width + 10, 12),
            (glow_width + 6, 20),
            (glow_width + 3, 34),
            (glow_width, 48)
        ]

        for width, alpha in layers:

            pygame.draw.line(
                glow,
                alpha_color(color, alpha * strength),
                start,
                end,
                max(1, int(width))
            )

        surface.blit(glow, (0, 0))

        pygame.draw.line(
            surface,
            rgb(color),
            start,
            end,
            max(1, int(core_width))
        )

    # ========================================================
    # 다각형 글로우 효과
    # ========================================================

    def draw_glow_polygon(
        self, surface, points, color, thickness, strength=1.0
    ):

        glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        layers = [
            (thickness + 18, 12),
            (thickness + 12, 22),
            (thickness + 7, 38),
            (thickness + 3, 65)
        ]

        for width, alpha in layers:

            pygame.draw.polygon(
                glow,
                alpha_color(color, alpha * strength),
                points
            )

        surface.blit(glow, (0, 0))

        pygame.draw.polygon(
            surface,
            rgb(color),
            points
        )

    # ========================================================
    # 전투 상자 그리기
    # ========================================================

    def draw_battle_box(self, surface):

        pygame.draw.rect(
            surface,
            BOX_BORDER_COLOR,
            (
                BOX_LEFT,
                BOX_TOP,
                BOX_WIDTH,
                BOX_HEIGHT
            ),
            2
        )

    # ========================================================
    # 플레이어 그리기
    # ========================================================

    def draw_player(self, surface):

        if self.game_over and self.hitstop <= 0:
            return

        glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        pygame.draw.circle(
            glow,
            alpha_color(CYAN, 22),
            (int(self.px), int(self.py)),
            self.visual_r + 8
        )

        pygame.draw.circle(
            glow,
            alpha_color(CYAN, 45),
            (int(self.px), int(self.py)),
            self.visual_r + 4
        )

        pygame.draw.circle(
            glow,
            alpha_color(CYAN, 75),
            (int(self.px), int(self.py)),
            self.visual_r + 2
        )

        surface.blit(glow, (0, 0))

        color = DANGER if self.game_over else CYAN

        pygame.draw.circle(
            surface,
            rgb(color),
            (int(self.px), int(self.py)),
            self.visual_r
        )

        pygame.draw.circle(
            surface,
            (255, 255, 255),
            (int(self.px), int(self.py)),
            self.visual_r,
            1
        )

    # ========================================================
    # 레이저 위치 선택
    # ========================================================

    def choose_laser_position(self, forced_type=None):

        margin = TRIPLE_WALL_MARGIN

        # 가로 레이저: 전투 상자의 위아래 경계 기준
        if forced_type == "H":

            if self.py < (BOX_TOP + BOX_BOTTOM) / 2:

                base = BOX_BOTTOM - margin
                pos = base - random.uniform(15, 75)

            else:

                base = BOX_TOP + margin
                pos = base + random.uniform(15, 75)

            pos = max(
                BOX_TOP + margin,
                min(BOX_BOTTOM - margin, pos)
            )

            return "H", pos

        # 세로 레이저: 전투 상자의 좌우 경계 기준
        if forced_type == "V":

            if self.px < (BOX_LEFT + BOX_RIGHT) / 2:

                base = BOX_RIGHT - margin
                pos = base - random.uniform(15, 75)

            else:

                base = BOX_LEFT + margin
                pos = base + random.uniform(15, 75)

            pos = max(
                BOX_LEFT + margin,
                min(BOX_RIGHT - margin, pos)
            )

            return "V", pos

        direction = random.choice(["H", "V"])

        return self.choose_laser_position(direction)

    # ========================================================
    # 단일 레이저 방향 선택
    # ========================================================

    def get_single_laser_direction(self):

        if self.single_laser_streak >= 3:

            direction = (
                "V" if self.single_laser_last_axis == "H" else "H"
            )

        else:
            direction = random.choice(["H", "V"])

        if direction == self.single_laser_last_axis:
            self.single_laser_streak += 1

        else:
            self.single_laser_last_axis = direction
            self.single_laser_streak = 1

        return direction

    # ========================================================
    # 난이도별 레이저 생성 간격
    # ========================================================

    def get_spawn_intervals(self):

        difficulty_step = self.score // 500

        single_interval = max(
            SINGLE_MIN_INTERVAL,
            SINGLE_START_INTERVAL - difficulty_step * SINGLE_REDUCTION
        )

        triple_interval = max(
            TRIPLE_MIN_INTERVAL,
            TRIPLE_START_INTERVAL - difficulty_step * TRIPLE_REDUCTION
        )

        ram_interval = max(
            RAM_MIN_INTERVAL,
            RAM_START_INTERVAL - difficulty_step * RAM_REDUCTION
        )

        return single_interval, triple_interval, ram_interval

    # ========================================================
    # 발사형 레이저 경고 시간 계산
    # ========================================================

    def get_ram_warning_time(self):

        difficulty_step = self.score // 500

        return max(
            RAM_WARNING_MIN_TIME,
            RAM_WARNING_TIME - difficulty_step * RAM_WARNING_REDUCTION
        )

    # ========================================================
    # 일반 레이저 생성
    # ========================================================

    def spawn_laser(self, laser_type, target_player=False, lifetime=None):

        if target_player:

            pos = self.py if laser_type == "H" else self.px

        else:

            laser_type, pos = self.choose_laser_position(laser_type)

        is_single = lifetime != TRIPLE_LIFETIME

        if lifetime is None:
            lifetime = SINGLE_LIFETIME

        self.lasers.append({

            "type": laser_type,
            "pos": pos,

            "warn": True,
            "timer": LASER_WARNING_TIME,

            "life": lifetime,
            "single": is_single,

            "blink": False,
            "hit_grace": 0,

            "triple_batch": None,
            "remove_timer": None
        })

    # ========================================================
    # 레이저 제거
    # ========================================================

    def remove_laser(self, laser):

        if laser in self.lasers:
            self.lasers.remove(laser)

    # ========================================================
    # 발사형 레이저 시작
    # ========================================================

    def start_ram_attack(self):

        if self.ram_attack is not None:
            return

        distances = {
            "left": self.px,
            "right": WIDTH - self.px,
            "top": self.py,
            "bottom": HEIGHT - self.py
        }

        farthest_edge = max(distances, key=distances.get)

        d = RAM_SPAWN_DISTANCE

        if farthest_edge == "left":

            source_x = -d
            source_y = random.uniform(40, HEIGHT - 40)

        elif farthest_edge == "right":

            source_x = WIDTH + d
            source_y = random.uniform(40, HEIGHT - 40)

        elif farthest_edge == "top":

            source_x = random.uniform(40, WIDTH - 40)
            source_y = -d

        else:

            source_x = random.uniform(40, WIDTH - 40)
            source_y = HEIGHT + d

        dx = self.px - source_x
        dy = self.py - source_y

        length = math.hypot(dx, dy)

        if length == 0:
            length = 1

        dx /= length
        dy /= length

        warning_duration = self.get_ram_warning_time()

        self.ram_attack = {

            "phase": "warning",

            "timer": warning_duration,
            "warning_duration": warning_duration,

            "dir_x": dx,
            "dir_y": dy,

            "source_x": source_x,
            "source_y": source_y,

            "beam_pos": 0,
            "hit_grace": 0
        }

    # ========================================================
    # 발사형 레이저 사각형 좌표 계산
    # ========================================================

    def get_ram_polygon(
        self, start_x, start_y, end_x, end_y, thickness
    ):

        dx = end_x - start_x
        dy = end_y - start_y

        length = math.hypot(dx, dy)

        if length == 0:

            return [
                (start_x, start_y),
                (start_x, start_y),
                (start_x, start_y),
                (start_x, start_y)
            ]

        nx = -dy / length
        ny = dx / length

        half = thickness / 2

        return [

            (start_x + nx * half, start_y + ny * half),
            (end_x + nx * half, end_y + ny * half),
            (end_x - nx * half, end_y - ny * half),
            (start_x - nx * half, start_y - ny * half)

        ]

    # ========================================================
    # 발사형 레이저 경고 경로 갱신
    # ========================================================

    def update_ram_warning_shape(self):

        attack = self.ram_attack

        if attack is None or attack["phase"] != "warning":
            return

        dx = self.px - attack["source_x"]
        dy = self.py - attack["source_y"]

        length = math.hypot(dx, dy)

        if length == 0:
            return

        attack["dir_x"] = dx / length
        attack["dir_y"] = dy / length

    # ========================================================
    # 발사형 레이저 경고 경로 그리기
    # ========================================================

    def draw_ram_warning(self, surface):

        attack = self.ram_attack

        if attack is None or attack["phase"] != "warning":
            return

        dx = attack["dir_x"]
        dy = attack["dir_y"]

        beam_length = math.hypot(WIDTH, HEIGHT) * 1.5

        end_x = attack["source_x"] + dx * beam_length
        end_y = attack["source_y"] + dy * beam_length

        points = self.get_ram_polygon(
            attack["source_x"],
            attack["source_y"],
            end_x,
            end_y,
            RAM_THICKNESS
        )

        warning_surface = pygame.Surface(
            (WIDTH, HEIGHT),
            pygame.SRCALPHA
        )

        remaining = (
            attack["timer"] / attack["warning_duration"]
        )

        alpha = int(65 + (1 - remaining) * 65)

        pygame.draw.polygon(
            warning_surface,
            alpha_color(RAM_WARNING_COLOR, alpha),
            points
        )

        pygame.draw.polygon(
            warning_surface,
            alpha_color(RAM_WARNING_COLOR, 45),
            points,
            2
        )

        surface.blit(warning_surface, (0, 0))

    # ========================================================
    # 발사형 레이저 잔상 그리기
    # ========================================================

    def draw_ram_trails(self, surface):

        if not self.ram_trails:
            return

        trail_surface = pygame.Surface(
            (WIDTH, HEIGHT),
            pygame.SRCALPHA
        )

        for trail in self.ram_trails:

            progress = trail["life"] / RAM_TRAIL_LIFETIME

            alpha = int(RAM_TRAIL_ALPHA * progress)

            pygame.draw.line(
                trail_surface,
                alpha_color(RAM_BEAM_COLOR, alpha),
                trail["start"],
                trail["end"],
                RAM_THICKNESS
            )

        surface.blit(trail_surface, (0, 0))

    # ========================================================
    # 발사형 레이저 빔 그리기
    # ========================================================

    def draw_ram_beam(self, surface, attack):

        dx = attack["dir_x"]
        dy = attack["dir_y"]

        start_x = attack["source_x"] + dx * attack["beam_pos"]
        start_y = attack["source_y"] + dy * attack["beam_pos"]

        end_x = start_x + dx * RAM_LENGTH
        end_y = start_y + dy * RAM_LENGTH

        extension = RAM_GLOW_EXTENSION

        glow_start_x = start_x - dx * extension
        glow_start_y = start_y - dy * extension

        glow_end_x = end_x + dx * extension
        glow_end_y = end_y + dy * extension

        outer_points = self.get_ram_polygon(
            glow_start_x,
            glow_start_y,
            glow_end_x,
            glow_end_y,
            RAM_THICKNESS + RAM_GLOW_WIDTH
        )

        inner_points = self.get_ram_polygon(
            glow_start_x,
            glow_start_y,
            glow_end_x,
            glow_end_y,
            RAM_THICKNESS + 4
        )

        beam_points = self.get_ram_polygon(
            start_x,
            start_y,
            end_x,
            end_y,
            RAM_THICKNESS
        )

        self.draw_glow_polygon(
            surface,
            outer_points,
            RAM_GLOW_OUTER,
            RAM_THICKNESS + RAM_GLOW_WIDTH
        )

        self.draw_glow_polygon(
            surface,
            inner_points,
            RAM_GLOW_INNER,
            RAM_THICKNESS + 4
        )

        pygame.draw.polygon(
            surface,
            rgb(RAM_BEAM_COLOR),
            beam_points
        )

    # ========================================================
    # 발사형 레이저 업데이트 및 충돌 판정
    # ========================================================

    def update_ram_attack(self, check_collision=True):

        attack = self.ram_attack

        if attack is None:
            return False

        dx = attack["dir_x"]
        dy = attack["dir_y"]

        # 경고 단계
        if attack["phase"] == "warning":

            attack["timer"] -= 1

            self.update_ram_warning_shape()

            if attack["timer"] <= 0:

                attack["phase"] = "fire"
                attack["beam_pos"] = 0

                attack["hit_grace"] = RAM_HIT_GRACE

            return False

        # 발사 단계
        if attack["phase"] == "fire":

            old_pos = attack["beam_pos"]

            attack["beam_pos"] += RAM_SPEED

            new_pos = attack["beam_pos"]

            # 발사형 레이저 잔상 생성
            if new_pos > old_pos:

                old_start = (
                    attack["source_x"] + dx * old_pos,
                    attack["source_y"] + dy * old_pos
                )

                new_start = (
                    attack["source_x"] + dx * new_pos,
                    attack["source_y"] + dy * new_pos
                )

                self.ram_trails.append({

                    "start": old_start,
                    "end": new_start,
                    "life": RAM_TRAIL_LIFETIME

                })

            # 잔상 수명 감소
            for trail in self.ram_trails[:]:

                trail["life"] -= 1

                if trail["life"] <= 0:
                    self.ram_trails.remove(trail)

            # 발사 직후 충돌 유예
            if attack["hit_grace"] > 0:

                attack["hit_grace"] -= 1

            elif check_collision and not self.game_over:

                rel_x = self.px - attack["source_x"]
                rel_y = self.py - attack["source_y"]

                along = rel_x * dx + rel_y * dy

                perpendicular = abs(
                    rel_x * (-dy) + rel_y * dx
                )

                hit_along = (
                    attack["beam_pos"] - self.pr
                    < along
                    < attack["beam_pos"] + RAM_LENGTH + self.pr
                )

                hit_side = (
                    perpendicular < RAM_THICKNESS / 2 + self.pr
                )

                if (
                    hit_along
                    and hit_side
                    and not self.is_dashing
                    and self.dash_grace == 0
                ):

                    return True

            diagonal = math.hypot(WIDTH, HEIGHT)

            if attack["beam_pos"] > diagonal * 2:

                self.ram_attack = None

            return False

        return False

    # ========================================================
    # 플레이어 이동 잔상 추가
    # ========================================================

    def add_move_trail(self, old_x, old_y, new_x, new_y):

        distance = math.hypot(
            new_x - old_x,
            new_y - old_y
        )

        if distance < 0.5:
            return

        self.move_trails.append({

            "start": (old_x, old_y),
            "end": (new_x, new_y),

            "life": 18,
            "max": 18

        })

    # ========================================================
    # 키 입력 처리
    # ========================================================

    def on_press(self, event):

        key = self.key_aliases.get(event.key)

        if key:

            self.keys[key] = True

            if not self.game_started:
                self.game_started = True

        elif event.key == pygame.K_SPACE:

            if self.game_started and not self.game_over:

                if self.dash_cooldown == 0:

                    self.start_dash()

                elif self.dash_cooldown <= 8:

                    self.dash_buffer = 8

        elif (
            event.key == pygame.K_RETURN
            and self.game_over
            and self.can_restart
        ):

            self.restart()

    # ========================================================
    # 키 해제 처리
    # ========================================================

    def on_release(self, event):

        key = self.key_aliases.get(event.key)

        if key:
            self.keys[key] = False

    # ========================================================
    # 대시 시작
    # ========================================================

    def start_dash(self):

        mx = (
            (1 if self.keys["Right"] else 0)
            - (1 if self.keys["Left"] else 0)
        )

        my = (
            (1 if self.keys["Down"] else 0)
            - (1 if self.keys["Up"] else 0)
        )

        if mx == 0 and my == 0:

            mx, my = self.last_dir

        if mx != 0 or my != 0:

            length = math.hypot(mx, my)

            self.dx_dash = (mx / length) * 16
            self.dy_dash = (my / length) * 16

            self.is_dashing = True

            self.dash_grace = 9
            self.dash_cooldown = 45
            self.dash_buffer = 0

    # ========================================================
    # 게임 재시작
    # ========================================================

    def restart(self):

        self.reset_game()

        self.game_started = True

    # ========================================================
    # 최초 공격 생성
    # ========================================================

    def spawn_initial_attacks(self):

        direction = self.get_single_laser_direction()

        self.spawn_laser(
            direction,
            target_player=True,
            lifetime=SINGLE_LIFETIME
        )

        self.initial_triple_delay = LASER_WARNING_TIME

        self.initial_ram_delay = None

        self.single_laser_timer = 0
        self.triple_laser_timer = 0
        self.ram_timer = 0

    # ========================================================
    # 3개 레이저 생성
    # ========================================================

    def spawn_triple_lasers(self):

        # 이전 묶음 제거 타이머 설정
        for laser in self.lasers:

            if (
                not laser["single"]
                and laser["remove_timer"] is None
            ):

                laser["remove_timer"] = TRIPLE_REMOVE_DELAY

        # 새 묶음 생성
        self.triple_batch_id += 1

        current_batch = self.triple_batch_id

        if random.choice([True, False]):

            directions = ["H", "H", "V"]

        else:

            directions = ["H", "V", "V"]

        random.shuffle(directions)

        for direction in directions:

            self.spawn_laser(
                direction,
                target_player=False,
                lifetime=TRIPLE_LIFETIME
            )

            laser = self.lasers[-1]

            laser["triple_batch"] = current_batch
            laser["remove_timer"] = None

    # ========================================================
    # 일반 레이저 업데이트 및 충돌 판정
    # ========================================================

    def update_lasers(self):

        for laser in self.lasers[:]:

            # 단일 레이저 수명
            if laser["single"]:

                laser["life"] -= 1

                if laser["life"] <= 0:

                    self.remove_laser(laser)
                    continue

            # 3개 레이저 제거 타이머
            else:

                if laser["remove_timer"] is not None:

                    laser["remove_timer"] -= 1

                    if laser["remove_timer"] <= 0:

                        self.remove_laser(laser)
                        continue

            # 경고 단계
            if laser["warn"]:

                laser["timer"] -= 1

                laser["blink"] = not laser["blink"]

                if laser["timer"] <= 0:

                    laser["warn"] = False
                    laser["blink"] = False

                    laser["hit_grace"] = LASER_HIT_GRACE

            else:

                # 레이저 활성화 직후 충돌 유예
                if laser["hit_grace"] > 0:

                    laser["hit_grace"] -= 1
                    continue

                if not self.is_dashing and self.dash_grace == 0:

                    if (
                        laser["type"] == "H"
                        and abs(self.py - laser["pos"]) < self.pr
                    ):

                        self.trigger_game_over()
                        return

                    elif (
                        laser["type"] == "V"
                        and abs(self.px - laser["pos"]) < self.pr
                    ):

                        self.trigger_game_over()
                        return

    # ========================================================
    # 공통 잔상 업데이트
    # ========================================================

    def update_common_fx(self):

        for ghost in self.ghosts[:]:

            ghost["life"] -= 1

            if ghost["life"] <= 0:
                self.ghosts.remove(ghost)

        for trail in self.move_trails[:]:

            trail["life"] -= 1

            if trail["life"] <= 0:
                self.move_trails.remove(trail)

    # ========================================================
    # 플레이어 폭발 효과 생성
    # ========================================================

    def explode_player(self):

        x, y, r = self.px, self.py, self.visual_r

        n = 10

        for i in range(n):

            a1 = math.pi * 2 * i / n
            a2 = math.pi * 2 * (i + 1) / n

            pts = [
                (0, 0),
                (r * math.cos(a1), r * math.sin(a1)),
                (r * math.cos(a2), r * math.sin(a2))
            ]

            gx = sum(p[0] for p in pts) / 3
            gy = sum(p[1] for p in pts) / 3

            mid = (a1 + a2) / 2

            sp = random.uniform(2.5, 6.5)

            self.fragments.append({

                "local": [
                    (p[0] - gx, p[1] - gy) for p in pts
                ],

                "cx": x + gx,
                "cy": y + gy,

                "vx": math.cos(mid) * sp,
                "vy": math.sin(mid) * sp,

                "angle": random.uniform(0, math.pi * 2),
                "spin": random.uniform(-0.4, 0.4),

                "life": 45,
                "max": 45

            })

        # 폭발 파편
        for _ in range(24):

            a = random.uniform(0, math.pi * 2)
            sp = random.uniform(2, 9)

            size = random.uniform(1.2, 3)

            self.sparks.append({

                "x": x,
                "y": y,

                "vx": math.cos(a) * sp,
                "vy": math.sin(a) * sp,

                "size": size,

                "color": random.choice([
                    CYAN,
                    "#ffffff",
                    DANGER
                ]),

                "life": 28,
                "max": 28

            })

        # 원형 충격파
        self.ring = {

            "x": x,
            "y": y,

            "r": 6,
            "dr": 6.0,

            "life": 18,
            "max": 18

        }

        self.shake = 10

    # ========================================================
    # 게임 오버 처리
    # ========================================================

    def trigger_game_over(self):

        if self.game_over:
            return

        self.game_over = True

        self.hitstop = 4
        self.death_timer = 0

        self.can_restart = False

    # ========================================================
    # 사망 연출 업데이트
    # ========================================================

    def update_death(self):

        if not self.game_over:
            return

        # 사망 후에도 발사형 레이저 진행
        self.update_ram_attack(check_collision=False)

        # 히트스톱
        if self.hitstop > 0:

            self.hitstop -= 1

            if self.hitstop == 0:
                self.explode_player()

            return

        # 폭발 파편 이동
        for f in self.fragments[:]:

            f["cx"] += f["vx"]
            f["cy"] += f["vy"]

            f["vx"] *= 0.96
            f["vy"] = f["vy"] * 0.96 + 0.12

            f["angle"] += f["spin"]

            f["life"] -= 1

            if f["life"] <= 0:
                self.fragments.remove(f)

        # 작은 파티클 이동
        for p in self.sparks[:]:

            p["x"] += p["vx"]
            p["y"] += p["vy"]

            p["vx"] *= 0.9
            p["vy"] *= 0.9

            p["life"] -= 1

            if p["life"] <= 0:
                self.sparks.remove(p)

        # 원형 충격파
        if self.ring:

            r = self.ring

            r["r"] += r["dr"]
            r["dr"] *= 0.9

            r["life"] -= 1

            if r["life"] <= 0:
                self.ring = None

        # 화면 흔들림 감쇠
        if self.shake > 0.5:

            self.shake *= 0.85

        elif self.shake:

            self.shake = 0

        self.death_timer += 1

        if self.death_timer >= 25:
            self.can_restart = True

    # ========================================================
    # 메인 게임 업데이트
    # ========================================================

    def update_game(self):

        if self.game_over:

            self.update_death()
            return

        old_x, old_y = self.px, self.py

        # ----------------------------------------------------
        # 대시 이동 및 일반 이동
        # ----------------------------------------------------

        # 대시 시작 시점의 상태 저장
        was_dashing = self.is_dashing

        if self.is_dashing:

            self.ghosts.append({

                "x": self.px,
                "y": self.py,

                "life": 10,
                "max": 10

            })

            self.px += self.dx_dash
            self.py += self.dy_dash

            self.dx_dash *= 0.8
            self.dy_dash *= 0.8

            if (
                abs(self.dx_dash) < 0.5
                and abs(self.dy_dash) < 0.5
            ):

                self.is_dashing = False
                self.dash_grace = 5

        # 대시가 종료된 프레임부터 일반 이동 적용
        if not self.is_dashing:

            # ------------------------------------------------
            # 일반 관성 이동
            # ------------------------------------------------

            mx = (
                (1 if self.keys["Right"] else 0)
                - (1 if self.keys["Left"] else 0)
            )

            my = (
                (1 if self.keys["Down"] else 0)
                - (1 if self.keys["Up"] else 0)
            )

            # 대각선 이동 정규화
            input_length = math.hypot(mx, my)

            if input_length > 0:

                mx /= input_length
                my /= input_length

                self.move_vx += mx * PLAYER_ACCELERATION
                self.move_vy += my * PLAYER_ACCELERATION

                self.last_dir = (

                    (1 if mx > 0 else (-1 if mx < 0 else 0)),
                    (1 if my > 0 else (-1 if my < 0 else 0))

                )

            else:

                # 키를 놓으면 감속
                self.move_vx *= PLAYER_FRICTION
                self.move_vy *= PLAYER_FRICTION

            # 최고 속도 제한
            velocity = math.hypot(
                self.move_vx,
                self.move_vy
            )

            if velocity > PLAYER_MAX_SPEED:

                scale = PLAYER_MAX_SPEED / velocity

                self.move_vx *= scale
                self.move_vy *= scale

            # 작은 잔여 속도 제거
            if abs(self.move_vx) < 0.025:
                self.move_vx = 0

            if abs(self.move_vy) < 0.025:
                self.move_vy = 0

            self.px += self.move_vx
            self.py += self.move_vy

        # ----------------------------------------------------
        # 전투 상자 내부 이동 제한
        # ----------------------------------------------------

        if self.px < BOX_LEFT + self.visual_r:

            self.px = BOX_LEFT + self.visual_r
            self.move_vx = 0

        elif self.px > BOX_RIGHT - self.visual_r:

            self.px = BOX_RIGHT - self.visual_r
            self.move_vx = 0

        if self.py < BOX_TOP + self.visual_r:

            self.py = BOX_TOP + self.visual_r
            self.move_vy = 0

        elif self.py > BOX_BOTTOM - self.visual_r:

            self.py = BOX_BOTTOM - self.visual_r
            self.move_vy = 0

        # 대시 중 이동 잔상 추가
        if was_dashing:

            self.add_move_trail(
                old_x,
                old_y,
                self.px,
                self.py
            )

        # ----------------------------------------------------
        # 점수 증가
        # ----------------------------------------------------

        self.score += 1

        # ----------------------------------------------------
        # 대시 쿨타임
        # ----------------------------------------------------

        if self.dash_cooldown > 0:

            self.dash_cooldown -= 1

            if (
                self.dash_cooldown == 0
                and self.dash_buffer > 0
            ):

                self.start_dash()

        if self.dash_buffer > 0:
            self.dash_buffer -= 1

        # 대시 후 무적 시간
        if self.dash_grace > 0:
            self.dash_grace -= 1

        # ----------------------------------------------------
        # 시작 대기 시간
        # ----------------------------------------------------

        if self.startup_delay > 0:

            self.startup_delay -= 1

            if self.startup_delay == 0:
                self.spawn_initial_attacks()

        else:

            self.single_laser_timer += 1
            self.ram_timer += 1

            (
                single_interval,
                triple_interval,
                ram_interval
            ) = self.get_spawn_intervals()

            # 최초 3개 레이저 대기
            if self.initial_triple_delay is not None:

                self.initial_triple_delay -= 1

                if self.initial_triple_delay <= 0:

                    self.spawn_triple_lasers()

                    self.initial_triple_delay = None

                    self.initial_ram_delay = LASER_WARNING_TIME

                    self.triple_laser_timer = 0

            # 최초 발사형 레이저 대기
            elif self.initial_ram_delay is not None:

                self.initial_ram_delay -= 1

                if self.initial_ram_delay <= 0:

                    self.start_ram_attack()

                    self.initial_ram_delay = None

                    self.ram_timer = 0

            else:

                self.triple_laser_timer += 1

            # ------------------------------------------------
            # 단일 레이저 생성 주기
            # ------------------------------------------------

            if self.single_laser_timer >= single_interval:

                self.single_laser_timer = 0

                direction = self.get_single_laser_direction()

                self.spawn_laser(
                    direction,
                    target_player=True,
                    lifetime=SINGLE_LIFETIME
                )

            # ------------------------------------------------
            # 3개 레이저 생성 주기
            # ------------------------------------------------

            if (
                self.initial_triple_delay is None
                and self.initial_ram_delay is None
                and self.triple_laser_timer >= triple_interval
            ):

                self.triple_laser_timer = 0

                self.spawn_triple_lasers()

            # ------------------------------------------------
            # 발사형 레이저 생성 주기
            # ------------------------------------------------

            if (
                self.initial_triple_delay is None
                and self.initial_ram_delay is None
                and self.ram_timer >= ram_interval
                and self.ram_attack is None
            ):

                self.ram_timer = 0

                self.start_ram_attack()

        # ----------------------------------------------------
        # 발사형 레이저 업데이트
        # ----------------------------------------------------

        if self.update_ram_attack():

            if not self.is_dashing and self.dash_grace == 0:

                self.trigger_game_over()
                return

        # ----------------------------------------------------
        # 일반 레이저 업데이트
        # ----------------------------------------------------

        self.update_lasers()

        if self.game_over:
            return

        # 레이저 최대 개수 제한
        while len(self.lasers) > MAX_LASERS:

            self.lasers.pop(0)

        self.update_common_fx()

    # ========================================================
    # 일반 레이저 그리기
    # ========================================================

    def draw_lasers(self, surface):

        for laser in self.lasers:

            pos = laser["pos"]

            if laser["type"] == "H":

                start = (0, int(pos))
                end = (WIDTH, int(pos))

            else:

                start = (int(pos), 0)
                end = (int(pos), HEIGHT)

            if laser["single"]:

                warning_width = SINGLE_WARNING_WIDTH
                active_width = SINGLE_ACTIVE_WIDTH
                glow_width = SINGLE_GLOW_WIDTH

            else:

                warning_width = TRIPLE_WARNING_WIDTH
                active_width = TRIPLE_ACTIVE_WIDTH
                glow_width = TRIPLE_GLOW_WIDTH

            # 경고 레이저
            if laser["warn"]:

                current_color = (
                    LASER_MINT if laser["blink"] else LASER
                )

                self.draw_glow_line(
                    surface,
                    start,
                    end,
                    current_color,
                    warning_width,
                    strength=0.65,
                    glow_width=glow_width
                )

            # 활성 레이저
            else:

                self.draw_glow_line(
                    surface,
                    start,
                    end,
                    LASER,
                    active_width,
                    strength=0.85,
                    glow_width=glow_width
                )

    # ========================================================
    # 플레이어 대시 잔상 그리기
    # ========================================================

    def draw_trails(self, surface):

        # 대시 잔상 전용 투명 레이어
        trail_surface = pygame.Surface(
            (WIDTH, HEIGHT),
            pygame.SRCALPHA
        )

        for trail in self.move_trails:

            t = 1 - trail["life"] / trail["max"]

            # 잔상이 천천히 흐려지도록 설정
            fade = (1 - t) ** 1.2

            # 기존보다 빨간 잔상 투명도 강화
            alpha = int(210 * fade)
            outer_alpha = int(85 * fade)
            core_alpha = int(235 * fade)

            # 기존보다 잔상 두께 강화
            thickness = max(
                1,
                int(7 * fade + 2)
            )

            start = trail["start"]
            end = trail["end"]

            # 바깥쪽 붉은 글로우
            pygame.draw.line(
                trail_surface,
                (255, 35, 75, outer_alpha),
                start,
                end,
                thickness + 10
            )

            # 중간 붉은 빛
            pygame.draw.line(
                trail_surface,
                (255, 45, 85, alpha),
                start,
                end,
                thickness + 4
            )

            # 중심의 선명한 빨간색
            pygame.draw.line(
                trail_surface,
                (255, 65, 105, core_alpha),
                start,
                end,
                thickness
            )

            # 잔상 끝부분을 둥글게 처리
            cap_radius = max(2, thickness // 2)

            for point in (start, end):

                pygame.draw.circle(
                    trail_surface,
                    (255, 65, 105, core_alpha),
                    (int(point[0]), int(point[1])),
                    cap_radius
                )

        surface.blit(trail_surface, (0, 0))

        # 기존 청록색 대시 잔상
        for ghost in self.ghosts:

            t = 1 - ghost["life"] / ghost["max"]

            color = lerp_color(
                CYAN,
                BG,
                0.4 + 0.6 * t
            )

            pygame.draw.circle(
                surface,
                color,
                (int(ghost["x"]), int(ghost["y"])),
                max(
                    2,
                    int(self.visual_r * (1 - t * 0.35))
                )
            )

    # ========================================================
    # 사망 연출 그리기
    # ========================================================

    def draw_death_effects(self, surface):

        # 플레이어 조각
        for f in self.fragments:

            c = math.cos(f["angle"])
            s = math.sin(f["angle"])

            coords = []

            for lx, ly in f["local"]:

                coords.append((
                    f["cx"] + lx * c - ly * s,
                    f["cy"] + lx * s + ly * c
                ))

            t = 1 - f["life"] / f["max"]

            color = lerp_color(CYAN, BG, t)

            pygame.draw.polygon(
                surface,
                color,
                coords
            )

            pygame.draw.polygon(
                surface,
                lerp_color("#ffffff", BG, t),
                coords,
                1
            )

        # 작은 파티클
        for p in self.sparks:

            t = 1 - p["life"] / p["max"]

            size = max(
                1,
                int(p["size"] * (1 - t * 0.6))
            )

            color = lerp_color(p["color"], BG, t)

            pygame.draw.circle(
                surface,
                color,
                (int(p["x"]), int(p["y"])),
                size
            )

        # 충격파
        if self.ring:

            r = self.ring

            t = 1 - r["life"] / r["max"]

            pygame.draw.circle(
                surface,
                lerp_color("#ffffff", BG, t),
                (int(r["x"]), int(r["y"])),
                max(1, int(r["r"])),
                max(1, int(3 * (1 - t)))
            )

    # ========================================================
    # 텍스트 그리기 공통 함수
    # ========================================================

    def draw_text(
        self, surface, text, font, color, position,
        center=False, right=False
    ):

        image = font.render(
            text,
            True,
            rgb(color)
        )

        rect = image.get_rect()

        if center:

            rect.center = position

        elif right:

            rect.midright = position

        else:

            rect.topleft = position

        surface.blit(image, rect)

    # ========================================================
    # UI 그리기
    # ========================================================

    def draw_ui(self, surface):

        dash_text = (
            "DASH: READY"
            if self.dash_cooldown == 0
            else "DASH: RECHARGING"
        )

        dash_color = (
            CYAN if self.dash_cooldown == 0 else DANGER
        )

        # 점수
        self.draw_text(
            surface,
            f"SCORE: {self.score}",
            self.font_small,
            TEXT if self.game_started else MUTED,
            (30, 17)
        )

        # 대시 상태
        dash_image = self.font_small.render(
            dash_text,
            True,
            rgb(dash_color)
        )

        surface.blit(
            dash_image,
            (
                WIDTH - 30 - dash_image.get_width(),
                17
            )
        )

        # 시작 화면
        if not self.game_started:

            self.draw_text(
                surface,
                "NEON GAUNTLET",
                self.font_large,
                CYAN,
                (WIDTH / 2, HEIGHT / 2 - 65),
                center=True
            )

            lines = [

                "[ ARROWS / WASD ]: MOVE   |   [ SPACE ]: DASH",
                "",
                "PRESS ANY MOVEMENT KEY TO START"

            ]

            y = HEIGHT / 2 + 15

            for line in lines:

                self.draw_text(
                    surface,
                    line,
                    self.font_medium,
                    CYAN,
                    (WIDTH / 2, y),
                    center=True
                )

                y += 23

        # 게임 오버 화면
        if self.game_over and self.death_timer >= 25:

            self.draw_text(
                surface,
                "GAME OVER",
                self.font_large,
                DANGER,
                (WIDTH / 2, HEIGHT / 2 - 45),
                center=True
            )

            self.draw_text(
                surface,
                f"SCORE  {self.score}",
                self.font_score,
                TEXT,
                (WIDTH / 2, HEIGHT / 2 + 10),
                center=True
            )

            self.draw_text(
                surface,
                "PRESS ENTER TO RETRY",
                self.font_small,
                MUTED,
                (WIDTH / 2, HEIGHT / 2 + 60),
                center=True
            )

    # ========================================================
    # 전체 화면 렌더링
    # ========================================================

    def draw(self):

        self.scene.fill((0, 0, 0, 0))

        # 배경
        self.draw_background(self.scene)

        # 플레이어 잔상
        self.draw_trails(self.scene)

        # 일반 레이저
        self.draw_lasers(self.scene)

        # 발사형 레이저
        if self.ram_attack:

            if self.ram_attack["phase"] == "warning":

                self.draw_ram_warning(self.scene)

            elif self.ram_attack["phase"] == "fire":

                self.draw_ram_trails(self.scene)

                self.draw_ram_beam(
                    self.scene,
                    self.ram_attack
                )

        else:

            self.draw_ram_trails(self.scene)

        # 플레이어
        if not self.game_over or self.hitstop > 0:

            self.draw_player(self.scene)

        # 사망 효과
        if self.game_over and self.hitstop <= 0:

            self.draw_death_effects(self.scene)

        # 전투 상자 테두리
        self.draw_battle_box(self.scene)

        # UI를 마지막에 그려 최상위 레이어 유지
        self.draw_ui(self.scene)

        # 실제 화면 출력
        self.screen.fill(rgb(BG))

        # 사망 시 화면 흔들림
        if self.shake > 0.5 and self.game_over:

            offset_x = random.uniform(-self.shake, self.shake)
            offset_y = random.uniform(-self.shake, self.shake)

        else:

            offset_x = 0
            offset_y = 0

        self.screen.blit(
            self.scene,
            (int(offset_x), int(offset_y))
        )

        pygame.display.flip()

    # ========================================================
    # 메인 게임 루프
    # ========================================================

    def run(self):

        while self.running:

            self.clock.tick(FPS)

            # 이벤트 처리
            for event in pygame.event.get():

                if event.type == pygame.QUIT:

                    self.running = False

                elif event.type == pygame.KEYDOWN:

                    self.on_press(event)

                elif event.type == pygame.KEYUP:

                    self.on_release(event)

            # 게임 업데이트
            if self.game_started and not self.game_over:

                self.update_game()

            elif self.game_over:

                self.update_death()

            # 화면 그리기
            self.draw()

        pygame.quit()


# ============================================================
# 프로그램 실행
# ============================================================

if __name__ == "__main__":

    game = NeonGauntletGame()
    game.run()
