import {afterEach,describe,expect,it,vi} from 'vitest';
import {beginQuestionMedia,isQuestionMediaPlaying} from './questionMediaPlayback';
describe('question media echo guard',()=>{
 afterEach(()=>vi.useRealTimers());
 it('holds recognition through nested playback and a short echo tail',()=>{vi.useFakeTimers();vi.setSystemTime(1000);const first=beginQuestionMedia(),second=beginQuestionMedia();expect(isQuestionMediaPlaying()).toBe(true);first();first();vi.advanceTimersByTime(400);expect(isQuestionMediaPlaying()).toBe(true);second();expect(isQuestionMediaPlaying()).toBe(true);vi.advanceTimersByTime(351);expect(isQuestionMediaPlaying()).toBe(false);});
});
