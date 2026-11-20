"""화면에 그리는 모든 코드. 게임 상태는 읽기만 하고 바꾸지 않는다."""
import math
import os
import sys

import pygame

import config as C

# ============================================================
# 색 / 글로우 공통
# ============================================================


def rgb(color):
    return pygame.Color(color)


def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    a, b = rgb(c1), rgb(c2)
    return (int(a.r + (b.r - a.r) * t),
            int(a.g + (b.g - a.g) * t),
            int(a.b + (b.b - a.b) * t))


def alpha_color(color, alpha):
    c = rgb(color)
    return (c.r, c.g, c.b, max(0, min(255, int(alpha))))


BORDER_COLOR = lerp_color(C.BG, C.CYAN, 0.35)
RAM_GLOW_OUTER = lerp_color(C.RAM_BEAM_COLOR, C.BG, 0.78)
RAM_GLOW_INNER = lerp_color(C.RAM_BEAM_COLOR, C.BG, 0.55)


def draw_glow_line(surface, start, end, color, core_width,
                   strength=1.0, glow_width=None):
    if glow_width is None:
        glow_width = core_width + 7
    glow = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
    for width, alpha in ((glow_width + 10, 12), (glow_width + 6, 20),
                         (glow_width + 3, 34), (glow_width, 48)):
        pygame.draw.line(glow, alpha_color(color, alpha * strength),
                         start, end, max(1, int(width)))
    surface.blit(glow, (0, 0))
    pygame.draw.line(surface, rgb(color), start, end, max(1, int(core_width)))


def draw_glow_polygon(surface, points, color, thickness, strength=1.0):
    glow = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
    for _w, alpha in ((thickness + 18, 12), (thickness + 12, 22),
                      (thickness + 7, 38), (thickness + 3, 65)):
        pygame.draw.polygon(glow, alpha_color(color, alpha * strength), points)
    surface.blit(glow, (0, 0))
    pygame.draw.polygon(surface, rgb(color), points)


def beam_polygon(sx, sy, ex, ey, thickness):
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    if length == 0:
        return [(sx, sy)] * 4
    nx, ny = -dy / length, dx / length
    half = thickness / 2
    return [(sx + nx * half, sy + ny * half), (ex + nx * half, ey + ny * half),
            (ex - nx * half, ey - ny * half), (sx - nx * half, sy - ny * half)]


# ============================================================
# 렌더러
# ============================================================

class Renderer:
    """창을 만들고, 게임 상태(game)를 받아 한 프레임을 그린다."""

    def __init__(self):
        self._set_windows_app_id()
        pygame.display.set_caption(C.WINDOW_TITLE)
        self.screen = pygame.display.set_mode((C.WIDTH, C.HEIGHT))
        self._set_window_icon()
        self.scene = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)

        self.font_small = pygame.font.SysFont(C.FONT, 14, bold=True)
        self.font_medium = pygame.font.SysFont(C.FONT, 15, bold=True)
        self.font_large = pygame.font.SysFont(C.FONT, 36, bold=True)
        self.font_score = pygame.font.SysFont(C.FONT, 17, bold=True)

    # ---------------- 창 설정 (Windows 작업표시줄 아이콘) ----------------
    @staticmethod
    def _set_windows_app_id():
        """작업표시줄에서 python이 아닌 이 게임의 아이콘으로 보이게 하는 앱 식별자."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(C.APP_ID)
        except Exception as exc:  # noqa: BLE001
            print(f"[LANE] 앱 식별자를 설정하지 못했어요: {exc}")

    def _set_window_icon(self):
        """창과 작업표시줄 아이콘. 파일이 없어도 게임은 그대로 실행된다."""
        self.icon_handle = None
        path = C.resource_path(C.ICON_FILE)
        if not os.path.isfile(path):
            print(f"[LANE] 아이콘 파일을 찾을 수 없어요: {path}")
            return
        try:
            pygame.display.set_icon(pygame.image.load(path).convert_alpha())
        except pygame.error as exc:
            print(f"[LANE] 아이콘을 불러오지 못했어요: {exc}")
            return
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = pygame.display.get_wm_info()["window"]
            user32 = ctypes.WinDLL("user32", use_last_error=True)

            user32.LoadImageW.restype = ctypes.c_void_p
            user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p,
                                          ctypes.c_uint, ctypes.c_int,
                                          ctypes.c_int, ctypes.c_uint]
            user32.SendMessageW.restype = ctypes.c_ssize_t
            user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                            ctypes.c_size_t, ctypes.c_void_p]

            # IMAGE_ICON = 1, LR_LOADFROMFILE = 0x10
            self.icon_handle = user32.LoadImageW(None, path, 1, 0, 0, 0x10)
            if self.icon_handle:
                # WM_SETICON = 0x0080, ICON_SMALL = 0, ICON_BIG = 1
                user32.SendMessageW(hwnd, 0x0080, 0, self.icon_handle)
                user32.SendMessageW(hwnd, 0x0080, 1, self.icon_handle)
        except Exception as exc:  # noqa: BLE001
            print(f"[LANE] 작업표시줄 아이콘을 설정하지 못했어요: {exc}")

    # ---------------- 한 프레임 ----------------
    def draw(self, game):
        s = self.scene
        s.fill((0, 0, 0, 0))

        self.background(s)
        self.player_trails(s, game.player)
        self.lasers(s, game.lasers)
        self.ram(s, game.ram)

        if not game.game_over or game.fx.hitstop > 0:
            self.player(s, game.player, dead=game.game_over)
        if game.game_over and game.fx.hitstop <= 0:
            self.death_fx(s, game.fx)

        self.battle_box(s)
        self.hud(s, game)

        self.screen.fill(rgb(C.BG))
        ox, oy = game.fx.shake_offset(game.game_over)
        self.screen.blit(s, (int(ox), int(oy)))
        pygame.display.flip()

    # ---------------- 배경 / 상자 ----------------
    def background(self, surface):
        surface.fill(rgb(C.BG))
        pygame.draw.rect(surface, lerp_color(C.BG, C.CYAN, 0.12),
                         (3, 3, C.WIDTH - 6, C.HEIGHT - 6), 1)
        length = 22
        for cx, cy, sx, sy in ((3, 3, 1, 1), (C.WIDTH - 3, 3, -1, 1),
                               (3, C.HEIGHT - 3, 1, -1),
                               (C.WIDTH - 3, C.HEIGHT - 3, -1, -1)):
            pygame.draw.line(surface, BORDER_COLOR, (cx, cy), (cx + length * sx, cy), 2)
            pygame.draw.line(surface, BORDER_COLOR, (cx, cy), (cx, cy + length * sy), 2)

    def battle_box(self, surface):
        pygame.draw.rect(surface, C.BOX_BORDER_COLOR,
                         (C.BOX_LEFT, C.BOX_TOP, C.BOX_WIDTH, C.BOX_HEIGHT), 2)

    # ---------------- 플레이어 ----------------
    def player(self, surface, p, dead=False):
        pos = (int(p.x), int(p.y))
        glow = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
        for extra, alpha in ((8, 22), (4, 45), (2, 75)):
            pygame.draw.circle(glow, alpha_color(C.CYAN, alpha), pos, p.visual_r + extra)
        surface.blit(glow, (0, 0))

        pygame.draw.circle(surface, rgb(C.DANGER if dead else C.CYAN), pos, p.visual_r)
        pygame.draw.circle(surface, (255, 255, 255), pos, p.visual_r, 1)

    def player_trails(self, surface, p):
        layer = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
        for trail in p.move_trails:
            t = 1 - trail["life"] / trail["max"]
            fade = (1 - t) ** 1.2
            alpha = int(210 * fade)
            outer_alpha = int(85 * fade)
            core_alpha = int(235 * fade)
            thickness = max(1, int(7 * fade + 2))
            start, end = trail["start"], trail["end"]

            pygame.draw.line(layer, (255, 35, 75, outer_alpha), start, end, thickness + 10)
            pygame.draw.line(layer, (255, 45, 85, alpha), start, end, thickness + 4)
            pygame.draw.line(layer, (255, 65, 105, core_alpha), start, end, thickness)

            cap = max(2, thickness // 2)
            for point in (start, end):
                pygame.draw.circle(layer, (255, 65, 105, core_alpha),
                                   (int(point[0]), int(point[1])), cap)
        surface.blit(layer, (0, 0))

        for ghost in p.ghosts:
            t = 1 - ghost["life"] / ghost["max"]
            pygame.draw.circle(surface, lerp_color(C.CYAN, C.BG, 0.4 + 0.6 * t),
                               (int(ghost["x"]), int(ghost["y"])),
                               max(2, int(p.visual_r * (1 - t * 0.35))))

    # ---------------- 일반 레이저 ----------------
    def lasers(self, surface, field):
        for laser in field.items:
            pos = int(laser["pos"])
            if laser["type"] == "H":
                start, end = (0, pos), (C.WIDTH, pos)
            else:
                start, end = (pos, 0), (pos, C.HEIGHT)

            if laser["single"]:
                warn_w, active_w, glow_w = (C.SINGLE_WARNING_WIDTH,
                                            C.SINGLE_ACTIVE_WIDTH, C.SINGLE_GLOW_WIDTH)
            else:
                warn_w, active_w, glow_w = (C.TRIPLE_WARNING_WIDTH,
                                            C.TRIPLE_ACTIVE_WIDTH, C.TRIPLE_GLOW_WIDTH)

            if laser["warn"]:
                color = C.LASER_MINT if laser["blink"] else C.LASER
                draw_glow_line(surface, start, end, color, warn_w,
                               strength=0.65, glow_width=glow_w)
            else:
                draw_glow_line(surface, start, end, C.LASER, active_w,
                               strength=0.85, glow_width=glow_w)

    # ---------------- 발사형 레이저 ----------------
    def ram(self, surface, ram):
        a = ram.attack
        if a is not None and a["phase"] == "warning":
            self._ram_warning(surface, a)
            return
        self._ram_trails(surface, ram.trails)
        if a is not None and a["phase"] == "fire":
            self._ram_beam(surface, a)

    def _ram_warning(self, surface, a):
        length = math.hypot(C.WIDTH, C.HEIGHT) * 1.5
        ex = a["source_x"] + a["dir_x"] * length
        ey = a["source_y"] + a["dir_y"] * length
        points = beam_polygon(a["source_x"], a["source_y"], ex, ey, C.RAM_THICKNESS)

        layer = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
        remaining = a["timer"] / a["warning_duration"]
        alpha = int(65 + (1 - remaining) * 65)
        pygame.draw.polygon(layer, alpha_color(C.RAM_WARNING_COLOR, alpha), points)
        pygame.draw.polygon(layer, alpha_color(C.RAM_WARNING_COLOR, 45), points, 2)
        surface.blit(layer, (0, 0))

    def _ram_trails(self, surface, trails):
        if not trails:
            return
        layer = pygame.Surface((C.WIDTH, C.HEIGHT), pygame.SRCALPHA)
        for trail in trails:
            alpha = int(C.RAM_TRAIL_ALPHA * trail["life"] / C.RAM_TRAIL_LIFETIME)
            pygame.draw.line(layer, alpha_color(C.RAM_BEAM_COLOR, alpha),
                             trail["start"], trail["end"], C.RAM_THICKNESS)
        surface.blit(layer, (0, 0))

    def _ram_beam(self, surface, a):
        dx, dy = a["dir_x"], a["dir_y"]
        sx = a["source_x"] + dx * a["beam_pos"]
        sy = a["source_y"] + dy * a["beam_pos"]
        ex, ey = sx + dx * C.RAM_LENGTH, sy + dy * C.RAM_LENGTH
        ext = C.RAM_GLOW_EXTENSION

        gs = (sx - dx * ext, sy - dy * ext)
        ge = (ex + dx * ext, ey + dy * ext)
        outer = beam_polygon(*gs, *ge, C.RAM_THICKNESS + C.RAM_GLOW_WIDTH)
        inner = beam_polygon(*gs, *ge, C.RAM_THICKNESS + 4)
        beam = beam_polygon(sx, sy, ex, ey, C.RAM_THICKNESS)

        draw_glow_polygon(surface, outer, RAM_GLOW_OUTER, C.RAM_THICKNESS + C.RAM_GLOW_WIDTH)
        draw_glow_polygon(surface, inner, RAM_GLOW_INNER, C.RAM_THICKNESS + 4)
        pygame.draw.polygon(surface, rgb(C.RAM_BEAM_COLOR), beam)

    # ---------------- 사망 연출 ----------------
    def death_fx(self, surface, fx):
        for f in fx.fragments:
            c, s = math.cos(f["angle"]), math.sin(f["angle"])
            coords = [(f["cx"] + lx * c - ly * s, f["cy"] + lx * s + ly * c)
                      for lx, ly in f["local"]]
            t = 1 - f["life"] / f["max"]
            pygame.draw.polygon(surface, lerp_color(C.CYAN, C.BG, t), coords)
            pygame.draw.polygon(surface, lerp_color("#ffffff", C.BG, t), coords, 1)

        for p in fx.sparks:
            t = 1 - p["life"] / p["max"]
            pygame.draw.circle(surface, lerp_color(p["color"], C.BG, t),
                               (int(p["x"]), int(p["y"])),
                               max(1, int(p["size"] * (1 - t * 0.6))))

        if fx.ring:
            r = fx.ring
            t = 1 - r["life"] / r["max"]
            pygame.draw.circle(surface, lerp_color("#ffffff", C.BG, t),
                               (int(r["x"]), int(r["y"])), max(1, int(r["r"])),
                               max(1, int(3 * (1 - t))))

    # ---------------- 글자 ----------------
    @staticmethod
    def _text(surface, text, font, color, pos, center=False):
        image = font.render(text, True, rgb(color))
        rect = image.get_rect()
        if center:
            rect.center = pos
        else:
            rect.topleft = pos
        surface.blit(image, rect)

    def hud(self, surface, game):
        ready = game.player.dash_cooldown == 0
        self._text(surface, f"SCORE: {game.score}", self.font_small,
                   C.TEXT if game.started else C.MUTED, (30, 17))

        dash = self.font_small.render(
            "DASH: READY" if ready else "DASH: RECHARGING", True,
            rgb(C.CYAN if ready else C.DANGER))
        surface.blit(dash, (C.WIDTH - 30 - dash.get_width(), 17))

        if not game.started:
            self._text(surface, C.TITLE_TEXT, self.font_large, C.CYAN,
                       (C.WIDTH / 2, C.HEIGHT / 2 - 65), center=True)
            y = C.HEIGHT / 2 + 15
            for line in ("[ ARROWS / WASD ]: MOVE   |   [ SPACE ]: DASH", "",
                         "PRESS ANY MOVEMENT KEY TO START"):
                self._text(surface, line, self.font_medium, C.CYAN,
                           (C.WIDTH / 2, y), center=True)
                y += 23

        if game.game_over and game.fx.ready_for_text:
            self._text(surface, "GAME OVER", self.font_large, C.DANGER,
                       (C.WIDTH / 2, C.HEIGHT / 2 - 45), center=True)
            self._text(surface, f"SCORE  {game.score}", self.font_score, C.TEXT,
                       (C.WIDTH / 2, C.HEIGHT / 2 + 10), center=True)
            self._text(surface, "PRESS ENTER TO RETRY", self.font_small, C.MUTED,
                       (C.WIDTH / 2, C.HEIGHT / 2 + 60), center=True)