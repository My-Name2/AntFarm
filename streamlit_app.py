"""
Ant Farm – Scientifically-informed side-view simulation.
Run with:  streamlit run streamlit_app.py
"""
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Ant Farm", page_icon="🐜", layout="wide")
st.title("🐜 Ant Farm")

components.html(r"""
<!DOCTYPE html><html><head>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#111;color:#eee;font-family:monospace;overflow:hidden}
#ui{display:flex;align-items:center;flex-wrap:wrap;gap:7px;padding:5px 10px;
    background:#1a1a1a;border-bottom:1px solid #333}
label{font-size:11px;color:#aaa}
input[type=range]{width:75px;vertical-align:middle}
.val{font-size:11px;color:#fff;min-width:20px;display:inline-block}
button{padding:3px 9px;border:none;border-radius:3px;cursor:pointer;font-size:12px;font-weight:bold}
#btnStart{background:#2a9;color:#fff}#btnStop{background:#a44;color:#fff}
#btnReset{background:#555;color:#fff}#btnFood{background:#a72;color:#fff}
#stats{display:flex;gap:12px;padding:3px 10px;background:#161616;
       border-bottom:1px solid #333;font-size:11px;flex-wrap:wrap}
#stats b{color:#8cf}
#legend{display:flex;gap:12px;padding:3px 10px;background:#0e0e0e;
        border-bottom:1px solid #222;font-size:10px;flex-wrap:wrap}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:3px;vertical-align:middle}
canvas{display:block}
</style></head><body>

<div id="ui">
  <label>Ants <span class="val" id="vAnts">25</span></label>
  <input type="range" id="sAnts" min="5" max="60" value="25">
  <label>Food <span class="val" id="vFood">35</span></label>
  <input type="range" id="sFood" min="5" max="80" value="35">
  <label>Width <span class="val" id="vW">120</span></label>
  <input type="range" id="sW" min="60" max="180" value="120">
  <label>Height <span class="val" id="vH">65</span></label>
  <input type="range" id="sH" min="40" max="100" value="65">
  <label>Speed <span class="val" id="vSpeed">1</span>x</label>
  <input type="range" id="sSpeed" min="1" max="10" value="1">
  <button id="btnStart">▶ Start</button>
  <button id="btnStop">⏹ Stop</button>
  <button id="btnReset">🔄 Reset</button>
  <button id="btnFood">🍎 +Food</button>
</div>

<div id="stats">
  Day <b id="sDay">1</b> <span id="sPhase">☀️ Noon</span> |
  Tick <b id="sTick">0</b> |
  Colony <b id="sPop">0</b> |
  Brood <b id="sBrood">0</b> |
  Food stored <b id="sStored">0</b> |
  Surface food <b id="sSurf">0</b> |
  Predators <b id="sPred">0</b>
</div>

<div id="legend">
  <span><span class="dot" style="background:#111;border:1px solid #888"></span>Worker</span>
  <span><span class="dot" style="background:#7ef"></span>Nurse</span>
  <span><span class="dot" style="background:#ff8c00"></span>Digger</span>
  <span><span class="dot" style="background:#e00"></span>Soldier</span>
  <span><span class="dot" style="background:#d050d0"></span>Queen</span>
  <span><span class="dot" style="background:#fff"></span>Egg</span>
  <span><span class="dot" style="background:#ffe080"></span>Larva/Pupa</span>
  <span><span class="dot" style="background:#f32"></span>Food</span>
  <span><span class="dot" style="background:#f60;border:2px solid #900"></span>Predator</span>
  <span style="color:#4af">■ Trail pheromone</span>
  <span style="color:#f44">■ Alarm pheromone</span>
  <span style="color:#da4">■ Repellent (depleted)</span>
</div>

<canvas id="farm"></canvas>

<script>
// ═══════════════════════════════════════════════════════════════════
//  CONSTANTS
// ═══════════════════════════════════════════════════════════════════
const Cell = Object.freeze({
  SKY:0, GRASS:1, DIRT:2, TUNNEL:3,
  QUEEN_CH:4,   // queen's central chamber
  NURSERY:5,    // upper brood chamber
  FOOD_ST:6,    // food storage chamber
  MIDDEN:7      // waste dump (near entrance, surface-adjacent)
});

const AT = Object.freeze({  // ant types
  QUEEN:0, NURSE:1, FORAGER:2, SOLDIER:3, DIGGER:4,
  EGG:5, LARVA:6, PUPA:7
});

const AS = Object.freeze({  // ant states
  IN_NEST:0, NURSING:1, LEAVING:2, FORAGING:3, RETURNING:4,
  DIGGING:5, GUARDING:6, CHASING:7, FLEEING:8, PHRAGMOSIS:9
});

const DAY_LEN  = 700;   // ticks per full day
const MAX_ANTS = 90;
const SCALE    = 9;

// Deneubourg model exponent for trail following
const TRAIL_K  = 0.5;   // base attractiveness
const TRAIL_N  = 2.0;   // amplification exponent

// Pheromone decay per tick
const TRAIL_DECAY = 0.992;  // trail lasts ~125 ticks
const ALARM_DECAY = 0.82;   // alarm fades in ~5 ticks
const BROOD_DECAY = 0.96;   // brood pheromone ~25 ticks
const REPEL_DECAY = 0.985;  // repellent marks exhausted food areas (~65 tick half-life)

// ═══════════════════════════════════════════════════════════════════
//  UTILITIES
// ═══════════════════════════════════════════════════════════════════
const rI  = (a,b)  => Math.floor(Math.random()*(b-a+1))+a;
const rC  = arr    => arr[Math.floor(Math.random()*arr.length)];
const clamp = (v,lo,hi) => Math.max(lo, Math.min(hi, v));
const lerp  = (a,b,t)   => a + (b-a)*t;

function weightedChoice(items, weights) {
  let sum = 0; for (const w of weights) sum += w;
  let r = Math.random()*sum;
  for (let i=0;i<items.length;i++) { r-=weights[i]; if(r<=0) return items[i]; }
  return items[items.length-1];
}

// ═══════════════════════════════════════════════════════════════════
//  SKY COLOURS  (midnight→dawn→noon→dusk cycle)
// ═══════════════════════════════════════════════════════════════════
const SKY_STOPS = [
  [3,3,25],       // 0.00  midnight
  [255,130,40],   // 0.25  dawn
  [90,170,255],   // 0.50  noon
  [240,75,15],    // 0.75  dusk
  [3,3,25],       // 1.00  midnight
];
function skyRGB(phase, yFrac) {
  const n=SKY_STOPS.length-1, fp=phase*n;
  const i=Math.floor(fp), t=fp-i;
  const [r1,g1,b1]=SKY_STOPS[clamp(i,0,n)];
  const [r2,g2,b2]=SKY_STOPS[clamp(i+1,0,n)];
  const d=1-yFrac*0.2;
  return [Math.round(lerp(r1,r2,t)*d), Math.round(lerp(g1,g2,t)*d), Math.round(lerp(b1,b2,t)*d)];
}

// ═══════════════════════════════════════════════════════════════════
//  ANT
// ═══════════════════════════════════════════════════════════════════
class Ant {
  constructor(x,y,type=AT.FORAGER) {
    this.x=x; this.y=y; this.type=type;
    this.age=0;
    this.hasFood=false; this.foodQuality=1;
    this.dx=rC([-1,1]); this.dy=0;
    this.alarmLevel=0;
    this.digTarget=null;
    this.fleeTimer=0;
    this.phragmosisTimer=0;   // blocks tunnel entrance

    // Developmental timers
    if      (type===AT.EGG)  { this.hatchIn=rI(55,80);  this.state=AS.IN_NEST; this.hunger=0; }
    else if (type===AT.LARVA){ this.hatchIn=rI(90,130);  this.state=AS.IN_NEST; this.hunger=rI(20,60); }
    else if (type===AT.PUPA) { this.hatchIn=rI(70,100);  this.state=AS.IN_NEST; this.hunger=0; }
    else if (type===AT.QUEEN){ this.state=AS.IN_NEST; this.hatchIn=0; }
    else if (type===AT.NURSE){ this.state=AS.NURSING; this.hatchIn=0; }
    else                     { this.state=AS.LEAVING; this.hatchIn=0; }
  }
}

// ═══════════════════════════════════════════════════════════════════
//  PREDATOR
// ═══════════════════════════════════════════════════════════════════
class Predator {
  constructor(x,y,type='spider') {
    this.x=x; this.y=y; this.type=type; // 'spider' | 'beetle'
    this.dx=rC([-1,1]); this.alive=true; this.kills=0; this.stunTimer=0;
  }
}

// ═══════════════════════════════════════════════════════════════════
//  ANTFARM
// ═══════════════════════════════════════════════════════════════════
class AntFarm {
  constructor(W,H,antCount,foodCount) {
    this.W=W; this.H=H;
    this.GY=Math.max(6, Math.floor(H/6));

    // Grid
    this.grid = Array.from({length:H}, ()=>new Uint8Array(W));

    // Pheromone layers (flat Float32Arrays, index = y*W+x)
    this.trail = new Float32Array(W*H);   // foraging trail (cyan glow)
    this.alarm = new Float32Array(W*H);   // alarm (red glow)
    this.brood = new Float32Array(W*H);   // brood/larvae pheromone (attracts nurses)
    this.repellent = new Float32Array(W*H); // marks depleted food zones (diverts foragers)

    // State
    this.food = new Map();   // "x,y" → quality (1-3)
    this.foodStored=0; this.tick=0;
    this.ants=[]; this.predators=[];
    this.midden=new Set();   // "x,y" cells of waste pile

    // Dirt texture
    this.shade=Array.from({length:H},()=>
      Float32Array.from({length:W},()=>0.80+Math.random()*0.40));

    // Stars
    this.stars=Array.from({length:70},()=>
      ({x:rI(0,W-1), y:rI(0,Math.max(1,this.GY-2)), br:Math.random()}));

    // Timers
    this.queenTimer=0; this.foodTimer=0; this.rainTimer=rI(800,1600);
    this.raining=false; this.rainLeft=0;
    this.nestInfo={}; // stores chamber coords for UI

    this.build();
    this.spawnFood(foodCount);
    this.initColony(antCount);
  }

  // ── WORLD BUILD ──────────────────────────────────────────────────
  build() {
    const{W,H,GY}=this;
    const cx=Math.floor(W/2);
    this.cx=cx;

    // Fill underground
    for(let y=GY;y<H;y++) for(let x=0;x<W;x++) this.grid[y][x]=Cell.DIRT;
    for(let x=0;x<W;x++) this.grid[GY][x]=Cell.GRASS;

    // ── Chamber layout (depth-based, biologically accurate) ──────
    // Real ants: brood near top (warmest underground), queen central,
    // food storage mid-level, waste near entrance or deep side tunnel.

    const shaftBase = GY+1;
    const nurseryY  = GY + Math.max(5, Math.floor((H-GY)*0.22));
    const queenY    = GY + Math.max(9, Math.floor((H-GY)*0.42));
    const foodStY   = GY + Math.max(12, Math.floor((H-GY)*0.58));

    this.nestInfo = {cx, GY, nurseryY, queenY, foodStY};

    // Entrance shaft (vertical, single-width — realistic bottleneck)
    for(let y=shaftBase;y<nurseryY-2;y++) this.grid[y][cx]=Cell.TUNNEL;

    // Nursery chamber (upper, warm)  — 3 rows × 11 cols
    this._fillChamber(cx, nurseryY, 5, 1, Cell.NURSERY);

    // Short shaft nursery→queen
    for(let y=nurseryY+2;y<queenY-2;y++) this.grid[y][cx]=Cell.TUNNEL;

    // Queen's chamber (central)  — 3 rows × 15 cols
    this._fillChamber(cx, queenY, 7, 2, Cell.QUEEN_CH);

    // Food storage  (lower right)
    this._fillChamber(cx+Math.floor(W/6), foodStY, 5, 2, Cell.FOOD_ST);

    // Shaft queen→food store
    for(let y=queenY+3;y<foodStY-1;y++) {
      const bx=cx+Math.floor((y-queenY)*W/6/(foodStY-queenY));
      if(this.inB(bx,y)) this.grid[y][bx]=Cell.TUNNEL;
    }

    // Midden tunnel (waste dump — goes sideways toward surface)
    const midX=cx-Math.floor(W/5);
    for(let y=nurseryY;y>GY+1;y--){
      const mx=cx+Math.floor((cx-midX)*(nurseryY-y)/(nurseryY-GY-1));
      if(this.inB(mx,y)) this.grid[y][mx]=Cell.TUNNEL;
    }
    // Midden pile on surface
    for(let dx=-2;dx<=2;dx++){
      const mx=clamp(midX+dx,0,W-1);
      this.midden.add(mx+','+GY);
    }

    // Side exploration tunnels from queen's chamber
    const brLen=Math.floor(W/5);
    for(let dx=1;dx<=brLen;dx++){
      if(cx-dx>=0) this.grid[queenY][cx-dx]=Cell.TUNNEL;
      if(cx+dx<W)  this.grid[queenY][cx+dx]=Cell.TUNNEL;
    }
    // Branch shafts going down
    for(const bx of [cx-brLen, cx+brLen]){
      if(bx<1||bx>=W-1) continue;
      for(let dy=1;dy<=6;dy++){
        const ny=queenY+dy; if(ny<H) this.grid[ny][bx]=Cell.TUNNEL;
      }
      for(let ddx=-3;ddx<=3;ddx++){
        const sx=bx+ddx, ny=Math.min(H-2,queenY+6);
        if(sx>0&&sx<W) this.grid[ny][sx]=Cell.TUNNEL;
      }
    }

    this.cx=cx;
  }

  _fillChamber(cx,cy,rx,ry,type){
    const{H,GY}=this;
    for(let dy=-ry;dy<=ry;dy++)
      for(let dx=-rx;dx<=rx;dx++){
        const nx=cx+dx, ny=cy+dy;
        if(nx>0&&nx<this.W-1&&ny>GY&&ny<H) this.grid[ny][nx]=type;
      }
  }

  // ── HELPERS ──────────────────────────────────────────────────────
  inB(x,y){ return x>=0&&x<this.W&&y>=0&&y<this.H; }
  idx(x,y){ return y*this.W+x; }
  pSurf(x,y){
    return this.inB(x,y)&&(this.grid[y][x]===Cell.SKY||this.grid[y][x]===Cell.GRASS);
  }
  pUnder(x,y){
    const c=this.grid[y]?.[x];
    return this.inB(x,y)&&c!==Cell.SKY&&c!==Cell.GRASS&&c!==Cell.DIRT;
  }
  isDirt(x,y){ return this.inB(x,y)&&this.grid[y][x]===Cell.DIRT; }

  // Simple greedy step toward target through passable cells
  stepTo(ax,ay,tx,ty,under){
    const ok=under?(x,y)=>this.pUnder(x,y):(x,y)=>this.pSurf(x,y);
    const ddx=ax===tx?0:(tx>ax?1:-1);
    const ddy=ay===ty?0:(ty>ay?1:-1);
    const cands=[[ax+ddx,ay+ddy],[ax+ddx,ay],[ax,ay+ddy],[ax-ddy,ay+ddx],[ax+ddy,ay-ddx]];
    for(const[nx,ny]of cands) if(ok(nx,ny)) return[nx,ny];
    const nb=[];
    for(let dx=-1;dx<=1;dx++) for(let dy=-1;dy<=1;dy++)
      if((dx||dy)&&ok(ax+dx,ay+dy)) nb.push([ax+dx,ay+dy]);
    return nb.length?rC(nb):[ax,ay];
  }

  // Deneubourg probabilistic step following trail pheromone (foragers)
  trailStep(ax,ay){
    const{W,GY}=this;
    const nb=[];
    for(let dx=-1;dx<=1;dx++) for(let dy=-1;dy<=1;dy++){
      if(!dx&&!dy) continue;
      const nx=ax+dx, ny=ay+dy;
      if(this.pSurf(nx,ny)) nb.push([nx,ny]);
    }
    if(!nb.length) return[ax,ay];
    // Weight = (k + trail)^n / (1 + repellent)  — Deneubourg + repellent avoidance
    const weights=nb.map(([nx,ny])=>{
      const i=this.idx(nx,ny);
      const t=this.trail[i];
      const rep=this.repellent[i];
      return Math.pow(TRAIL_K + t, TRAIL_N) * Math.max(0.05, 1-rep*0.035);
    });
    return weightedChoice(nb,weights);
  }

  // ── SPAWNING ─────────────────────────────────────────────────────
  spawnFood(n){
    let placed=0,tries=0;
    while(placed<n&&tries<n*60&&this.food.size<90){
      tries++;
      const x=rI(1,this.W-2), y=rI(0,this.GY-1), k=x+','+y;
      if(!this.food.has(k)){ this.food.set(k,rI(1,3)); placed++; }
    }
  }

  initColony(n){
    const{cx,nestInfo:{nurseryY,queenY}}=this;
    // Queen in queen's chamber
    this.ants.push(new Ant(cx, queenY, AT.QUEEN));

    // Initial brood in nursery
    for(let i=0;i<6;i++){
      const t=rC([AT.EGG,AT.EGG,AT.LARVA]);
      this.ants.push(new Ant(clamp(cx+rI(-4,4),1,this.W-2),
                             clamp(nurseryY+rI(-1,1),this.GY+1,this.H-2), t));
    }

    // Nurses (young)
    for(let i=0;i<Math.max(2,Math.floor(n*0.2));i++){
      const a=new Ant(clamp(cx+rI(-3,3),1,this.W-2),nurseryY,AT.NURSE);
      a.age=rI(0,20); this.ants.push(a);
    }
    // Diggers
    for(let i=0;i<Math.max(1,Math.floor(n*0.25));i++){
      const a=new Ant(clamp(cx+rI(-4,4),1,this.W-2),
                      clamp(queenY+rI(-1,1),this.GY+1,this.H-2),AT.DIGGER);
      this.ants.push(a);
    }
    // Foragers (bulk)
    const rem=n-this.ants.filter(a=>a.type<=AT.DIGGER).length+1;
    for(let i=0;i<rem;i++){
      const a=new Ant(clamp(cx+rI(-4,4),1,this.W-2),
                      clamp(queenY+rI(-1,1),this.GY+1,this.H-2),AT.FORAGER);
      a.age=rI(30,60); this.ants.push(a);
    }
  }

  // ── DAY / NIGHT ───────────────────────────────────────────────────
  dayPhase(){ return (this.tick%DAY_LEN)/DAY_LEN; }
  isDay(){ const p=this.dayPhase(); return p>0.22&&p<0.78; }
  nightFade(){
    const p=this.dayPhase();
    if(p<0.22) return 1-p/0.22;
    if(p>0.78) return (p-0.78)/0.22;
    return 0;
  }

  // ── ANT BEHAVIOUR ─────────────────────────────────────────────────
  moveAnt(ant){
    const{GY,cx,nestInfo}=this;
    ant.age++;
    ant.alarmLevel=Math.max(0, ant.alarmLevel-0.1);

    // ── Brood: develop in place, emit brood pheromone ──────────────
    if(ant.type===AT.EGG||ant.type===AT.LARVA||ant.type===AT.PUPA){
      // Emit brood pheromone — larvae emit more when hungry (hunger-signalling)
      const i=this.idx(ant.x,ant.y);
      if(ant.type===AT.LARVA){
        ant.hunger=Math.min(100,(ant.hunger||0)+0.3);
        this.brood[i]=Math.min(100, this.brood[i]+(1.0+ant.hunger*0.025));
      } else {
        this.brood[i]=Math.min(80, this.brood[i]+1.2);
      }
      // Development (faster if nurse nearby)
      let nurseBonus=1;
      for(const other of this.ants){
        if(other.type===AT.NURSE&&Math.abs(other.x-ant.x)<=2&&Math.abs(other.y-ant.y)<=1)
          { nurseBonus=1.8; break; }
      }
      if(ant.age >= ant.hatchIn/nurseBonus){
        if(ant.type===AT.EGG){
          ant.type=AT.LARVA; ant.age=0; ant.hatchIn=rI(90,130);
        } else if(ant.type===AT.LARVA){
          ant.type=AT.PUPA; ant.age=0; ant.hatchIn=rI(65,95);
        } else {
          // Eclosion: become adult — age polyethism (young=nurse first)
          const nurses=this.ants.filter(a=>a.type===AT.NURSE).length;
          const foragers=this.ants.filter(a=>a.type===AT.FORAGER).length;
          const soldiers=this.ants.filter(a=>a.type===AT.SOLDIER).length;
          // Colony decides role based on current needs
          if(nurses < Math.floor(this.ants.length*0.15))
            ant.type=AT.NURSE;
          else if(soldiers < 2 && this.foodStored>15)
            ant.type=AT.SOLDIER;
          else if(foragers < this.ants.length*0.4)
            ant.type=AT.FORAGER;
          else
            ant.type=rC([AT.FORAGER,AT.FORAGER,AT.DIGGER]);
          ant.state=ant.type===AT.NURSE?AS.NURSING:AS.LEAVING;
          ant.age=0; ant.hatchIn=0;
        }
      }
      return;
    }

    // ── Queen: lay eggs when fed ───────────────────────────────────
    if(ant.type===AT.QUEEN){
      this.queenTimer++;
      const layRate=Math.max(60, 120 - this.foodStored);
      if(this.queenTimer>=layRate && this.ants.length<MAX_ANTS && this.foodStored>2){
        this.queenTimer=0;
        this.foodStored=Math.max(0,this.foodStored-1);
        const ex=clamp(ant.x+rI(-3,3),1,this.W-2);
        const ey=clamp(nestInfo.nurseryY+rI(-1,1),GY+1,this.H-2);
        this.ants.push(new Ant(ex,ey,AT.EGG));
      }
      return;
    }

    // ── Phragmosis: soldier blocking entrance ─────────────────────
    if(ant.state===AS.PHRAGMOSIS){
      ant.phragmosisTimer--;
      if(ant.phragmosisTimer<=0) ant.state=AS.GUARDING;
      return;
    }

    // ── Alarm sensing — 3-zone cascade (Oecophylla model) ─────────
    const alarmHere=this.alarm[this.idx(ant.x,ant.y)];
    // Soldiers detect alarm at 2x sensitivity (lower detection threshold)
    const alarmThresh=ant.type===AT.SOLDIER?2.5:5;
    if(alarmHere>alarmThresh){
      ant.alarmLevel=Math.min(1, ant.alarmLevel+alarmHere/80);
    }
    // Zone 3 (high alarm, >35): workers also release alarm — positive feedback cascade
    if(alarmHere>35&&ant.type!==AT.SOLDIER&&ant.y<=this.GY){
      const ai=this.idx(ant.x,ant.y);
      this.alarm[ai]=Math.min(100, this.alarm[ai]+10);
    }

    // ── Flee if worker with high alarm ───────────────────────────
    if(ant.type!==AT.SOLDIER&&ant.alarmLevel>0.6&&ant.y<=GY){
      ant.state=AS.FLEEING; ant.fleeTimer=rI(6,14);
    }
    if(ant.state===AS.FLEEING){
      ant.fleeTimer--;
      // Run away from nearest predator
      const pred=this.predators.find(p=>Math.abs(p.x-ant.x)<=6&&p.alive);
      if(pred){ ant.dx=ant.x>pred.x?1:-1; }
      const nx=clamp(ant.x+ant.dx,0,this.W-1);
      if(this.pSurf(nx,GY)){ant.x=nx;ant.y=GY;}
      if(ant.fleeTimer<=0) ant.state=AS.FORAGING;
      return;
    }

    // ── Nurse ─────────────────────────────────────────────────────
    if(ant.type===AT.NURSE){
      this._moveNurse(ant); return;
    }

    // ── Soldier ──────────────────────────────────────────────────
    if(ant.type===AT.SOLDIER){
      this._moveSoldier(ant); return;
    }

    // ── Digger ───────────────────────────────────────────────────
    if(ant.type===AT.DIGGER&&ant.state===AS.DIGGING){
      this._digStep(ant); return;
    }

    // ── LEAVING: head from nest to surface ────────────────────────
    if(ant.state===AS.LEAVING){
      // Slow down at night; rain strongly suppresses foraging (Hölldobler & Wilson)
      if(!this.isDay()&&Math.random()<0.6) return;
      if(this.raining&&Math.random()<0.88) return;
      [ant.x,ant.y]=this.stepTo(ant.x,ant.y,cx,GY+1,true);
      if(ant.y===GY+1&&ant.x===cx){
        ant.y=GY;
        if(ant.type===AT.DIGGER){
          ant.state=AS.DIGGING; ant.digTarget=this._findDigFrontier();
        } else {
          ant.state=AS.FORAGING; ant.dx=rC([-1,1]);
        }
      }
      return;
    }

    // ── FORAGING: probabilistic trail-following ───────────────────
    if(ant.state===AS.FORAGING){
      // Trophallaxis: if passing another ant with food in tunnel, share
      if(ant.y>GY){
        for(const o of this.ants){
          if(o!==ant&&o.hasFood&&o.x===ant.x&&o.y===ant.y&&Math.random()<0.25){
            ant.hasFood=true; ant.foodQuality=o.foodQuality;
            o.hasFood=false; ant.state=AS.RETURNING; return;
          }
        }
        // Head to surface through tunnels
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,cx,GY,true);
        if(ant.x===cx&&ant.y===GY) ant.y=GY-1>0?GY-1:GY;
        return;
      }

      // Rain: retreat immediately — ants wait inside on stored reserves
      if(this.raining){ ant.state=AS.RETURNING; return; }

      // On surface: use Deneubourg trail model
      const prevX=ant.x, prevY=ant.y;
      if(Math.random()<0.15) ant.dx=rC([-1,-1,0,1,1]);
      [ant.x,ant.y]=this.trailStep(ant.x,ant.y);
      if(ant.x===prevX&&ant.y===prevY){
        // Fallback: simple walk
        const nx=clamp(prevX+ant.dx,0,this.W-1);
        if(this.pSurf(nx,GY)){ant.x=nx;ant.y=GY;}
        else ant.dx=-ant.dx;
      }
      if(ant.x===0||ant.x===this.W-1) ant.dx=-ant.dx;

      // Sense alarm → release more alarm, start fleeing
      if(ant.alarmLevel>0.5){
        this.alarm[this.idx(ant.x,ant.y)]=Math.min(100,
          this.alarm[this.idx(ant.x,ant.y)]+20);
      }

      // Pick up food (sense within 1 cell)
      for(const[k,q]of this.food){
        const[fx,fy]=k.split(',').map(Number);
        if(Math.abs(fx-ant.x)<=1&&Math.abs(fy-ant.y)<=1){
          this.food.delete(k);
          ant.hasFood=true; ant.foodQuality=q;
          ant.state=AS.RETURNING; ant.dx=-ant.dx;
          // Deposit repellent at pickup site — marks partially-exhausted area
          const ri=this.idx(fx,fy);
          this.repellent[ri]=Math.min(60, this.repellent[ri]+18);
          break;
        }
      }
      return;
    }

    // ── RETURNING: lay trail pheromone proportional to food quality ─
    if(ant.state===AS.RETURNING){
      // Deposit trail pheromone at every step
      const ii=this.idx(ant.x,ant.y);
      const deposit=12*ant.foodQuality;  // higher quality → stronger trail
      this.trail[ii]=Math.min(200, this.trail[ii]+deposit);

      if(ant.y<=GY){
        // On surface: head to entrance
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,cx,GY,false);
        if(ant.x===cx&&ant.y===GY) ant.y=GY+1;
      } else {
        // Underground: head to food storage chamber
        const{foodStY}=nestInfo;
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,cx,foodStY,true);
        const c=this.grid[ant.y]?.[ant.x];
        if(c===Cell.FOOD_ST||c===Cell.QUEEN_CH){
          this.foodStored+=ant.foodQuality;
          ant.hasFood=false; ant.state=AS.IN_NEST;
        }
      }
      return;
    }

    // ── IN_NEST: rest briefly then leave ─────────────────────────
    if(ant.state===AS.IN_NEST){
      if(Math.random()<0.10) ant.state=AS.LEAVING;
    }
  }

  // ── NURSE BEHAVIOUR ───────────────────────────────────────────────
  _moveNurse(ant){
    const{nurseryY}=this.nestInfo;
    // Follow brood pheromone gradient in nursery
    const nb=[];
    for(let dx=-1;dx<=1;dx++) for(let dy=-1;dy<=1;dy++){
      if(!dx&&!dy) continue;
      const nx=ant.x+dx, ny=ant.y+dy;
      if(this.pUnder(nx,ny)) nb.push([nx,ny,this.brood[this.idx(nx,ny)]]);
    }
    if(!nb.length) return;
    // Move toward highest brood pheromone (with some randomness)
    nb.sort((a,b)=>b[2]-a[2]);
    if(Math.random()<0.7&&nb[0][2]>2)
      [ant.x,ant.y]=[nb[0][0],nb[0][1]];
    else
      [ant.x,ant.y]=rC(nb).slice(0,2);

    // Trophallaxis: feed hungry larvae from colony food reserve (social stomach)
    for(const larva of this.ants){
      if(larva.type===AT.LARVA&&(larva.hunger||0)>30&&
         Math.abs(larva.x-ant.x)<=1&&Math.abs(larva.y-ant.y)<=1&&this.foodStored>0){
        larva.hunger=Math.max(0,(larva.hunger||0)-30);
        this.foodStored=Math.max(0,this.foodStored-0.5);
        break;
      }
    }

    // Age polyethism: old enough nurses become foragers
    if(ant.age>60&&Math.random()<0.005){
      ant.type=AT.FORAGER; ant.state=AS.LEAVING;
    }
  }

  // ── SOLDIER BEHAVIOUR ─────────────────────────────────────────────
  _moveSoldier(ant){
    const{GY,cx}=this;
    const alarmHere=this.alarm[this.idx(ant.x,ant.y)];

    // Phragmosis: block entrance when under heavy assault
    if(ant.x===cx&&ant.y===GY+1&&this.alarm[this.idx(cx,GY)]>60){
      ant.state=AS.PHRAGMOSIS; ant.phragmosisTimer=rI(15,30); return;
    }

    // Chase nearest predator with alarm signal
    const pred=this.predators.find(p=>p.alive&&
      Math.abs(p.x-ant.x)<=12&&Math.abs(p.y-ant.y)<=3);
    if(pred||alarmHere>15){
      const target=pred||{x:cx,y:GY};
      if(ant.y<=GY){
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,target.x,target.y,false);
        // Attack: stun predator
        if(pred&&Math.abs(ant.x-pred.x)<=1){
          pred.stunTimer=rI(8,20);
          this.alarm[this.idx(ant.x,ant.y)]=Math.min(100,
            this.alarm[this.idx(ant.x,ant.y)]+5);
          if(pred.stunTimer>40) pred.alive=false;  // killed after sustained attack
        }
      } else {
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,cx,GY+1,true);
        if(ant.y===GY+1&&ant.x===cx) ant.y=GY;
      }
    } else {
      // Patrol near entrance on surface
      if(ant.y<=GY){
        if(Math.random()<0.15) ant.dx=rC([-1,1]);
        const nx=clamp(ant.x+ant.dx,clamp(cx-18,0,this.W-1),clamp(cx+18,0,this.W-1));
        if(this.pSurf(nx,GY)){ant.x=nx;ant.y=GY;}
      } else {
        ant.y=GY;
      }
    }
  }

  // ── DIGGER BEHAVIOUR ──────────────────────────────────────────────
  _findDigFrontier(){
    // Weighted toward digging down and outward, away from existing chambers
    const candidates=[];
    for(let y=this.GY+2;y<this.H-2;y++)
      for(let x=2;x<this.W-2;x++){
        const c=this.grid[y][x];
        if(c!==Cell.TUNNEL&&c!==Cell.QUEEN_CH&&c!==Cell.NURSERY&&c!==Cell.FOOD_ST) continue;
        for(const[dx,dy]of[[0,1],[1,0],[-1,0],[1,1],[-1,1],[0,2]]){
          if(this.isDirt(x+dx,y+dy)){
            // Prefer downward and outward
            const bias=1+(dy>0?0.8:0)+(Math.abs(x-this.cx)>this.W/6?0.4:0);
            candidates.push([x,y,bias]);
            break;
          }
        }
      }
    if(!candidates.length) return null;
    // Weighted random pick
    const weights=candidates.map(c=>c[2]);
    const chosen=weightedChoice(candidates,weights);
    return[chosen[0],chosen[1]];
  }

  _digStep(ant){
    const{GY}=this;
    if(!ant.digTarget){ ant.digTarget=this._findDigFrontier(); }
    if(!ant.digTarget){ ant.state=AS.RETURNING; return; }

    const[tx,ty]=ant.digTarget;
    if(ant.y>GY){
      [ant.x,ant.y]=this.stepTo(ant.x,ant.y,tx,ty,true);
      if(ant.x===tx&&ant.y===ty){
        // Dig one adjacent dirt cell (prefer down/sideways per stigmergy model)
        const dirs=[[0,1],[1,0],[-1,0],[1,1],[-1,1],[0,2]].sort(()=>Math.random()-.5);
        let dug=false;
        for(const[dx,dy]of dirs){
          const nx=ant.x+dx,ny=ant.y+dy;
          if(this.isDirt(nx,ny)){
            this.grid[ny][nx]=Cell.TUNNEL;
            ant.digTarget=[nx,ny]; dug=true; break;
          }
        }
        if(!dug) ant.digTarget=null;
        // Randomly start new chamber (stigmergy: cluster effect)
        if(Math.random()<0.03 && ant.digTarget){
          const[fx,fy]=ant.digTarget;
          this._fillChamber(fx,fy,2,1,Cell.TUNNEL);
          ant.digTarget=null;
        }
        if(Math.random()<0.06){ ant.state=AS.RETURNING; ant.digTarget=null; }
      }
    } else {
      [ant.x,ant.y]=this.stepTo(ant.x,ant.y,this.cx,GY,false);
      if(ant.x===this.cx&&ant.y===GY) ant.y=GY+1;
    }
  }

  // ── PREDATORS ─────────────────────────────────────────────────────
  spawnPredator(type='spider'){
    const side=Math.random()<0.5?0:this.W-1;
    this.predators.push(new Predator(side, this.GY, type));
  }

  movePredators(){
    const{GY}=this;
    for(const p of this.predators){
      if(!p.alive) continue;
      if(p.stunTimer>0){ p.stunTimer--; continue; }

      // Chase nearest surface ant
      let target=null, bestD=15*(p.type==='spider'?1:1.5);
      for(const ant of this.ants){
        if(ant.y>GY||ant.type===AT.QUEEN||ant.type<=AT.PUPA) continue;
        const d=Math.abs(ant.x-p.x)+Math.abs(ant.y-p.y);
        if(d<bestD){bestD=d;target=ant;}
      }
      if(target) p.dx=target.x>p.x?1:-1;
      else if(Math.random()<0.1) p.dx=rC([-1,1]);

      const spd=p.type==='spider'?1:1;
      const nx=clamp(p.x+p.dx*spd,0,this.W-1);
      if(this.pSurf(nx,GY)){p.x=nx;p.y=GY;}
      else p.dx=-p.dx;

      // Kill ants; release their alarm pheromone (death pheromone cascade)
      for(const ant of this.ants){
        if(ant.x===p.x&&ant.y===p.y&&ant.y<=GY&&ant.type!==AT.QUEEN&&ant.type>AT.PUPA){
          ant._dead=true;
          // Death pheromone → alarm cascade
          const ai=this.idx(ant.x,ant.y);
          this.alarm[ai]=Math.min(100, this.alarm[ai]+80);
          p.kills++;
        }
      }
    }
    this.predators=this.predators.filter(p=>p.alive);
    this.ants=this.ants.filter(a=>!a._dead);
  }

  // ── PHEROMONE UPDATE ──────────────────────────────────────────────
  updatePheromones(){
    const N=this.W*this.H;
    // Simple diffusion + decay for alarm (needs to spread fast)
    const newAlarm=new Float32Array(N);
    const W=this.W,H=this.H;
    for(let y=1;y<H-1;y++){
      for(let x=1;x<W-1;x++){
        const i=y*W+x, v=this.alarm[i];
        if(v<0.1) continue;
        const spread=v*0.12;
        newAlarm[i]       +=v*0.52;
        newAlarm[(y-1)*W+x]+=spread;
        newAlarm[(y+1)*W+x]+=spread;
        newAlarm[y*W+x-1] +=spread;
        newAlarm[y*W+x+1] +=spread;
      }
    }
    // Decay
    for(let i=0;i<N;i++){
      this.trail[i]*=TRAIL_DECAY;
      if(this.trail[i]<0.05) this.trail[i]=0;
      this.brood[i]*=BROOD_DECAY;
      if(this.brood[i]<0.1) this.brood[i]=0;
      this.alarm[i]=newAlarm[i]*ALARM_DECAY;
      if(this.alarm[i]<0.1) this.alarm[i]=0;
      this.repellent[i]*=REPEL_DECAY;
      if(this.repellent[i]<0.1) this.repellent[i]=0;
    }
    // Rain washes surface pheromones
    if(this.raining){
      for(let x=0;x<W;x++){
        const i=this.GY*W+x;
        this.trail[i]*=0.7; this.alarm[i]*=0.7; this.repellent[i]*=0.85;
      }
    }
  }

  // ── MAIN UPDATE ───────────────────────────────────────────────────
  update(){
    this.tick++;
    const phase=this.dayPhase();
    const night=phase<0.2||phase>0.8;

    // Move ants
    for(const ant of this.ants) this.moveAnt(ant);

    // Predators
    this.movePredators();
    const maxPred=night?3:1;
    if(this.predators.length<maxPred&&Math.random()<(night?0.004:0.001))
      this.spawnPredator(night?'spider':'beetle');
    // Dawn: predators retreat
    if(phase>0.2&&phase<0.25&&Math.random()<0.05&&this.predators.length)
      this.predators.shift();

    // Pheromones
    this.updatePheromones();

    // Food regeneration (faster in day, plants "grow")
    this.foodTimer++;
    const fInterval=this.isDay()?20:70;
    if(this.foodTimer>=fInterval){ this.foodTimer=0; if(this.food.size<80) this.spawnFood(1); }

    // Rain events
    this.rainTimer--;
    if(this.rainTimer<=0&&!this.raining){
      this.raining=true; this.rainLeft=rI(40,120); this.rainTimer=rI(600,1400);
    }
    if(this.raining){ this.rainLeft--; if(this.rainLeft<=0) this.raining=false; }
  }
}

// ═══════════════════════════════════════════════════════════════════
//  RENDERER
// ═══════════════════════════════════════════════════════════════════
function render(farm, ctx){
  const{W,H,GY}=farm;
  const iw=W*SCALE, ih=H*SCALE;
  const img=ctx.createImageData(iw,ih);
  const d=img.data;
  const phase=farm.dayPhase();
  const nf=farm.nightFade();

  // Entity lookups
  const antMap=new Map(), broodMap=new Map();
  for(const ant of farm.ants){
    const k=ant.x+','+ant.y;
    if(ant.type===AT.EGG||ant.type===AT.LARVA||ant.type===AT.PUPA||ant.type===AT.QUEEN||ant.type===AT.NURSE){
      if(!broodMap.has(k)) broodMap.set(k,ant);
    } else {
      if(!antMap.has(k)) antMap.set(k,ant);
    }
  }
  const predSet=new Set(farm.predators.filter(p=>p.alive).map(p=>p.x+','+p.y));

  // Rain drops (visual)
  const rainDrops=new Set();
  if(farm.raining){
    for(let i=0;i<30;i++) rainDrops.add(rI(0,W-1)+','+rI(0,GY));
  }

  for(let gy=0;gy<H;gy++){
    for(let gx=0;gx<W;gx++){
      const cell=farm.grid[gy][gx];
      const ii=farm.idx(gx,gy);
      let r,g,b;

      // Base cell colour
      if(cell===Cell.SKY){
        [r,g,b]=skyRGB(phase,gy/Math.max(1,GY));
      } else if(cell===Cell.GRASS){
        const v=(gx*7+gy*3)%18, bright=1-nf*0.65;
        r=Math.round(28*bright); g=Math.round((138+v)*bright); b=Math.round(28*bright);
      } else if(cell===Cell.DIRT){
        const s=farm.shade[gy][gx];
        r=clamp(101*s|0,0,255); g=clamp(67*s|0,0,255); b=clamp(33*s|0,0,255);
      } else if(cell===Cell.TUNNEL){
        r=28; g=14; b=5;
      } else if(cell===Cell.NURSERY){
        // Warm golden — warmest underground chamber
        const s=0.82+0.28*((gx+gy)%2);
        r=clamp(170*s|0,0,255); g=clamp(105*s|0,0,255); b=clamp(15*s|0,0,255);
      } else if(cell===Cell.QUEEN_CH){
        const s=0.80+0.28*((gx+gy)%2);
        r=clamp(150*s|0,0,255); g=clamp(95*s|0,0,255); b=clamp(10*s|0,0,255);
      } else if(cell===Cell.FOOD_ST){
        // Slightly greenish-brown food storage
        const s=0.85+0.22*((gx+gy)%2);
        r=clamp(90*s|0,0,255); g=clamp(90*s|0,0,255); b=clamp(18*s|0,0,255);
      } else {
        r=30; g=14; b=5; // midden
      }

      // Trail pheromone overlay (cyan tint in tunnels/underground)
      if(cell!==Cell.SKY&&cell!==Cell.GRASS&&cell!==Cell.DIRT){
        const t=Math.min(1,farm.trail[ii]/120);
        if(t>0.02){ r=Math.round(lerp(r,20,t*0.55)); g=Math.round(lerp(g,160,t*0.45)); b=Math.round(lerp(b,220,t*0.65)); }
      } else if(cell===Cell.GRASS||cell===Cell.SKY){
        const t=Math.min(1,farm.trail[ii]/120);
        if(t>0.02){ r=Math.round(lerp(r,20,t*0.4)); g=Math.round(lerp(g,160,t*0.3)); b=Math.round(lerp(b,220,t*0.5)); }
      }

      // Alarm pheromone overlay (red tint)
      const al=Math.min(1,farm.alarm[ii]/80);
      if(al>0.05){ r=Math.min(255,Math.round(r+al*140)); g=Math.round(lerp(g,0,al*0.4)); b=Math.round(lerp(b,0,al*0.4)); }

      // Repellent pheromone overlay (warm yellow-ochre on surface — marks depleted areas)
      if(cell===Cell.GRASS||cell===Cell.SKY){
        const rep=Math.min(1,farm.repellent[ii]/50);
        if(rep>0.08){ r=Math.min(255,Math.round(r+rep*80)); g=Math.min(255,Math.round(g+rep*45)); b=Math.round(b*Math.max(0,1-rep*0.5)); }
      }

      // Brood pheromone in nursery (soft warm glow)
      if(cell===Cell.NURSERY){
        const br=Math.min(1,farm.brood[ii]/60);
        if(br>0.05){ r=Math.min(255,Math.round(r+br*40)); g=Math.min(255,Math.round(g+br*20)); }
      }

      const k=gx+','+gy;
      const ant=antMap.get(k);
      const broodEnt=broodMap.get(k);
      const hasPred=predSet.has(k);
      const fq=farm.food.get(k)||0;
      const isRain=rainDrops.has(k);
      const isStar=cell===Cell.SKY&&nf>0.3&&
        farm.stars.some(s=>s.x===gx&&s.y===gy);
      const isMidden=farm.midden.has(k);

      const s2=SCALE/2-0.5;
      const dotR2=Math.pow(Math.max(2,SCALE/3),2);
      const smR2=Math.pow(Math.max(1,SCALE*0.22),2);

      for(let sy=0;sy<SCALE;sy++){
        for(let sx=0;sx<SCALE;sx++){
          const dist2=(sx-s2)*(sx-s2)+(sy-s2)*(sy-s2);
          const pi=((gy*SCALE+sy)*iw+(gx*SCALE+sx))*4;

          if(hasPred&&dist2<=dotR2*1.5){
            // Predator: bright orange-red with dark core
            const inner=dist2<=dotR2*0.25;
            d[pi]=inner?60:230; d[pi+1]=inner?10:70; d[pi+2]=inner?0:0;
          } else if(ant&&dist2<=dotR2){
            // Ant colour by type/state
            if(ant.type===AT.SOLDIER){
              d[pi]=220; d[pi+1]=20; d[pi+2]=20;
            } else if(ant.type===AT.DIGGER){
              d[pi]=255; d[pi+1]=135; d[pi+2]=0;
            } else if(ant.hasFood){
              d[pi]=255; d[pi+1]=215; d[pi+2]=0;  // gold = carrying
            } else if(ant.alarmLevel>0.5){
              d[pi]=200; d[pi+1]=50; d[pi+2]=50;  // red-tinted when alarmed
            } else {
              d[pi]=15; d[pi+1]=15; d[pi+2]=15;   // worker
            }
          } else if(fq>0&&dist2<=dotR2){
            // Food: size/brightness reflects quality
            d[pi]=200+fq*18; d[pi+1]=30; d[pi+2]=20;
          } else if(broodEnt&&dist2<=smR2){
            if(broodEnt.type===AT.EGG)        {d[pi]=245;d[pi+1]=245;d[pi+2]=245;}
            else if(broodEnt.type===AT.LARVA) {d[pi]=230;d[pi+1]=210;d[pi+2]=130;}
            else if(broodEnt.type===AT.PUPA)  {d[pi]=190;d[pi+1]=170;d[pi+2]=100;}
            else if(broodEnt.type===AT.QUEEN) {
              // Queen: larger magenta dot
              if(dist2<=dotR2){d[pi]=210;d[pi+1]=40;d[pi+2]=210;}
              else {d[pi]=r;d[pi+1]=g;d[pi+2]=b;}
            } else if(broodEnt.type===AT.NURSE){
              d[pi]=100; d[pi+1]=230; d[pi+2]=230; // cyan nurse
            } else { d[pi]=r;d[pi+1]=g;d[pi+2]=b; }
          } else if(isMidden&&cell===Cell.GRASS){
            // Midden: dark pile of waste
            d[pi]=55; d[pi+1]=38; d[pi+2]=20;
          } else if(isRain){
            d[pi]=clamp(r+30,0,255); d[pi+1]=clamp(g+40,0,255); d[pi+2]=clamp(b+80,0,255);
          } else if(isStar){
            const br=Math.round(180*nf);
            d[pi]=br; d[pi+1]=br; d[pi+2]=br+25;
          } else if(cell===Cell.GRASS&&sx===(SCALE/2|0)&&gx%3===0&&sy<SCALE-1){
            const bright=1-nf*0.65;
            d[pi]=Math.round(35*bright); d[pi+1]=Math.round(195*bright); d[pi+2]=Math.round(35*bright);
          } else {
            d[pi]=r; d[pi+1]=g; d[pi+2]=b;
          }
          d[pi+3]=255;
        }
      }

      // Sun / Moon arc
      if(cell===Cell.SKY&&gy===Math.floor(GY*0.35)){
        const sunX=Math.round(W*(0.5+0.38*Math.cos(phase*Math.PI*2)));
        const moonX=Math.round(W*(0.5+0.38*Math.cos((phase+0.5)*Math.PI*2)));
        const isNight=nf>0.35;
        const bodyX=isNight?moonX:sunX;
        if(Math.abs(gx-bodyX)<=2){
          for(let sy=0;sy<SCALE;sy++) for(let sx=0;sx<SCALE;sx++){
            const dx=sx-s2, dy=sy-s2;
            if(dx*dx+dy*dy<=SCALE*SCALE*0.28){
              const pi=((gy*SCALE+sy)*iw+(gx*SCALE+sx))*4;
              if(isNight){d[pi]=235;d[pi+1]=235;d[pi+2]=210;}
              else       {d[pi]=255;d[pi+1]=235;d[pi+2]=55;}
              d[pi+3]=255;
            }
          }
        }
      }
    }
  }
  ctx.putImageData(img,0,0);

  // Rain streaks overlay (canvas-native for speed)
  if(farm.raining){
    ctx.save();
    ctx.strokeStyle='rgba(160,200,255,0.18)';
    ctx.lineWidth=1;
    for(let i=0;i<60;i++){
      const x=rI(0,W)*SCALE, y=rI(0,GY)*SCALE;
      ctx.beginPath(); ctx.moveTo(x,y); ctx.lineTo(x+2,y+8); ctx.stroke();
    }
    ctx.restore();
  }
}

// ═══════════════════════════════════════════════════════════════════
//  UI / ANIMATION LOOP
// ═══════════════════════════════════════════════════════════════════
const canvas=document.getElementById('farm');
const ctx=canvas.getContext('2d');
let farm,running=false,speed=1;

function reset(){
  const W=+sW.value,H=+sH.value;
  canvas.width=W*SCALE; canvas.height=H*SCALE;
  farm=new AntFarm(W,H,+sAnts.value,+sFood.value);
  render(farm,ctx); updateStats();
}

const PHASE_LABELS=['🌙 Night','🌅 Dawn','☀️ Day','🌇 Dusk'];
function updateStats(){
  const p=farm.dayPhase();
  const li=Math.round(p*4)%4;
  sPhase.textContent=PHASE_LABELS[li]+(farm.raining?' 🌧️':'');
  sDay.textContent=Math.floor(farm.tick/DAY_LEN)+1;
  sTick.textContent=farm.tick;
  sPop.textContent=farm.ants.filter(a=>a.type<=AT.DIGGER).length;
  sBrood.textContent=farm.ants.filter(a=>a.type>=AT.EGG&&a.type<=AT.PUPA).length;
  sStored.textContent=farm.foodStored;
  sSurf.textContent=farm.food.size;
  sPred.textContent=farm.predators.length;
}

for(const[s,v]of[['sAnts','vAnts'],['sFood','vFood'],['sW','vW'],['sH','vH'],['sSpeed','vSpeed']]){
  document.getElementById(s).addEventListener('input',e=>{
    document.getElementById(v).textContent=e.target.value;
    if(s==='sSpeed') speed=+e.target.value;
  });
}
btnStart.onclick=()=>{running=true;};
btnStop.onclick=()=>{running=false;};
btnReset.onclick=()=>{running=false;reset();};
btnFood.onclick=()=>{if(farm)farm.spawnFood(20);};

let last=0; const MS=260;
function loop(ts){
  requestAnimationFrame(loop);
  if(!farm||!running||ts-last<MS) return;
  last=ts;
  for(let i=0;i<speed;i++) farm.update();
  render(farm,ctx); updateStats();
}
reset();
requestAnimationFrame(loop);
</script></body></html>
""", height=760, scrolling=False)
