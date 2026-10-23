export async function api<T>(path:string, body?:unknown):Promise<T> {
  let response:Response;
  try{response = await fetch('/api'+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(15000)});}
  catch{throw new Error('Сервер не отвечает. Проверьте запуск backend и подключение, затем повторите действие.');}
  if(!response.ok){const e=await response.json().catch(()=>null);throw new Error(typeof e?.detail==='string'?e.detail:`Ошибка сервера ${response.status}`);}
  return response.json();
}
