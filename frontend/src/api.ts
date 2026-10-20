export type Agent = {id:string;name:string;role:string;directive:string;provider:string;model:string;server:string;tools:string[];x:number;y:number;status:string;queued:number;output:string;metrics:{tokens:number;tps:number;pid:number|null;effective_provider?:string}};
export type Route = {source:string;target:string};
export type Event = {type:string;message:string;agent_id:string;time:number;target?:string;job_id?:string};
export type State = {mode:'local'|'cloud';agents:Agent[];edges:Route[];events:Event[];jobs:{id:string;goal:string;status:string;pending:number;errors:number}[]};
export type Integrations = {ollama:{url:string;online:boolean;models:string[];error?:string}[];codex:boolean;ollama_cli:boolean;anthropic:boolean;local_model:string;codex_local_model:string};
export type Telemetry = {cpu:number;memory:number;ram_gb:number;units:Record<string,{pid:number;ram_mb:number;cpu_seconds:number}>};
export async function api<T=unknown>(path:string,method='GET',body?:unknown):Promise<T>{
 const r=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
 const data=await r.json(); if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;
}
