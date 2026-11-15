import fs from 'node:fs';
import {compile,renderPngFromSvg} from '@chanmeng666/archlang';
const folder=process.argv[2];
const source=fs.readFileSync(folder+'/VILLA.arch','utf8');
const r=compile(source,{width:1900});
if(r.errors.length||r.pages?.length!==2)throw Error(JSON.stringify(r.errors));
for(const p of r.pages){
 const svg=p.svg.replace(/<text\b[^>]*>[\s\S]*?<\/text>/g,t=>t.includes('m²')?'':t);
 const diagnostics=[];
 const png=await renderPngFromSvg(svg,{onDiagnostic:d=>diagnostics.push(d)});
 if(diagnostics.length)throw Error(JSON.stringify(diagnostics));
 fs.writeFileSync(folder+'/'+(p.level===0?'GROUND':'FIRST')+'.png',png);
}
console.log('PNG only:',folder);
