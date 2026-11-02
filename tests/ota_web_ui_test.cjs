const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/app.js','utf8');
function page(saved){
 const nodes={},storage=new Map(saved?[['pm-prepared',JSON.stringify(saved)]]:[]);
 const sandbox={document:{getElementById(id){return nodes[id]??={textContent:'',value:'',hidden:false,classList:{toggle(){}},replaceChildren(){}};}},sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},fetch:()=>new Promise(()=>{}),setInterval(){},confirm:()=>false,Option:function(){}};
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
 console.log('PASS: visible missing-package error; refresh restores package without starting a transfer');
})();
