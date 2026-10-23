import {mkdir, cp, access, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
await mkdir(root+'public/wasm', {recursive:true});
await mkdir(root+'public/models', {recursive:true});
await cp(root+'node_modules/@mediapipe/tasks-vision/wasm', root+'public/wasm', {recursive:true});
const path=root+'public/models/gesture_recognizer.task';
try { await access(path); }
catch {
  const url='https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task';
  try {
    const response=await fetch(url, {signal:AbortSignal.timeout(120000)});
    if (!response.ok) throw new Error('HTTP '+response.status);
    await writeFile(path, new Uint8Array(await response.arrayBuffer()));
    console.log('Модель MediaPipe сохранена локально.');
  } catch (e) {
    console.error('Не удалось скачать модель MediaPipe. Повторите: node scripts/setup-mediapipe.mjs');
    throw e;
  }
}
