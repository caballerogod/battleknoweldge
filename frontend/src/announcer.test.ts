import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {QuizAnnouncer} from './announcer';

function setup(enabled=true){
  const localVoice={lang:'ru-RU',name:'Russian local',localService:true} as SpeechSynthesisVoice;
  const spoken:SpeechSynthesisUtterance[]=[];
  const engine={getVoices:vi.fn(()=>[{lang:'en-US',localService:true} as SpeechSynthesisVoice,localVoice]),speak:vi.fn((utterance:SpeechSynthesisUtterance)=>spoken.push(utterance)),cancel:vi.fn()};
  const saveEnabled=vi.fn();
  const announcer=new QuizAnnouncer({engine:()=>engine,utterance:text=>({text,onend:null,onerror:null} as unknown as SpeechSynthesisUtterance),readEnabled:()=>enabled,saveEnabled});
  const end=(index=spoken.length-1)=>spoken[index].onend?.({} as SpeechSynthesisEvent);
  return {announcer,engine,spoken,end,localVoice,saveEnabled};
}
describe('quiz announcements (synthesis adapter tests, not physical audio)',()=>{
  beforeEach(()=>vi.useFakeTimers());afterEach(()=>{vi.clearAllTimers();vi.useRealTimers();});
  it.each([['camera-on','Камера включена.'],['microphone-on','Микрофон включён.']] as const)('announces %s in Russian', (event,text)=>{
    const s=setup();s.announcer.announce(event);expect(s.spoken[0].text).toBe(text);expect(s.spoken[0].lang).toBe('ru-RU');expect(s.spoken[0].voice).toBe(s.localVoice);
  });
  it.each([['correct','Ответ верный!'],['incorrect','Ответ неверный.']] as const)('announces %s with a quiz pause', (event,text)=>{
    const s=setup();s.announcer.announce(event);expect(s.spoken).toHaveLength(0);expect(s.announcer.isBlocking).toBe(true);vi.advanceTimersByTime(350);expect(s.spoken[0].text).toBe(text);expect(s.spoken[0].rate).toBeLessThan(1);expect(s.spoken[0].pitch).toBeLessThan(1);
  });
  it('queues devices behind a delayed result without losing its timer',()=>{
    const s=setup();s.announcer.announce('correct');s.announcer.announce('camera-on');vi.advanceTimersByTime(350);expect(s.spoken.map(u=>u.text)).toEqual(['Ответ верный!']);s.end();expect(s.spoken.map(u=>u.text)).toEqual(['Ответ верный!','Камера включена.']);
  });
  it('blocks recognition until the complete queue and echo tail finish',()=>{
    const s=setup(),listener=vi.fn();s.announcer.onPlaybackChange(listener);s.announcer.announce('camera-on');s.announcer.announce('microphone-on');s.end(0);expect(listener).toHaveBeenCalledExactlyOnceWith(true);s.end(1);vi.advanceTimersByTime(599);expect(s.announcer.isBlocking).toBe(true);vi.advanceTimersByTime(1);expect(listener).toHaveBeenLastCalledWith(false);
  });
  it('cancels delayed output when muted and persists preference',()=>{
    const s=setup();s.announcer.announce('correct');s.announcer.setEnabled(false);vi.advanceTimersByTime(2000);expect(s.spoken).toHaveLength(0);expect(s.announcer.announce('camera-on')).toBe(false);expect(s.saveEnabled).toHaveBeenCalledWith(false);expect(s.announcer.isBlocking).toBe(false);
  });
  it('can enable sound again',()=>{const s=setup(false);expect(s.announcer.announce('camera-on')).toBe(false);s.announcer.setEnabled(true);expect(s.announcer.announce('camera-on')).toBe(true);});
  it('handles unavailable synthesis without blocking the game',()=>{
    const a=new QuizAnnouncer({engine:()=>null,utterance:()=>{throw new Error('not supported');}});expect(a.announce('camera-on')).toBe(false);expect(a.isBlocking).toBe(false);expect(a.getSnapshot().message).toContain('недоступна');
  });
  it('clears blocked playback on an engine error or missing end event',()=>{
    const s=setup();s.announcer.announce('camera-on');s.spoken[0].onerror?.({} as SpeechSynthesisErrorEvent);vi.advanceTimersByTime(600);expect(s.announcer.isBlocking).toBe(false);s.announcer.announce('microphone-on');vi.advanceTimersByTime(16000);expect(s.announcer.isBlocking).toBe(false);expect(s.engine.cancel).toHaveBeenCalled();
  });
  it('ignores stale synthesis callbacks after cancellation',()=>{
    const s=setup();s.announcer.announce('camera-on');const lateEnd=s.spoken[0].onend;s.announcer.cancel();s.announcer.announce('microphone-on');lateEnd?.call(s.spoken[0],{} as SpeechSynthesisEvent);expect(s.announcer.isBlocking).toBe(true);s.end();vi.advanceTimersByTime(600);expect(s.announcer.isBlocking).toBe(false);
  });
  it('plays the real cue adapter before speaking the answer',async()=>{
    const s=setup();let finishCue!:()=>void;const playCue=vi.fn(()=>new Promise<void>(resolve=>{finishCue=resolve;}));
    const a=new QuizAnnouncer({engine:()=>s.engine,utterance:text=>({text} as SpeechSynthesisUtterance),playCue});
    a.announce('correct');vi.advanceTimersByTime(350);expect(playCue).toHaveBeenCalledWith('correct');expect(s.spoken).toHaveLength(0);finishCue();await Promise.resolve();expect(s.spoken[0].text).toBe('Ответ верный!');
  });
  it('starts the result cue immediately after the stage has already provided its reveal pause',()=>{
    const s=setup(),playCue=vi.fn(()=>new Promise<void>(()=>{}));
    const a=new QuizAnnouncer({engine:()=>s.engine,utterance:text=>({text} as SpeechSynthesisUtterance),playCue});
    a.announce('correct',{pauseMs:0});expect(playCue).toHaveBeenCalledExactlyOnceWith('correct');expect(s.spoken).toHaveLength(0);a.cancel();
  });
  it('does not speak after audio is cancelled while the cue is playing',async()=>{
    const s=setup();let finishCue!:()=>void;const a=new QuizAnnouncer({engine:()=>s.engine,utterance:text=>({text} as SpeechSynthesisUtterance),playCue:()=>new Promise<void>(resolve=>{finishCue=resolve;})});
    a.announce('incorrect');vi.advanceTimersByTime(350);a.cancel();finishCue();await Promise.resolve();expect(s.spoken).toHaveLength(0);
  });
  it('still plays local cues if speech synthesis is not supported',async()=>{
    const playCue=vi.fn(async()=>{}),a=new QuizAnnouncer({engine:()=>null,utterance:()=>{throw Error('no TTS');},playCue});expect(a.announce('timeout')).toBe(true);vi.advanceTimersByTime(350);await Promise.resolve();expect(playCue).toHaveBeenCalledWith('timeout');vi.advanceTimersByTime(600);expect(a.isBlocking).toBe(false);
  });
});
