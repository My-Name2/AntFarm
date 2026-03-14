"""
Ant Farm – Top-down simulation.
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
.val{font-size:11px;color:#fff;min-width:22px;display:inline-block}
button{padding:3px 9px;border:none;border-radius:3px;cursor:pointer;font-size:12px;font-weight:bold}
#btnStart{background:#2a9;color:#fff}#btnStop{background:#a44;color:#fff}
#btnReset{background:#555;color:#fff}#btnFood{background:#a72;color:#fff}
#stats{display:flex;gap:12px;padding:3px 10px;background:#161616;
       border-bottom:1px solid #333;font-size:11px;flex-wrap:wrap}
#stats b{color:#8cf}
#legend{display:flex;gap:10px;padding:3px 10px;background:#0e0e0e;
        border-bottom:1px solid #222;font-size:10px;flex-wrap:wrap}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;
     margin-right:3px;vertical-align:middle}
.sq{display:inline-block;width:9px;height:9px;margin-right:3px;vertical-align:middle}
canvas{display:block;cursor:crosshair}
</style></head><body>

<div id="ui">
  <label>Ants <span class="val" id="vAnts">40</span></label>
  <input type="range" id="sAnts" min="10" max="100" value="40">
  <label>Food <span class="val" id="vFood">50</span></label>
  <input type="range" id="sFood" min="10" max="120" value="50">
  <label>Width <span class="val" id="vW">130</span></label>
  <input type="range" id="sW" min="70" max="200" value="130">
  <label>Height <span class="val" id="vH">90</span></label>
  <input type="range" id="sH" min="50" max="130" value="90">
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
  Workers <b id="sPop">0</b> |
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
  <span><span class="dot" style="background:#e64;border:2px solid #900"></span>Predator</span>
  <span><span class="sq" style="background:#0bf"></span>Trail pheromone</span>
  <span><span class="sq" style="background:#f44"></span>Alarm pheromone</span>
  <span><span class="sq" style="background:#da4"></span>Repellent</span>
  <span><span class="sq" style="background:#824"></span>Tunnel</span>
  <span><span class="sq" style="background:#a5519e"></span>Queen chamber</span>
  <span><span class="sq" style="background:#8a6820"></span>Nursery</span>
  <span><span class="sq" style="background:#3a7a30"></span>Food storage</span>
</div>

<canvas id="farm"></canvas>

<script>
// ═══════════════════════════════════════════════════════════════════
//  CONSTANTS
// ═══════════════════════════════════════════════════════════════════
const SCALE   = 7;      // pixels per grid cell
const DAY_LEN = 700;    // ticks per full day
const MAX_ANTS= 160;

// Deneubourg pheromone model
const TRAIL_K = 0.4, TRAIL_N = 2.0;

// Pheromone decay per tick
const TRAIL_DECAY  = 0.993;   // trails persist ~140 ticks → highways form
const ALARM_DECAY  = 0.78;    // alarm volatilises fast (~4 ticks)
const BROOD_DECAY  = 0.97;    // brood signal medium
const REPEL_DECAY  = 0.987;   // repellent marks depleted patches (~55 ticks)

const Cell = Object.freeze({
  GRASS:0, DIRT:1, ROCK:2,
  TUNNEL:3, QUEEN_CH:4, NURSERY:5, FOOD_ST:6, MIDDEN:7
});

const AT = Object.freeze({   // ant types
  QUEEN:0, NURSE:1, FORAGER:2, SOLDIER:3, DIGGER:4,
  EGG:5, LARVA:6, PUPA:7
});

const AS = Object.freeze({   // ant states
  IN_NEST:0, NURSING:1, LEAVING:2, FORAGING:3, RETURNING:4,
  DIGGING:5, GUARDING:6, CHASING:7, FLEEING:8
});

// ═══════════════════════════════════════════════════════════════════
//  UTILITIES
// ═══════════════════════════════════════════════════════════════════
const rI    = (a,b)  => Math.floor(Math.random()*(b-a+1))+a;
const rC    = arr    => arr[Math.floor(Math.random()*arr.length)];
const clamp = (v,lo,hi) => Math.max(lo, Math.min(hi, v));
const lerp  = (a,b,t)   => a+(b-a)*t;

function weightedChoice(items, weights) {
  let sum=0; for(const w of weights) sum+=w;
  let r=Math.random()*sum;
  for(let i=0;i<items.length;i++){ r-=weights[i]; if(r<=0) return items[i]; }
  return items[items.length-1];
}

// Day/night ambient light colour
const SKY_STOPS=[
  [0,0,15],       // midnight
  [245,115,30],   // dawn
  [255,240,200],  // noon (warm sunlight)
  [230,60,10],    // dusk
  [0,0,15],       // midnight
];
function ambientRGB(phase){
  const n=SKY_STOPS.length-1, fp=phase*n;
  const i=Math.floor(fp), t=fp-i;
  const[r1,g1,b1]=SKY_STOPS[Math.min(i,n)];
  const[r2,g2,b2]=SKY_STOPS[Math.min(i+1,n)];
  return[Math.round(lerp(r1,r2,t)),Math.round(lerp(g1,g2,t)),Math.round(lerp(b1,b2,t))];
}

// ═══════════════════════════════════════════════════════════════════
//  ANT
// ═══════════════════════════════════════════════════════════════════
class Ant {
  constructor(x,y,type=AT.FORAGER){
    this.x=x; this.y=y; this.type=type;
    this.age=0;
    // Heading for correlated random walk
    const ang=Math.random()*Math.PI*2;
    this.dx=Math.sign(Math.cos(ang))||1;
    this.dy=Math.sign(Math.sin(ang));
    this.hasFood=false; this.foodQuality=1;
    this.alarmLevel=0; this.fleeTimer=0;
    this.digTarget=null;
    this.underground=false;  // true when inside nest cells

    if     (type===AT.EGG)  {this.hatchIn=rI(55,80);  this.state=AS.IN_NEST; this.hunger=0;}
    else if(type===AT.LARVA){this.hatchIn=rI(90,130); this.state=AS.IN_NEST; this.hunger=rI(20,60);}
    else if(type===AT.PUPA) {this.hatchIn=rI(65,95);  this.state=AS.IN_NEST; this.hunger=0;}
    else if(type===AT.QUEEN){this.state=AS.IN_NEST; this.hatchIn=0;}
    else if(type===AT.NURSE){this.state=AS.NURSING;  this.hatchIn=0; this.underground=true;}
    else                    {this.state=AS.LEAVING;  this.hatchIn=0;}
  }
}

// ═══════════════════════════════════════════════════════════════════
//  PREDATOR
// ═══════════════════════════════════════════════════════════════════
class Predator {
  constructor(x,y,type='spider'){
    this.x=x; this.y=y; this.type=type;
    const ang=Math.random()*Math.PI*2;
    this.dx=Math.sign(Math.cos(ang))||1;
    this.dy=Math.sign(Math.sin(ang));
    this.alive=true; this.kills=0; this.stunTimer=0;
  }
}

// ═══════════════════════════════════════════════════════════════════
//  ANTFARM
// ═══════════════════════════════════════════════════════════════════
class AntFarm {
  constructor(W,H,antCount,foodCount){
    this.W=W; this.H=H;
    this.cx=Math.floor(W/2);
    this.cy=Math.floor(H/2);

    this.grid  = Array.from({length:H},()=>new Uint8Array(W));
    this.depth = new Float32Array(W*H);  // normalized BFS depth from entrance
    this.shade = Array.from({length:H},()=>
      Float32Array.from({length:W},()=>0.82+Math.random()*0.36));

    // Pheromone layers
    this.trail    = new Float32Array(W*H);
    this.alarm    = new Float32Array(W*H);
    this.brood    = new Float32Array(W*H);
    this.repellent= new Float32Array(W*H);

    this.food=new Map(); this.foodStored=0; this.tick=0;
    this.ants=[]; this.predators=[]; this.midden=new Set();
    this.nestInfo={};
    this.queenTimer=0; this.foodTimer=0;
    this.rainTimer=rI(800,1600); this.raining=false; this.rainLeft=0;

    this.build();
    this.computeDepths();
    this.spawnFood(foodCount);
    this.initColony(antCount);
  }

  // ── WORLD BUILD ──────────────────────────────────────────────────
  build(){
    const{W,H,cx,cy}=this;

    // Base layer: all grass
    for(let y=0;y<H;y++) for(let x=0;x<W;x++) this.grid[y][x]=Cell.GRASS;

    // Disturbed dirt halo around nest entrance
    for(let dy=-7;dy<=7;dy++) for(let dx=-7;dx<=7;dx++){
      if(dx*dx+dy*dy<=50&&this.inB(cx+dx,cy+dy))
        this.grid[cy+dy][cx+dx]=Cell.DIRT;
    }

    // Build underground nest (visible from above as dark cells)
    this._buildNest();

    // Scatter rocks (impassable obstacles, create foraging variety)
    const nRocks=Math.floor(W*H/350);
    for(let i=0;i<nRocks;i++){
      const rx=rI(4,W-5), ry=rI(4,H-5);
      if((rx-cx)**2+(ry-cy)**2 > 256){   // clear of nest
        const rs=rI(1,3);
        for(let dy=-rs;dy<=rs;dy++) for(let dx=-rs;dx<=rs;dx++)
          if(Math.random()<0.72&&this.inB(rx+dx,ry+dy)&&
             this.grid[ry+dy][rx+dx]===Cell.GRASS)
            this.grid[ry+dy][rx+dx]=Cell.ROCK;
      }
    }
  }

  _buildNest(){
    const{cx,cy,W,H}=this;
    const shaftLen=Math.min(Math.floor(H*0.22), H-cy-6);

    // Entrance: single-cell opening
    this.grid[cy][cx]=Cell.TUNNEL;

    // Guard gallery: ring of tunnel cells just outside entrance
    for(let a=0;a<Math.PI*2;a+=Math.PI/8){
      const gx=Math.round(cx+Math.cos(a)*3);
      const gy=Math.round(cy+Math.sin(a)*3);
      if(this.inB(gx,gy)) this.grid[gy][gx]=Cell.TUNNEL;
    }

    // Main shaft going "down" (south = deeper in top-down)
    for(let i=1;i<=shaftLen;i++)
      if(cy+i<H-2) this.grid[cy+i][cx]=Cell.TUNNEL;

    // Queen's chamber at bottom of main shaft
    const qy=cy+shaftLen;
    this._fillChamber(cx,qy,5,2,Cell.QUEEN_CH);
    this.nestInfo.queenX=cx; this.nestInfo.queenY=qy;

    // Nursery: left branch from upper-mid shaft
    const nurY=cy+Math.max(3,Math.floor(shaftLen*0.40));
    const nurLen=Math.min(Math.floor(W*0.13),cx-5);
    for(let i=1;i<=nurLen;i++) if(cx-i>=2) this.grid[nurY][cx-i]=Cell.TUNNEL;
    this._fillChamber(cx-nurLen,nurY,4,2,Cell.NURSERY);
    this.nestInfo.nurseryX=cx-nurLen; this.nestInfo.nurseryY=nurY;

    // Food storage: right branch from lower-mid shaft
    const fstY=cy+Math.max(5,Math.floor(shaftLen*0.65));
    const fstLen=Math.min(Math.floor(W*0.13),W-cx-6);
    for(let i=1;i<=fstLen;i++) if(cx+i<W-2) this.grid[fstY][cx+i]=Cell.TUNNEL;
    this._fillChamber(cx+fstLen,fstY,4,2,Cell.FOOD_ST);
    this.nestInfo.foodStX=cx+fstLen; this.nestInfo.foodStY=fstY;

    // Midden: diagonal tunnel off to upper-left
    const midX=cx-9, midY=cy-6;
    for(let t=0;t<=9;t++){
      const mx=Math.round(lerp(cx,midX,t/9));
      const my=Math.round(lerp(cy,midY,t/9));
      if(this.inB(mx,my)) this.grid[my][mx]=Cell.TUNNEL;
    }
    this._fillChamber(midX,midY,3,1,Cell.MIDDEN);
    for(let dx=-2;dx<=2;dx++) this.midden.add((midX+dx)+','+midY);

    // Exploration branches from queen's chamber
    const brLen=Math.floor(Math.min(W,H)/9);
    for(const[adx,ady] of [[-1,0],[1,0],[0,1],[-1,1],[1,1]]){
      for(let i=1;i<=brLen;i++){
        const bx=cx+adx*i, by=qy+ady*i;
        if(this.inB(bx,by)&&by<H-2) this.grid[by][bx]=Cell.TUNNEL;
        else break;
      }
    }
  }

  _fillChamber(cx,cy,rx,ry,type){
    for(let dy=-ry;dy<=ry;dy++) for(let dx=-rx;dx<=rx;dx++){
      const nx=cx+dx, ny=cy+dy;
      if(this.inB(nx,ny)) this.grid[ny][nx]=type;
    }
  }

  // BFS from entrance to assign normalized depth values to underground cells
  computeDepths(){
    const{W,H,cx,cy}=this;
    this.depth.fill(-1);
    const queue=[[cx,cy,0]];
    this.depth[cy*W+cx]=0;
    let maxD=0;
    while(queue.length){
      const[x,y,d]=queue.shift();
      for(const[dx,dy] of [[-1,0],[1,0],[0,-1],[0,1]]){
        const nx=x+dx, ny=y+dy;
        if(!this.inB(nx,ny)) continue;
        const i=ny*W+nx, c=this.grid[ny][nx];
        if(this.depth[i]>=0) continue;
        if(c===Cell.TUNNEL||c===Cell.QUEEN_CH||c===Cell.NURSERY||
           c===Cell.FOOD_ST||c===Cell.MIDDEN){
          this.depth[i]=d+1; maxD=Math.max(maxD,d+1);
          queue.push([nx,ny,d+1]);
        }
      }
    }
    if(maxD>0) for(let i=0;i<this.depth.length;i++)
      if(this.depth[i]>=0) this.depth[i]/=maxD;
  }

  // ── HELPERS ──────────────────────────────────────────────────────
  inB(x,y){return x>=0&&x<this.W&&y>=0&&y<this.H;}
  idx(x,y){return y*this.W+x;}

  isUnderground(x,y){
    const c=this.grid[y]?.[x];
    return c===Cell.TUNNEL||c===Cell.QUEEN_CH||c===Cell.NURSERY||
           c===Cell.FOOD_ST||c===Cell.MIDDEN;
  }
  isSurface(x,y){
    const c=this.grid[y]?.[x];
    return this.inB(x,y)&&c!==Cell.ROCK&&!this.isUnderground(x,y);
  }
  isPassable(x,y){return this.inB(x,y)&&this.grid[y][x]!==Cell.ROCK;}

  // Greedy step toward target through passable cells
  stepTo(ax,ay,tx,ty){
    const ddx=ax===tx?0:(tx>ax?1:-1);
    const ddy=ay===ty?0:(ty>ay?1:-1);
    const cands=[[ax+ddx,ay+ddy],[ax+ddx,ay],[ax,ay+ddy],
                 [ax-ddy,ay+ddx],[ax+ddy,ay-ddx]];
    for(const[nx,ny]of cands) if(this.isPassable(nx,ny)) return[nx,ny];
    const nb=[];
    for(let dx=-1;dx<=1;dx++) for(let dy=-1;dy<=1;dy++)
      if((dx||dy)&&this.isPassable(ax+dx,ay+dy)) nb.push([ax+dx,ay+dy]);
    return nb.length?rC(nb):[ax,ay];
  }

  // Deneubourg probabilistic trail-following step (8-dir, surface only)
  trailStep(ax,ay){
    const nb=[];
    for(let dx=-1;dx<=1;dx++) for(let dy=-1;dy<=1;dy++){
      if(!dx&&!dy) continue;
      const nx=ax+dx, ny=ay+dy;
      if(this.isSurface(nx,ny)) nb.push([nx,ny]);
    }
    if(!nb.length) return[ax,ay];
    const weights=nb.map(([nx,ny])=>{
      const i=this.idx(nx,ny);
      const t=this.trail[i], rep=this.repellent[i];
      return Math.pow(TRAIL_K+t,TRAIL_N)*Math.max(0.05,1-rep*0.035);
    });
    return weightedChoice(nb,weights);
  }

  // ── SPAWNING ─────────────────────────────────────────────────────
  spawnFood(n){
    let placed=0, tries=0;
    const{cx,cy}=this;
    while(placed<n&&tries<n*80&&this.food.size<110){
      tries++;
      const x=rI(2,this.W-3), y=rI(2,this.H-3);
      const dx=x-cx, dy=y-cy;
      if(this.grid[y][x]===Cell.GRASS&&dx*dx+dy*dy>100){
        const k=x+','+y;
        if(!this.food.has(k)){this.food.set(k,rI(1,3));placed++;}
      }
    }
  }

  initColony(n){
    const{cx,cy,nestInfo:{queenX,queenY,nurseryX,nurseryY,foodStX,foodStY}}=this;

    // Queen
    const q=new Ant(queenX,queenY,AT.QUEEN);
    q.underground=true; this.ants.push(q);

    // Initial brood in nursery
    for(let i=0;i<8;i++){
      const t=rC([AT.EGG,AT.EGG,AT.LARVA,AT.LARVA,AT.PUPA]);
      const a=new Ant(clamp(nurseryX+rI(-3,3),1,this.W-2),
                      clamp(nurseryY+rI(-1,1),1,this.H-2),t);
      a.underground=true; this.ants.push(a);
    }

    // Nurses
    const nN=Math.max(3,Math.floor(n*0.18));
    for(let i=0;i<nN;i++){
      const a=new Ant(clamp(nurseryX+rI(-2,2),1,this.W-2),nurseryY,AT.NURSE);
      a.age=rI(0,25); a.underground=true; this.ants.push(a);
    }

    // Soldiers (patrol entrance perimeter)
    const nS=Math.max(2,Math.floor(n*0.08));
    for(let i=0;i<nS;i++){
      const ang=Math.random()*Math.PI*2;
      const a=new Ant(Math.round(cx+Math.cos(ang)*5),
                      Math.round(cy+Math.sin(ang)*5), AT.SOLDIER);
      a.state=AS.GUARDING; this.ants.push(a);
    }

    // Diggers
    const nD=Math.max(2,Math.floor(n*0.10));
    for(let i=0;i<nD;i++){
      const a=new Ant(queenX,queenY,AT.DIGGER);
      a.underground=true; a.state=AS.DIGGING; this.ants.push(a);
    }

    // Foragers (the bulk, start at entrance)
    const used=this.ants.filter(a=>a.type<=AT.DIGGER).length;
    const nF=Math.max(0,n-used+1);
    for(let i=0;i<nF;i++){
      const a=new Ant(cx,cy,AT.FORAGER);
      a.age=rI(20,60); this.ants.push(a);
    }
  }

  // ── DAY / NIGHT ───────────────────────────────────────────────────
  dayPhase(){return(this.tick%DAY_LEN)/DAY_LEN;}
  isDay(){const p=this.dayPhase();return p>0.22&&p<0.78;}
  nightFade(){
    const p=this.dayPhase();
    if(p<0.22) return 1-p/0.22;
    if(p>0.78) return(p-0.78)/0.22;
    return 0;
  }

  // ── ANT BEHAVIOUR ─────────────────────────────────────────────────
  moveAnt(ant){
    const{cx,cy,nestInfo}=this;
    ant.age++;
    ant.alarmLevel=Math.max(0,ant.alarmLevel-0.1);

    // ── Brood: develop, emit pheromone ────────────────────────────
    if(ant.type===AT.EGG||ant.type===AT.LARVA||ant.type===AT.PUPA){
      const i=this.idx(ant.x,ant.y);
      if(ant.type===AT.LARVA){
        ant.hunger=Math.min(100,(ant.hunger||0)+0.3);
        this.brood[i]=Math.min(100,this.brood[i]+(1.0+ant.hunger*0.025));
      } else {
        this.brood[i]=Math.min(80,this.brood[i]+1.2);
      }
      let nurseBonus=1;
      for(const o of this.ants){
        if(o.type===AT.NURSE&&Math.abs(o.x-ant.x)<=2&&Math.abs(o.y-ant.y)<=1){
          nurseBonus=1.8; break;
        }
      }
      if(ant.age>=ant.hatchIn/nurseBonus){
        if(ant.type===AT.EGG){
          ant.type=AT.LARVA; ant.age=0; ant.hatchIn=rI(90,130);
        } else if(ant.type===AT.LARVA){
          ant.type=AT.PUPA; ant.age=0; ant.hatchIn=rI(65,95);
        } else {
          // Eclosion: assign role based on colony needs (age polyethism)
          const nurses=this.ants.filter(a=>a.type===AT.NURSE).length;
          const soldiers=this.ants.filter(a=>a.type===AT.SOLDIER).length;
          const foragers=this.ants.filter(a=>a.type===AT.FORAGER).length;
          if(nurses<Math.floor(this.ants.length*0.15))
            ant.type=AT.NURSE;
          else if(soldiers<2&&this.foodStored>10)
            ant.type=AT.SOLDIER;
          else if(foragers<this.ants.length*0.4)
            ant.type=AT.FORAGER;
          else
            ant.type=rC([AT.FORAGER,AT.FORAGER,AT.DIGGER]);
          ant.state=ant.type===AT.NURSE?AS.NURSING:AS.LEAVING;
          ant.underground=ant.type===AT.NURSE;
          ant.age=0; ant.hatchIn=0;
        }
      }
      return;
    }

    // ── Queen: lay eggs ───────────────────────────────────────────
    if(ant.type===AT.QUEEN){
      this.queenTimer++;
      const layRate=Math.max(60,120-this.foodStored);
      if(this.queenTimer>=layRate&&this.ants.length<MAX_ANTS&&this.foodStored>2){
        this.queenTimer=0;
        this.foodStored=Math.max(0,this.foodStored-1);
        const ex=clamp(nestInfo.nurseryX+rI(-3,3),1,this.W-2);
        const ey=clamp(nestInfo.nurseryY+rI(-1,1),1,this.H-2);
        const egg=new Ant(ex,ey,AT.EGG); egg.underground=true; this.ants.push(egg);
      }
      return;
    }

    // ── Alarm sensing (3-zone Oecophylla model) ───────────────────
    const ai=this.idx(ant.x,ant.y);
    const alarmHere=this.alarm[ai];
    // Soldiers detect at 2× sensitivity
    if(alarmHere>(ant.type===AT.SOLDIER?2.5:5))
      ant.alarmLevel=Math.min(1,ant.alarmLevel+alarmHere/80);
    // Zone 3: workers re-emit alarm (positive feedback cascade)
    if(alarmHere>35&&ant.type!==AT.SOLDIER&&!ant.underground)
      this.alarm[ai]=Math.min(100,this.alarm[ai]+10);

    // ── Flee ─────────────────────────────────────────────────────
    if(ant.type!==AT.SOLDIER&&ant.alarmLevel>0.6&&!ant.underground){
      ant.state=AS.FLEEING; ant.fleeTimer=rI(8,16);
    }
    if(ant.state===AS.FLEEING){
      ant.fleeTimer--;
      const pred=this.predators.find(p=>p.alive&&
        Math.abs(p.x-ant.x)<=8&&Math.abs(p.y-ant.y)<=8);
      if(pred){
        const fdx=ant.x>pred.x?1:-1, fdy=ant.y>pred.y?1:-1;
        const nx=clamp(ant.x+fdx,0,this.W-1);
        const ny=clamp(ant.y+fdy,0,this.H-1);
        if(this.isPassable(nx,ny)&&!this.isUnderground(nx,ny)){
          ant.x=nx; ant.y=ny;
        }
      }
      if(ant.fleeTimer<=0) ant.state=ant.hasFood?AS.RETURNING:AS.FORAGING;
      return;
    }

    // ── Type-specific behaviours ──────────────────────────────────
    if(ant.type===AT.NURSE)  { this._moveNurse(ant);   return; }
    if(ant.type===AT.SOLDIER){ this._moveSoldier(ant); return; }
    if(ant.type===AT.DIGGER&&ant.state===AS.DIGGING){ this._digStep(ant); return; }

    // ── LEAVING: emerge from nest to surface ──────────────────────
    if(ant.state===AS.LEAVING){
      if(!this.isDay()&&Math.random()<0.60) return;  // mostly diurnal
      if(this.raining&&Math.random()<0.88) return;   // rain suppresses foraging
      [ant.x,ant.y]=this.stepTo(ant.x,ant.y,cx,cy);
      if(ant.x===cx&&ant.y===cy){
        ant.underground=false;
        ant.state=AS.FORAGING;
        const ang=Math.random()*Math.PI*2;
        ant.dx=Math.sign(Math.cos(ang))||1;
        ant.dy=Math.sign(Math.sin(ang));
      }
      return;
    }

    // ── FORAGING: correlated random walk + Deneubourg trail following
    if(ant.state===AS.FORAGING){
      // Trophallaxis while underground (shared social stomach)
      if(ant.underground){
        for(const o of this.ants){
          if(o!==ant&&o.hasFood&&o.x===ant.x&&o.y===ant.y&&Math.random()<0.25){
            ant.hasFood=true; ant.foodQuality=o.foodQuality;
            o.hasFood=false; ant.state=AS.RETURNING; return;
          }
        }
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,cx,cy);
        if(ant.x===cx&&ant.y===cy) ant.underground=false;
        return;
      }

      // Rain: immediately return (Hölldobler & Wilson: rain suppresses foraging)
      if(this.raining){ ant.state=AS.RETURNING; return; }

      // Correlated random walk: small heading perturbation each step
      if(Math.random()<0.14){
        ant.dx=clamp(ant.dx+rC([-1,0,0,1]),-1,1);
        ant.dy=clamp(ant.dy+rC([-1,0,0,1]),-1,1);
        if(!ant.dx&&!ant.dy) ant.dx=rC([-1,1]);
      }

      // Deneubourg trail-following (probabilistic weighted choice)
      const[nx,ny]=this.trailStep(ant.x,ant.y);
      if(this.isSurface(nx,ny)){
        ant.x=nx; ant.y=ny;
      } else {
        ant.dx=-ant.dx; ant.dy=-ant.dy;
        const bx=clamp(ant.x+ant.dx,0,this.W-1);
        const by=clamp(ant.y+ant.dy,0,this.H-1);
        if(this.isSurface(bx,by)){ ant.x=bx; ant.y=by; }
      }
      ant.x=clamp(ant.x,0,this.W-1);
      ant.y=clamp(ant.y,0,this.H-1);
      if(ant.x<=0||ant.x>=this.W-1) ant.dx=-ant.dx;
      if(ant.y<=0||ant.y>=this.H-1) ant.dy=-ant.dy;

      // Emit alarm if alarmed
      if(ant.alarmLevel>0.5)
        this.alarm[this.idx(ant.x,ant.y)]=Math.min(100,this.alarm[this.idx(ant.x,ant.y)]+20);

      // Pick up food (sense within 1 cell radius)
      for(const[k,q]of this.food){
        const[fx,fy]=k.split(',').map(Number);
        if(Math.abs(fx-ant.x)<=1&&Math.abs(fy-ant.y)<=1){
          this.food.delete(k);
          ant.hasFood=true; ant.foodQuality=q;
          ant.state=AS.RETURNING;
          ant.dx=-ant.dx; ant.dy=-ant.dy;
          // Deposit repellent at pickup site (marks partially-depleted area)
          const ri=this.idx(fx,fy);
          this.repellent[ri]=Math.min(60,this.repellent[ri]+18);
          break;
        }
      }
      return;
    }

    // ── RETURNING: deposit trail, head to nest entrance ───────────
    if(ant.state===AS.RETURNING){
      if(!ant.underground){
        // Deposit trail proportional to food quality — builds the highway
        const ii=this.idx(ant.x,ant.y);
        this.trail[ii]=Math.min(200,this.trail[ii]+12*ant.foodQuality);
        // Head toward entrance
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,cx,cy);
        if(ant.x===cx&&ant.y===cy) ant.underground=true;
      } else {
        // Underground: navigate to food storage chamber
        const{foodStX,foodStY}=nestInfo;
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,foodStX,foodStY);
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
      if(Math.random()<0.08) ant.state=AS.LEAVING;
    }
  }

  // ── NURSE BEHAVIOUR ───────────────────────────────────────────────
  _moveNurse(ant){
    // Follow brood pheromone gradient (stay in nursery area)
    const nb=[];
    for(let dx=-1;dx<=1;dx++) for(let dy=-1;dy<=1;dy++){
      if(!dx&&!dy) continue;
      const nx=ant.x+dx, ny=ant.y+dy;
      if(this.isUnderground(nx,ny))
        nb.push([nx,ny,this.brood[this.idx(nx,ny)]]);
    }
    if(nb.length){
      nb.sort((a,b)=>b[2]-a[2]);
      if(Math.random()<0.70&&nb[0][2]>2)
        [ant.x,ant.y]=[nb[0][0],nb[0][1]];
      else{ const r=rC(nb); ant.x=r[0]; ant.y=r[1]; }
    }

    // Trophallaxis: feed hungry larvae from colony food reserve
    for(const larva of this.ants){
      if(larva.type===AT.LARVA&&(larva.hunger||0)>30&&
         Math.abs(larva.x-ant.x)<=1&&Math.abs(larva.y-ant.y)<=1&&this.foodStored>0){
        larva.hunger=Math.max(0,(larva.hunger||0)-30);
        this.foodStored=Math.max(0,this.foodStored-0.5);
        break;
      }
    }

    // Age polyethism: older nurses graduate to foraging
    if(ant.age>65&&Math.random()<0.005){
      ant.type=AT.FORAGER; ant.state=AS.LEAVING; ant.underground=true;
    }
  }

  // ── SOLDIER BEHAVIOUR ─────────────────────────────────────────────
  _moveSoldier(ant){
    const{cx,cy}=this;
    const alarmHere=this.alarm[this.idx(ant.x,ant.y)];
    const pred=this.predators.find(p=>p.alive&&
      Math.abs(p.x-ant.x)<=14&&Math.abs(p.y-ant.y)<=14);

    if(pred||alarmHere>12){
      const target=pred||{x:cx,y:cy};
      [ant.x,ant.y]=this.stepTo(ant.x,ant.y,target.x,target.y);
      if(pred&&Math.abs(ant.x-pred.x)<=1&&Math.abs(ant.y-pred.y)<=1){
        pred.stunTimer=rI(8,20);
        this.alarm[this.idx(ant.x,ant.y)]=Math.min(100,this.alarm[this.idx(ant.x,ant.y)]+5);
        if(pred.stunTimer>40) pred.alive=false;
      }
    } else {
      // Patrol in a ring around the entrance
      if(Math.random()<0.12){
        ant.dx=rC([-1,0,1]); ant.dy=rC([-1,0,1]);
        if(!ant.dx&&!ant.dy) ant.dx=1;
      }
      const patR=7;
      const dSq=(ant.x-cx)**2+(ant.y-cy)**2;
      if(dSq<(patR-1)**2){ ant.dy=1; }
      if(dSq>(patR+2)**2){
        const d=Math.sqrt(dSq)||1;
        ant.dx=Math.round((cx-ant.x)/d);
        ant.dy=Math.round((cy-ant.y)/d);
      }
      const nx=clamp(ant.x+ant.dx,0,this.W-1);
      const ny=clamp(ant.y+ant.dy,0,this.H-1);
      if(this.isPassable(nx,ny)&&!this.isUnderground(nx,ny)){
        ant.x=nx; ant.y=ny;
      }
    }
  }

  // ── DIGGER BEHAVIOUR ──────────────────────────────────────────────
  _findDigFrontier(){
    const cands=[];
    for(let y=1;y<this.H-1;y++) for(let x=1;x<this.W-1;x++){
      const c=this.grid[y][x];
      if(c!==Cell.TUNNEL&&c!==Cell.QUEEN_CH&&c!==Cell.NURSERY&&c!==Cell.FOOD_ST) continue;
      for(const[dx,dy]of[[0,1],[1,0],[-1,0],[0,-1],[1,1],[-1,1],[1,-1],[-1,-1]]){
        if(this.grid[y+dy]?.[x+dx]===Cell.DIRT){
          const bias=1+(dy>0?0.6:0)+(Math.abs(x-this.cx)>this.W/10?0.3:0);
          cands.push([x+dx,y+dy,bias]); break;
        }
      }
    }
    if(!cands.length) return null;
    const ch=weightedChoice(cands,cands.map(c=>c[2]));
    return[ch[0],ch[1]];
  }

  _digStep(ant){
    if(!ant.digTarget) ant.digTarget=this._findDigFrontier();
    if(!ant.digTarget){ ant.state=AS.IN_NEST; return; }
    const[tx,ty]=ant.digTarget;
    [ant.x,ant.y]=this.stepTo(ant.x,ant.y,tx,ty);
    if(ant.x===tx&&ant.y===ty){
      const dirs=[[0,1],[1,0],[-1,0],[0,-1],[1,1],[-1,1],[1,-1],[-1,-1]]
        .sort(()=>Math.random()-.5);
      let dug=false;
      for(const[dx,dy]of dirs){
        const nx=ant.x+dx, ny=ant.y+dy;
        if(this.grid[ny]?.[nx]===Cell.DIRT){
          this.grid[ny][nx]=Cell.TUNNEL;
          ant.digTarget=[nx,ny]; dug=true; break;
        }
      }
      if(!dug) ant.digTarget=null;
      if(Math.random()<0.04&&ant.digTarget){
        const[fx,fy]=ant.digTarget;
        this._fillChamber(fx,fy,2,1,Cell.TUNNEL);
        ant.digTarget=null;
      }
      if(Math.random()<0.06){ ant.state=AS.IN_NEST; ant.digTarget=null; }
    }
  }

  // ── PREDATORS ─────────────────────────────────────────────────────
  spawnPredator(type='spider'){
    const side=rC([0,1,2,3]);
    let x,y;
    if(side===0){x=rI(2,this.W-3);y=0;}
    else if(side===1){x=rI(2,this.W-3);y=this.H-1;}
    else if(side===2){x=0;y=rI(2,this.H-3);}
    else{x=this.W-1;y=rI(2,this.H-3);}
    this.predators.push(new Predator(x,y,type));
  }

  movePredators(){
    for(const p of this.predators){
      if(!p.alive) continue;
      if(p.stunTimer>0){ p.stunTimer--; continue; }
      let target=null, bestD=22;
      for(const ant of this.ants){
        if(ant.underground||ant.type===AT.QUEEN||ant.type>AT.DIGGER) continue;
        const d=Math.abs(ant.x-p.x)+Math.abs(ant.y-p.y);
        if(d<bestD){ bestD=d; target=ant; }
      }
      if(target){
        p.dx=target.x>p.x?1:(target.x<p.x?-1:0);
        p.dy=target.y>p.y?1:(target.y<p.y?-1:0);
      } else if(Math.random()<0.12){
        p.dx=rC([-1,0,1]); p.dy=rC([-1,0,1]);
        if(!p.dx&&!p.dy) p.dx=1;
      }
      const nx=clamp(p.x+p.dx,0,this.W-1);
      const ny=clamp(p.y+p.dy,0,this.H-1);
      if(this.isPassable(nx,ny)&&!this.isUnderground(nx,ny)){
        p.x=nx; p.y=ny;
      } else{ p.dx=rC([-1,0,1]); p.dy=rC([-1,0,1]); }

      // Kill surface ants; death releases alarm cascade
      for(const ant of this.ants){
        if(ant.x===p.x&&ant.y===p.y&&!ant.underground&&
           ant.type!==AT.QUEEN&&ant.type>AT.PUPA){
          ant._dead=true;
          this.alarm[this.idx(ant.x,ant.y)]=Math.min(100,
            this.alarm[this.idx(ant.x,ant.y)]+80);
          p.kills++;
        }
      }
    }
    this.predators=this.predators.filter(p=>p.alive);
    this.ants=this.ants.filter(a=>!a._dead);
  }

  // ── PHEROMONE UPDATE ──────────────────────────────────────────────
  updatePheromones(){
    const N=this.W*this.H, W=this.W, H=this.H;
    // Alarm diffuses to 4 neighbours each tick (fast volatilisation)
    const newAlarm=new Float32Array(N);
    for(let y=1;y<H-1;y++) for(let x=1;x<W-1;x++){
      const i=y*W+x, v=this.alarm[i];
      if(v<0.1) continue;
      const spread=v*0.12;
      newAlarm[i]+=v*0.52;
      newAlarm[(y-1)*W+x]+=spread; newAlarm[(y+1)*W+x]+=spread;
      newAlarm[y*W+x-1] +=spread;  newAlarm[y*W+x+1] +=spread;
    }
    for(let i=0;i<N;i++){
      this.trail[i]*=TRAIL_DECAY;    if(this.trail[i]<0.05)  this.trail[i]=0;
      this.brood[i]*=BROOD_DECAY;    if(this.brood[i]<0.1)   this.brood[i]=0;
      this.repellent[i]*=REPEL_DECAY;if(this.repellent[i]<0.1)this.repellent[i]=0;
      this.alarm[i]=newAlarm[i]*ALARM_DECAY; if(this.alarm[i]<0.1) this.alarm[i]=0;
    }
    // Rain washes surface pheromones faster
    if(this.raining){
      for(let y=0;y<H;y++) for(let x=0;x<W;x++){
        if(this.grid[y][x]===Cell.GRASS||this.grid[y][x]===Cell.DIRT){
          const i=y*W+x;
          this.trail[i]*=0.60; this.alarm[i]*=0.70; this.repellent[i]*=0.85;
        }
      }
    }
  }

  // ── MAIN UPDATE ───────────────────────────────────────────────────
  update(){
    this.tick++;
    const phase=this.dayPhase();
    const night=phase<0.2||phase>0.8;

    for(const ant of this.ants) this.moveAnt(ant);

    this.movePredators();
    const maxPred=night?3:1;
    if(this.predators.length<maxPred&&Math.random()<(night?0.003:0.001))
      this.spawnPredator(night?'spider':'beetle');
    if(phase>0.2&&phase<0.25&&this.predators.length) this.predators.shift();

    this.updatePheromones();

    // Food regeneration (faster during day — plants grow)
    this.foodTimer++;
    if(this.foodTimer>=(this.isDay()?25:80)){
      this.foodTimer=0;
      if(this.food.size<90) this.spawnFood(1);
    }

    // Rain events
    this.rainTimer--;
    if(this.rainTimer<=0&&!this.raining){
      this.raining=true; this.rainLeft=rI(50,130); this.rainTimer=rI(600,1400);
    }
    if(this.raining){ this.rainLeft--; if(this.rainLeft<=0) this.raining=false; }
  }
}

// ═══════════════════════════════════════════════════════════════════
//  RENDERER — top-down view
// ═══════════════════════════════════════════════════════════════════
function render(farm, ctx){
  const{W,H}=farm;
  const iw=W*SCALE, ih=H*SCALE;
  const img=ctx.createImageData(iw,ih);
  const d=img.data;
  const phase=farm.dayPhase();
  const nf=farm.nightFade();

  // Ambient: 1.0 at noon, 0.35 at midnight
  const ambient=lerp(0.35, 1.0, 1-nf);
  const[ambR,ambG,ambB]=ambientRGB(phase);
  // Tint factor: how much ambient sky colour bleeds onto ground
  const tint=lerp(0, 0.22, 1-nf);

  // Entity lookup maps (one entity per cell in render)
  const antMap=new Map(), broodMap=new Map();
  for(const ant of farm.ants){
    const k=ant.x+','+ant.y;
    if(ant.type===AT.EGG||ant.type===AT.LARVA||ant.type===AT.PUPA||
       ant.type===AT.QUEEN||ant.type===AT.NURSE){
      if(!broodMap.has(k)) broodMap.set(k,ant);
    } else {
      if(!antMap.has(k)) antMap.set(k,ant);
    }
  }
  const predSet=new Set(farm.predators.filter(p=>p.alive).map(p=>p.x+','+p.y));

  for(let gy=0;gy<H;gy++) for(let gx=0;gx<W;gx++){
    const cell=farm.grid[gy][gx];
    const ii=farm.idx(gx,gy);
    const s=farm.shade[gy][gx];
    let r,g,b;

    if(cell===Cell.GRASS){
      // Varied green with subtle texture
      const tx=(gx*7+gy*11)%20, ty=(gx*13+gy*7)%25;
      r=Math.round((38+tx)*s*ambient);
      g=Math.round((112+ty)*s*ambient);
      b=Math.round((28+tx*0.4)*s*ambient);
    } else if(cell===Cell.DIRT){
      const tx=(gx*5+gy*9)%22;
      r=Math.round((128+tx)*s*ambient);
      g=Math.round((90+tx*0.7)*s*ambient);
      b=Math.round((48+tx*0.4)*s*ambient);
    } else if(cell===Cell.ROCK){
      const rv=(gx*7+gy*11)%28;
      r=Math.round((95+rv)*s*ambient*0.75);
      g=Math.round((90+rv)*s*ambient*0.75);
      b=Math.round((85+rv)*s*ambient*0.75);
    } else {
      // Underground cells: depth-based darkness (deeper = darker)
      const dep=farm.depth[ii];
      const dark=dep>=0?lerp(0.60,0.18,dep):0.35;
      if(cell===Cell.TUNNEL){
        r=Math.round(40*dark); g=Math.round(24*dark); b=Math.round(10*dark);
      } else if(cell===Cell.QUEEN_CH){
        r=Math.round(190*dark); g=Math.round(80*dark); b=Math.round(170*dark);
      } else if(cell===Cell.NURSERY){
        r=Math.round(200*dark); g=Math.round(135*dark); b=Math.round(22*dark);
      } else if(cell===Cell.FOOD_ST){
        r=Math.round(70*dark); g=Math.round(165*dark); b=Math.round(55*dark);
      } else { // MIDDEN
        r=Math.round(75*dark); g=Math.round(58*dark); b=Math.round(28*dark);
      }
    }

    // Apply night sky colour tint to surface cells
    if(cell===Cell.GRASS||cell===Cell.DIRT){
      r=Math.round(lerp(r,ambR,tint));
      g=Math.round(lerp(g,ambG,tint));
      b=Math.round(lerp(b,ambB,tint));
    }

    // ── Pheromone overlays ───────────────────────────────────────
    // Trail pheromone: bright cyan glow (most visible on grass)
    const tr=Math.min(1,farm.trail[ii]/100);
    if(tr>0.02){
      r=Math.round(lerp(r,15,tr*0.55));
      g=Math.round(lerp(g,190,tr*0.55));
      b=Math.round(lerp(b,255,tr*0.72));
    }
    // Alarm pheromone: red glow
    const al=Math.min(1,farm.alarm[ii]/80);
    if(al>0.05){
      r=Math.min(255,Math.round(r+al*185));
      g=Math.round(lerp(g,0,al*0.55));
      b=Math.round(lerp(b,0,al*0.55));
    }
    // Repellent: warm ochre on surface (marks depleted food zones)
    if(cell===Cell.GRASS||cell===Cell.DIRT){
      const rep=Math.min(1,farm.repellent[ii]/50);
      if(rep>0.08){
        r=Math.min(255,Math.round(r+rep*95));
        g=Math.min(255,Math.round(g+rep*50));
        b=Math.round(b*Math.max(0,1-rep*0.55));
      }
    }
    // Brood pheromone: warm glow in nursery
    if(cell===Cell.NURSERY){
      const br=Math.min(1,farm.brood[ii]/60);
      if(br>0.05){
        r=Math.min(255,Math.round(r+br*45));
        g=Math.min(255,Math.round(g+br*25));
      }
    }

    // ── Entities ─────────────────────────────────────────────────
    const k=gx+','+gy;
    const ant=antMap.get(k);
    const broodEnt=broodMap.get(k);
    const hasPred=predSet.has(k);
    const fq=farm.food.get(k)||0;
    const isMidden=farm.midden.has(k);

    const s2=SCALE/2-0.5;
    const dotR2=Math.pow(Math.max(2,SCALE*0.36),2);
    const smR2 =Math.pow(Math.max(1,SCALE*0.22),2);

    for(let sy=0;sy<SCALE;sy++) for(let sx=0;sx<SCALE;sx++){
      const dist2=(sx-s2)**2+(sy-s2)**2;
      const pi=((gy*SCALE+sy)*iw+(gx*SCALE+sx))*4;

      if(hasPred&&dist2<=dotR2*1.6){
        const inner=dist2<=dotR2*0.28;
        d[pi]=inner?70:235; d[pi+1]=inner?12:80; d[pi+2]=inner?0:5;
      } else if(ant&&dist2<=dotR2){
        if(ant.type===AT.SOLDIER){
          d[pi]=225; d[pi+1]=30;  d[pi+2]=30;
        } else if(ant.type===AT.DIGGER){
          d[pi]=255; d[pi+1]=140; d[pi+2]=0;
        } else if(ant.hasFood){
          d[pi]=255; d[pi+1]=218; d[pi+2]=0;  // gold = carrying food
        } else if(ant.alarmLevel>0.5){
          d[pi]=205; d[pi+1]=55;  d[pi+2]=55;
        } else {
          // Underground ants dimmer
          const dim=ant.underground?0.55:1;
          d[pi]=Math.round(18*dim); d[pi+1]=Math.round(18*dim); d[pi+2]=Math.round(18*dim);
        }
      } else if(fq>0&&dist2<=dotR2){
        d[pi]=185+fq*22; d[pi+1]=38; d[pi+2]=22;
      } else if(broodEnt&&dist2<=smR2){
        if(broodEnt.type===AT.EGG){
          d[pi]=245; d[pi+1]=245; d[pi+2]=245;
        } else if(broodEnt.type===AT.LARVA){
          d[pi]=225; d[pi+1]=200; d[pi+2]=125;
        } else if(broodEnt.type===AT.PUPA){
          d[pi]=190; d[pi+1]=168; d[pi+2]=98;
        } else if(broodEnt.type===AT.QUEEN){
          if(dist2<=dotR2){d[pi]=215;d[pi+1]=50;d[pi+2]=215;}
          else{d[pi]=r;d[pi+1]=g;d[pi+2]=b;}
        } else if(broodEnt.type===AT.NURSE){
          d[pi]=85; d[pi+1]=215; d[pi+2]=215;
        } else{d[pi]=r;d[pi+1]=g;d[pi+2]=b;}
      } else if(isMidden&&(cell===Cell.MIDDEN||cell===Cell.TUNNEL)){
        d[pi]=58; d[pi+1]=47; d[pi+2]=22;
      } else {
        d[pi]=r; d[pi+1]=g; d[pi+2]=b;
      }
      d[pi+3]=255;
    }
  }
  ctx.putImageData(img,0,0);

  // Night overlay (darkens and adds blue tint)
  if(nf>0){
    ctx.fillStyle=`rgba(0,5,30,${nf*0.60})`;
    ctx.fillRect(0,0,iw,ih);
  }

  // Stars at night (scattered over entire top-down view)
  if(nf>0.3&&farm._stars){
    ctx.fillStyle=`rgba(255,255,220,${nf*0.75})`;
    for(const[sx,sy]of farm._stars){
      const px=sx*SCALE+(SCALE>>1), py=sy*SCALE+(SCALE>>1);
      const r=nf*1.5;
      ctx.beginPath(); ctx.arc(px,py,r,0,Math.PI*2); ctx.fill();
    }
  }

  // Rain streaks
  if(farm.raining){
    ctx.save();
    ctx.strokeStyle='rgba(160,200,255,0.13)';
    ctx.lineWidth=1;
    for(let i=0;i<90;i++){
      const x=rI(0,W)*SCALE, y=rI(0,H)*SCALE;
      ctx.beginPath(); ctx.moveTo(x,y); ctx.lineTo(x+1,y+7); ctx.stroke();
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
  const W=+sW.value, H=+sH.value;
  canvas.width=W*SCALE; canvas.height=H*SCALE;
  farm=new AntFarm(W,H,+sAnts.value,+sFood.value);
  // Generate stars (random points over the whole grid)
  farm._stars=Array.from({length:80},()=>[rI(0,W-1),rI(0,H-1)]);
  render(farm,ctx); updateStats();
}

const PHASE_LABELS=['🌙 Night','🌅 Dawn','☀️ Day','🌇 Dusk'];
function updateStats(){
  const p=farm.dayPhase();
  sPhase.textContent=PHASE_LABELS[Math.round(p*4)%4]+(farm.raining?' 🌧️':'');
  sDay.textContent=Math.floor(farm.tick/DAY_LEN)+1;
  sTick.textContent=farm.tick;
  sPop.textContent=farm.ants.filter(a=>a.type>=AT.FORAGER&&a.type<=AT.DIGGER).length;
  sBrood.textContent=farm.ants.filter(a=>a.type>=AT.EGG&&a.type<=AT.PUPA).length;
  sStored.textContent=Math.floor(farm.foodStored);
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
btnReset.onclick=()=>{running=false; reset();};
btnFood.onclick=()=>{if(farm) farm.spawnFood(25);};

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
""", height=800, scrolling=False)
