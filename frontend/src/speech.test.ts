import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {SpeechController,speechError,type SpeechEngine,type SpeechEvent} from './speech';

function setup(supported=true){
  const engines:SpeechEngine[]=[];
  const create=vi.fn(()=>{if(!supported)return null;const e:SpeechEngine={lang:'',continuous:true,interimResults:false,onstart:null,onend:null,onerror:null,onresult:null,onnomatch:null,start:vi.fn(),abort:vi.fn()};engines.push(e);return e;});
  const handlers={state:vi.fn(),text:vi.fn(),error:vi.fn(),action:vi.fn(),isSpeaking:vi.fn(()=>false)};
  const controller=new SpeechController(create,handlers);
  return {engines,create,handlers,controller};
}
function result(phrase:string,final=true):SpeechEvent{return {resultIndex:0,results:{length:1,0:{isFinal:final,0:{transcript:phrase}}}};}
describe('speech lifecycle (synthetic engine events, no physical microphone)',()=>{
  beforeEach(()=>vi.useFakeTimers());afterEach(()=>{vi.clearAllTimers();vi.useRealTimers();});
  it('explains unsupported browser without claiming to listen',()=>{const s=setup(false);s.controller.start();expect(s.handlers.state).toHaveBeenLastCalledWith('off');expect(s.handlers.error).toHaveBeenLastCalledWith(speechError('unsupported'));expect(s.handlers.error.mock.lastCall?.[0]).toContain('встроенном браузере');});
  it('distinguishes starting from actual listening',()=>{const s=setup();s.controller.start();expect(s.handlers.state).toHaveBeenLastCalledWith('starting');expect(s.engines[0].lang).toBe('ru-RU');expect(s.engines[0].continuous).toBe(false);s.engines[0].onstart?.();expect(s.handlers.state).toHaveBeenLastCalledWith('listening');vi.advanceTimersByTime(9000);expect(s.handlers.error).toHaveBeenLastCalledWith('');});
  it('times out an engine that exposes the API but never starts',()=>{const s=setup();s.controller.start();vi.advanceTimersByTime(8000);expect(s.handlers.error).toHaveBeenLastCalledWith(speechError('timeout'));expect(s.engines[0].abort).toHaveBeenCalledOnce();expect(s.handlers.state).toHaveBeenLastCalledWith('off');});
  it('shows interim text but executes only final results',()=>{const s=setup();s.controller.start();const e=s.engines[0];e.onstart?.();e.onresult?.(result('первый',false));expect(s.handlers.action).not.toHaveBeenCalled();e.onresult?.(result('первый'));expect(s.handlers.action).toHaveBeenCalledExactlyOnceWith({type:'select',index:0});});
  it('passes final free answers to the game without treating them as A–D commands',()=>{
    const s=setup(),phrase=vi.fn(),controller=new SpeechController(s.create,{...s.handlers,phrase});controller.start();const e=s.engines[0];e.onstart?.();e.onresult?.(result('Меркурий',false));expect(phrase).not.toHaveBeenCalled();e.onresult?.(result('Меркурий'));e.onresult?.(result('первый'));expect(phrase.mock.calls).toEqual([['Меркурий'],['первый']]);expect(s.handlers.action).not.toHaveBeenCalled();s.handlers.isSpeaking.mockReturnValue(true);e.onresult?.(result('Это голос игры'));expect(phrase).toHaveBeenCalledTimes(2);controller.stop();
  });
  it('handles a spoken ordinal transcribed by the browser as digit 1',()=>{const s=setup();s.controller.start();s.engines[0].onstart?.();s.engines[0].onresult?.(result('1',false));expect(s.handlers.action).not.toHaveBeenCalled();s.engines[0].onresult?.(result('1'));expect(s.handlers.action).toHaveBeenCalledExactlyOnceWith({type:'select',index:0});});
  it('ignores unknown and synthetic spoken question commands',()=>{const s=setup();s.controller.start();s.engines[0].onresult?.(result('первый или второй'));expect(s.handlers.action).not.toHaveBeenCalled();s.handlers.isSpeaking.mockReturnValue(true);s.engines[0].onresult?.(result('подтвердить'));expect(s.handlers.action).not.toHaveBeenCalled();});
  it('restarts after an utterance and cancels a queued restart on explicit stop',()=>{const s=setup();s.controller.start();s.engines[0].onstart?.();s.engines[0].onresult?.(result('второй'));s.engines[0].onend?.();vi.advanceTimersByTime(350);expect(s.create).toHaveBeenCalledTimes(2);s.engines[1].onend?.();s.controller.stop();vi.advanceTimersByTime(1000);expect(s.create).toHaveBeenCalledTimes(2);});
  it('does not restart stale callbacks after disable',()=>{const s=setup();s.controller.start();const end=s.engines[0].onend;const transcript=s.engines[0].onresult;s.controller.stop();end?.();transcript?.(result('подтвердить'));vi.advanceTimersByTime(9000);expect(s.create).toHaveBeenCalledOnce();expect(s.handlers.action).not.toHaveBeenCalled();});
  it('pauses capture during announcements and ignores delayed echo results',()=>{
    const s=setup();s.controller.start();s.engines[0].onstart?.();const lateResult=s.engines[0].onresult;s.controller.setPlaybackActive(true);expect(s.engines[0].abort).toHaveBeenCalledOnce();expect(s.handlers.state).toHaveBeenLastCalledWith('paused');lateResult?.(result('1'));expect(s.handlers.action).not.toHaveBeenCalled();s.controller.setPlaybackActive(false);expect(s.create).toHaveBeenCalledTimes(2);s.engines[1].onresult?.(result('1'));expect(s.handlers.action).toHaveBeenCalledWith({type:'select',index:0});
  });
  it('does not resume after the user turns the microphone off while audio is playing',()=>{
    const s=setup();s.controller.start();s.controller.setPlaybackActive(true);s.controller.stop();s.controller.setPlaybackActive(false);expect(s.create).toHaveBeenCalledOnce();
  });
  it('notifies ready once per explicit activation, not on playback resume',()=>{
    const ready=vi.fn(),s=setup();const controller=new SpeechController(s.create,{...s.handlers,ready});controller.start();s.engines[0].onstart?.();controller.setPlaybackActive(true);controller.setPlaybackActive(false);s.engines[1].onstart?.();expect(ready).toHaveBeenCalledOnce();
  });
  it('waits until existing audio finishes before opening the microphone',()=>{
    const s=setup();s.controller.setPlaybackActive(true);s.controller.start();expect(s.create).not.toHaveBeenCalled();expect(s.handlers.state).toHaveBeenLastCalledWith('paused');s.controller.setPlaybackActive(false);expect(s.create).toHaveBeenCalledOnce();
  });
  it('stops after three empty sessions instead of infinite reconnecting',()=>{const s=setup();s.controller.start();for(let i=0;i<3;i++){s.engines[i].onstart?.();s.engines[i].onerror?.({error:'no-speech'});s.engines[i].onend?.();vi.advanceTimersByTime(350);}expect(s.create).toHaveBeenCalledTimes(3);expect(s.handlers.error).toHaveBeenLastCalledWith(speechError('silent'));});
  it.each(['network','not-allowed','service-not-allowed','audio-capture','language-not-supported'])('reports %s and stops',code=>{const s=setup();s.controller.start();s.engines[0].onerror?.({error:code});vi.advanceTimersByTime(9000);expect(s.handlers.error).toHaveBeenLastCalledWith(speechError(code));expect(s.handlers.state).toHaveBeenLastCalledWith('off');expect(s.create).toHaveBeenCalledOnce();});
});
