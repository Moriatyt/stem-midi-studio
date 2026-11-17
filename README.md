# STEM / MIDI Studio

把歌曲或分离好的音轨转成可编辑的伴奏 MIDI。导出键盘、鼓、贝斯和吉他四类声部，可以下载合并 MIDI 或分轨结果包。键盘包含钢琴、电钢琴、风琴和合成器音色。

- **直接识别**：上传原曲，由线上 YourMT3 识别。
- **分轨后识别**：上传已有分轨，或用 Demucs 在本机 CPU 上分轨，再逐轨识别。可用本地钢琴专用模型补漏，并从残余伴奏补充键盘音符。
- **继续任务**：重新使用已分离音轨和成功识别的结果。线上额度不足时，可以下载已完成的部分。
- **导入 MIDI**：在本地筛选四类伴奏声部并重新导出。

## 在 Windows 上运行

安装 Python 3.11 或更高版本，从项目根目录在 PowerShell 执行：

```powershell
py -3.11 -m venv work/venv
.\work\venv\Scripts\python.exe -m pip install -r .\apps\accompaniment-midi-v2\requirements.txt
.\apps\accompaniment-midi-v2\start.cmd
```

如使用的是已激活的 Python 3.11 或更高版本，可将第一行换成 `python -m venv work/venv`。浏览器会打开工作台，实际地址以启动窗口显示为准。

直接识别和上传已分离音轨均使用 [YourMT3 公开演示服务](https://huggingface.co/spaces/mimbres/YourMT3)。提交音频前，页面会请你确认上传。可在「账号与高级设置」填写自己的 Hugging Face Token，或通过 `HF_TOKEN` 环境变量提供。服务可能限制配额、排队或临时不可用。

## 安装本机分轨和钢琴增强

安装 Conda 后，在项目根目录执行以下脚本。分轨需要下载模型，钢琴增强另需下载钢琴模型及依赖。

```powershell
.\apps\accompaniment-midi-v2\install-separator.ps1
.\apps\accompaniment-midi-v2\install-keyboard.ps1
```

只安装分轨环境时，可以在页面取消勾选「钢琴增强」。CPU 分轨建议先用 15–30 秒的片段。上传已有分轨时，各轨需保留相同起点，包括开头静音。模型对复杂混音、弱音和相近音色可能有漏音或错音，导出的 MIDI 适合作为可编辑的扒谱初稿。

## 版本与文件

- [当前版](apps/accompaniment-midi-v2/)提供工作台、四类导出、分轨、键盘增强与任务恢复。
- [第一版](apps/accompaniment-midi/)保留了最初的直接识别和四类导出。可复用上述界面环境，运行 `apps/accompaniment-midi/start.ps1`。
- 运行环境和模型位于本地 `work/`。处理结果和识别缓存分别位于相应版本的 `results/` 和 `cache/`。

本项目源码采用 [MIT 许可证](LICENSE)。外部服务、依赖及模型分别适用各自的条款。模型代码和权重由上游提供。[YourMT3](https://github.com/mimbres/YourMT3) · [Demucs](https://github.com/facebookresearch/demucs) · [Piano Transcription](https://github.com/bytedance/piano_transcription)
