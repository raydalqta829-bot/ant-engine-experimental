import fs from 'node:fs';
import {compile,describe,lint,renderPngFromSvg,toPdf,toDxf} from '@chanmeng666/archlang';
const source=fs.readFileSync('VILLA.arch','utf8'),r=compile(source,{width:1500});
if(r.errors.length)throw Error(JSON.stringify(r.errors));
if(r.pages?.length!==2)throw Error('Expected two storeys');
const diagnostics=[];
for(const p of r.pages){
 const stem=p.level===0?'COORD_GROUND':'COORD_FIRST';
 const svg=p.svg.replace(/<text\b[^>]*>[\s\S]*?<\/text>/g,t=>t.includes('m²')?'':t);
 const scene={...p.scene,nodes:p.scene.nodes.filter(n=>n.layer!=='dims'&&!(n.prim.t==='text'&&n.prim.value.includes('m²')))};
 fs.writeFileSync(stem+'.svg',svg);
 fs.writeFileSync(stem+'.png',await renderPngFromSvg(svg,{onDiagnostic:d=>diagnostics.push(d)}));
 fs.writeFileSync(stem+'.pdf',await toPdf(scene,{onDiagnostic:d=>diagnostics.push(d)}));
 fs.writeFileSync(stem+'.dxf',toDxf(scene));
}
fs.writeFileSync('VILLA_FACTS.json',JSON.stringify(describe(source),null,2));
fs.writeFileSync('VILLA_LINT.json',JSON.stringify(lint(source),null,2));
fs.writeFileSync('RENDER_DIAGNOSTICS.json',JSON.stringify(diagnostics,null,2));
if(diagnostics.length)throw Error(JSON.stringify(diagnostics));
console.log('Two coordinated levels rendered with official ArchLang backends');
