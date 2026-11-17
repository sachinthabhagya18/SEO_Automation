import { spawnSync } from 'node:child_process';
const id=process.argv[2];
if (!/^[a-zA-Z0-9-]+$/.test(id || '')) process.exit(2);
const result=spawnSync('n8n',['execute','--id',id,'--rawOutput'],{encoding:'utf8',timeout:180000,maxBuffer:2000000,
  env:{...process.env,N8N_RUNNERS_ENABLED:'false',N8N_LOG_LEVEL:'error'}});
if (result.status!==0) {
  const diagnostic=(result.stderr+'\n'+result.stdout).split('\n').filter(line=>/error|cannot|port|invalid|unknown|failed|unrecognized|not found/i.test(line)).slice(-6).join('\n')
    .replace(/Bearer\s+[^\s"',}]+/gi,'Bearer [redacted]').replace(/[A-Za-z0-9_+\/=\-]{32,}/g,'[redacted]').slice(-1200);
  process.stderr.write('Workflow execution failed: '+JSON.stringify({status:result.status,signal:result.signal,error_code:result.error?.code,stdout_bytes:result.stdout?.length,stderr_bytes:result.stderr?.length})+'. Sanitized diagnostic:\n'+diagnostic+'\n');process.exit(1);
}
let parsed;
const output=result.stdout.trim();
try { parsed=JSON.parse(output); } catch {
  // n8n startup messages can precede its raw JSON output.
  for(let i=output.indexOf('{');i>=0 && !parsed;i=output.indexOf('{',i+1)) {
    try { parsed=JSON.parse(output.slice(i)); } catch {}
  }
}
if (!parsed) { process.stderr.write('Execution returned no parseable result; raw output suppressed.\n');process.exit(1); }
const runs=parsed.data?.resultData?.runData ?? parsed.resultData?.runData ?? {};
if (parsed.data?.resultData?.error || parsed.resultData?.error) {process.stderr.write('Workflow node failed; inspect the local n8n execution.\n');process.exit(1);}
const summary={workflow_id:id,nodes:Object.keys(runs),execution_verified:true};
for(const [name,values] of Object.entries(runs)) {
  const value=values.at(-1)?.data?.main?.[0]?.[0]?.json;
  if(value?.state) summary[name]={state:value.state,job_id:value.job_id ?? null};
}
if (!summary.nodes.length) { process.stderr.write('No executed nodes found in the result.\n');process.exit(1); }
process.stdout.write(JSON.stringify(summary)+'\n');
