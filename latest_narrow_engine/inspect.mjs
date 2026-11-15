import fs from 'node:fs';
import path from 'node:path';
import {compile,describe} from '@chanmeng666/archlang';
const file=process.argv[2],source=fs.readFileSync(file,'utf8'),r=compile(source);
if(r.errors.length)throw Error(JSON.stringify(r.errors));
fs.writeFileSync(path.join(path.dirname(file),'COMPILER_FACTS.json'),JSON.stringify(describe(source),null,2));
