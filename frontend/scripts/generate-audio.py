"""Create original quiz-show-style cues; no samples or melodies from a TV show.
Run manually with Python 3.11+: python scripts/generate-audio.py
Writes a separate fallback folder; never overwrites the broadcast excerpts.
"""
from array import array
from math import exp, pi, sin
from pathlib import Path
import wave

RATE = 22050
OUT = Path(__file__).resolve().parent.parent / 'public' / 'audio' / 'synthesized-fallback'
OUT.mkdir(parents=True, exist_ok=True)


def render(name, duration, notes, drone=False):
    samples = []
    for i in range(int(duration * RATE)):
        t = i / RATE
        value = 0.
        if drone:
            pulse = .5 + .5 * sin(2*pi*2*t)
            value = .12*sin(2*pi*55*t) + .05*sin(2*pi*82.5*t) + .025*pulse*sin(2*pi*165*t)
        for start, length, frequency, volume in notes:
            age = t-start
            if 0 <= age < length:
                envelope = min(1, age/.008) * min(1, (length-age)/.04) * exp(-age*2.8/length)
                # Soft struck-metal/synth timbre with individually enveloped notes.
                value += volume*envelope*(sin(2*pi*frequency*age)+.22*sin(2*pi*frequency*2*age)+.08*sin(2*pi*frequency*3*age))
        value *= min(1,t/.025,(duration-t)/.035)
        samples.append(value)
    scale = .84 / max(.84, max(abs(s) for s in samples))
    pcm = array('h', (int(max(-1,min(1,s*scale))*32767) for s in samples))
    with wave.open(str(OUT / f'{name}.wav'), 'wb') as output:
        output.setparams((1,2,RATE,len(pcm),'NONE','not compressed'))
        output.writeframes(pcm.tobytes())
    print(f'{name}.wav: {duration:.2f}s')


render('intro', 1.8, [(0,.7,110,.35),(.16,.7,164.81,.27),(.34,.8,220,.25),(.56,1.1,329.63,.23),(.56,1.1,440,.18)])
render('suspense', 8, [(i*.5,.28,220 if i%4==0 else 165,.045) for i in range(16)], drone=True)
render('select', .2, [(0,.18,660,.22),(0,.13,990,.08)])
render('correct', 1.9, [(0,.8,220,.25),(.16,.8,277.18,.24),(.32,.9,329.63,.24),(.54,1.25,440,.23),(.54,1.25,554.37,.15),(.54,1.25,659.25,.12)])
render('incorrect', 1.6, [(0,1.4,110,.32),(0,1.25,116.54,.18),(.3,1.15,82.41,.22),(.3,1.15,164.81,.15)])
render('timeout', 1.25, [(0,.27,440,.26),(.3,.27,330,.26),(.6,.6,165,.32)])
render('tick', .09, [(0,.085,1500,.13),(0,.05,2250,.045)])
