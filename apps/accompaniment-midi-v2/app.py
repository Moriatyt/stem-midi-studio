import os
from startup import TITLE, configure_ports, open_existing
configure_ports()
if __name__ == '__main__' and open_existing():
    raise SystemExit(0)
os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')
import certifi
os.environ.setdefault('SSL_CERT_FILE', certifi.where())

import gradio as gr
from backend import process, resumable_tasks

MODES = {'上传已分离音轨（推荐）':'stems', '原歌曲直接识别':'direct',
         '本机 CPU 自动分轨后识别':'local', '继续已分轨任务':'resume', '导入已有 MIDI':'midi'}


def run(mode, audio, bass, guitar, keys, drums, other, ensemble, midi,
        consent, aligned, bpm, minimum_ms, use_cache, hf_token=None, resume_id=None, keyboard_enhance=True, progress=gr.Progress()):
    stems = dict(bass=bass, guitar=guitar, keys=keys, drums=drums, other=other, ensemble=ensemble)
    if mode == '上传已分离音轨（推荐）' and other and ensemble:
        raise gr.Error('“其他残余音轨”和“单独管弦音轨”请选择一种，避免相同管弦音符重复加入。')
    try:
        return process(MODES[mode], audio, stems, midi, consent, aligned,
                       bpm, minimum_ms, use_cache, progress, hf_token=(hf_token or '').strip() or None, resume_id=resume_id, keyboard_enhance=keyboard_enhance)
    except Exception as error:
        raise gr.Error(str(error)) from error


def build_app():
    with gr.Blocks(title=TITLE, analytics_enabled=False) as app:
        gr.HTML('<header class="studio-hero"><div class="studio-brand">STEM / MIDI STUDIO</div><h1>把喜欢的音乐，变成可创作的音符。</h1><p>分离伴奏，提取演奏。为下一次编曲留出空间。</p><div class="studio-tags"><span>KEYS · 键盘</span><span>DRUMS · 鼓</span><span>BASS · 贝斯</span><span>GUITAR · 吉他</span></div></header>')
        with gr.Row(equal_height=False):
            with gr.Column(scale=3, min_width=320, elem_id='workspace'):
                gr.Markdown('### 01 / 导入音乐')
                mode = gr.Dropdown(list(MODES), value='本机 CPU 自动分轨后识别', label='处理方式')
                with gr.Group() as audio_group:
                    audio = gr.Audio(type='filepath', label='原歌曲', sources=['upload'])
                with gr.Group(visible=False) as stems_group:
                    gr.Markdown('各音轨需保持相同起点与开头静音，可只上传需要的声部。')
                    with gr.Row():
                        keys = gr.Audio(type='filepath', label='键盘', sources=['upload'])
                        drums = gr.Audio(type='filepath', label='鼓', sources=['upload'])
                    with gr.Row():
                        bass = gr.Audio(type='filepath', label='贝斯', sources=['upload'])
                        guitar = gr.Audio(type='filepath', label='吉他', sources=['upload'])
                    with gr.Accordion('补充残余伴奏 · 可选', open=False):
                        other = gr.Audio(type='filepath', label='残余伴奏，用于键盘补漏', sources=['upload'])
                    aligned = gr.Checkbox(label='音轨起点一致，未单独裁剪或移动')
                ensemble = gr.Audio(type='filepath', visible=False)
                with gr.Group(visible=False) as midi_group:
                    midi = gr.File(label='多轨 MIDI', file_types=['.mid','.midi'])
                choices = resumable_tasks()
                with gr.Group(visible=False) as resume_group:
                    resume_id = gr.Dropdown(choices, value=choices[0] if choices else None, label='选择已分轨任务')
                    refresh = gr.Button('刷新任务', size='sm')
                def refresh_tasks():
                    items = resumable_tasks()
                    return gr.Dropdown(choices=items, value=items[0] if items else None)
                refresh.click(refresh_tasks, outputs=resume_id)
                keyboard_enhance = gr.Checkbox(value=True, label='钢琴增强 · 本地补漏', info='针对钢琴分轨额外识别，保留和弦与弱音候选，会增加处理时间。')
                with gr.Accordion('账号与高级设置', open=False):
                    hf_token = gr.Textbox(type='password', label='Hugging Face Token', placeholder='可选，仅用于本次调用')
                    gr.Markdown('[获取 Token](https://huggingface.co/settings/tokens) · 线上识别受账号 GPU 额度限制。')
                    bpm = gr.Number(value=120, minimum=20, maximum=300, label='导出网格速度 · BPM', info='仅设置节拍网格，不改变演奏时间。')
                    minimum_ms = gr.Slider(0,150,value=0,step=5,label='短音过滤 · 毫秒',info='0 为关闭；也会影响鼓点。')
                    use_cache = gr.Checkbox(value=True,label='复用已完成的识别结果')
                consent = gr.Checkbox(label='同意将音频上传至 YourMT3 进行线上识别')
                button = gr.Button('生成伴奏 MIDI  →',variant='primary',elem_id='generate')
            with gr.Column(scale=2,min_width=280,elem_id='output-panel'):
                gr.Markdown('### 02 / 你的伴奏')
                gr.Markdown('识别完成后，在这里下载可编辑的 MIDI。')
                status = gr.Textbox(label='处理状态',placeholder='等待一段音乐。\n\n准备好后，点击「生成伴奏 MIDI」。',lines=8)
                merged = gr.File(label='合并 MIDI')
                archive = gr.File(label='分轨与完整结果包')
                gr.Markdown('键盘 · 鼓 · 贝斯 · 吉他\n\n结果可导入音乐制作软件继续编辑。弱音和复杂混音仍需试听核对。')
        def select_mode(value):
            code = MODES[value]
            return (gr.update(visible=code in ('direct','local')),gr.update(visible=code=='stems'),gr.update(visible=code=='midi'),gr.update(visible=code=='resume'),gr.update(visible=code in ('local','stems','resume')),gr.update(visible=code!='midi'))
        mode.change(select_mode,mode,[audio_group,stems_group,midi_group,resume_group,keyboard_enhance,consent])
        button.click(run,[mode,audio,bass,guitar,keys,drums,other,ensemble,midi,consent,aligned,bpm,minimum_ms,use_cache,hf_token,resume_id,keyboard_enhance],[status,merged,archive])
        gr.HTML('<div class="studio-note">为创作提供初稿 · 保留你的判断与演奏</div>')
    return app


if __name__ == '__main__':
    from pathlib import Path
    css = Path(__file__).with_name('studio.css').read_text(encoding='utf-8')
    theme = gr.themes.Base(primary_hue='green', neutral_hue='slate', font=['Segoe UI','Microsoft YaHei','sans-serif'])
    build_app().queue(default_concurrency_limit=1).launch(server_name='127.0.0.1', inbrowser=True, css=css, theme=theme)
