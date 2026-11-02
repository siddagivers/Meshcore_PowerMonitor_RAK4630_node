const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/app.js','utf8');
function page(saved){
 const nodes={},storage=new Map(saved?[['pm-prepared',JSON.stringify(saved)]]:[]);
 const sandbox={document:{getElementById(id){return nodes[id]??={textContent:'',value:'',hidden:false,classList:{toggle(){}},replaceChildren(){}};}},sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},fetch:()=>new Promise(()=>{}),setInterval(){},confirm:()=>false,Option:function(){}};
 vm.createContext(sandbox);vm.runInContext(source,sandbox);return {sandbox,nodes,storage};
}
(async()=>{
 const missing=page();await vm.runInContext('action(()=>start(false))',missing.sandbox);
 assert.match(missing.nodes['transfer-notice'].textContent,/No package is selected/);
 const metadata={sha256:'a'.repeat(64),signer:'b'.repeat(64),image_bytes:380556};
 const first=page();vm.runInContext('showPackage('+JSON.stringify(metadata)+')',first.sandbox);
 assert.equal(JSON.parse(first.storage.get('pm-prepared')).sha256,metadata.sha256);
 const restored=page(metadata);assert.equal(restored.nodes.package.hidden,false);
 assert.equal(restored.nodes['package-download'].href,'/packages/'+metadata.sha256+'.mota');
 assert.match(restored.nodes['transfer-notice'].textContent,/Package prepared/);
 vm.runInContext('showTransferDetails('+JSON.stringify({status:'running',sent:21000,total:30000,elapsed_seconds:30,eta_seconds:180,sha256:'844497f0'+'a'.repeat(56)})+')',restored.sandbox);
 assert.match(restored.nodes['transfer-timing'].textContent,/30s/);
 assert.match(restored.nodes['transfer-timing'].textContent,/3m 0s/);
 assert.equal(restored.nodes['activation-command'].textContent,'pm ota apply 844497f0');
 vm.runInContext('showTransferDetails('+JSON.stringify({status:'waiting',sent:32000,total:381566,elapsed_seconds:600,retry_in_seconds:120,attempt:2,sha256:'844497f0'+'a'.repeat(56)})+')',restored.sandbox);
 assert.match(restored.nodes['transfer-timing'].textContent,/auto-resume in 2m 0s/);
 restored.nodes['auto-resume'].checked=true;restored.nodes['auto-resume'].onchange();
 assert.equal(restored.nodes.activate.disabled,true);
 for(const id of ['target','repeater-nickname','password'])first.sandbox.document.getElementById(id);
 first.nodes.target.value='c'.repeat(64);first.nodes['repeater-nickname'].value='Hill repeater';first.nodes.password.value='never-store-this';await first.nodes['save-repeater'].onclick();assert.equal(JSON.parse(first.storage.get('pm-repeaters'))[0].name,'Hill repeater');assert.equal(JSON.stringify([...first.storage]).includes('never-store-this'),false);first.nodes['saved-repeaters'].value='c'.repeat(64);await first.nodes['saved-repeaters'].onchange();assert.equal(first.nodes.target.value,'c'.repeat(64));assert.equal(first.nodes.password.value,'');await first.nodes['remove-repeater'].onclick();assert.equal(JSON.parse(first.storage.get('pm-repeaters')).length,0);
 vm.runInContext('showRoute('+JSON.stringify({known:true,hop_count:1,target:'Target',hops:[{id:'00',candidates:['Hill','Valley']}]})+')',restored.sandbox);assert.match(restored.nodes['transfer-route'].textContent,/possible: Hill \/ Valley/);assert.match(restored.nodes['transfer-route'].textContent,/1 repeater hops/);vm.runInContext('showRoute('+JSON.stringify({known:true,hop_count:0,target:'Target',hops:[]})+')',restored.sandbox);assert.match(restored.nodes['transfer-route'].textContent,/Direct, no repeater hops/);
 console.log('PASS: visible errors, refresh restores package, elapsed/ETA and exact activation command');
})();
