const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes={},requests=[];
function node(){return {value:'',textContent:'',style:{},options:[],classList:{toggle(){}},append(...items){this.children=(this.children||[]).concat(items);},replaceChildren(...items){this.children=items;this.options=items;},scrollIntoView(){}};}
const sandbox={document:{getElementById:id=>nodes[id]??=node(),createElement:()=>node(),title:''},localStorage:{getItem:()=>null,setItem(){}},fetch:(...args)=>{requests.push(args);return new Promise(()=>{});},setInterval(){},confirm:()=>false,Option:function(text,value){return {textContent:text,value};},TextEncoder};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync('inbox/app.js','utf8'),sandbox);
assert.equal(requests.length,1);assert.equal(requests[0][0],'/api/state');
vm.runInContext('contacts=[{public_key:"aa".repeat(32),adv_name:"Test node"}];channels=[{index:0,name:"Public"}];events=[{id:1,kind:"contact_message",direction:"in",peer:"aa",received:1,text:"<script>unsafe</script>",payload:{}}];showContacts();showEvents();',sandbox);
assert.equal(nodes.destination.options.length,3);
assert.equal(vm.runInContext('label('+JSON.stringify({kind:'channel_message',peer:'0'})+')',sandbox),'Channel Public');
assert.equal(vm.runInContext('label('+JSON.stringify({kind:'channel_message',peer:'7'})+')',sandbox),'Channel 7');
assert.equal(nodes.messages.children[0].children[1].textContent,'<script>unsafe</script>');
assert.match(nodes.unread.textContent,/1 unread/);
vm.runInContext('events.push({id:2,kind:"telemetry_response",direction:"in",peer:"aa",received:2,text:"",payload:{lpp:[]}});showEvents();',sandbox);
assert.equal(nodes.messages.children.length,1,'Telemetry must not appear in the chat inbox');
vm.runInContext("lastId=1",sandbox);nodes.read.onclick();assert.equal(nodes.unread.textContent,'');
assert.equal(requests.length,1,'Loading and rendering must never send a message');
console.log('PASS: contact/channel selection, unread state, literal message rendering; no automatic sends');
(async()=>{
 assert.equal(vm.runInContext('defaultFavourites.length',sandbox),5);
 vm.runInContext('contacts=[{public_key:"bb".repeat(32),adv_name:"Zed"},{public_key:"cc".repeat(32),adv_name:"Alpha"}];favourites=new Set(["bb".repeat(32)]);showContacts();',sandbox);
 assert.equal(nodes.destination.options[1].value,'contact:'+'bb'.repeat(32));
 assert.match(nodes.destination.options[1].textContent,/★/);
 assert.equal(nodes.contacts.children[0].className,'favourite-contact');
 await nodes.contacts.children[0].children[0].onclick();
 assert.equal(nodes.destination.options[1].value,'contact:'+'cc'.repeat(32));
 assert.equal(requests.length,1,'Favourite changes must not send radio messages');
 console.log('PASS: five pinned contacts, favourites first, star highlight and local toggle without radio traffic');
})().catch(error=>{console.error(error);process.exitCode=1;});
