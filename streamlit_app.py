"""
Ant Farm – Side View (full simulation)
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
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#111;color:#eee;font-family:monospace;overflow:hidden}
  #ui{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:6px 10px;
      background:#1a1a1a;border-bottom:1px solid #333}
  label{font-size:11px;color:#aaa}
  input[type=range]{width:80px;vertical-align:middle}
  span.val{font-size:11px;color:#fff;min-width:22px;display:inline-block}
  button{padding:4px 10px;border:none;border-radius:4px;cursor:pointer;
         font-size:12px;font-weight:bold}
  #btnStart{background:#2a9;color:#fff}
  #btnStop{background:#a44;color:#fff}
  #btnReset{background:#555;color:#fff}
  #btnFood{background:#a72;color:#fff}
  #stats{display:flex;gap:16px;padding:4px 10px;background:#161616;
         border-bottom:1px solid #333;font-size:12px;flex-wrap:wrap}
  #stats b{color:#8cf}
  canvas{display:block}
</style>
</head>
<body>
<div id="ui">
  <label>Ants <span class="val" id="vAnts">20</span></label>
  <input type="range" id="sAnts" min="5" max="60" value="20">
  <label>Food <span class="val" id="vFood">30</span></label>
  <input type="range" id="sFood" min="5" max="80" value="30">
  <label>Width <span class="val" id="vW">110</span></label>
  <input type="range" id="sW" min="60" max="180" value="110">
  <label>Height <span class="val" id="vH">60</span></label>
  <input type="range" id="sH" min="35" max="100" value="60">
  <label>Speed <span class="val" id="vSpeed">1</span>x</label>
  <input type="range" id="sSpeed" min="1" max="10" value="1">
  <button id="btnStart">▶ Start</button>
  <button id="btnStop">⏹ Stop</button>
  <button id="btnReset">🔄 Reset</button>
  <button id="btnFood">🍎 +Food</button>
</div>
<div id="stats">
  Day <b id="sDay">1</b> &nbsp;
  <span id="sTimeLabel">☀️ Noon</span> &nbsp;|&nbsp;
  Tick <b id="sTick">0</b> &nbsp;|&nbsp;
  Colony <b id="sPop">0</b> &nbsp;|&nbsp;
  Eggs <b id="sEggs">0</b> &nbsp;|&nbsp;
  Food stored <b id="sStored">0</b> &nbsp;|&nbsp;
  Surface food <b id="sSurf">0</b> &nbsp;|&nbsp;
  Predators <b id="sPred">0</b>
</div>
<canvas id="farm"></canvas>

<script>
// ── Constants ─────────────────────────────────────────────────────────────────
const Cell = Object.freeze({SKY:0,GRASS:1,DIRT:2,TUNNEL:3,NEST:4});
const AS   = Object.freeze({LEAVING:0,FORAGING:1,RETURNING:2,IN_NEST:3,DIGGING:4,FLEEING:5,GUARDING:6});
const AT   = Object.freeze({WORKER:0,DIGGER:1,SOLDIER:2,QUEEN:3,EGG:4,LARVA:5});
const DAY_LEN = 600;   // ticks per full day
const MAX_ANTS = 80;
const SCALE = 9;

// ── Utilities ─────────────────────────────────────────────────────────────────
const rI=(a,b)=>Math.floor(Math.random()*(b-a+1))+a;
const rC=a=>a[Math.floor(Math.random()*a.length)];
const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
const lerp=(a,b,t)=>a+(b-a)*t;
const lerpI=(a,b,t)=>Math.round(lerp(a,b,t));

// ── Day / Night sky colour ────────────────────────────────────────────────────
// phase: 0=midnight,0.25=dawn,0.5=noon,0.75=dusk
function skyRGB(phase, yFrac) {
  // Key colour stops [r,g,b] at phase 0,0.25,0.5,0.75,1
  const stops = [
    [3,   3,  20],   // midnight
    [255,130,  40],  // dawn
    [100,185,255],   // noon
    [240, 80,  20],  // dusk
    [3,   3,  20],   // midnight again
  ];
  const n = stops.length - 1;
  const fp = phase * n;
  const i  = Math.floor(fp);
  const t  = fp - i;
  const [r1,g1,b1] = stops[clamp(i,  0,n)];
  const [r2,g2,b2] = stops[clamp(i+1,0,n)];
  // Darken toward ground
  const d = 1 - yFrac * 0.18;
  return [lerpI(r1,r2,t)*d|0, lerpI(g1,g2,t)*d|0, lerpI(b1,b2,t)*d|0];
}

// ── Ant ──────────────────────────────────────────────────────────────────────
class Ant {
  constructor(x,y,type=AT.WORKER) {
    this.x=x; this.y=y; this.type=type;
    this.state = (type===AT.QUEEN||type===AT.EGG||type===AT.LARVA) ? AS.IN_NEST : AS.LEAVING;
    this.hasFood=false; this.dx=rC([-1,1]); this.dy=0;
    this.age=0; this.hatchIn = (type===AT.EGG)?rI(60,90):(type===AT.LARVA)?rI(80,120):0;
    this.digTarget=null; this.fleeTimer=0;
  }
}

// ── Predator (surface spider) ─────────────────────────────────────────────────
class Predator {
  constructor(x,y) {
    this.x=x; this.y=y; this.dx=rC([-1,1]);
    this.alive=true; this.target=null; this.kills=0;
  }
}

// ── AntFarm ───────────────────────────────────────────────────────────────────
class AntFarm {
  constructor(W,H,antCount,foodCount) {
    this.W=W; this.H=H;
    this.GY=Math.max(6,Math.floor(H/6));
    this.grid=Array.from({length:H},()=>new Uint8Array(W));
    this.food=new Set(); this.foodStored=0; this.tick=0;
    this.ants=[]; this.predators=[];
    this.shade=Array.from({length:H},()=>
      Float32Array.from({length:W},()=>0.82+Math.random()*0.36));
    this.queenLayTimer=0; this.foodRespawnTimer=0;
    this.stars=Array.from({length:60},()=>({
      x:rI(0,W-1),y:rI(0,Math.floor(H/6)-2),br:Math.random()
    }));
    this.build();
    this.spawnFood(foodCount);
    this.spawnColony(antCount);
  }

  // ── World building ──────────────────────────────────────────────────────────
  build() {
    const {W,H,GY}=this;
    const cx=Math.floor(W/2);
    this.cx=cx;
    this.nestY=GY+Math.max(9,Math.floor((H-GY)/3));

    for(let y=GY;y<H;y++) for(let x=0;x<W;x++) this.grid[y][x]=Cell.DIRT;
    for(let x=0;x<W;x++) this.grid[GY][x]=Cell.GRASS;

    // Main nest chamber
    for(let dy=-2;dy<=2;dy++) for(let dx=-7;dx<=7;dx++){
      const ny=this.nestY+dy,nx=cx+dx;
      if(ny>GY&&ny<H&&nx>=0&&nx<W) this.grid[ny][nx]=Cell.NEST;
    }
    // Entrance shaft
    for(let y=GY+1;y<this.nestY-2;y++) this.grid[y][cx]=Cell.TUNNEL;

    // Horizontal branches
    const br=Math.floor(W/4);
    for(let dx=1;dx<=br;dx++){
      if(cx-dx>=0) this.grid[this.nestY][cx-dx]=Cell.TUNNEL;
      if(cx+dx<W)  this.grid[this.nestY][cx+dx]=Cell.TUNNEL;
    }
    // Side shafts + small chambers
    for(const bx of [cx-br,cx+br]){
      if(bx<0||bx>=W) continue;
      for(let dy=1;dy<=5;dy++){const ny=this.nestY+dy;if(ny<H)this.grid[ny][bx]=Cell.TUNNEL;}
      for(let ddx=-2;ddx<=2;ddx++){
        const sx=bx+ddx,ny=Math.min(H-1,this.nestY+5);
        if(sx>=0&&sx<W) this.grid[ny][sx]=Cell.TUNNEL;
      }
    }
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────
  inB(x,y){return x>=0&&x<this.W&&y>=0&&y<this.H;}
  pSurf(x,y){return this.inB(x,y)&&(this.grid[y][x]===Cell.SKY||this.grid[y][x]===Cell.GRASS);}
  pUnder(x,y){return this.inB(x,y)&&(this.grid[y][x]===Cell.TUNNEL||this.grid[y][x]===Cell.NEST);}
  isDirt(x,y){return this.inB(x,y)&&this.grid[y][x]===Cell.DIRT;}

  stepTo(ax,ay,tx,ty,under){
    const ok=under?(x,y)=>this.pUnder(x,y):(x,y)=>this.pSurf(x,y);
    const ddx=ax===tx?0:(tx>ax?1:-1);
    const ddy=ay===ty?0:(ty>ay?1:-1);
    for(const[nx,ny]of[[ax+ddx,ay+ddy],[ax+ddx,ay],[ax,ay+ddy],[ax-ddy,ay+ddx],[ax+ddy,ay-ddx]])
      if(ok(nx,ny))return[nx,ny];
    const nb=[];
    for(let dx=-1;dx<=1;dx++)for(let dy=-1;dy<=1;dy++)
      if((dx||dy)&&ok(ax+dx,ay+dy))nb.push([ax+dx,ay+dy]);
    return nb.length?rC(nb):[ax,ay];
  }

  // ── Spawning ─────────────────────────────────────────────────────────────────
  spawnFood(n){
    let placed=0,tries=0;
    while(placed<n&&tries<n*50&&this.food.size<80){
      tries++;
      const x=rI(1,this.W-2),y=rI(0,this.GY-1),k=x+','+y;
      if(!this.food.has(k)){this.food.add(k);placed++;}
    }
  }

  spawnColony(n){
    // Queen
    this.ants.push(new Ant(this.cx,this.nestY,AT.QUEEN));
    // Initial eggs
    for(let i=0;i<5;i++){
      const x=clamp(this.cx+rI(-3,3),0,this.W-1);
      const y=clamp(this.nestY+rI(-1,1),0,this.H-1);
      this.ants.push(new Ant(x,y,AT.EGG));
    }
    // Workers and diggers
    const diggers=Math.floor(n*0.3);
    for(let i=0;i<n;i++){
      const type=i<diggers?AT.DIGGER:AT.WORKER;
      const x=clamp(this.cx+rI(-4,4),0,this.W-1);
      const y=clamp(this.nestY+rI(-1,1),0,this.H-1);
      this.ants.push(new Ant(x,y,type));
    }
  }

  // ── Day / Night ──────────────────────────────────────────────────────────────
  dayPhase(){return(this.tick%DAY_LEN)/DAY_LEN;}  // 0=midnight,0.25=dawn,0.5=noon,0.75=dusk
  isDay(){const p=this.dayPhase();return p>0.2&&p<0.8;}
  isDusk(){const p=this.dayPhase();return p>0.7;}

  // ── Ant logic ─────────────────────────────────────────────────────────────────
  moveAnt(ant){
    const{GY}=this;
    ant.age++;

    // Hatch eggs / larvae
    if((ant.type===AT.EGG||ant.type===AT.LARVA)&&ant.age>=ant.hatchIn){
      if(ant.type===AT.EGG){ant.type=AT.LARVA;ant.age=0;ant.hatchIn=rI(80,130);}
      else{
        // Become adult — pick type based on colony needs
        const workers=this.ants.filter(a=>a.type===AT.WORKER).length;
        const diggers=this.ants.filter(a=>a.type===AT.DIGGER).length;
        ant.type=(diggers<workers*0.35)?AT.DIGGER:AT.WORKER;
        ant.state=AS.LEAVING;
      }
      return;
    }
    if(ant.type===AT.EGG||ant.type===AT.LARVA) return;

    // Queen: lay egg periodically
    if(ant.type===AT.QUEEN){
      this.queenLayTimer++;
      if(this.queenLayTimer>100&&this.ants.length<MAX_ANTS){
        this.queenLayTimer=0;
        const x=clamp(ant.x+rI(-2,2),0,this.W-1);
        const y=clamp(ant.y+rI(-1,1),0,this.H-1);
        this.ants.push(new Ant(x,y,AT.EGG));
      }
      return;
    }

    // Soldier: patrol nest entrance, attack nearby predators
    if(ant.type===AT.SOLDIER){
      this._moveSoldier(ant);
      return;
    }

    // Flee from predator
    if(ant.fleeTimer>0){
      ant.fleeTimer--;
      ant.state=AS.FLEEING;
    }

    const nearPred=this.predators.find(p=>Math.abs(p.x-ant.x)<=5&&Math.abs(p.y-ant.y)<=3);
    if(nearPred&&ant.y<=GY){
      ant.fleeTimer=rI(8,18);
      ant.state=AS.FLEEING;
      ant.dx=ant.x>nearPred.x?1:-1;
    }

    if(ant.state===AS.FLEEING){
      const nx=clamp(ant.x+ant.dx,0,this.W-1);
      const ny=GY;
      if(this.pSurf(nx,ny)){ant.x=nx;ant.y=ny;}
      else ant.dx=-ant.dx;
      if(ant.fleeTimer<=0) ant.state=AS.FORAGING;
      return;
    }

    // DIGGER specific state
    if(ant.type===AT.DIGGER&&ant.state===AS.DIGGING){
      this._digStep(ant);
      return;
    }

    // Standard states
    if(ant.state===AS.LEAVING){
      [ant.x,ant.y]=this.stepTo(ant.x,ant.y,this.cx,GY+1,true);
      if(ant.y===GY+1&&ant.x===this.cx){
        ant.y=GY;
        // Diggers go dig if colony has food
        if(ant.type===AT.DIGGER&&this.foodStored>3&&Math.random()<0.7){
          ant.state=AS.DIGGING;
          ant.digTarget=this._findDigTarget();
        } else {
          // Slow down at night
          if(!this.isDay()&&Math.random()<0.5){ant.state=AS.IN_NEST;return;}
          ant.state=AS.FORAGING;
          ant.dx=rC([-1,1]);
        }
      }

    } else if(ant.state===AS.FORAGING){
      if(Math.random()<0.2) ant.dx=rC([-1,-1,0,1,1]);
      const ny=Math.random()>0.35?GY:Math.max(0,GY-rI(1,3));
      const nx=clamp(ant.x+ant.dx,0,this.W-1);
      if(this.pSurf(nx,ny)){ant.x=nx;ant.y=ny;}
      if(ant.x===0||ant.x===this.W-1) ant.dx=-ant.dx;

      for(const k of this.food){
        const[fx,fy]=k.split(',').map(Number);
        if(Math.abs(fx-ant.x)<=1&&Math.abs(fy-ant.y)<=1){
          this.food.delete(k);ant.hasFood=true;ant.state=AS.RETURNING;ant.dx=-ant.dx;break;
        }
      }

    } else if(ant.state===AS.RETURNING){
      if(ant.y<=GY){
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,this.cx,GY,false);
        if(ant.x===this.cx&&ant.y===GY) ant.y=GY+1;
      } else {
        [ant.x,ant.y]=this.stepTo(ant.x,ant.y,this.cx,this.nestY,true);
        if(this.grid[ant.y][ant.x]===Cell.NEST){
          ant.state=AS.IN_NEST; ant.hasFood=false; this.foodStored++;
          // Promote to soldier if colony is large enough
          if(ant.type===AT.WORKER&&this.foodStored>20&&
             this.ants.filter(a=>a.type===AT.SOLDIER).length<3&&Math.random()<0.05){
            ant.type=AT.SOLDIER;
          }
        }
      }

    } else if(ant.state===AS.IN_NEST){
      if(Math.random()<0.12) ant.state=AS.LEAVING;
    }
  }

  _moveSoldier(ant){
    const{GY}=this;
    const pred=this.predators.find(p=>Math.abs(p.x-ant.x)<=8&&Math.abs(p.y-ant.y)<=2);
    if(pred){
      // Chase predator
      [ant.x,ant.y]=this.stepTo(ant.x,ant.y,pred.x,pred.y,false);
      if(ant.x===pred.x&&ant.y===pred.y){pred.alive=false;}  // kill predator
    } else {
      // Patrol near entrance
      if(ant.y<=GY){
        if(Math.random()<0.15) ant.dx=rC([-1,1]);
        const nx=clamp(ant.x+ant.dx,clamp(this.cx-15,0,this.W-1),clamp(this.cx+15,0,this.W-1));
        if(this.pSurf(nx,GY)){ant.x=nx;ant.y=GY;}
      } else {
        ant.y=GY; // emerge
      }
    }
  }

  _findDigTarget(){
    // Find a tunnel frontier cell (tunnel adjacent to dirt), prefer going down/sideways
    const candidates=[];
    for(let y=this.GY+1;y<this.H-1;y++)
      for(let x=1;x<this.W-1;x++){
        if(this.grid[y][x]!==Cell.TUNNEL&&this.grid[y][x]!==Cell.NEST) continue;
        for(const[dx,dy]of[[1,0],[-1,0],[0,1],[1,1],[-1,1]]){
          if(this.isDirt(x+dx,y+dy)){candidates.push([x,y]);break;}
        }
      }
    return candidates.length?rC(candidates):null;
  }

  _digStep(ant){
    const{GY}=this;
    if(!ant.digTarget){
      ant.digTarget=this._findDigTarget();
      if(!ant.digTarget){ant.state=AS.RETURNING;return;}
    }
    const[tx,ty]=ant.digTarget;
    if(ant.y>GY){
      // Underground — move to dig target
      [ant.x,ant.y]=this.stepTo(ant.x,ant.y,tx,ty,true);
      if(ant.x===tx&&ant.y===ty){
        // Dig one adjacent dirt cell (prefer down/sideways)
        const dirs=[[0,1],[1,0],[-1,0],[1,1],[-1,1]].sort(()=>Math.random()-.5);
        let dug=false;
        for(const[dx,dy]of dirs){
          const nx=ant.x+dx,ny=ant.y+dy;
          if(this.isDirt(nx,ny)){
            this.grid[ny][nx]=Cell.TUNNEL;
            ant.digTarget=[nx,ny]; // continue digging from new cell
            dug=true;
            break;
          }
        }
        if(!dug){ant.digTarget=null;} // dead end, find new target
        // After digging a while, return home
        if(Math.random()<0.08){ant.state=AS.RETURNING;ant.digTarget=null;}
      }
    } else {
      // On surface — head back underground
      [ant.x,ant.y]=this.stepTo(ant.x,ant.y,this.cx,GY,false);
      if(ant.x===this.cx&&ant.y===GY) ant.y=GY+1;
    }
  }

  // ── Predators ────────────────────────────────────────────────────────────────
  spawnPredator(){
    const x=rC([0,this.W-1]);
    this.predators.push(new Predator(x,this.GY));
  }

  movePredators(){
    const{GY}=this;
    for(const p of this.predators){
      if(!p.alive) continue;
      // Chase nearest ant on surface
      let closest=null,bestD=12;
      for(const ant of this.ants){
        if(ant.y>GY||ant.type===AT.EGG||ant.type===AT.LARVA||ant.type===AT.QUEEN) continue;
        const d=Math.abs(ant.x-p.x)+Math.abs(ant.y-p.y);
        if(d<bestD){bestD=d;closest=ant;}
      }
      if(closest){
        p.dx=closest.x>p.x?1:-1;
      } else {
        if(Math.random()<0.1) p.dx=rC([-1,1]);
      }
      const nx=clamp(p.x+p.dx,0,this.W-1);
      if(this.pSurf(nx,GY)){p.x=nx;p.y=GY;}
      else p.dx=-p.dx;

      // Kill ants in same cell
      for(const ant of this.ants){
        if(ant.x===p.x&&ant.y===p.y&&ant.y<=GY&&
           ant.type!==AT.QUEEN&&ant.type!==AT.EGG&&ant.type!==AT.LARVA){
          ant._dead=true; p.kills++;
        }
      }
    }
    this.predators=this.predators.filter(p=>p.alive);
    this.ants=this.ants.filter(a=>!a._dead);
  }

  // ── Main update ───────────────────────────────────────────────────────────────
  update(){
    this.tick++;
    const phase=this.dayPhase();

    // Move all ants
    for(const ant of this.ants) this.moveAnt(ant);

    // Predators: spawn at dusk/night, removed at dawn
    this.movePredators();
    if(phase>0.75||phase<0.2){  // night
      const maxPred=3;
      if(this.predators.length<maxPred&&Math.random()<0.005) this.spawnPredator();
    } else {
      // Dawn — chase predators away
      if(this.predators.length&&phase>0.2&&phase<0.25){
        if(Math.random()<0.1) this.predators.shift();
      }
    }

    // Food regeneration — faster during day
    this.foodRespawnTimer++;
    const foodInterval=this.isDay()?25:80;
    if(this.foodRespawnTimer>=foodInterval){
      this.foodRespawnTimer=0;
      if(this.food.size<70) this.spawnFood(1);
    }
  }
}

// ── Renderer ──────────────────────────────────────────────────────────────────
function render(farm,ctx){
  const{W,H,GY}=farm;
  const iw=W*SCALE,ih=H*SCALE;
  const img=ctx.createImageData(iw,ih);
  const d=img.data;
  const phase=farm.dayPhase();
  const nightFade=clamp((phase<0.25?(0.25-phase)/0.25:(phase-0.75)/0.25),0,1); // 0=day,1=night

  // Ant / food lookup maps
  const antMap=new Map();
  for(const ant of farm.ants){
    if(ant.type===AT.EGG||ant.type===AT.LARVA||ant.type===AT.QUEEN) continue;
    const k=ant.x+','+ant.y;
    if(!antMap.has(k)) antMap.set(k,ant);
  }
  const nestEntities=new Map(); // eggs/larvae/queen in nest cells
  for(const ant of farm.ants){
    if(ant.type===AT.EGG||ant.type===AT.LARVA||ant.type===AT.QUEEN){
      const k=ant.x+','+ant.y;
      if(!nestEntities.has(k)) nestEntities.set(k,ant);
    }
  }
  const predMap=new Set(farm.predators.filter(p=>p.alive).map(p=>p.x+','+p.y));

  // Star positions (only visible at night)
  const starSet=new Set(farm.stars.filter(()=>true).map(s=>s.x+','+s.y));

  for(let gy=0;gy<H;gy++){
    for(let gx=0;gx<W;gx++){
      const cell=farm.grid[gy][gx];
      let r,g,b;

      if(cell===Cell.SKY){
        const yf=gy/Math.max(1,GY);
        [r,g,b]=skyRGB(phase,yf);
      } else if(cell===Cell.GRASS){
        // Darken grass at night
        const v=(gx*7+gy*3)%20;
        const bright=1-nightFade*0.6;
        r=Math.round(30*bright); g=Math.round((140+v)*bright); b=Math.round(30*bright);
      } else if(cell===Cell.DIRT){
        const s=farm.shade[gy][gx];
        r=clamp(101*s|0,0,255); g=clamp(67*s|0,0,255); b=clamp(33*s|0,0,255);
      } else if(cell===Cell.TUNNEL){
        r=28; g=14; b=5;
      } else { // NEST
        const s=0.85+0.3*((gx+gy)%2);
        r=clamp(160*s|0,0,255); g=clamp(108*s|0,0,255); b=clamp(18*s|0,0,255);
      }

      const k=gx+','+gy;
      const ant=antMap.get(k);
      const nestEnt=nestEntities.get(k);
      const hasPred=predMap.has(k);
      const hasFood=farm.food.has(k);
      const isStar=cell===Cell.SKY&&starSet.has(k);

      const s2=SCALE/2-0.5;
      const dotR2=Math.pow(Math.max(2,SCALE/3),2);
      const smallR2=Math.pow(Math.max(1,SCALE/5),2);

      for(let sy=0;sy<SCALE;sy++){
        for(let sx=0;sx<SCALE;sx++){
          const dist2=(sx-s2)*(sx-s2)+(sy-s2)*(sy-s2);
          const i=((gy*SCALE+sy)*iw+(gx*SCALE+sx))*4;

          if(hasPred&&dist2<=dotR2*1.4){
            // Predator: orange-red with dark centre
            const inner=dist2<=dotR2*0.3;
            d[i]=inner?80:220; d[i+1]=inner?20:60; d[i+2]=inner?0:0;
          } else if(ant&&dist2<=dotR2){
            // Ant colour by type
            if(ant.type===AT.SOLDIER)     {d[i]=220;d[i+1]=30; d[i+2]=30;}
            else if(ant.type===AT.DIGGER) {d[i]=255;d[i+1]=140;d[i+2]=0;}
            else if(ant.hasFood)          {d[i]=255;d[i+1]=215;d[i+2]=0;}
            else                          {d[i]=15; d[i+1]=15; d[i+2]=15;}
          } else if(hasFood&&dist2<=dotR2){
            d[i]=255;d[i+1]=50;d[i+2]=30;
          } else if(nestEnt&&dist2<=smallR2){
            // Egg=white, Larva=pale yellow, Queen=magenta
            if(nestEnt.type===AT.EGG)        {d[i]=240;d[i+1]=240;d[i+2]=240;}
            else if(nestEnt.type===AT.LARVA) {d[i]=220;d[i+1]=200;d[i+2]=120;}
            else                             {d[i]=220;d[i+1]=50; d[i+2]=220;} // queen
          } else if(isStar&&nightFade>0.3){
            const br=Math.round(200*nightFade);
            d[i]=br;d[i+1]=br;d[i+2]=br+20;
          } else if(cell===Cell.GRASS&&sx===SCALE/2|0&&gx%3===0&&sy<SCALE-1){
            const bright=1-nightFade*0.6;
            d[i]=Math.round(40*bright);d[i+1]=Math.round(200*bright);d[i+2]=Math.round(40*bright);
          } else {
            d[i]=r;d[i+1]=g;d[i+2]=b;
          }
          d[i+3]=255;
        }
      }

      // Draw sun or moon in sky
      if(cell===Cell.SKY&&gy===Math.floor(GY*0.35)){
        const sunX=Math.round(W*(0.5+0.35*Math.cos(phase*Math.PI*2)));
        const moonX=Math.round(W*(0.5+0.35*Math.cos((phase+0.5)*Math.PI*2)));
        const isNightBody=nightFade>0.4;
        const bodyX=isNightBody?moonX:sunX;
        if(Math.abs(gx-bodyX)<=2){
          for(let sy=0;sy<SCALE;sy++) for(let sx=0;sx<SCALE;sx++){
            const dx=sx-s2,dy=sy-s2;
            if(dx*dx+dy*dy<=SCALE*SCALE*0.25){
              const i=((gy*SCALE+sy)*iw+(gx*SCALE+sx))*4;
              if(isNightBody){d[i]=230;d[i+1]=230;d[i+2]=200;}
              else           {d[i]=255;d[i+1]=230;d[i+2]=50;}
              d[i+3]=255;
            }
          }
        }
      }
    }
  }
  ctx.putImageData(img,0,0);
}

// ── UI wiring ─────────────────────────────────────────────────────────────────
const canvas=document.getElementById('farm');
const ctx=canvas.getContext('2d');
let farm,running=false,speed=1;

function cfg(){
  return{W:+sW.value,H:+sH.value,ants:+sAnts.value,food:+sFood.value};
}
function reset(){
  const c=cfg();
  canvas.width=c.W*SCALE; canvas.height=c.H*SCALE;
  farm=new AntFarm(c.W,c.H,c.ants,c.food);
  render(farm,ctx); updateStats();
}
function updateStats(){
  const p=farm.dayPhase();
  const labels=['🌙 Night','🌅 Dawn','☀️ Day','🌇 Dusk','🌙 Night'];
  const li=Math.round(p*4)%4;
  sTimeLabel.textContent=labels[li];
  sDay.textContent=Math.floor(farm.tick/DAY_LEN)+1;
  sTick.textContent=farm.tick;
  sPop.textContent=farm.ants.filter(a=>a.type<=AT.SOLDIER).length;
  sEggs.textContent=farm.ants.filter(a=>a.type===AT.EGG||a.type===AT.LARVA).length;
  sStored.textContent=farm.foodStored;
  sSurf.textContent=farm.food.size;
  sPred.textContent=farm.predators.length;
}

for(const[sid,vid]of[['sAnts','vAnts'],['sFood','vFood'],['sW','vW'],['sH','vH'],['sSpeed','vSpeed']]){
  document.getElementById(sid).addEventListener('input',e=>{
    document.getElementById(vid).textContent=e.target.value;
    if(sid==='sSpeed') speed=+e.target.value;
  });
}
btnStart.onclick=()=>{running=true;};
btnStop.onclick=()=>{running=false;};
btnReset.onclick=()=>{running=false;reset();};
btnFood.onclick=()=>{if(farm)farm.spawnFood(15);};

let last=0;
const MS=280;
function loop(ts){
  requestAnimationFrame(loop);
  if(!farm||!running) return;
  if(ts-last<MS) return;
  last=ts;
  for(let i=0;i<speed;i++) farm.update();
  render(farm,ctx);
  updateStats();
}
reset();
requestAnimationFrame(loop);
</script>
</body>
</html>
""", height=720, scrolling=False)
