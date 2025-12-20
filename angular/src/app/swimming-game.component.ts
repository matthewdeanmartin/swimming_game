import { Component, ElementRef, ViewChild, AfterViewInit, OnDestroy, HostListener } from '@angular/core';

// --- Configuration ---
const SCREEN_WIDTH = 1000;
const SCREEN_HEIGHT = 600;
const PIXELS_PER_METER = 20.0;
const POOL_LENGTH_METERS = 40.0;
const FINISH_LINE_X = POOL_LENGTH_METERS * PIXELS_PER_METER;
const MAX_BREATH_TIME = 17.0;
const FAST_CADENCE_THRESHOLD = 0.25;

// Colors
const COLORS = {
  WATER: '#148CC8',
  LANE_LINE: '#FFE600',
  TEXT: '#FFFFFF',
  RED: '#FF3232',
  GREEN: '#32FF32',
  BLUE: '#3232FF',
  PURPLE: '#C832C8',
  YELLOW: '#FFFF00',
  BREATH_GOOD: '#64FFFF',
  BREATH_BAD: '#FF3232',
};

// --- Utilities ---
const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(v, b));

interface ControlScheme {
  left: string;
  right: string;
  kick: string;
  breathe: string;
}

// --- Player Logic ---
class Player {
  name: string;
  keys: ControlScheme;
  color: string;
  laneY: number;

  // Physics State
  posX = 20.0;
  velocity = 0.0;
  stamina = 1.0;
  fatigue = 0.0;

  // 17 Second Rule
  breathTimer = MAX_BREATH_TIME;

  // Stroke Mechanics
  lastStrokeTime = 0.0;
  lastStrokeSide: 'L' | 'R' | null = null;
  strokeCount = 0;
  penaltyTimer = 0.0;

  // Game State
  drowned = false;
  finished = false;
  finishTime = 0.0;
  sinkOffset = 0.0;

  constructor(name: string, keys: ControlScheme, color: string, laneY: number) {
    this.name = name;
    this.keys = keys;
    this.color = color;
    this.laneY = laneY;
  }

  handleInput(code: string, now: number) {
    if (this.drowned || this.finished) return;

    if (code === this.keys.left) this.stroke('L', now);
    else if (code === this.keys.right) this.stroke('R', now);
    else if (code === this.keys.kick) this.kick();
    else if (code === this.keys.breathe) this.breathe();
  }

  private stroke(side: 'L' | 'R', now: number) {
    const dt = now - this.lastStrokeTime;
    const isMashing = dt < FAST_CADENCE_THRESHOLD;

    // Rhythm efficiency
    let efficiency = 0.8;
    if (this.lastStrokeTime > 0) {
      const target = 0.5;
      // Bell curve formula for timing bonus
      efficiency = Math.exp(-Math.pow(dt - target, 2) / (2 * Math.pow(0.1, 2)));
    }

    const altBonus = this.lastStrokeSide !== side ? 1.0 : 0.6;

    if (isMashing) {
      this.velocity -= 50.0;
      this.penaltyTimer = 0.5;
      this.fatigue = clamp(this.fatigue + 0.05, 0, 1);
    } else {
      let thrust = 80.0 * efficiency * altBonus;
      thrust *= (0.5 + 0.5 * this.stamina);
      thrust *= (1.0 - 0.5 * this.fatigue);
      this.velocity += thrust;
    }

    this.lastStrokeTime = now;
    this.lastStrokeSide = side;
    this.strokeCount++;

    this.stamina = clamp(this.stamina - 0.03, 0, 1);
    this.fatigue = clamp(this.fatigue + 0.01, 0, 1);
  }

  private kick() {
    this.velocity += 15.0 * this.stamina;
    this.stamina = clamp(this.stamina - 0.05, 0, 1);
  }

  private breathe() {
    this.breathTimer = MAX_BREATH_TIME;
    this.velocity *= 0.8;
    this.stamina = clamp(this.stamina + 0.1, 0, 1);
  }

  update(dt: number, currentTime: number) {
    if (this.finished) return;

    if (this.drowned) {
      this.velocity = 0;
      this.sinkOffset += 20 * dt;
      return;
    }

    // Breath Timer
    this.breathTimer -= dt;
    if (this.breathTimer <= 0) {
      this.drowned = true;
      this.breathTimer = 0;
    }

    // Recovery
    this.stamina = clamp(this.stamina + (dt * 0.05), 0, 1);
    this.fatigue = clamp(this.fatigue - (dt * 0.02), 0, 1);
    if (this.penaltyTimer > 0) this.penaltyTimer -= dt;

    // Drag
    let dragFactor = 2.0;
    if (this.breathTimer < 5.0) dragFactor += 1.0;

    const drag = this.velocity * dragFactor * dt;
    this.velocity -= drag;

    if (this.penaltyTimer <= 0 && this.velocity < 0) this.velocity = 0;

    // Move
    this.posX += this.velocity * dt;

    // Check Finish
    if (this.posX >= FINISH_LINE_X) {
      this.posX = FINISH_LINE_X;
      this.finished = true;
      this.finishTime = currentTime;
    }
  }

  draw(ctx: CanvasRenderingContext2D, offsetX: number) {
    const drawX = this.posX + offsetX;
    const drawY = this.laneY + (this.drowned ? this.sinkOffset : 0);
    const size = 32;

    if (drawX + size < 0 || drawX - size > SCREEN_WIDTH) return;

    ctx.save();

    // Drowning opacity
    if (this.drowned) {
       ctx.globalAlpha = Math.max(0, 1 - (this.sinkOffset / 100));
    }

    // Body (Circle)
    ctx.fillStyle = this.drowned ? '#555' : this.color;
    ctx.beginPath();
    ctx.arc(drawX, drawY, size, 0, Math.PI * 2);
    ctx.fill();

    // Nose
    ctx.fillStyle = '#FFF';
    ctx.beginPath();
    ctx.arc(drawX + size - 5, drawY, 5, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();

    // HUD
    const hudX = drawX - 30;
    const hudY = this.laneY - 50;

    if (this.drowned) {
      ctx.fillStyle = COLORS.RED;
      ctx.font = 'bold 16px Arial';
      ctx.fillText("DROWNED!", hudX, hudY);
    } else if (this.finished) {
      ctx.fillStyle = COLORS.LANE_LINE;
      ctx.font = 'bold 16px Arial';
      ctx.fillText(`FINISH! ${this.finishTime.toFixed(2)}s`, hudX, hudY);
    } else {
      const barW = 60;
      const barH = 8;

      // Breath Bar
      ctx.fillStyle = '#320000';
      ctx.fillRect(hudX, hudY, barW, barH);
      const breathPct = this.breathTimer / MAX_BREATH_TIME;
      ctx.fillStyle = breathPct > 0.3 ? COLORS.BREATH_GOOD : COLORS.BREATH_BAD;
      ctx.fillRect(hudX, hudY, barW * breathPct, barH);

      // Stamina Bar
      ctx.fillStyle = '#1e1e00';
      ctx.fillRect(hudX, hudY + 10, barW, 4);
      ctx.fillStyle = '#FFFF00';
      ctx.fillRect(hudX, hudY + 10, barW * this.stamina, 4);

      // Warnings
      ctx.font = 'bold 14px Arial';
      if (this.penaltyTimer > 0) {
        ctx.fillStyle = COLORS.RED;
        ctx.fillText("TOO FAST!", hudX + 70, hudY + 10);
      } else if (this.breathTimer < 5) {
        ctx.fillStyle = COLORS.RED;
        ctx.fillText("BREATHE!", hudX + 70, hudY + 10);
      }
    }
  }
}

// --- Angular Component ---
@Component({
  selector: 'app-swimming-game',
  templateUrl: './swimming-game.component.html',
  styleUrls: ['./swimming-game.component.css']
})
export class SwimmingGameComponent implements AfterViewInit, OnDestroy {

  @ViewChild('gameCanvas', { static: true })
  canvasRef!: ElementRef<HTMLCanvasElement>;

  // Game Properties
  private ctx!: CanvasRenderingContext2D;
  private animationFrameId: number = 0;
  private previousTime: number = 0;
  private players: Player[] = [];

  public gameState: 'playing' | 'winner' | 'drowned' = 'playing';
  public winnerName: string = '';
  public instructions = "P1: A/D Stroke, S Kick, W Breathe | P2: J/L Stroke, K Kick, I Breathe";

  ngAfterViewInit(): void {
    const canvas = this.canvasRef.nativeElement;
    canvas.width = SCREEN_WIDTH;
    canvas.height = SCREEN_HEIGHT;
    this.ctx = canvas.getContext('2d')!;

    this.initGame();

    // Start loop
    this.previousTime = performance.now();
    this.animationFrameId = requestAnimationFrame(this.gameLoop.bind(this));
  }

  ngOnDestroy(): void {
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
  }

  initGame() {
    this.players = [
      new Player("Red", { left: 'KeyA', right: 'KeyD', kick: 'KeyS', breathe: 'KeyW' }, COLORS.RED, 150),
      new Player("Blue", { left: 'KeyJ', right: 'KeyL', kick: 'KeyK', breathe: 'KeyI' }, COLORS.BLUE, 350)
    ];
    this.gameState = 'playing';
    this.winnerName = '';
    this.previousTime = performance.now();
  }

  @HostListener('window:keydown', ['$event'])
  handleKeyDown(event: KeyboardEvent) {
    if (event.repeat) return;

    // Handle Restart
    if (this.gameState !== 'playing' && event.code === 'Space') {
      this.initGame();
      return;
    }

    const now = performance.now() / 1000;
    this.players.forEach(p => p.handleInput(event.code, now));
  }

  gameLoop(time: number) {
    const dt = Math.min((time - this.previousTime) / 1000, 0.1);
    this.previousTime = time;

    this.update(dt, time / 1000);
    this.draw();

    this.animationFrameId = requestAnimationFrame(this.gameLoop.bind(this));
  }

  update(dt: number, totalTime: number) {
    if (this.gameState !== 'playing') return; // Pause updates if game over

    let activeWinner: Player | null = null;
    let allDrowned = true;

    this.players.forEach(p => {
      p.update(dt, totalTime);
      if (p.finished && !activeWinner) activeWinner = p;
      if (!p.drowned) allDrowned = false;
    });

    if (activeWinner) {
      this.gameState = 'winner';
      this.winnerName = (activeWinner as Player).name;
    } else if (allDrowned) {
      this.gameState = 'drowned';
    }
  }

  draw() {
    // 1. Clear & Background
    this.ctx.fillStyle = COLORS.WATER;
    this.ctx.fillRect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT);

    // 2. Camera Logic (Simple Follow)
    const leaderX = Math.max(...this.players.map(p => p.posX));
    let targetCamX = leaderX - 200;
    targetCamX = clamp(targetCamX, 0, FINISH_LINE_X - SCREEN_WIDTH + 100);
    const offsetX = -targetCamX;

    // 3. Draw Environment
    this.drawEnvironment(offsetX);

    // 4. Draw Players
    this.players.forEach(p => p.draw(this.ctx, offsetX));
  }

  drawEnvironment(offsetX: number) {
    // Finish Line
    const finishScreenX = FINISH_LINE_X + offsetX;
    if (finishScreenX > -50 && finishScreenX < SCREEN_WIDTH + 50) {
      this.ctx.fillStyle = '#000';
      this.ctx.fillRect(finishScreenX, 0, 20, SCREEN_HEIGHT);

      // Checkers
      for (let y = 0; y < SCREEN_HEIGHT; y += 20) {
        this.ctx.fillStyle = ((y / 20) % 2 === 0) ? '#FFF' : '#000';
        this.ctx.fillRect(finishScreenX, y, 20, 20);
      }

      this.ctx.fillStyle = '#FFF';
      this.ctx.font = 'bold 40px Arial';
      this.ctx.fillText("FINISH", finishScreenX - 30, 40);
    }

    // Distance Markers
    this.ctx.lineWidth = 1;
    this.ctx.strokeStyle = COLORS.LANE_LINE;
    this.ctx.fillStyle = '#FFF';
    this.ctx.font = 'bold 16px Arial';

    for (let m = 0; m <= POOL_LENGTH_METERS; m += 5) {
      const px = m * PIXELS_PER_METER + offsetX;
      if (px > 0 && px < SCREEN_WIDTH) {
        this.ctx.beginPath();
        this.ctx.moveTo(px, 0);
        this.ctx.lineTo(px, SCREEN_HEIGHT);
        this.ctx.stroke();
        this.ctx.fillText(`${m}m`, px + 5, SCREEN_HEIGHT - 30);
      }
    }
  }
}