import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {QuizSoundtrack,audioUrl,type AudioPlayer} from './soundtrack';
function setup(){
  const nodes:(AudioPlayer&{url:string})[]=[];
  const create=vi.fn((url:string)=>{const a={url,play:vi.fn(async()=>{}),pause:vi.fn(),currentTime:0,volume:1,loop:false,preload:'',onended:null,onerror:null} as AudioPlayer&{url:string};nodes.push(a);return a;});
  return {sound:new QuizSoundtrack(create),create,nodes};
}
describe('local WAV soundtrack',()=>{
  beforeEach(()=>vi.useFakeTimers());afterEach(()=>{vi.clearAllTimers();vi.useRealTimers();});
  it('loops the quiet question bed and pauses it for microphone or speech',()=>{
    const s=setup();s.sound.setQuestionActive(true);const bed=s.nodes[0];expect(bed.url).toBe(audioUrl('suspense'));expect(bed.loop).toBe(true);expect(bed.volume).toBeLessThan(.25);s.sound.setMicrophoneActive(true);expect(bed.pause).toHaveBeenCalled();const count=vi.mocked(bed.play).mock.calls.length;s.sound.setSpeechActive(true);s.sound.setSpeechActive(false);expect(vi.mocked(bed.play).mock.calls.length).toBe(count);s.sound.setMicrophoneActive(false);expect(vi.mocked(bed.play).mock.calls.length).toBeGreaterThan(count);
  });
  it('finishes a real cue on the media ended event',async()=>{
    const s=setup(),done=vi.fn();const cue=s.sound.playCue('correct').then(done);expect(s.nodes[0].url).toBe(audioUrl('correct'));s.nodes[0].onended?.call(s.nodes[0] as unknown as GlobalEventHandlers,new Event('ended'));await cue;expect(done).toHaveBeenCalledOnce();
  });
  it('releases pending cue playback on mute',async()=>{const s=setup();const pending=s.sound.playCue('incorrect');s.sound.setEnabled(false);await pending;expect(s.nodes[0].pause).toHaveBeenCalled();await s.sound.playCue('correct');expect(s.nodes).toHaveLength(1);});
  it('does not play timer ticks into an active microphone',async()=>{const s=setup();s.sound.setMicrophoneActive(true);await s.sound.playCue('tick');expect(s.create).not.toHaveBeenCalled();});
  it('releases a cue if a browser never sends the ended event',async()=>{const s=setup();const pending=s.sound.playCue('timeout');vi.advanceTimersByTime(10000);await pending;expect(s.nodes[0].pause).toHaveBeenCalled();});
});

describe('question media soundtrack isolation',()=>{
 it('pauses the bed and suppresses timer ticks while a question clip plays',async()=>{const s=setup();s.sound.setQuestionActive(true);const bed=s.nodes[0],played=vi.mocked(bed.play).mock.calls.length;s.sound.setMediaActive(true);expect(bed.pause).toHaveBeenCalled();await s.sound.playCue('tick');expect(s.nodes).toHaveLength(1);s.sound.setMediaActive(false);expect(vi.mocked(bed.play).mock.calls.length).toBeGreaterThan(played);});
});
