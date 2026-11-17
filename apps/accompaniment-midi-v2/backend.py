import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path

from core import BASE, LABELS, export_sources

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[1] / 'work'
SPACE = 'mimbres/YourMT3'


def transcribe(audio, target, use_cache=True, hf_token=None):
    from gradio_client import Client, handle_file
    key = hashlib.sha256(SPACE.encode() + Path(audio).read_bytes()).hexdigest()
    cached = ROOT / 'cache' / f'{key}.mid'
    cached.parent.mkdir(exist_ok=True)
    if not use_cache or not cached.exists():
        client = Client(SPACE, token=hf_token or os.getenv('HF_TOKEN') or None)
        result = client.predict(handle_file(str(audio)), api_name='/process_audio')
        if isinstance(result, (tuple, list)):
            result = result[0]
        match = re.search(r'data:audio/(?:midi|mid|x-midi);base64,([A-Za-z0-9+/=]+)', str(result))
        if not match:
            raise ValueError('YourMT3 没有返回 MIDI 数据')
        data = base64.b64decode(match.group(1), validate=True)
        temporary = target.with_suffix('.download.mid')
        temporary.write_bytes(data)
        import pretty_midi
        pretty_midi.PrettyMIDI(str(temporary))
        shutil.copy2(temporary, cached)
        temporary.unlink()
    shutil.copy2(cached, target)


def separate(audio, folder):
    python = WORK / 'demucs-env' / 'python.exe'
    if not python.exists():
        raise RuntimeError('尚未安装本地分轨环境。请运行 install-separator.ps1，或选择上传已分离音轨。')
    normalized = folder / 'input.wav'
    log = folder / 'separation.log'
    # A bundled ffmpeg executable avoids requiring a system ffmpeg installation.
    prepare = 'import imageio_ffmpeg,subprocess,sys; subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-y","-i",sys.argv[1],"-ar","44100","-ac","2",sys.argv[2]],check=True)'
    env = os.environ.copy()
    env['TORCH_HOME'] = str(WORK / 'model-cache')
    with log.open('w', encoding='utf-8') as stream:
        for args in ([str(python), '-c', prepare, str(audio), str(normalized)],
                     [str(python), '-m', 'demucs', '-n', 'htdemucs_6s', '-d', 'cpu', '-j', '1', '--shifts', '1', '-o', str(folder / 'stems'), str(normalized)]):
            result = subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, env=env, timeout=7200)
            if result.returncode:
                raise RuntimeError(f'本机分轨失败，详情见 {log}')
    stem_dir = folder / 'stems' / 'htdemucs_6s' / 'input'
    files = {role: stem_dir / f'{name}.wav' for role, name in [('bass','bass'),('guitar','guitar'),('keys','piano'),('drums','drums'),('other','other')]}
    if not all(p.is_file() for p in files.values()):
        raise RuntimeError(f'分轨文件不完整，详情见 {log}')
    return files


def saved_stems(folder):
    stem_dir = folder / 'stems' / 'htdemucs_6s' / 'input'
    return {role: stem_dir / f'{name}.wav' for role, name in [('bass','bass'),('guitar','guitar'),('keys','piano'),('drums','drums'),('other','other')]}


def resumable_tasks():
    paths = [p for p in (ROOT / 'results').glob('*') if p.is_dir() and (p / 'manifest.json').exists()
             and all(v.is_file() for v in saved_stems(p).values())]
    return [p.name for p in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)]


def quota_message(error):
    text = str(error)
    if 'quota' not in text.lower() or not any(k in text.lower() for k in ('gpu','zerogpu')):
        return None
    wait = re.search(r'Try again in ([\d:]+)', text, re.I)
    return ('线上 GPU 额度不足，本机分轨结果已保留。' +
            (f'服务提示需等待 {wait.group(1)}（以本次报错时刻为准）。' if wait else '') +
            '\n可使用 Hugging Face Token 按账号额度调用；Token 不保证无限额度。额度恢复后再继续，不会自动反复请求。')


def transcribe_piano(audio, target, use_cache=True):
    python = WORK / 'demucs-env/python.exe'
    checkpoint = WORK / 'model-cache/piano/high_resolution.pth'
    if not checkpoint.exists() or checkpoint.stat().st_size < 160000000:
        raise RuntimeError('本地钢琴模型尚未就绪，请关闭钢琴专用模型选项，或安装并下载模型。')
    key = hashlib.sha256(b'piano-specialist-v1' + Path(audio).read_bytes()).hexdigest()
    cached = ROOT / 'cache' / f'piano-{key}.mid'
    cached.parent.mkdir(exist_ok=True)
    if use_cache and cached.exists():
        shutil.copy2(cached,target)
        return
    log = target.with_suffix('.log')
    env = os.environ.copy()
    env['NUMBA_CACHE_DIR'] = str(WORK / 'numba-cache')
    with log.open('w',encoding='utf-8') as stream:
        result = subprocess.run([str(python),str(ROOT/'piano_worker.py'),str(audio),str(target),str(checkpoint)],
                                env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=7200)
    if result.returncode:
        raise RuntimeError(f'钢琴专用识别失败，详情见 {log}')
    import pretty_midi
    pretty_midi.PrettyMIDI(str(target))
    shutil.copy2(target,cached)


def process(mode, audio, stems, midi, consent, aligned, bpm, minimum_ms, use_cache, progress=lambda *a, **k: None, hf_token=None, resume_id=None, keyboard_enhance=False):
    if mode != 'midi' and not consent:
        raise ValueError('请勾选同意线上音频处理。')
    if mode == 'stems' and (not any(stems.values()) or not aligned):
        raise ValueError('请上传至少一个音轨，并确认所有音轨起点相同。')
    if mode in ('direct','local') and not audio:
        raise ValueError('请上传原歌曲。')
    if mode == 'midi' and not midi:
        raise ValueError('请上传多轨 MIDI。')
    if mode == 'resume':
        if not resume_id or not re.fullmatch(r'[a-f0-9]{12}', resume_id):
            raise ValueError('请选择有效的已分轨任务。')
        folder = ROOT / 'results' / resume_id
        stems = saved_stems(folder)
        if not all(p.is_file() for p in stems.values()):
            raise ValueError('任务的分轨文件不完整，无法继续。')
    else:
        folder = ROOT / 'results' / uuid.uuid4().hex[:12]
        folder.mkdir(parents=True)
    manifest = {'mode':mode, 'model': SPACE, 'status':'running', 'sources':[], 'keyboard_enhance':keyboard_enhance}
    manifest_path = folder / 'manifest.json'
    def save():
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    try:
        if mode == 'midi':
            tasks = [('ensemble', midi)]
        else:
            if mode == 'local':
                progress(.05, desc='CPU 六轨分离中；可能耗时较长')
                stems = separate(audio, folder)
            tasks = [('ensemble', audio)] if mode == 'direct' else [(k,v) for k,v in stems.items() if v]
            tasks.sort(key=lambda task: 0 if task[0]=='keys' else 1)
        sources = []
        raw = folder / 'raw_midi'
        raw.mkdir(exist_ok=True)
        if keyboard_enhance and mode in ('stems','local','resume') and stems.get('keys'):
            progress(.12, desc='本地钢琴专用模型补充识别（CPU）')
            specialist = raw / 'keys_specialist.mid'
            if not (mode == 'resume' and use_cache and specialist.exists()):
                transcribe_piano(stems['keys'],specialist,use_cache)
            sources.append(('keys_specialist',specialist))
            manifest['sources'].append({'role':'keys_specialist','file':str(specialist.relative_to(folder))})
            save()
        manifest['total_sources'] = len(tasks) + len(sources)
        save()
        for i, (role, path) in enumerate(tasks):
            progress(.15 + .65*i/len(tasks), desc=f'识别 {LABELS.get(role, role)} ({i+1}/{len(tasks)})')
            target = raw / f'{role}.mid'
            if mode == 'midi':
                shutil.copy2(path, target)
            elif mode == 'resume' and use_cache and target.exists():
                import pretty_midi
                pretty_midi.PrettyMIDI(str(target))
            elif hf_token:
                transcribe(path, target, use_cache, hf_token=hf_token)
            else:
                transcribe(path, target, use_cache)
            sources.append((role, target))
            manifest['sources'].append({'role':role, 'file':str(target.relative_to(folder))})
            save()
        progress(.9, desc='导出键盘、鼓、贝斯、吉他')
        report = export_sources(sources, folder / 'midi', bpm, minimum_ms)
        manifest.update(status='complete', report=report)
        save()
        archive = folder / 'accompaniment_v2.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for file in folder.rglob('*'):
                if file.is_file() and file.suffix in ('.mid','.json','.log'):
                    bundle.write(file, file.relative_to(folder))
        lines = [f'{LABELS[k]}：{v} 个音符' for k,v in report['notes'].items()]
        lines += [f'键盘重复音符合并：{report["keyboard_duplicates_removed"]} 个', f'按来源 / 乐器类别排除：{report["discarded_notes"]} 个音符', f'短音过滤：{report["short_notes_removed"]} 个', f'结果目录：{folder}']
        return '\n'.join(lines), str(folder / 'midi/accompaniment.mid'), str(archive)
    except Exception as error:
        # Never persist a supplied credential, even if a remote error echoes it.
        safe_error = str(error).replace(hf_token, '[REDACTED]') if hf_token else str(error)
        friendly = quota_message(error)
        manifest.update(status='quota_limited' if friendly else 'failed', error=safe_error)
        save()
        if friendly:
            partial = None
            if sources:
                export_sources(sources,folder/'midi',bpm,minimum_ms)
                partial = str(folder/'midi/accompaniment.mid')
            archive = folder / 'saved_progress.zip'
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
                bundle.write(manifest_path, 'manifest.json')
                for file in (folder / 'raw_midi').glob('*.mid'):
                    bundle.write(file, f'raw_midi/{file.name}')
                if partial:
                    for file in (folder / 'midi').glob('*.mid'):
                        bundle.write(file,f'partial_midi/{file.name}')
            complete = len(manifest['sources'])
            return f'{friendly}\n任务编号：{folder.name}\n已完成识别 {complete}/{manifest.get("total_sources",len(tasks))} 个来源。分轨文件仍在本机任务目录。\n选择“继续已分轨任务”并使用此编号即可恢复。' + ('\n当前下载仅为部分结果，尚未完成所有声部。' if partial else ''), partial, str(archive)
        raise RuntimeError(f'{safe_error}\n任务记录及已完成结果保存在 {folder}。') from None
