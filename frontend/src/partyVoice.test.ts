import {afterEach,expect,it,vi} from 'vitest';
import {playPartyVoice,stopPartyVoice} from './partyVoice';
afterEach(()=>{stopPartyVoice();vi.unstubAllGlobals();vi.useRealTimers();});
it('plays bundled recordings and resolves when playback ends',async()=>{
 let node:any;vi.stubGlobal('Audio',class{onended:any;onerror:any;volume=1;pause=vi.fn();play=vi.fn(async()=>{});constructor(public src:string){node=this;}});
 const done=playPartyVoice('Камера включена.');expect(node.src).toContain('/audio/voice/camera-on.mp3');node.onended();expect(await done).toBe(true);
});
it('cancellation releases a recording that never sends an end event',async()=>{
 vi.stubGlobal('Audio',class{onended:any;onerror:any;pause=vi.fn();play=vi.fn(async()=>{});});
 const done=playPartyVoice('Ответ верный!');stopPartyVoice();expect(await done).toBe(false);
});
it('failed or unknown recordings do not fall back to robotic speech',async()=>{
 vi.stubGlobal('Audio',class{pause=vi.fn();play=vi.fn(async()=>{throw Error('blocked');});});
 expect(await playPartyVoice('Ответ неверный.')).toBe(false);expect(await playPartyVoice('unknown')).toBe(false);
});
