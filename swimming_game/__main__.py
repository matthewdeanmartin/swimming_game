import pygame
import sys
import os
import math
import time

# --- Configuration ---
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 600
FPS = 60

# Physics Constants (Tuned for Pygame scale)
PIXELS_PER_METER = 20.0
POOL_LENGTH_METERS = 40.0
FINISH_LINE_X = POOL_LENGTH_METERS * PIXELS_PER_METER
MAX_BREATH_TIME = 17.0  # 17 Seconds rule
FAST_CADENCE_THRESHOLD = 0.25
SPEED_MULTIPLIER = 120.0  # Visual speed scaling

# Colors
WATER_COLOR = (20, 140, 200)
LANE_LINE_COLOR = (255, 230, 0)
TEXT_COLOR = (255, 255, 255)
UI_BG_COLOR = (0, 0, 0, 150)
RED = (255, 50, 50)
GREEN = (50, 255, 50)
BLUE = (50, 50, 255)
PURPLE = (200, 50, 200)


# --- Asset Management ---
class AssetLoader:
    def __init__(self):
        self.images = {}
        self.base_path = os.path.join(os.path.dirname(__file__), 'assets')

    def load_image(self, filename, fallback_color, size=(64, 64)):
        """Try to load an image, return a colored rect if it fails."""
        path = os.path.join(self.base_path, filename)
        try:
            img = pygame.image.load(path)
            if filename == "pool.png":
                return pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT))
            return pygame.transform.scale(img, size)
        except (pygame.error, FileNotFoundError, OSError):
            # Fallback surface
            surf = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.circle(surf, fallback_color, (size[0] // 2, size[1] // 2), size[0] // 2)
            # Add a direction indicator (nose)
            pygame.draw.circle(surf, (255, 255, 255), (size[0] - 10, size[1] // 2), 5)
            return surf


# --- Physics & Player Class ---
def clamp(v, a, b):
    return max(a, min(v, b))


class Player:
    def __init__(self, name, keys, color_name, lane_y, assets):
        self.name = name
        self.keys = keys  # Dict of controls
        self.lane_y = lane_y

        # Images
        c_map = {'red': RED, 'blue': BLUE, 'purple': PURPLE, 'yellow': (255, 255, 0)}
        c = c_map.get(color_name, (255, 255, 255))
        self.img_swim = assets.load_image(f"swimmer {color_name}.png", c)
        self.img_drown = assets.load_image(f"drowning {color_name}.png", (50, 50, 50))

        # Physics State
        self.pos_x = 20.0
        self.velocity = 0.0
        self.stamina = 1.0
        self.fatigue = 0.0

        # The 17 Second Rule
        self.breath_timer = MAX_BREATH_TIME

        # Stroke Mechanics
        self.last_stroke_time = 0.0
        self.last_stroke_side = None  # 'L' or 'R'
        self.stroke_count = 0
        self.penalty_timer = 0.0

        # Game State
        self.drowned = False
        self.finished = False
        self.finish_time = 0.0

        # Drowning Animation State
        self.sink_offset = 0.0

    def handle_input(self, key, now):
        if self.drowned or self.finished: return

        # Stroke Left
        if key == self.keys['left']:
            self._stroke('L', now)
        # Stroke Right
        elif key == self.keys['right']:
            self._stroke('R', now)
        # Kick
        elif key == self.keys['kick']:
            self._kick()
        # Breathe
        elif key == self.keys['breathe']:
            self._breathe()

    def _stroke(self, side, now):
        # Anti-mash logic
        dt = now - self.last_stroke_time
        is_mashing = dt < FAST_CADENCE_THRESHOLD

        # Rhythm efficiency bonus (perfect rhythm is ~0.5s)
        efficiency = 0.8
        if self.last_stroke_time > 0:
            target = 0.5
            efficiency = math.exp(-((dt - target) ** 2) / (2 * 0.1 ** 2))

        # Alternating arm bonus
        alt_bonus = 1.0 if self.last_stroke_side != side else 0.6

        if is_mashing:
            # Penalty: Knock backward
            self.velocity -= 50.0
            self.penalty_timer = 0.5
            self.fatigue = clamp(self.fatigue + 0.05, 0, 1)
        else:
            # Thrust calculation
            thrust = 80.0 * efficiency * alt_bonus
            thrust *= (0.5 + 0.5 * self.stamina)
            thrust *= (1.0 - 0.5 * self.fatigue)
            self.velocity += thrust

        self.last_stroke_time = now
        self.last_stroke_side = side
        self.stroke_count += 1

        # Costs
        self.stamina = clamp(self.stamina - 0.03, 0, 1)
        self.fatigue = clamp(self.fatigue + 0.01, 0, 1)

    def _kick(self):
        # Small boost, high stamina cost
        self.velocity += 15.0 * self.stamina
        self.stamina = clamp(self.stamina - 0.05, 0, 1)

    def _breathe(self):
        # Reset the 17s timer
        self.breath_timer = MAX_BREATH_TIME
        # Breathing slows you down slightly (drag)
        self.velocity *= 0.8
        # Recover a little stamina
        self.stamina = clamp(self.stamina + 0.1, 0, 1)

    def update(self, dt):
        if self.finished: return

        if self.drowned:
            self.velocity = 0
            # Sinking Animation:
            # Increase sink offset.
            # We want it to sink relatively slowly (20px per second)
            self.sink_offset += 20 * dt
            return

        # 1. Update Breath Timer
        self.breath_timer -= dt
        if self.breath_timer <= 0:
            self.drowned = True
            self.breath_timer = 0

        # 2. Recovery
        self.stamina = clamp(self.stamina + (dt * 0.05), 0, 1)
        self.fatigue = clamp(self.fatigue - (dt * 0.02), 0, 1)
        if self.penalty_timer > 0: self.penalty_timer -= dt

        # 3. Drag (Water resistance)
        drag_factor = 2.0
        # Drag increases if out of air or tired
        if self.breath_timer < 5.0: drag_factor += 1.0

        drag = self.velocity * drag_factor * dt
        self.velocity -= drag

        # Constant Glide (unless penalized)
        min_speed = 10.0
        if self.penalty_timer <= 0 and self.velocity < min_speed and self.velocity > 0:
            # Look of momentum
            pass

        if self.velocity < 0 and self.penalty_timer <= 0: self.velocity = 0

        # 4. Move
        self.pos_x += self.velocity * dt

        # 5. Check Finish
        if self.pos_x >= FINISH_LINE_X:
            self.pos_x = FINISH_LINE_X
            self.finished = True
            self.finish_time = pygame.time.get_ticks() / 1000.0

    def draw(self, screen, font):
        # Determine image
        img = self.img_drown if self.drowned else self.img_swim

        # --- Drawing the Player ---
        if self.drowned:
            # Clipping Effect:
            # We move the image DOWN by sink_offset.
            # We crop the HEIGHT by sink_offset (taking from the top of the source image).
            # This makes the bottom of the image visually disappear as it passes a threshold.

            img_w = img.get_width()
            img_h = img.get_height()

            # Calculate how much of the image is still visible
            visible_height = int(img_h - self.sink_offset)

            if visible_height > 0:
                # Source Rect: Take the top portion of the image (0,0) to (w, visible_height)
                src_rect = pygame.Rect(0, 0, img_w, visible_height)

                # Destination: Move down by sink_offset
                dest_pos = (self.pos_x, self.lane_y + self.sink_offset)

                screen.blit(img, dest_pos, area=src_rect)
        else:
            # Normal drawing
            screen.blit(img, (self.pos_x, self.lane_y))

        # --- HUD above player ---
        hud_x = self.pos_x
        hud_y = self.lane_y - 40

        if self.drowned:
            txt = font.render("DROWNED!", True, RED)
            screen.blit(txt, (hud_x, hud_y))
        elif self.finished:
            # FIX: Corrected variable name from LANDE_LINE_COLOR to LANE_LINE_COLOR
            txt = font.render(f"FINISHED! {self.finish_time:.2f}s", True, LANE_LINE_COLOR)
            screen.blit(txt, (hud_x, hud_y))
        else:
            # 1. Breath Timer (Bar)
            bar_w = 60
            bar_h = 8

            # Breath Bar Background
            pygame.draw.rect(screen, (50, 0, 0), (hud_x, hud_y, bar_w, bar_h))
            # Breath Bar Fill
            breath_pct = self.breath_timer / MAX_BREATH_TIME
            breath_col = (100, 255, 255) if breath_pct > 0.3 else (255, 50, 50)
            pygame.draw.rect(screen, breath_col, (hud_x, hud_y, bar_w * breath_pct, bar_h))

            # Stamina Bar (Below breath)
            pygame.draw.rect(screen, (30, 30, 0), (hud_x, hud_y + 10, bar_w, 4))
            pygame.draw.rect(screen, (255, 255, 0), (hud_x, hud_y + 10, bar_w * self.stamina, 4))

            # Text Labels
            if self.penalty_timer > 0:
                msg = font.render("TOO FAST!", True, RED)
                screen.blit(msg, (hud_x + 70, hud_y))
            elif self.breath_timer < 5:
                msg = font.render("BREATHE!", True, RED)
                screen.blit(msg, (hud_x + 70, hud_y))


# --- Main Game Loop ---

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Swimming Simulator - 17s Breath Challenge")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 16, bold=True)
    big_font = pygame.font.SysFont("Arial", 40, bold=True)

    assets = AssetLoader()

    # Load Pool Background (or fallback)
    bg_img = assets.load_image("pool.png", WATER_COLOR)

    # Setup Players
    # P1: WASD style
    # P2: IJKL style (as requested by 'Left player and right player have the same basic keys')
    p1 = Player("Red",
                keys={'left': pygame.K_a, 'right': pygame.K_d, 'kick': pygame.K_s, 'breathe': pygame.K_w},
                color_name='red',
                lane_y=150,
                assets=assets)

    p2 = Player("Blue",
                keys={'left': pygame.K_j, 'right': pygame.K_l, 'kick': pygame.K_k, 'breathe': pygame.K_i},
                color_name='blue',
                lane_y=350,
                assets=assets)

    players = [p1, p2]

    # Camera / Scrolling
    camera_x = 0

    running = True
    winner = None

    while running:
        dt = clock.tick(FPS) / 1000.0  # Delta time in seconds
        now = time.time()

        # --- Input ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                # Handle restart
                if (winner or all(p.drowned for p in players)) and event.key == pygame.K_SPACE:
                    main()  # lazy restart
                    return

                # Pass keys to players
                for p in players:
                    p.handle_input(event.key, now)

        # --- Updates ---
        for p in players:
            p.update(dt)
            if p.finished and winner is None:
                winner = p

        # --- Camera Logic ---
        # Camera follows the leader, but clamps to pool bounds
        leader_x = max(p.pos_x for p in players)
        target_cam_x = leader_x - 200
        target_cam_x = clamp(target_cam_x, 0, FINISH_LINE_X - SCREEN_WIDTH + 100)
        # Smooth camera
        camera_x += (target_cam_x - camera_x) * 5 * dt

        # --- Drawing ---
        screen.fill(WATER_COLOR)

        # Parallax/Static Background
        # We tile the water or draw the pool image
        if bg_img:
            # Simple tiling or stretching logic could go here
            # For now, just draw a huge blue rect or the image
            screen.blit(bg_img, (0, 0))
            screen.blit(bg_img, (SCREEN_WIDTH, 0))  # simplistic tile

        # Draw Lanes and Lines relative to camera
        offset_x = -camera_x

        # Draw Finish Line
        finish_screen_x = FINISH_LINE_X + offset_x
        if -50 < finish_screen_x < SCREEN_WIDTH + 50:
            pygame.draw.rect(screen, (0, 0, 0), (finish_screen_x, 0, 20, SCREEN_HEIGHT))
            # Checkered pattern
            for y in range(0, SCREEN_HEIGHT, 20):
                color = (255, 255, 255) if (y // 20) % 2 == 0 else (0, 0, 0)
                pygame.draw.rect(screen, color, (finish_screen_x, y, 20, 20))

            # "Finnish Fist" (Finish Text)
            txt = big_font.render("FINISH", True, (255, 255, 255))
            screen.blit(txt, (finish_screen_x - 30, 20))

        # Draw Distance Markers
        for m in range(0, int(POOL_LENGTH_METERS), 5):
            px = m * PIXELS_PER_METER + offset_x
            if 0 < px < SCREEN_WIDTH:
                pygame.draw.line(screen, LANE_LINE_COLOR, (px, 0), (px, SCREEN_HEIGHT), 1)
                mark = font.render(f"{m}m", True, (255, 255, 255))
                screen.blit(mark, (px + 5, SCREEN_HEIGHT - 30))

        # Draw Players (apply offset)
        for p in players:
            # We temporarily modify pos_x for drawing relative to camera, then restore it
            real_x = p.pos_x
            p.pos_x = real_x + offset_x
            p.draw(screen, font)
            p.pos_x = real_x  # Restore

        # --- Global HUD ---
        # Instructions
        pygame.draw.rect(screen, UI_BG_COLOR, (0, 0, SCREEN_WIDTH, 40))
        instr = font.render("P1: [A]/[D] Stroke, [S] Kick, [W] Breathe  ||  P2: [J]/[L] Stroke, [K] Kick, [I] Breathe",
                            True, TEXT_COLOR)
        screen.blit(instr, (20, 10))

        # End Game State
        if winner:
            msg = big_font.render(f"{winner.name} WINS! Press SPACE to Restart", True, GREEN)
            rect = msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            pygame.draw.rect(screen, (0, 0, 0), rect.inflate(20, 20))
            screen.blit(msg, rect)
        elif all(p.drowned for p in players):
            msg = big_font.render("EVERYONE DROWNED. Press SPACE to Restart", True, RED)
            rect = msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            pygame.draw.rect(screen, (0, 0, 0), rect.inflate(20, 20))
            screen.blit(msg, rect)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()