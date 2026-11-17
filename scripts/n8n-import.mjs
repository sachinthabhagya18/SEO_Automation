// stdin carries runtime credentials/workflow JSON. No secret data is printed.
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
const [kind, owner] = process.argv.slice(2);
if (!['workflow','credentials'].includes(kind) || !/^[a-zA-Z0-9-]+$/.test(owner || '')) process.exit(2);
const input = readFileSync(0,'utf8');
JSON.parse(input);
const path = '/tmp/seo-import-'+randomUUID()+'.json';
try {
  writeFileSync(path,input,{mode:0o600});
  const result=spawnSync('n8n',['import:'+kind,'--input',path,'--userId',owner],{encoding:'utf8',timeout:120000});
  if (result.status!==0) { process.stderr.write('n8n '+kind+' import failed; credential-bearing output suppressed.\n');process.exitCode=1; }
  else process.stdout.write('n8n '+kind+' import verified.\n');
} finally { unlinkSync(path); }
