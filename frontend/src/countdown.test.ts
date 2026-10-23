import {describe,expect,it} from 'vitest';
import {deadlineAnchor,remainingSeconds} from './countdown';
describe('server-anchored question timer',()=>{
  it('starts at 30 and reaches zero at the exact deadline',()=>{const end=deadlineAnchor(1030,1000,500);expect(remainingSeconds(end,500)).toBe(30);expect(remainingSeconds(end,29501)).toBe(1);expect(remainingSeconds(end,30500)).toBe(0);expect(remainingSeconds(end,90000)).toBe(0);});
  it('refresh restores remaining time instead of granting another 30 seconds',()=>{const resumed=deadlineAnchor(1030,1022,900);expect(remainingSeconds(resumed,900)).toBe(8);});
  it('expired questions never receive a fresh countdown',()=>expect(remainingSeconds(deadlineAnchor(1030,1040,700),700)).toBe(0));
});
