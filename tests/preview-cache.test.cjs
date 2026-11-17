const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = readFileSync('backend/static/src/preview.js','utf8');
function editor(fetch) {
  const nodes = {
    'metadata-preview-data': {textContent: JSON.stringify({mode:'new',site_id:1,title:'Old',description:'Old description',base_page_id:'',page_urls:{1:'https://example.test/a',2:'https://example.test/b'},page_titles:{1:'Page A',2:'Page B'}})},
    id_page:{value:'1'}, id_proposed_title:{value:'User typed title'}, id_proposed_description:{value:'User typed description'},
    id_change_title:{checked:true}, id_change_description:{checked:true}
  };
  const context={window:{},document:{getElementById:id=>nodes[id] || null},fetch,Date,URL,setTimeout};
  vm.createContext(context);vm.runInContext(source,context);
  return {component:context.window.metadataPreview(),nodes};
}
const snapshot = title => ({ready:true,stored:{title,description:'Saved description'},page_title:title,read_at:new Date().toISOString(),state:'ready'});
const response = value => ({ok:true,json:async()=>value});
(async()=>{
  const first=editor(async()=>response(snapshot('Saved title')));
  await first.component.loadMetadata();
  assert.equal(first.nodes.id_proposed_title.value,'User typed title');
  assert.equal(first.component.title,'User typed title');
  first.component.useSavedMetadata();
  assert.equal(first.nodes.id_proposed_title.value,'Saved title');
  const pending=[];
  const second=editor(()=>new Promise(resolve=>pending.push(resolve)));
  const a=second.component.loadMetadata();second.nodes.id_page.value='2';
  const b=second.component.loadMetadata();
  pending[1](response(snapshot('Page B saved')));await b;
  pending[0](response(snapshot('Page A late')));await a;
  second.component.useSavedMetadata();
  assert.equal(second.nodes.id_proposed_title.value,'Page B saved');
  console.log('Preview cache: typed edits preserved, explicit import works, stale page response ignored.');
})().catch(error=>{console.error(error);process.exitCode=1;});
