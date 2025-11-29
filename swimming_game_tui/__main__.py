#!/usr/bin/env python3
# Swimming Simulator (Terminal Prototype)
# Upgrades:
# - Heavy anti-mash penalty: strokes faster than FAST_CADENCE_THRESHOLD push swimmer BACKWARDS briefly.
# - Faster swimmer via SPEED_MULTIPLIER and tuned drag.
# - Dynamic coaching tips under meters.
# - Race time limit (configurable) with hard stop.
# - Wide-screen pool (auto-fits terminal). Faster speed shows more movement.
# - Constant glide (minimum forward velocity) for both players when not penalized.
# - 2P HUD side-by-side to prevent scrolling.

from __future__ import annotations
import sys, time, threading, math, os

# ===== Config =====
MAX_RACE_TIME = 60.0          # seconds; hard stop
FAST_CADENCE_THRESHOLD = 0.25 # s between strokes considered too fast (anti-mash)
PENALTY_BACKWARD_IMPULSE = 1.2 # m/s knocked off (can go negative)
PENALTY_DURATION = 0.6        # seconds of penalty window (min-glide disabled)
SPEED_MULTIPLIER = 1.35       # global multiplier to make swimmer faster
BASE_DRAG_COEF = 0.75         # lower than before to sustain motion
FRICTION = 0.30               # baseline velocity bleed
MIN_GLIDE_SPEED = 0.22        # constant forward motion (m/s) when not penalized
HUD_BAR_WIDTH = 28            # width of HUD bars
POOL_LEFT_MARGIN = 2          # visual left margin in chars

# ---------- Cross-platform nonblocking keyboard ----------
if os.name == "nt":
    import msvcrt  # type: ignore
    class KeyReader:
        def __init__(self): self.alive = True
        def getch(self) -> str | None:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00","\xe0") and msvcrt.kbhit():
                    _ = msvcrt.getwch()
                    return None
                return ch
            return None
        def cleanup(self): self.alive = False
else:
    import termios, tty, select
    class KeyReader:
        def __init__(self):
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd); self.alive = True
        def getch(self) -> str | None:
            r,_,_ = select.select([sys.stdin],[],[],0)
            if r:
                ch = os.read(self.fd, 4).decode(errors="ignore")
                return ch[0] if ch else None
            return None
        def cleanup(self):
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old); self.alive = False

# ---------- ANSI helpers ----------
CSI = "\x1b["; HIDE = CSI+"?25l"; SHOW = CSI+"?25h"; CLS = CSI+"2J"; HOME = CSI+"H"

def move(y: int, x: int) -> str: return f"{CSI}{y};{x}H"

def clear_to_eol() -> str: return CSI+"K"

# ---------- Double-buffered screen ----------
class Screen:
    def __init__(self, width: int, height: int):
        self.w,self.h = width,height
        self.front = [""]*height
        self.back  = [" "*width for _ in range(height)]
    def draw_line(self, y: int, s: str):
        if 0 <= y < self.h:
            txt = s
            if len(txt) < self.w: txt += " "*(self.w-len(txt))
            else: txt = txt[:self.w]
            self.back[y] = txt
    def clear(self): self.back = [" "*self.w for _ in range(self.h)]
    def flush(self):
        out=[]
        for y in range(self.h):
            if self.back[y] != self.front[y]:
                out.append(move(y+1,1)+self.back[y]+clear_to_eol())
        if out:
            sys.stdout.write("".join(out)); sys.stdout.flush(); self.front[:] = self.back[:]

# ---------- Game data ----------
def clamp(v,a,b): return a if v<a else b if v>b else v

class Player:
    def __init__(self, name: str, keys: dict[str,str], lane_y: int, pool_len_m=25.0):
        self.name=name; self.keys=keys; self.lane_y=lane_y; self.pool_len=pool_len_m
        self.pos=0.0; self.v=0.0; self.o2=1.0; self.sta=1.0; self.fatigue=0.0
        self.last_stroke=None; self.stroke_time=0.0; self.stroke_count=0
        self.breath_cooldown=0.0; self.finished=False; self.finish_time=None
        self.penalty_timer=0.0
    def handle_key(self, ch: str, t: float):
        if ch == self.keys.get("left"):  self._stroke('L', t)
        elif ch == self.keys.get("right"): self._stroke('R', t)
        elif ch == self.keys.get("kick"):  self._kick()
        elif ch == self.keys.get("breathe"): self._breathe()
    def _stroke(self, side: str, now: float):
        # Anti-mash check
        fast = False
        if self.stroke_time>0 and (now - self.stroke_time) < FAST_CADENCE_THRESHOLD:
            fast = True
        # Rhythm efficiency around ~0.47s
        eff=0.8
        if self.stroke_time>0:
            dt=now-self.stroke_time; target=0.47
            eff=math.exp(-((dt-target)**2)/(2*0.08**2))
        alt_bonus = 1.0 if (self.last_stroke and self.last_stroke!=side) else 0.6
        thrust = SPEED_MULTIPLIER * 1.9 * eff * alt_bonus * (0.6+0.4*self.sta) * (0.6+0.4*self.o2) * (1.0-0.5*self.fatigue)
        if fast:
            # Apply backward impulse and start penalty window
            self.v -= PENALTY_BACKWARD_IMPULSE
            self.penalty_timer = max(self.penalty_timer, PENALTY_DURATION)
        else:
            self.v += thrust * 0.28
        self.stroke_time=now; self.last_stroke=side; self.stroke_count+=1
        # Costs
        self.sta = clamp(self.sta - 0.04, 0.0, 1.0)
        self.o2  = clamp(self.o2  - 0.012, 0.0, 1.0)
        self.fatigue = clamp(self.fatigue + (0.03 if fast else 0.018), 0.0, 1.0)
    def _kick(self):
        self.v += SPEED_MULTIPLIER * 0.28 * (0.5+0.5*self.sta)
        self.sta = clamp(self.sta - 0.015, 0.0, 1.0)
        self.fatigue = clamp(self.fatigue + 0.01, 0.0, 1.0)
    def _breathe(self):
        if self.breath_cooldown<=0.0:
            self.o2 = clamp(self.o2 + 0.38, 0.0, 1.0)
            self.breath_cooldown = 0.8
    def update(self, dt: float):
        # Recovery & decay
        self.sta = clamp(self.sta + dt*0.075*(0.7 if self.v>0.9 else 1.0), 0.0, 1.0)
        self.o2  = clamp(self.o2 - dt*0.028*(1.15 if self.v>1.3 else 1.0), 0.0, 1.0)
        self.fatigue = clamp(self.fatigue - dt*0.05, 0.0, 1.0)
        if self.breath_cooldown>0: self.breath_cooldown -= dt
        if self.penalty_timer>0: self.penalty_timer -= dt
        # Drag & friction
        drag_coef = BASE_DRAG_COEF * (1.5 if self.o2<0.15 else 1.0)
        if self.breath_cooldown>0.6: drag_coef *= 1.15
        # Glide bonus when not stroking very recently
        glide=0.9
        if self.stroke_time>0 and (time.perf_counter()-self.stroke_time) > 0.35:
            glide=0.8
        drag = drag_coef * (self.v**2) * dt * glide
        self.v -= drag + FRICTION*dt
        # Constant glide (unless penalized)
        if self.penalty_timer <= 0:
            if self.v < MIN_GLIDE_SPEED:
                self.v = MIN_GLIDE_SPEED
        # Update position, allow slight backward but not beyond wall 0
        self.pos += self.v * dt
        if self.pos < 0: self.pos = 0.0
        if self.pos >= self.pool_len and not self.finished:
            self.finished=True

# ---------- Input thread ----------
class InputThread:
    def __init__(self, keyreader: KeyReader):
        self.reader=keyreader; self.q=[]; self.lock=threading.Lock()
        self.t=threading.Thread(target=self.run, daemon=True); self.alive=True; self.t.start()
    def run(self):
        while self.alive and self.reader.alive:
            ch=self.reader.getch()
            if ch:
                with self.lock: self.q.append(ch.lower())
            time.sleep(0.001)
    def pop_all(self):
        with self.lock: items=self.q[:]; self.q.clear(); return items
    def stop(self): self.alive=False

# ---------- HUD / Coaching ----------

def bar(label: str, value: float, width: int, emoji: str) -> str:
    v=clamp(value,0.0,1.0); filled=int(round(v*width)); empty=width-filled
    return f"{emoji} {label}: " + "█"*filled + "░"*empty + f" {int(v*100):3d}%"

def speed_bar(spd: float, max_spd: float, width: int, emoji: str) -> str:
    v=clamp(spd/max_spd,0.0,1.0); filled=int(round(v*width)); empty=width-filled
    return f"{emoji} Speed: " + "█"*filled + "░"*empty + f" {spd:4.2f} m/s"

def coaching(p: Player, now: float) -> str:
    tips=[]
    # Cadence advice
    if p.stroke_time>0:
        dt = now - p.stroke_time
        if dt < FAST_CADENCE_THRESHOLD:
            tips.append("Too fast: pause 0.3–0.5s")
        elif dt > 0.9:
            tips.append("Stroke now: A/D rhythm")
    # Resources
    if p.o2 < 0.35: tips.append("Breathe (W)")
    if p.sta < 0.35: tips.append("Glide 1s to recover")
    if p.fatigue > 0.6: tips.append("Slow cadence")
    if p.penalty_timer>0: tips.append("Penalty: stop mashing")
    if not tips: tips = ["Alternate A-D, breathe every 3–5 strokes"]
    # Join with bullets
    return " • ".join(tips)[:max(20, HUD_BAR_WIDTH*2+10)]

# ---------- Overlay helper ----------
class Overlay:
    @staticmethod
    def put(screen: Screen, y: int, x: int, s: str):
        if not (0 <= y < screen.h) or x >= screen.w: return
        base = screen.back[y]
        if len(base) < screen.w: base += " "*(screen.w-len(base))
        s = s[: max(0, screen.w - x)]
        screen.back[y] = base[:x] + s + base[x+len(s):]

# ---------- Rendering ----------

def render_pool(screen: Screen, players: list[Player], t0: float, header: str, now: float):
    screen.clear(); W,H = screen.w, screen.h
    screen.draw_line(0, header[:W])

    left = POOL_LEFT_MARGIN
    pool_chars = max(20, W - left - 2)  # wide screen auto-fit
    right = left + pool_chars
    meters_to_cols = pool_chars / max(1.0, max(p.pool_len for p in players))

    water = "≈"; lane_sep = "─" * pool_chars
    for p in players:
        y = p.lane_y
        line = " "*left + (water * pool_chars)
        screen.draw_line(y, line)
        screen.draw_line(y-1, " "*left + lane_sep)
        screen.draw_line(y+1, " "*left + lane_sep)
        col = left + int(p.pos * meters_to_cols)
        swimmer = "🏊" + " "
        pre = (" "*left) + (water * max(0, min(pool_chars, col - left)))
        post_len = max(0, right - len(pre) - len(swimmer))
        post = (water * post_len)
        swimline = pre + swimmer + post
        screen.draw_line(y, swimline[:W])

    # Side-by-side HUD
    top_hud_y = max(p.lane_y for p in players) + 2
    col_split = max(W//2, 50)

    if len(players)>=1:
        p=players[0]
        Overlay.put(screen, top_hud_y, 1, f"🧑 {p.name}  {'🏁' if p.finished else '✓'}")
        ms=[bar("O₂",p.o2,HUD_BAR_WIDTH,"🫁"), bar("Stamina",p.sta,HUD_BAR_WIDTH,"💪"), speed_bar(p.v,4.0,HUD_BAR_WIDTH,"🏁"), "💡 "+coaching(p, now)]
        for i,m in enumerate(ms): Overlay.put(screen, top_hud_y+1+i, 1, m)

    if len(players)>=2:
        p=players[1]; start_x = min(W-2, col_split)
        Overlay.put(screen, top_hud_y, start_x, f"🧑‍🤝‍🧑 {p.name}  {'🏁' if p.finished else '✓'}")
        ms=[bar("O₂",p.o2,HUD_BAR_WIDTH,"🫁"), bar("Stamina",p.sta,HUD_BAR_WIDTH,"💪"), speed_bar(p.v,4.0,HUD_BAR_WIDTH,"🏁"), "💡 "+coaching(p, now)]
        for i,m in enumerate(ms): Overlay.put(screen, top_hud_y+1+i, start_x, m)

    screen.draw_line(H-1, "Controls: P1[A/D]=stroke [S]=kick [W]=breathe | P2[J/L] [K] [I] | [Q]=quit  —  Anti-mash ON")

# ---------- Game loop ----------

def game(mode_two_players: bool):
    try: cols, rows = os.get_terminal_size()
    except OSError: cols, rows = 120, 30
    rows = max(rows, 30); cols = max(cols, 96)
    screen = Screen(cols, rows)

    reader = KeyReader(); it = InputThread(reader)

    p1 = Player("Player 1", keys={"left":"a","right":"d","kick":"s","breathe":"w"}, lane_y=6)
    players=[p1]
    if mode_two_players:
        p2 = Player("Player 2", keys={"left":"j","right":"l","kick":"k","breathe":"i"}, lane_y=12)
        players.append(p2)

    sys.stdout.write(HIDE+CLS+HOME); sys.stdout.flush()
    t0 = time.perf_counter(); last=t0; dt_cap=1/60.0; running=True

    try:
        while running:
            now=time.perf_counter(); dt=now-last
            if dt < dt_cap:
                time.sleep(dt_cap-dt); now=time.perf_counter(); dt=now-last
            last=now

            # Time limit
            if (now - t0) >= MAX_RACE_TIME:
                for p in players:
                    if not p.finished:
                        p.finished=True; p.finish_time = now - t0
                running=False

            for ch in it.pop_all():
                if ch=='q': running=False; break
                for p in players: p.handle_key(ch, now)

            for p in players:
                if not p.finished:
                    p.update(dt)
                    if p.pos >= p.pool_len:
                        p.finished=True; p.finish_time = now - t0

            if all(p.finished for p in players): running=False

            header = f"🏊 Swimming Simulator — {'2P' if mode_two_players else '1P'}  Time: {now-t0:5.2f}/{MAX_RACE_TIME:.0f}s  (Anti-mash, Glide)"
            render_pool(screen, players, t0, header, now)
            screen.flush()

        # Summary
        y = max(p.lane_y for p in players) + 12
        lines=[""]
        for p in players:
            ttxt = f"{p.finish_time:0.2f}s" if p.finish_time is not None else "—"
            lines.append(f"{p.name}: time={ttxt} strokes={p.stroke_count} avg_speed={p.pos/max(p.finish_time or 1e-6,1e-6):.2f} m/s pos={p.pos:.1f}m")
        lines.append("Press any key to exit…")
        for i,ln in enumerate(lines):
            if y+i < screen.h-1: screen.draw_line(y+i, ln)
        screen.flush()
        while True:
            ch=reader.getch()
            if ch: break
            time.sleep(0.02)
    finally:
        it.stop(); reader.cleanup(); sys.stdout.write(SHOW+"\n"); sys.stdout.flush()

# ---------- Menu / entry ----------

def main():
    mode_two=False
    if len(sys.argv)>=2 and sys.argv[1] in ("2","--two","--2p"): mode_two=True
    elif len(sys.argv)<2:
        try:
            print("Swimming Simulator (Terminal Prototype)")
            print("1) One Player  [A/D stroke, S kick, W breathe]")
            print("2) Two Players [P2 uses J/L stroke, K kick, I breathe]")
            print("Q) Quit")
            sel=input("Select [1/2]: ").strip().lower()
            if sel=="2": mode_two=True
            elif sel=="q": return
        except (EOFError,KeyboardInterrupt): return
    game(mode_two)

if __name__ == "__main__":
    if os.name=="nt":
        try:
            import ctypes
            k=ctypes.windll.kernel32; h=k.GetStdHandle(-11); mode=ctypes.c_uint32()
            if k.GetConsoleMode(h, ctypes.byref(mode)):
                k.SetConsoleMode(h, mode.value | 0x0004)
        except Exception: pass
    main()
