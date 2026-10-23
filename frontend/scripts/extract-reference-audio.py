"""Extract the selected short broadcast cues from a local copy of the reference.

Usage: python scripts/extract-reference-audio.py reference.m4a --ffmpeg ffmpeg
The application needs only the resulting WAV files, never Python or YouTube.
"""
import argparse, json, subprocess
from pathlib import Path

CLIPS = {
    'intro': (0.35, 4.5, 'Заставка выпуска'),
    'suspense': (2178.5, 12.8, 'Ожидание ответа на вопрос об изобретении шприца'),
    'select': (2653.30, .70, 'Фиксация ответа в последнем вопросе'),
    'correct': (572.28, 3.8, 'Верный ответ на вопрос об автомобиле'),
    'incorrect': (2669.30, 3.30, 'Неверный ответ в последнем вопросе'),
    'timeout': (2669.30, 2.6, 'Тот же сигнал проигрыша для истечения времени в нашей игре'),
    'tick': (547.55, .18, 'Короткий фрагмент отсчёта звонка другу'),
    'correct-major': (1872.55, 5.8, 'Верный ответ и переход к следующей сумме'),
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / 'public' / 'audio'
    manifest = {'source': 'https://www.youtube.com/watch?v=Yzhau6No0KY',
                'title': 'Кто хочет стать миллионером — 18 ноября 2007',
                'kind': 'broadcast-excerpts', 'clips': {}}
    for name, (start, duration, purpose) in CLIPS.items():
        fade = .012 if duration < 1 else .06
        filters = f'highpass=f=65,lowpass=f=12000,volume=2.5,afade=t=in:d={fade},afade=t=out:st={duration-fade}:d={fade},alimiter=limit=0.93:level=false'
        subprocess.run([args.ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                        '-ss', str(start), '-i', str(args.source), '-t', str(duration),
                        '-vn', '-af', filters, '-ar', '32000', '-ac', '1',
                        '-c:a', 'pcm_s16le', str(output / f'{name}.wav')], check=True)
        manifest['clips'][name] = {'file': f'{name}.wav', 'start': start, 'duration': duration, 'purpose': purpose}
    (output / 'sources.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Extracted {len(CLIPS)} reference excerpts into {output}')

if __name__ == '__main__':
    main()
