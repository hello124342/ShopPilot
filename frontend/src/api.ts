export type ApiError = Error & {status?:number;requestId?:string}
const csrf=()=>document.cookie.split('; ').find(v=>v.startsWith('shopilot_csrf='))?.split('=')[1]
export async function api<T=any>(path:string,init:RequestInit={}):Promise<T>{
  const headers=new Headers(init.headers); if(init.body&&!headers.has('Content-Type'))headers.set('Content-Type','application/json'); const token=csrf(); if(token)headers.set('X-CSRF-Token',decodeURIComponent(token));
  const response=await fetch(path,{...init,headers,credentials:'include'}); const body=await response.json().catch(()=>null); if(!response.ok){const error=new Error(body?.message||body?.error_code||`HTTP ${response.status}`) as ApiError;error.status=response.status;error.requestId=response.headers.get('X-Request-ID')||undefined;throw error}return body as T
}
