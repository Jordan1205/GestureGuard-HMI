import {useCallback,useEffect,useState} from 'react';
import type {Snapshot} from './types';
export async function api<T=unknown>(path:string,body?:unknown):Promise<T>{
  const response=await fetch(`/api/${path}`,body===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!response.ok){let message=`Request failed (${response.status})`;try{const data=await response.json();message=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail)}catch{/* Response can be plain text during startup. */}throw new Error(message)}
  const data=await response.json();
  if(data&&data.ok===false)throw new Error(data.message??'The active interaction policy rejected this request.');
  return data as T;
}
export function useSnapshot(){
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null),[connected,setConnected]=useState(false),[error,setError]=useState('');
  useEffect(()=>{let alive=true,socket:WebSocket|undefined,retry:ReturnType<typeof setTimeout>|undefined,last=0;
    const accept=(s:Snapshot)=>{if(alive&&s.engine&&s.vision){setSnapshot(s);setConnected(true);last=Date.now()}};
    const connect=()=>{if(!alive)return;socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);socket.onmessage=e=>{try{accept(JSON.parse(e.data))}catch{/* Ignore invalid messages, preserving last validated state. */}};socket.onclose=()=>{if(alive)retry=setTimeout(connect,2000)};socket.onerror=()=>socket?.close()};
    const poll=async()=>{if(!alive)return;if(Date.now()-last>1500){try{accept(await api<Snapshot>('snapshot'))}catch{if(alive)setConnected(false)}}};
    connect();void poll();const timer=setInterval(poll,2000);return()=>{alive=false;clearInterval(timer);if(retry)clearTimeout(retry);socket?.close()};
  },[]);
  const request=useCallback(async(path:string,body?:unknown)=>{try{const result=await api(path,body);setError('');return result}catch(e){setError(e instanceof Error?e.message:'Unable to complete request');return null}},[]);
  return {snapshot,connected,error,setError,request};
}
