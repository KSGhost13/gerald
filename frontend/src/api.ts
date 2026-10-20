export type Agent = {id:string;name:string;role:string;directive:string;provider:string;model:string;server:string;tools:string[];qwen_profile?:string;x:number;y:number;status:string;queued:number;output:string;metrics:{tokens:number;tps:number;pid:number|null;effective_provider?:string}};
export type Route = {source:string;target:string};
export type Event = {type:string;message:string;agent_id:string;time:number;target?:string;job_id?:string};
export type SessionRequest = {id:string;job_id:string;prompt:string;status:string;progress:string;response:string;error:string;created_at:number;updated_at:number};
export type SessionState = {binding:null|{thread_id:string;title:string;automation_id:string;poll_seconds:number;last_seen:number|null};pending:SessionRequest[];recent:SessionRequest[];paused:boolean};
export type State = {mode:'local'|'cloud';agents:Agent[];edges:Route[];events:Event[];jobs:{id:string;goal:string;status:string;pending:number;errors:number}[];session?:SessionState};
export type Integrations = {ollama:{url:string;online:boolean;models:string[];error?:string}[];codex:boolean;ollama_cli:boolean;anthropic:boolean;local_model:string;codex_local_model:string;codex_auth?:{signed_in:boolean;method:string;message:string};codex_models?:{id:string;name:string}[];codex_models_cached_at?:string|null};
export type Telemetry = {cpu:number;memory:number;ram_gb:number;units:Record<string,{pid:number;ram_mb:number;cpu_seconds:number}>};
export async function api<T=unknown>(path:string,method='GET',body?:unknown):Promise<T>{
 const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
 const data=await r.json(); if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;
}
