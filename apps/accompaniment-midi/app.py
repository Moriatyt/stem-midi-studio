"""Cloud YourMT3 transcription and four-family MIDI export."""
import base64
import copy
import os
os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')
import certifi
os.environ.setdefault('SSL_CERT_FILE', certifi.where())
import re
import uuid
import zipfile
from pathlib import Path

import gradio as gr
import pretty_midi
from gradio_client import Client, handle_file

ROOT = Path(__file__).resolve().parent


def export_tracks(source, destination):
    midi = pretty_midi.PrettyMIDI(str(source))
    families = {name: [] for name in ('bass', 'guitar', 'keys', 'drums')}
    ignored = 0
    for instrument in midi.instruments:
        if instrument.is_drum:
            family = 'drums'
        elif 32 <= instrument.program <= 39:
            family = 'bass'
        elif 24 <= instrument.program <= 31:
            family = 'guitar'
        elif 0 <= instrument.program <= 23:
            family = 'keys'
        else:
            ignored += len(instrument.notes)
            continue
        families[family].append(instrument)
    combined = copy.deepcopy(midi)
    combined.instruments = []
    counts = {}
    for family, instruments in families.items():
        track = pretty_midi.Instrument(program={'bass': 33, 'guitar': 24, 'keys': 0, 'drums': 0}[family], is_drum=family == 'drums', name=family)
        for instrument in instruments:
            track.notes.extend(copy.deepcopy(instrument.notes))
        track.notes.sort(key=lambda note: (note.start, note.pitch))
        counts[family] = len(track.notes)
        combined.instruments.append(track)
        single = copy.deepcopy(midi)
        single.instruments = [copy.deepcopy(track)]
        single.write(str(destination / f'{family}.mid'))
    combined.write(str(destination / 'accompaniment.mid'))
    return counts, ignored


def run(audio, existing, online, progress=gr.Progress()):
    folder = ROOT / 'results' / uuid.uuid4().hex[:12]
    folder.mkdir(parents=True)
    if existing:
        source = Path(existing)
    else:
        if not audio:
            raise gr.Error('请先上传歌曲，或导入已有的多轨 MIDI。')
        if not online:
            raise gr.Error('线上转录需要勾选音频上传同意选项。')
        progress(0.1, desc='连接线上 YourMT3 服务')
        try:
            client = Client('mimbres/YourMT3', token=os.getenv('HF_TOKEN') or None)
            result = client.predict(handle_file(audio), api_name='/process_audio')
            if isinstance(result, (tuple, list)):
                result = result[0]
            match = re.search(r'data:audio/(?:midi|mid|x-midi);base64,([A-Za-z0-9+/=]+)', str(result))
            if not match:
                raise ValueError('服务没有返回可解析的 MIDI 数据')
            source = folder / 'model_original.mid'
            source.write_bytes(base64.b64decode(match.group(1), validate=True))
        except Exception as error:
            raise gr.Error(f'线上转录未完成：{error}。公开演示可能休眠、排队或限制 API；也可导入已有 MIDI。') from error
    progress(0.85, desc='整理四个伴奏声部')
    counts, ignored = export_tracks(source, folder)
    archive = folder / 'four_tracks.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for file in folder.glob('*.mid'):
            bundle.write(file, file.name)
    summary = '\n'.join(f'{name}：{count} 个音符' for name, count in counts.items())
    return f'{summary}\n未归入四类的音符：{ignored}\n空声部表示模型未识别到，不会补造音符。', str(folder / 'accompaniment.mid'), str(archive)


with gr.Blocks(title='伴奏扒谱', analytics_enabled=False) as app:
    gr.Markdown('# 伴奏扒谱\n导出贝斯、吉他、键盘、鼓四个声部。建议先试 30 秒片段。')
    gr.Markdown('线上模式使用 YourMT3 公开演示，可能排队或暂时不可用。键盘按 GM 钢琴、半音阶打击乐及风琴类别归组；合成器、弦乐等暂不归入。识别结果需要试听校正。')
    audio = gr.Audio(type='filepath', label='上传歌曲')
    consent = gr.Checkbox(label='同意将这段音频上传到 Hugging Face 的 YourMT3 服务进行识别')
    existing = gr.File(label='或者导入已有多轨 MIDI（仅本地整理）', file_types=['.mid', '.midi'])
    button = gr.Button('生成伴奏 MIDI', variant='primary')
    status = gr.Textbox(label='处理结果', lines=6)
    merged = gr.File(label='合并多轨 MIDI')
    archive = gr.File(label='四个独立 MIDI 与合并文件')
    button.click(run, [audio, existing, consent], [status, merged, archive])

if __name__ == '__main__':
    app.queue(default_concurrency_limit=1).launch(server_name='127.0.0.1', inbrowser=True)
