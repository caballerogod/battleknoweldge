/** Anchor server remaining time to the monotonic client clock, never to a resettable counter. */
export const deadlineAnchor=(deadline:number,serverNow:number,clientNow:number)=>clientNow+Math.max(0,(deadline-serverNow)*1000);
export const remainingSeconds=(deadline:number,now:number,limit=30)=>Math.max(0,Math.min(limit,Math.ceil((deadline-now)/1000)));
