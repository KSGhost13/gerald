import {useState} from 'react';
import type {Integrations} from './api';

export default function ModelPicker({provider,model,server,onChange,integrations}:{provider:string;model:string;server:string;onChange:(value:string)=>void;integrations?:Integrations}){
 const local=['ollama','ollama-cli','codex-ollama'].includes(provider);
 const options=local?[...new Set(integrations?.ollama.filter(s=>!server||s.url===server).flatMap(s=>s.models)||[])].map(id=>({id,name:id})):provider==='codex'?integrations?.codex_models||[]:[];
 const [custom,setCustom]=useState(!!model&&!options.some(m=>m.id===model));
 const session=provider==='codex-session';
 return <div className="model-picker"><label htmlFor="agent-model">MODEL</label><select id="agent-model" aria-label="Agent model" disabled={session} value={custom?'__custom__':model} onChange={e=>{const value=e.target.value;setCustom(value==='__custom__');onChange(value==='__custom__'?'':value)}}><option value="">{session?'Selected in the linked Codex chat':'Provider default'}</option>{options.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}<option value="__custom__">Custom model ID…</option></select>{custom&&!session&&<input aria-label="Custom agent model" placeholder="Enter exact model ID" value={model} onChange={e=>onChange(e.target.value)} maxLength={160}/>}{provider==='codex'&&<small>{integrations?.codex_auth?.message||'Checking CLI sign-in…'}<br/>Models come from the local Codex catalogue; availability is checked when running. Cloud mode is required.</small>}{session&&<small>This master agent follows its linked chat’s model, not a separate dashboard model.</small>}</div>
}
