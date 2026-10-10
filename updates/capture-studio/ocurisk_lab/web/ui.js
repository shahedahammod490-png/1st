export const $=id=>document.getElementById(id);
export function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(cls)n.className=cls;return n;}
export function notice(text,error=false){const n=$('notice');n.textContent=text;n.classList.toggle('error',error);n.hidden=false;clearTimeout(notice.timer);notice.timer=setTimeout(()=>n.hidden=true,9000);}
export class ApiError extends Error {
  constructor(message){super(message);this.name='ApiError';}
}
export function reportError(error){
  const connection=$('connection');
  if(error instanceof ApiError && connection)connection.textContent='Service request failed';
  notice(error.message,true);
}
export async function api(path,options={}){
  const method=options.method||'GET';let response;
  try{response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...options.headers}});}
  catch(error){const failure=new ApiError(`${method} ${path}: Network request failed — ${error.message}`);reportError(failure);throw failure;}
  let data;
  try{data=await response.json();}
  catch(error){const failure=new ApiError(`${method} ${path}: Invalid JSON response (HTTP ${response.status})`);reportError(failure);throw failure;}
  if(!response.ok){
    const detail=typeof data?.error==='string'?data.error:JSON.stringify(data?.error||data);
    const failure=new ApiError(`${method} ${path}: HTTP ${response.status} — ${detail}`);reportError(failure);throw failure;
  }
  const connection=$('connection');if(connection)connection.textContent='Local service connected';
  return data;
}
export const post=(p,data)=>api(p,{method:'POST',body:JSON.stringify(data)});
export function button(text,action,cls=''){const n=el('button',text,cls);n.type='button';n.onclick=async()=>{n.disabled=true;try{await action();}catch(e){reportError(e);}finally{n.disabled=false;}};return n;}
export function card(title){const n=el('section',null,'card');if(title)n.append(el('h2',title));return n;}
export function empty(title,desc){const n=el('div',null,'empty');n.append(el('strong',title),el('span',desc));return n;}
export function detail(data,title='Provenance & raw record'){const n=el('details');n.append(el('summary',title),el('pre',JSON.stringify(data,null,2)));return n;}
export function field(label,name,type='text',options){const l=el('label',label),n=el(options?'select':type==='textarea'?'textarea':'input');n.name=name;n.id=name;if(options)for(const v of options){const o=el('option',Array.isArray(v)?v[1]:v);o.value=Array.isArray(v)?v[0]:v;n.append(o);}else if(n.tagName==='INPUT')n.type=type;l.append(n);return l;}
export function check(label,name){const l=field(label,name,'checkbox');l.className='check';return l;}
export function table(headers,rows){const w=el('div',null,'table-wrap'),t=el('table'),head=el('tr');headers.forEach(h=>head.append(el('th',h)));t.append(head);for(const row of rows){const r=el('tr');row.forEach(v=>{const td=el('td');td.append(v instanceof Node?v:document.createTextNode(v===null||v===undefined?'Missing':String(v)));r.append(td);});t.append(r);}w.append(t);return w;}
export const list=x=>Array.isArray(x)?x:x?.items||x?.algorithms||x?.experiments||x?.jobs||x?.models||x?.records||[];
export function download(text,name,type='text/plain'){const a=el('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
export function heading(kicker,title,desc){const n=el('div',null,'page-heading'),copy=el('div');copy.append(el('div',kicker,'eyebrow'),el('h1',title),el('p',desc,'muted'));n.append(copy);return n;}
export function required(form,names){for(const name of names)form.elements[name].required=true;}
export function submit(form,text,fn){const b=el('button',text,'primary');b.type='submit';const a=el('div',null,'actions');a.append(b);form.append(a);form.onsubmit=async e=>{e.preventDefault();b.disabled=true;try{await fn(Object.fromEntries(new FormData(form)));}catch(e){reportError(e);}finally{b.disabled=false;}};}
