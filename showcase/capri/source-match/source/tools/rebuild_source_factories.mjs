import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {stripTypeScriptTypes} from 'node:module';
const base=fileURLToPath(new URL('../',import.meta.url));
mkdirSync(base+'build/native',{recursive:true});
const clean=s=>s.replace(/^import\s[\s\S]*?from\s+['"][^'"]+['"];?\s*$/gm,'').replace(/\bexport\s+(?=const|let|function|class|interface|type)/g,'');
let shark='';
for(const f of ['math.ts','species.ts','world.ts','renderer.ts']){
 let s=clean(readFileSync(base+'upstream/ascii-sharks/'+f,'utf8'));
 if(f==='renderer.ts'){
  s=s.replace('const ACCENTS = ["#e0892c", "#e03a32", "#b44ae0", "#33c8cc", "#3cb54a", "#3150e8", "#d9c14a"]','const ACCENTS = ["#ff1265", "#ff3980", "#b44ae0", "#28fb86", "#1fca73", "#bd7ad9", "#f4f1ee"]');
  s=s.replace('g.fillStyle = "#000"','g.fillStyle = "#100a19"');
 }
 shark+='\n'+stripTypeScriptTypes(s,{mode:'transform'});
}
shark=`function createCapriOcean(canvas){\n// Source: stackedlol/ascii-sharks. Palette and embedding adaptation only.\n${shark}\n
 const world=new World();const renderer=new AsciiRenderer(canvas);renderer.setFontFamily('ui-monospace, Menlo, monospace');
 renderer.resize(900,620,1);world.resize(900,620,renderer.cellWidth,renderer.cellHeight);
 for(let i=0;i<240;i++)world.step(1/60);
 let acc=0;
 return {step(dt){acc+=dt;let n=0;while(acc>=1/60&&n<4){world.step(1/60);acc-=1/60;n++;}if(n===4)acc=0;renderer.render(world,dt||1/60);},pointer(x,y,active){world.pointer.x=x*900;world.pointer.y=y*620;world.pointer.active=active;},splash(x,y){world.splash(x*900,y*620);}};
}\n`;
writeFileSync(base+'build/native/ocean-source.js',shark);

const horizonFiles=['config.js','util.js','state.js','gl/shaders/fullscreen.vert.js','gl/shaders/scene.frag.js','gl/shaders/glyph.frag.js','gl/shaders/particles.js','gl/context.js','gl/glyphs.js','page.js','layout.js','sim/hole.js','sim/eat.js','sim/tick.js','gl/renderer.js'];
let horizon='';
for(const f of horizonFiles){
 let s=clean(readFileSync(base+'upstream/horizon/'+f,'utf8'));
 if(f==='config.js'){
  s=s.replace("bg: '#12110e', ink: '#f2f1ec', pink: '#ff2b8f', meta: '#12110e'","bg: '#100a19', ink: '#a69ab1', pink: '#ff1265', meta: '#100a19'");
  s+='\nconst S=Object.assign({},DEFAULTS,{cell:6,theme:"stage",stats:false,ignoreReduced:false,text:"The current request, latest correction, relevant source and acceptance checks travel together. Keep original evidence retrievable. Hand off the task with its scope, write ownership, findings and limits. Review the candidate against the request before the human decides what ships."});\nconst reduced=()=>motionReduced();\nconst ESSAY=S.text;\n';
 }
 if(f==='gl/glyphs.js')s=s.replace(/\bdrawGlyphs\b/g,'drawAtlasGlyphs');
 if(f==='layout.js'){
  s=s.replace(/function stageBox\(\) \{[\s\S]*?\n\}/,'function stageBox(){return {x:0,y:0,w:960,h:600};}');
  s=s.replace(/^  stage\.style\..*$/gm,'');
 }
 if(f==='page.js')s=s.replace('66 * G.dpr','8 * G.dpr').replace('60 * G.dpr','8 * G.dpr');
 horizon+='\n'+s;
}
const licence=readFileSync(base+'upstream/horizon/LICENSE.md','utf8');
horizon=`function createCapriHorizon(canvas,motionReduced){\n/* ${licence} */\nconst cv=canvas,stage=canvas.parentElement,el={mass:{textContent:''},stats:{textContent:''}};\nfunction setSpec(){}function syncSpec(){}\n${horizon}\n
 if(!initGL(cv))return null;
 G.dpr=1;st.intro=7;initRenderer();rebuildGlyphs();tick(0);render();
 fontsReady.then(()=>rebuildGlyphs());
 return {step(dt){tick(dt);render();},replay(){st.intro=0;st.sim=0;H.kick=0;H.kickV=0;parts.length=0;buildPage();},feed(){H.kickV+=1.2;H.pulseT=0;H.pulseA=.12;eat(1/60,true);},tilt(d){S.tilt=clamp(S.tilt+d,0,78);}};
}\n`;
writeFileSync(base+'build/native/horizon-source.js',horizon);
console.log('Source factories written',shark.length,horizon.length);
