# Trình dựng notebook worker Colab (nbformat 4). Chạy: python -I build_worker_notebook.py
# Worker chạy liên tục trên Colab, nhận job từ Drive/jobs/pending, xử lý lần lượt các giai đoạn,
# ghi kết quả vào Drive/output/<job_id>/ và cập nhật Drive/jobs/status/<job_id>.json.
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "colab"
OUT.mkdir(parents=True, exist_ok=True)


def md(t):
    return {"cell_type": "markdown", "metadata": {}, "source": t.strip("\n").splitlines(True)}


def code(t):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": t.strip("\n").splitlines(True)}


cells = [
    md("""# Content Factory Worker (Colab T4)

Chạy notebook này **một lần** rồi để tab mở. Worker tự nhận job do ứng dụng Local đẩy vào Drive.

Luồng job: `jobs/pending/<id>.json` -> `jobs/running/<id>.json` -> `jobs/done/<id>.json` (hoặc `failed/`).
Trạng thái: `jobs/status/<id>.json`. Kết quả: `output/<id>/`.

Nói thẳng về giới hạn:
- Colab miễn phí tự ngắt phiên sau một thời gian không hoạt động hoặc sau tối đa vài giờ. Khi ngắt, bạn phải mở lại notebook và bấm chạy; job đang dở sẽ được xếp lại hàng đợi.
- Các giai đoạn dưới đây gọi lại mã cài đặt đã viết trong 4 notebook riêng. Những chỗ ghi `TODO` là chưa kiểm chứng trên Colab thật.

> Runtime > Change runtime type > T4 GPU."""),
    code(r'''
#@title Cấu hình
POLL_SECONDS = 20        #@param {type:"integer"}
MAX_IDLE_MINUTES = 150   #@param {type:"integer"}
'''),
    code(r'''
from google.colab import drive
import os, json, time, subprocess, shutil, traceback, pathlib
drive.mount('/content/drive')
BASE = '/content/drive/MyDrive/content-factory'
J = {k: f'{BASE}/jobs/{k}' for k in ('pending', 'running', 'done', 'failed', 'status')}
IN_DIR, OUT_DIR, MODEL_DIR = f'{BASE}/input', f'{BASE}/output', f'{BASE}/models'
for d in list(J.values()) + [IN_DIR, OUT_DIR, MODEL_DIR]:
    os.makedirs(d, exist_ok=True)

def sh(cmd, cwd=None, check=True):
    print('$', cmd)
    r = subprocess.run(cmd, shell=True, cwd=cwd, text=True, capture_output=True)
    print(r.stdout[-1500:])
    if r.returncode != 0:
        print('LOI:', r.stderr[-1500:])
        if check:
            raise RuntimeError(f'Lenh that bai: {cmd}')
    return r

def set_status(job_id, stage, state, note=''):
    p = f'{J["status"]}/{job_id}.json'
    json.dump({'id': job_id, 'stage': stage, 'state': state, 'note': note, 'time': time.time()},
              open(p, 'w', encoding='utf-8'), ensure_ascii=False)
'''),
    md("## Giai đoạn 1: giọng nói (GPT-SoVITS)\nCài một lần khi job đầu tiên cần. Mẫu giọng 5 giây chỉ dùng zero-shot. README GPT-SoVITS không liệt kê tiếng Việt."),
    code(r'''
def ensure_sovits():
    if os.path.isdir('/content/GPT-SoVITS/GPT_SoVITS/pretrained_models/s1v3.ckpt') or os.path.exists('/content/.sovits_ready'):
        return
    sh('apt-get -y -qq install ffmpeg libsox-dev')
    if not os.path.isdir('/content/GPT-SoVITS'):
        sh('git clone https://github.com/RVC-Boss/GPT-SoVITS.git /content/GPT-SoVITS')
    sh('pip install -q -r extra-req.txt --no-deps', cwd='/content/GPT-SoVITS')
    sh('pip install -q -r requirements.txt', cwd='/content/GPT-SoVITS')
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id='lj1995/GPT-SoVITS', local_dir='/content/GPT-SoVITS/GPT_SoVITS/pretrained_models')
    open('/content/.sovits_ready', 'w').write('1')

def stage_tts(job, outdir):
    import requests
    ensure_sovits()
    ref = job.get('ref_audio', 'voice/mau_giong.wav')
    ref_txt = pathlib.Path(f'{IN_DIR}/{job.get("ref_text", "voice/mau_giong.txt")}').read_text(encoding='utf-8').strip()
    api = subprocess.Popen('python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml',
                           shell=True, cwd='/content/GPT-SoVITS')  # TODO: kiem tra tham so api_v2.py
    try:
        time.sleep(45)
        payload = {'text': job['script'], 'text_lang': job.get('lang', 'en'),
                   'ref_audio_path': f'{IN_DIR}/{ref}', 'prompt_text': ref_txt,
                   'prompt_lang': job.get('ref_lang', 'en'), 'text_split_method': 'cut5',
                   'batch_size': 1, 'media_type': 'wav', 'streaming_mode': False}  # TODO: kiem tra ten truong
        r = requests.post('http://127.0.0.1:9880/tts', json=payload, timeout=1800)
        r.raise_for_status()
        out = f'{outdir}/voice.wav'
        open(out, 'wb').write(r.content)
        return out
    finally:
        api.terminate()
'''),
    md("## Giai đoạn 2: dựng video (OpenMontage)\nOpenMontage vận hành qua trợ lý lập trình AI, README không nêu lệnh render từ tệp kịch bản. Giai đoạn này chỉ chạy nếu job bật `use_claude_code` và Colab Secrets có `ANTHROPIC_API_KEY`; nếu không, nó ghi chú rõ và dừng ở giai đoạn này."),
    code(r'''
def stage_video(job, outdir):
    name = job['id']
    if not os.path.isdir('/content/OpenMontage'):
        sh('apt-get -y -qq install ffmpeg make')
        sh('git clone https://github.com/calesthio/OpenMontage.git /content/OpenMontage')
        sh('make setup', cwd='/content/OpenMontage', check=False)  # TODO: kiem tra
    proj = pathlib.Path('/content/OpenMontage/projects') / name
    proj.mkdir(parents=True, exist_ok=True)
    (proj / 'script.txt').write_text(job['script'], encoding='utf-8')
    if not job.get('use_claude_code'):
        raise RuntimeError('Job khong bat use_claude_code: OpenMontage can tro ly AI de dung video (xem ghi chu).')
    from google.colab import userdata
    os.environ['ANTHROPIC_API_KEY'] = userdata.get('ANTHROPIC_API_KEY')
    sh('npm install -g @anthropic-ai/claude-code')
    prompt = (f"{job.get('instruction', 'Make a vertical 1080x1920 short. Use free assets only.')}\n"
              f"Approved script: projects/{name}/script.txt. Render to projects/{name}/renders/final.mp4.")
    r = subprocess.run(['claude', '-p', prompt, '--permission-mode', 'acceptEdits'],
                       cwd='/content/OpenMontage', text=True, capture_output=True)  # TODO: kiem tra co Claude Code tren Colab
    print(r.stdout[-3000:])
    f = proj / 'renders' / 'final.mp4'
    if not f.exists():
        raise RuntimeError('Khong thay renders/final.mp4 sau khi dung.')
    out = f'{outdir}/video.mp4'
    shutil.copy2(f, out)
    return out
'''),
    md("## Giai đoạn 3: khớp khẩu hình (LatentSync 1.5, vừa với T4 16 GB)"),
    code(r'''
def stage_lipsync(job, outdir, video, audio):
    if not os.path.isdir('/content/LatentSync'):
        sh('apt-get -y -qq install ffmpeg libgl1')
        sh('git clone https://github.com/bytedance/LatentSync.git /content/LatentSync')
        sh('pip install -q -r requirements.txt', cwd='/content/LatentSync')
        for f in ('whisper/tiny.pt', 'latentsync_unet.pt'):
            # TODO: kiem tra ten repo HF cua ban 1.5 (README chi xac nhan 1.6, can 18 GB VRAM)
            sh(f'huggingface-cli download ByteDance/LatentSync-1.5 {f} --local-dir /content/LatentSync/checkpoints', check=False)
    out = f'{outdir}/lipsync.mp4'
    cmd = ['python', '-m', 'scripts.inference', '--unet_config_path', 'configs/unet/stage2.yaml',  # TODO: kiem tra
           '--inference_ckpt_path', 'checkpoints/latentsync_unet.pt', '--inference_steps', '20',
           '--guidance_scale', '1.5', '--enable_deepcache',
           '--video_path', video, '--audio_path', audio, '--video_out_path', out]
    r = subprocess.run(cmd, cwd='/content/LatentSync', text=True, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('LatentSync loi: ' + r.stderr[-800:])
    return out
'''),
    md("## Giai đoạn 4: upscale 4K\nVideo2X cần Vulkan (chưa xác minh trên T4). Ở đây dùng phương án chắc chắn chạy được: FFmpeg lanczos (không phải AI). Muốn dùng Video2X/Real-ESRGAN, xem notebook `colab_video2x.ipynb`."),
    code(r'''
def stage_upscale(job, outdir, video):
    out = f'{outdir}/final_4k.mp4'
    vf = 'scale=3840:2160:force_original_aspect_ratio=decrease:flags=lanczos,pad=3840:2160:(ow-iw)/2:(oh-ih)/2'
    r = subprocess.run(['ffmpeg', '-y', '-i', video, '-vf', vf, '-c:v', 'libx264', '-crf', '18',
                        '-pix_fmt', 'yuv420p', '-c:a', 'copy', out], text=True, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('FFmpeg loi: ' + r.stderr[-800:])
    return out
'''),
    md("## Vòng lặp worker\nDừng bằng nút Stop. Tự thoát khi nhàn rỗi quá `MAX_IDLE_MINUTES` để không giữ GPU vô ích."),
    code(r'''
def process(path):
    job = json.load(open(path, encoding='utf-8'))
    jid = job['id']
    running = f'{J["running"]}/{jid}.json'
    shutil.move(path, running)
    outdir = f'{OUT_DIR}/{jid}'
    os.makedirs(outdir, exist_ok=True)
    stages = job.get('stages', ['tts', 'video', 'lipsync', 'upscale'])
    try:
        audio = video = None
        if 'tts' in stages:
            set_status(jid, 'tts', 'running'); audio = stage_tts(job, outdir)
        if 'video' in stages:
            set_status(jid, 'video', 'running'); video = stage_video(job, outdir)
        if 'lipsync' in stages and video and audio:
            set_status(jid, 'lipsync', 'running'); video = stage_lipsync(job, outdir, video, audio)
        if 'upscale' in stages and video:
            set_status(jid, 'upscale', 'running'); video = stage_upscale(job, outdir, video)
        set_status(jid, 'done', 'done', note=video or audio or '')
        shutil.move(running, f'{J["done"]}/{jid}.json')
    except Exception as e:
        traceback.print_exc()
        set_status(jid, 'error', 'failed', note=str(e)[:500])
        shutil.move(running, f'{J["failed"]}/{jid}.json')

# Job dang chay do phien bi ngat: xep lai hang doi.
for f in os.listdir(J['running']):
    shutil.move(f'{J["running"]}/{f}', f'{J["pending"]}/{f}')

idle = time.time()
print('Worker dang cho job tai', J['pending'])
while time.time() - idle < MAX_IDLE_MINUTES * 60:
    jobs = sorted(f for f in os.listdir(J['pending']) if f.endswith('.json'))
    if jobs:
        process(f'{J["pending"]}/{jobs[0]}')
        idle = time.time()
    else:
        time.sleep(POLL_SECONDS)
print('Het thoi gian nhan roi, worker thoat.')
'''),
]

nb = {"nbformat": 4, "nbformat_minor": 4,
      "metadata": {"colab": {"provenance": [], "gpuType": "T4"},
                   "kernelspec": {"name": "python3", "display_name": "Python 3"},
                   "language_info": {"name": "python"}, "accelerator": "GPU"},
      "cells": cells}
p = OUT / "colab_worker.ipynb"
p.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote", p)