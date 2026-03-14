"""
Ant Farm – Side View
All simulation and rendering runs in the browser via JS canvas.
No per-frame network traffic → zero flicker.
Run with:  streamlit run streamlit_app.py
"""
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Ant Farm", page_icon="🐜", layout="wide")
st.title("🐜 Ant Farm")

components.html("""
<!DOCTYPE html>
<html>
<head>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #111; color: #eee; font-family: monospace; }
  #ui {
    display: flex; align-items: center; flex-wrap: wrap;
    gap: 10px; padding: 8px 12px; background: #1a1a1a;
    border-bottom: 1px solid #333;
  }
  #ui label { font-size: 12px; color: #aaa; }
  #ui input[type=range] { width: 90px; }
  #ui span { font-size: 12px; color: #fff; min-width: 24px; display:inline-block; }
  button {
    padding: 5px 12px; border: none; border-radius: 4px;
    cursor: pointer; font-size: 13px; font-weight: bold;
  }
  #btnStart  { background: #2a9; color: #fff; }
  #btnStop   { background: #a44; color: #fff; }
  #btnReset  { background: #555; color: #fff; }
  #btnFood   { background: #a72; color: #fff; }
  #stats {
    display: flex; gap: 20px; padding: 6px 12px;
    background: #161616; border-bottom: 1px solid #333; font-size: 13px;
  }
  #stats span { color: #8cf; }
  canvas { display: block; }
</style>
</head>
<body>

<div id="ui">
  <label>Ants <span id="vAnts">20</span></label>
  <input type="range" id="sAnts" min="5" max="60" value="20">

  <label>Food <span id="vFood">25</span></label>
  <input type="range" id="sFood" min="5" max="80" value="25">

  <label>Width <span id="vW">100</span></label>
  <input type="range" id="sW" min="50" max="160" value="100">

  <label>Height <span id="vH">55</span></label>
  <input type="range" id="sH" min="30" max="90" value="55">

  <label>Speed <span id="vSpeed">1</span>x</label>
  <input type="range" id="sSpeed" min="1" max="8" value="1">

  <button id="btnStart">▶ Start</button>
  <button id="btnStop">⏹ Stop</button>
  <button id="btnReset">🔄 Reset</button>
  <button id="btnFood">🍎 +Food</button>
</div>

<div id="stats">
  Tick: <span id="sTick">0</span>
  &nbsp;|&nbsp; Food stored: <span id="sStored">0</span>
  &nbsp;|&nbsp; On surface: <span id="sSurface">0</span>
  &nbsp;|&nbsp; Carrying: <span id="sCarrying">0</span>
</div>

<canvas id="farm"></canvas>

<script>
// ── Enums ────────────────────────────────────────────────────────────────────
const Cell = Object.freeze({SKY:0, GRASS:1, DIRT:2, TUNNEL:3, NEST:4});
const AS   = Object.freeze({LEAVING:0, FORAGING:1, RETURNING:2, IN_NEST:3});

// ── Helpers ──────────────────────────────────────────────────────────────────
const rI = (a,b) => Math.floor(Math.random()*(b-a+1))+a;
const rC = a => a[Math.floor(Math.random()*a.length)];

// ── Ant ──────────────────────────────────────────────────────────────────────
class Ant {
  constructor(x,y) {
    this.x=x; this.y=y;
    this.state=AS.LEAVING; this.hasFood=false;
    this.dx=rC([-1,1]); this.dy=0;
  }
}

// ── World ────────────────────────────────────────────────────────────────────
class AntFarm {
  constructor(W, H, antCount, foodCount) {
    this.W=W; this.H=H;
    this.GY = Math.max(5, Math.floor(H/6));
    this.grid = Array.from({length:H}, ()=>new Uint8Array(W));
    this.food = new Set();
    this.foodStored=0; this.tick=0;
    this.ants=[];
    this.shade = Array.from({length:H}, ()=>
      Float32Array.from({length:W}, ()=>0.85+Math.random()*0.3));
    this.build();
    this.spawnFood(foodCount);
    this.spawnAnts(antCount);
  }

  build() {
    const {W,H,GY} = this;
    const cx = Math.floor(W/2);
    this.cx  = cx;
    this.nestY = GY + Math.max(8, Math.floor((H-GY)/3));

    for (let y=GY; y<H; y++)
      for (let x=0; x<W; x++) this.grid[y][x]=Cell.DIRT;
    for (let x=0; x<W; x++) this.grid[GY][x]=Cell.GRASS;

    // Nest chamber
    for (let dy=-2; dy<=2; dy++)
      for (let dx=-6; dx<=6; dx++) {
        const ny=this.nestY+dy, nx=cx+dx;
        if (ny>GY && ny<H && nx>=0 && nx<W) this.grid[ny][nx]=Cell.NEST;
      }

    // Main shaft
    for (let y=GY+1; y<this.nestY-2; y++) this.grid[y][cx]=Cell.TUNNEL;

    // Horizontal branches
    const br = Math.floor(W/4);
    for (let dx=1; dx<=br; dx++) {
      if (cx-dx>=0) this.grid[this.nestY][cx-dx]=Cell.TUNNEL;
      if (cx+dx<W)  this.grid[this.nestY][cx+dx]=Cell.TUNNEL;
    }

    // Side chambers
    for (const bx of [cx-br, cx+br]) {
      if (bx<0||bx>=W) continue;
      for (let dy=1; dy<=4; dy++) { const ny=this.nestY+dy; if(ny<H) this.grid[ny][bx]=Cell.TUNNEL; }
      for (let ddx=-2; ddx<=2; ddx++) {
        const sx=bx+ddx, ny=Math.min(H-1,this.nestY+4);
        if (sx>=0&&sx<W) this.grid[ny][sx]=Cell.TUNNEL;
      }
    }
  }

  inB(x,y)  { return x>=0&&x<this.W&&y>=0&&y<this.H; }
  pSurf(x,y){ return this.inB(x,y)&&(this.grid[y][x]===Cell.SKY||this.grid[y][x]===Cell.GRASS); }
  pUnder(x,y){ return this.inB(x,y)&&(this.grid[y][x]===Cell.TUNNEL||this.grid[y][x]===Cell.NEST); }

  stepTo(ax,ay,tx,ty,under) {
    const ok = under ? (x,y)=>this.pUnder(x,y) : (x,y)=>this.pSurf(x,y);
    const ddx = ax===tx?0:(tx>ax?1:-1);
    const ddy = ay===ty?0:(ty>ay?1:-1);
    for (const [nx,ny] of [[ax+ddx,ay+ddy],[ax+ddx,ay],[ax,ay+ddy],[ax-ddy,ay+ddx],[ax+ddy,ay-ddx]])
      if (ok(nx,ny)) return [nx,ny];
    const nb=[];
    for (let dx=-1;dx<=1;dx++) for(let dy=-1;dy<=1;dy++)
      if((dx||dy)&&ok(ax+dx,ay+dy)) nb.push([ax+dx,ay+dy]);
    return nb.length ? rC(nb) : [ax,ay];
  }

  spawnFood(n) {
    let placed=0, tries=0;
    while (placed<n && tries<n*40) {
      tries++;
      const x=rI(0,this.W-1), y=rI(0,this.GY-1), k=x+','+y;
      if (!this.food.has(k)) { this.food.add(k); placed++; }
    }
  }

  spawnAnts(n) {
    for (let i=0;i<n;i++) {
      const x=Math.max(0,Math.min(this.W-1,this.cx+rI(-4,4)));
      const y=Math.max(0,Math.min(this.H-1,this.nestY+rI(-1,1)));
      this.ants.push(new Ant(x,y));
    }
  }

  moveAnt(ant) {
    const GY=this.GY;
    if (ant.state===AS.LEAVING) {
      [ant.x,ant.y]=this.stepTo(ant.x,ant.y,this.cx,GY+1,true);
      if (ant.y===GY+1&&ant.x===this.cx) { ant.y=GY; ant.state=AS.FORAGING; ant.dx=rC([-1,1]); }

    } else if (ant.state===AS.FORAGING) {
      if (Math.random()<0.2) ant.dx=rC([-1,-1,0,1,1]);
      const ny=Math.random()>0.35?GY:Math.max(0,GY-rI(1,3));
      const nx=Math.max(0,Math.min(this.W-1,ant.x+ant.dx));
      if (this.pSurf(nx,ny)){ant.x=nx;ant.y=ny;}
      if (ant.x===0||ant.x===this.W-1) ant.dx=-ant.dx;
      for (const k of this.food) {
        const [fx,fy]=k.split(',').map(Number);
        if (Math.abs(fx-ant.x)<=1&&Math.abs(fy-ant.y)<=1) {
          this.food.delete(k); ant.hasFood=true; ant.state=AS.RETURNING; ant.dx=-ant.dx; break;
        }
      }

    } else if (ant.state===AS.RETURNING) {
      if (ant.y<=GY) {
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,this.cx,GY,false);
        if (ant.x===this.cx&&ant.y===GY) ant.y=GY+1;
      } else {
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,this.cx,this.nestY,true);
        if (this.grid[ant.y][ant.x]===Cell.NEST) { ant.state=AS.IN_NEST; ant.hasFood=false; this.foodStored++; }
      }

    } else if (ant.state===AS.IN_NEST) {
      if (Math.random()<0.15) ant.state=AS.LEAVING;
    }
  }

  dig() {
    if (Math.random()>0.04) return;
    const y=rI(this.GY+1,this.H-2), x=rI(1,this.W-2);
    if (this.grid[y][x]!==Cell.TUNNEL&&this.grid[y][x]!==Cell.NEST) return;
    for (const [dx,dy] of [[1,0],[-1,0],[0,1]].sort(()=>Math.random()-.5)) {
      const nx=x+dx, ny=y+dy;
      if (this.inB(nx,ny)&&this.grid[ny][nx]===Cell.DIRT) { this.grid[ny][nx]=Cell.TUNNEL; return; }
    }
  }

  update() {
    this.tick++;
    for (const ant of this.ants) this.moveAnt(ant);
    this.dig();
    if (this.tick%60===0) this.spawnFood(3);
  }
}

// ── Renderer ─────────────────────────────────────────────────────────────────
const SCALE = 10;

function render(farm, ctx) {
  const {W,H,GY} = farm;
  const iw=W*SCALE, ih=H*SCALE;
  const img = ctx.createImageData(iw, ih);
  const d   = img.data;

  const antMap = new Map();
  for (const ant of farm.ants) {
    const k=ant.x+','+ant.y;
    antMap.set(k, (antMap.get(k)||false)||ant.hasFood);
  }

  for (let gy=0; gy<H; gy++) {
    for (let gx=0; gx<W; gx++) {
      const cell = farm.grid[gy][gx];
      let r,g,b;

      if (cell===Cell.SKY) {
        const t=gy/Math.max(1,GY);
        r=135+Math.round(41*t); g=206+Math.round(20*t); b=235+Math.round(15*t);
      } else if (cell===Cell.GRASS) {
        const v=(gx*7+gy*3)%20; r=30; g=140+v; b=30;
      } else if (cell===Cell.DIRT) {
        const s=farm.shade[gy][gx];
        r=Math.min(255,101*s|0); g=Math.min(255,67*s|0); b=Math.min(255,33*s|0);
      } else if (cell===Cell.TUNNEL) {
        r=30; g=16; b=6;
      } else { // NEST
        const s=0.88+0.24*((gx+gy)%2);
        r=Math.min(255,160*s|0); g=Math.min(255,110*s|0); b=Math.min(255,20*s|0);
      }

      const k=gx+','+gy;
      const hasAnt=antMap.has(k);
      const hasFood=farm.food.has(k);
      const carrying=hasAnt&&antMap.get(k);
      const dotR2=Math.pow(Math.max(2,SCALE/3),2);
      const cx2=SCALE/2-0.5, cy2=SCALE/2-0.5;

      for (let sy=0; sy<SCALE; sy++) {
        for (let sx=0; sx<SCALE; sx++) {
          const dist2=(sx-cx2)*(sx-cx2)+(sy-cy2)*(sy-cy2);
          const base=(gy*SCALE+sy)*iw+(gx*SCALE+sx);
          const i=base*4;

          if ((hasAnt||hasFood) && dist2<=dotR2) {
            if (hasAnt)       { d[i]=carrying?255:15; d[i+1]=carrying?215:15; d[i+2]=carrying?0:15; }
            else if (hasFood) { d[i]=255; d[i+1]=50; d[i+2]=30; }
          } else if (cell===Cell.GRASS && sx===SCALE/2|0 && gx%3===0 && sy<SCALE-1) {
            d[i]=40; d[i+1]=200; d[i+2]=40;
          } else {
            d[i]=r; d[i+1]=g; d[i+2]=b;
          }
          d[i+3]=255;
        }
      }
    }
  }
  ctx.putImageData(img,0,0);
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
const canvas = document.getElementById('farm');
const ctx    = canvas.getContext('2d');
let farm, running=false, speed=1;

function getConfig() {
  return {
    W:    +document.getElementById('sW').value,
    H:    +document.getElementById('sH').value,
    ants: +document.getElementById('sAnts').value,
    food: +document.getElementById('sFood').value,
  };
}

function reset() {
  const c=getConfig();
  canvas.width  = c.W*SCALE;
  canvas.height = c.H*SCALE;
  farm = new AntFarm(c.W, c.H, c.ants, c.food);
  render(farm, ctx);
  updateStats();
}

function updateStats() {
  document.getElementById('sTick').textContent    = farm.tick;
  document.getElementById('sStored').textContent  = farm.foodStored;
  document.getElementById('sSurface').textContent = farm.food.size;
  document.getElementById('sCarrying').textContent= farm.ants.filter(a=>a.hasFood).length;
}

// Slider live labels
for (const [sid, vid] of [['sAnts','vAnts'],['sFood','vFood'],['sW','vW'],['sH','vH'],['sSpeed','vSpeed']]) {
  document.getElementById(sid).addEventListener('input', e => {
    document.getElementById(vid).textContent = e.target.value;
    if (sid==='sSpeed') speed = +e.target.value;
  });
}

document.getElementById('btnStart').onclick  = () => { running=true;  };
document.getElementById('btnStop').onclick   = () => { running=false; };
document.getElementById('btnReset').onclick  = () => { running=false; reset(); };
document.getElementById('btnFood').onclick   = () => { if(farm) farm.spawnFood(10); };

// Animation loop
let last=0;
const MS_PER_TICK = 300;

function loop(ts) {
  requestAnimationFrame(loop);
  if (!farm||!running) return;
  if (ts-last < MS_PER_TICK) return;
  last=ts;
  for (let i=0;i<speed;i++) farm.update();
  render(farm,ctx);
  updateStats();
}

reset();
requestAnimationFrame(loop);
</script>
</body>
</html>
""", height=700, scrolling=False)
