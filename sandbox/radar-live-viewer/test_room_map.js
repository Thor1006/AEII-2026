// Synthetic fixtures exercise only the pure accumulator; nothing is served to the live viewer.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'index.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];new vm.Script(script);
const block=script.split('// ROOM_MAP_BEGIN:')[1].split('// ROOM_MAP_END')[0];
const RoomMap=vm.runInNewContext(block.slice(block.indexOf('\n'))+'\nRoomMap;');
const p=(x=.12,y=1.02,z=-.12,velocity=0)=>({x,y,z,velocity});
let tests=0;
function check(name,test){test();tests++;console.log('PASS',name);}
function stable(map,start=1,at=0,point=p()){for(let n=0;n<3;n++)map.addFrame(start+n,[point],at+n*10);}
check('distinct-frame persistence and duplicate frame/cell suppression',()=>{
 const m=new RoomMap();m.addFrame(1,[p(),p(),p()],0);assert.equal(m.snapshot().points.length,0);
 assert.equal(m.addFrame(1,[p()],1),false);m.addFrame(2,[p()],10);assert.equal(m.snapshot().points.length,0);
 m.addFrame(3,[p()],20);assert.equal(m.snapshot().points.length,1);assert.equal(m.snapshot().points[0].hits,3);
});
check('cell coordinates and distance derive from measured points',()=>{
 const m=new RoomMap();stable(m);const q=m.snapshot().points[0];assert(Math.abs(q.x-.12)<1e-12);assert(Math.abs(q.z+.12)<1e-12);assert(Math.abs(q.range-Math.hypot(.12,1.02,-.12))<1e-12);
});
check('observations expire and cannot establish free space',()=>{
 const m=new RoomMap({windowMs:100});stable(m);m.tick(111,true);assert.equal(m.snapshot().points.length,0);m.tick(121,true);assert.equal(m.snapshot().candidates,0);assert.equal(m.cells.size,0);
});
check('memory is bounded and least-recently-seen cells are evicted',()=>{
 const m=new RoomMap({maxCells:2,requiredHits:1});m.addFrame(1,[p(.11),p(.31),p(.51)],0);assert.equal(m.cells.size,2);m.addFrame(2,[p(.31)],1);m.addFrame(3,[p(.71)],2);const xs=Array.from(m.snapshot().points,q=>Number(q.x.toFixed(2))).sort();assert.deepEqual(xs,[.31,.71]);assert.equal(m.evictions,2);
});
check('moving-return option clears old map and does not replay old frames',()=>{
 const m=new RoomMap();stable(m,1,0,p(.12,1.02,-.12,.5));assert.equal(m.cells.size,0);m.setIncludeMoving(true,30);assert.equal(m.addFrame(3,[p()],31),false);stable(m,4,40,p(.12,1.02,-.12,.5));assert.equal(m.snapshot().points.length,1);
});
check('pause freezes map; resume expires old observations without replay',()=>{
 const m=new RoomMap();stable(m);m.setPaused(true,30);m.addFrame(4,[p()],40000);m.tick(50000,true);assert.equal(m.snapshot().points.length,1);m.setPaused(false,50000);assert.equal(m.snapshot().points.length,0);assert.equal(m.addFrame(4,[p()],50001),false);stable(m,5,50010);assert.equal(m.snapshot().points.length,1);
});
check('stopped or stale radar freezes historical map',()=>{
 const m=new RoomMap();stable(m);m.tick(50000,false);assert.equal(m.snapshot().points.length,1);assert.equal(m.snapshot().duration_seconds,.02);
});
check('clear preserves frame deduplication; new session resets it',()=>{
 const m=new RoomMap();stable(m);m.clear(25);assert.equal(m.cells.size,0);assert.equal(m.addFrame(3,[p()],26),false);m.resetSession(30);stable(m,1,40);assert.equal(m.snapshot().points.length,1);assert.equal(m.paused,false);
});
check('invalid coordinates, invalid frames and behind-radar points rejected',()=>{
 const m=new RoomMap();assert.equal(m.addFrame(1.5,[p()],0),false);stable(m,1,0,p(NaN));stable(m,4,40,p(.12,-1));stable(m,7,80,p(.12,1,Infinity));assert.equal(m.cells.size,0);assert.equal(m.addFrame(10,[p()],NaN),false);
});
check('incoming history accumulates once, even when rendering queue is bounded',()=>{
 const c={performance:{now:()=>1000},render:()=>{},requestAnimationFrame:()=>{}};vm.createContext(c);
 const source=script.slice(script.indexOf('// ROOM_MAP_BEGIN:'),script.indexOf('const byId='));vm.runInContext(source,c);
 const state={live:true,frame:40,frames_received:40,points:[p()],recent_frames:Array.from({length:40},(_,i)=>({frame:i+1,points:[p()],age_seconds:.01}))};
 c.acceptState(state);c.acceptState(state);
 assert.equal(vm.runInContext('roomMap.framesUsed',c),40);assert.equal(vm.runInContext('pendingFrames.length',c),24);
 assert.equal(vm.runInContext('roomMap.snapshot().points.length',c),1);
 c.acceptState({...state,live:false,frame:null,frames_received:0,recent_frames:[]});
 assert.equal(vm.runInContext('roomMap.snapshot().points.length',c),0);
 assert.equal(vm.runInContext('roomMap.lastFrame',c),0);
});
check('reconnect clears old accumulation before accepting new frames',()=>{
 const c={performance:{now:()=>1000},render:()=>{},requestAnimationFrame:()=>{}};vm.createContext(c);
 vm.runInContext(script.slice(script.indexOf('// ROOM_MAP_BEGIN:'),script.indexOf('const byId=')),c);
 const state={live:true,frame:3,frames_received:3,points:[p()],recent_frames:[1,2,3].map(frame=>({frame,points:[p()],age_seconds:0}))};c.acceptState(state);
 vm.runInContext('mapConnectionLost=true',c);c.acceptState({...state,frame:4,frames_received:4,recent_frames:[{frame:4,points:[p()],age_seconds:0}]});
 assert.equal(vm.runInContext('roomMap.snapshot().points.length',c),0);assert.equal(vm.runInContext('roomMap.framesUsed',c),1);
});
console.log(`${tests} room-map checks passed; browser JavaScript syntax valid.`);
