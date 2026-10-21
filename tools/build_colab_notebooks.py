# Trình dựng 4 notebook Colab (.ipynb, nbformat 4). Chạy: python -I build_colab_notebooks.py
import json
from pathlib import Path

OUT = Path(r"C:\Users\Chinh Nguyen\Desktop\New folder\claude\content-factory\colab")
OUT.mkdir(parents=True, exist_ok=True)


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip("\n").splitlines(True)}


def notebook(cells):
    return {
        "nbformat": 4,
        "nbformat_minor": 4,
        "metadata": {
            "colab": {"provenance": [], "gpuType": "T4"},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python"},
            "accelerator": "GPU",
        },
        "cells": cells,
    }


def save(name, cells):
    p = OUT / name
    p.write_text(json.dumps(notebook(cells), ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", p)


GPU_NOTE = """> **Bước 0:** vào `Runtime > Change runtime type > T4 GPU` rồi bấm Save. Phiên Colab miễn phí có giới hạn thời gian; mọi kết quả đều được lưu ra Google Drive để không mất khi phiên bị ngắt.

Cấu trúc thư mục trên Drive (tự tạo ở ô mount):

```
MyDrive/content-factory/
  input/    <- đưa kịch bản .txt, video, audio lên đây
  output/   <- kết quả để tải về Local
  models/   <- trọng số / checkpoint
```
"""

MOUNT = r'''
from google.colab import drive
import os
drive.mount('/content/drive')
BASE = '/content/drive/MyDrive/content-factory'
IN_DIR, OUT_DIR, MODEL_DIR = f'{BASE}/input', f'{BASE}/output', f'{BASE}/models'
for d in (IN_DIR, OUT_DIR, MODEL_DIR):
    os.makedirs(d, exist_ok=True)
print('Input :', IN_DIR)
print('Output:', OUT_DIR)
print('Models:', MODEL_DIR)
'''

GPU_CHECK = r'''
import subprocess
r = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
print(r.stdout if r.returncode == 0 else 'KHONG THAY GPU. Hay chon Runtime > Change runtime type > T4 GPU.')
'''

# ---------------------------------------------------------------- 1. OpenMontage
nb1 = [
    md("""# OpenMontage trên Colab (T4)

Repo: https://github.com/calesthio/OpenMontage (giấy phép **AGPL-3.0** theo README).

**Nói thẳng về giới hạn (theo README đã đọc):**
- OpenMontage vận hành qua một **trợ lý lập trình AI** (Claude Code, Cursor, Codex...). README **không** nêu lệnh CLI riêng để render từ một tệp kịch bản. Luồng chung: `research -> proposal -> script -> scene_plan -> assets -> edit -> compose`, các bước sáng tạo dừng chờ bạn duyệt.
- Notebook này: cài môi trường, đặt kịch bản vào dự án, rồi (tùy chọn) gọi Claude Code ở chế độ không tương tác. Cờ của Claude Code đánh dấu `# TODO: kiểm tra` vì chưa xác minh trên Colab.
- README ghi mặc định: ngưỡng xin duyệt $0.50/hành động, trần ngân sách $10. Không có khóa API vẫn dựng được (Piper TTS offline, nguồn video mở, Remotion/HyperFrames + FFmpeg).
- AGPL-3.0: nếu bạn chạy bản sửa đổi như một dịch vụ mạng thì có nghĩa vụ công bố mã nguồn. README không nói gì về điều khoản của dịch vụ bên thứ ba hay bản quyền nội dung tạo ra; hãy tự kiểm tra.

""" + GPU_NOTE),
    md("## 1. Cấu hình (chỉnh ở đây)"),
    code(r'''
#@title Tham số
PROJECT_NAME = "my-video"      #@param {type:"string"}
SCRIPT_FILE  = "kichban.txt"   #@param {type:"string"}
OPENMONTAGE_COMMIT = ""        #@param {type:"string"}
# Để trống = lấy bản mới nhất. Dán mã commit để ghim phiên bản.
RUN_CLAUDE_CODE = False        #@param {type:"boolean"}
# Cần khóa ANTHROPIC_API_KEY trong Colab Secrets (biểu tượng chìa khóa bên trái).
EXTRA_INSTRUCTION = "Make a vertical 1080x1920 short from this script. Use free assets only."  #@param {type:"string"}
'''),
    md("## 2. Mount Drive và kiểm tra GPU"),
    code(MOUNT),
    code(GPU_CHECK),
    md("## 3. Cài đặt OpenMontage\nTheo README: `git clone`, `make setup` (hoặc `pip install -r requirements.txt` + `npm install` trong `remotion-composer`). Yêu cầu Python 3.10+, FFmpeg, Node 18+ (HyperFrames cần Node 22+)."),
    code(r'''
import subprocess, os, shutil

def sh(cmd, cwd=None, check=True):
    print('$', cmd)
    r = subprocess.run(cmd, shell=True, cwd=cwd, text=True, capture_output=True)
    print(r.stdout[-3000:])
    if r.returncode != 0:
        print('LOI:', r.stderr[-3000:])
        if check:
            raise RuntimeError(f'Lenh that bai: {cmd}')
    return r

sh('apt-get -y -qq install ffmpeg make')
print(sh('node -v', check=False).stdout)
# TODO: kiem tra - neu Node < 22, cai Node 22 (vd. qua nodesource) de HyperFrames chay duoc.
if not os.path.isdir('/content/OpenMontage'):
    sh('git clone https://github.com/calesthio/OpenMontage.git /content/OpenMontage')
if OPENMONTAGE_COMMIT:
    sh(f'git checkout {OPENMONTAGE_COMMIT}', cwd='/content/OpenMontage')
sh('git rev-parse HEAD', cwd='/content/OpenMontage')
sh('make setup', cwd='/content/OpenMontage', check=False)  # TODO: kiem tra - neu loi, chay chuoi lenh thay the trong README
'''),
    md("## 4. Đưa kịch bản từ Drive/input vào dự án"),
    code(r'''
import pathlib
src = pathlib.Path(IN_DIR) / SCRIPT_FILE
assert src.exists(), f'Khong thay {src}. Hay dua kich ban .txt len Drive/input.'
script_text = src.read_text(encoding='utf-8')
proj = pathlib.Path('/content/OpenMontage/projects') / PROJECT_NAME
proj.mkdir(parents=True, exist_ok=True)
(proj / 'script.txt').write_text(script_text, encoding='utf-8')
print('Da chep kich ban:', proj / 'script.txt', f'({len(script_text)} ky tu)')
PROMPT = (f"{EXTRA_INSTRUCTION}\nProject name: {PROJECT_NAME}.\n"
          f"The approved script is in projects/{PROJECT_NAME}/script.txt. Render to projects/{PROJECT_NAME}/renders/final.mp4.")
print(PROMPT)
'''),
    md("## 5. Chạy dựng video\n**Cách A (khuyến nghị, đúng thiết kế của OpenMontage):** mở repo trong một trợ lý AI và dán `PROMPT` ở trên. Trên Colab thì dùng cách B nếu bạn có khóa API.\n\n**Cách B (thử nghiệm):** cài Claude Code CLI và chạy không tương tác."),
    code(r'''
import os, subprocess
if not RUN_CLAUDE_CODE:
    print('RUN_CLAUDE_CODE = False: bo qua. Hay dung Cach A, hoac bat tham so nay.')
else:
    from google.colab import userdata
    os.environ['ANTHROPIC_API_KEY'] = userdata.get('ANTHROPIC_API_KEY')
    subprocess.run('npm install -g @anthropic-ai/claude-code', shell=True, check=True)
    # TODO: kiem tra - co va quyen cua Claude Code khi chay bang root tren Colab.
    r = subprocess.run(['claude', '-p', PROMPT, '--permission-mode', 'acceptEdits'],
                       cwd='/content/OpenMontage', text=True, capture_output=True)
    print(r.stdout[-6000:])
    if r.returncode != 0:
        print('LOI:', r.stderr[-3000:])
'''),
    md("## 6. Chép kết quả ra Drive/output"),
    code(r'''
import glob, shutil, os
found = glob.glob(f'/content/OpenMontage/projects/{PROJECT_NAME}/renders/*.mp4')
if not found:
    print('Chua co video trong renders/. Kiem tra buoc 5 (README chi neu ro duong dan projects/<ten>/renders/final.mp4).')
for f in found:
    dst = os.path.join(OUT_DIR, f'{PROJECT_NAME}_{os.path.basename(f)}')
    shutil.copy2(f, dst)
    print('KET QUA:', dst, f'({os.path.getsize(dst)/1e6:.1f} MB)')
'''),
]

# ---------------------------------------------------------------- 2. GPT-SoVITS
nb2 = [
    md("""# GPT-SoVITS trên Colab (T4)

Repo: https://github.com/RVC-Boss/GPT-SoVITS

## Về mẫu giọng 5 giây (nói thẳng)
Theo README của repo:
- **Zero-shot (không huấn luyện):** cần mẫu giọng khoảng **5 giây**. Đây là mức bạn đang có, **đủ để suy luận zero-shot** (dùng làm audio tham chiếu).
- **Few-shot / fine-tune:** README nêu khoảng **1 phút** dữ liệu huấn luyện. Fine-tune với 5 giây **không phù hợp** (dễ quá khớp, giọng kém ổn định). Muốn fine-tune hãy thu ít nhất ~1 phút giọng sạch, một người nói, không nhạc nền.
- Nếu chỉ có 5 giây: bỏ qua mục huấn luyện, đi thẳng tới mục **Suy luận zero-shot**.

## Chuẩn bị mẫu giọng
- Định dạng wav/mp3, mono, giọng sạch, không vang, không nhạc. Với zero-shot, mẫu tham chiếu nên dài 3-10 giây và bạn phải biết **nội dung chữ** của nó (dùng làm `prompt_text`).
- Đặt vào `Drive/content-factory/input/voice/` (vd. `mau_giong.wav`) kèm `mau_giong.txt` chứa lời nói.

""" + GPU_NOTE),
    md("## 1. Cấu hình"),
    code(r'''
#@title Tham số
VOICE_DIR     = "voice"            #@param {type:"string"}
REF_AUDIO     = "mau_giong.wav"    #@param {type:"string"}
REF_TEXT_FILE = "mau_giong.txt"    #@param {type:"string"}
REF_LANG      = "vi"               #@param {type:"string"}
SCRIPT_FILE   = "kichban.txt"      #@param {type:"string"}
TEXT_LANG     = "vi"               #@param {type:"string"}
EXP_NAME      = "giong_cua_toi"    #@param {type:"string"}
GPTSOVITS_COMMIT = ""              #@param {type:"string"}
# LUU Y: README liet ke ma ngon ngu zh, ja, en, ko, yue. Tieng Viet KHONG co trong danh sach do.
# TODO: kiem tra - GPT-SoVITS co ho tro 'vi' hay khong. Neu khong, dung 'en' (chat luong tieng Viet co the kem).
'''),
    md("## 2. Mount Drive và kiểm tra GPU"),
    code(MOUNT),
    code(GPU_CHECK),
    md("## 3. Cài đặt\nREADME dùng conda (`install.sh`). Trên Colab ta dùng cách **cài thủ công** của README: `pip install -r extra-req.txt --no-deps` rồi `pip install -r requirements.txt`, cùng FFmpeg và libsox-dev. README đã kiểm thử Python 3.12 + PyTorch 2.7.1 (CUDA 12.8)."),
    code(r'''
import subprocess, os
def sh(cmd, cwd=None, check=True):
    print('$', cmd)
    r = subprocess.run(cmd, shell=True, cwd=cwd, text=True, capture_output=True)
    print(r.stdout[-2500:])
    if r.returncode != 0:
        print('LOI:', r.stderr[-2500:])
        if check:
            raise RuntimeError(f'Lenh that bai: {cmd}')
    return r

sh('python --version')
sh('apt-get -y -qq install ffmpeg libsox-dev')
if not os.path.isdir('/content/GPT-SoVITS'):
    sh('git clone https://github.com/RVC-Boss/GPT-SoVITS.git /content/GPT-SoVITS')
if GPTSOVITS_COMMIT:
    sh(f'git checkout {GPTSOVITS_COMMIT}', cwd='/content/GPT-SoVITS')
sh('git rev-parse HEAD', cwd='/content/GPT-SoVITS')
sh('pip install -q -r extra-req.txt --no-deps', cwd='/content/GPT-SoVITS')
sh('pip install -q -r requirements.txt', cwd='/content/GPT-SoVITS')
# TODO: kiem tra - Colab co the can khop phien ban torch/CUDA voi README; neu xung dot, doc loi o tren.
'''),
    md("## 4. Tải mô hình tiền huấn luyện\nREADME: tải từ Hugging Face `lj1995/GPT-SoVITS` vào `GPT_SoVITS/pretrained_models` (đây là bước thay cho `install.sh`)."),
    code(r'''
from huggingface_hub import snapshot_download
snapshot_download(repo_id='lj1995/GPT-SoVITS', local_dir='/content/GPT-SoVITS/GPT_SoVITS/pretrained_models')
print('Da tai xong mo hinh tien huan luyen.')
# TODO: kiem tra - du dung luong (nhieu GB). Neu can ASR tieng Anh/Nhat (Faster Whisper Large V3), dat vao tools/asr/models.
'''),
    md("## 5A. (Chỉ khi có >= ~1 phút giọng) Tiền xử lý\nCắt audio rồi ASR để tạo file `.list` (`vocal_path|speaker_name|language|text`). Lệnh dưới lấy từ README; các tham số số liệu là giá trị gợi ý, hãy xem `python tools/slice_audio.py --help` nếu lỗi."),
    code(r'''
import subprocess, os
SLICED = '/content/work/sliced'
ASR_OUT = '/content/work/asr'
os.makedirs(SLICED, exist_ok=True); os.makedirs(ASR_OUT, exist_ok=True)
RAW = f'{IN_DIR}/{VOICE_DIR}'
if not os.path.isdir(RAW):
    print('Khong co thu muc giong:', RAW)
else:
    # README ghi 'python audio_slicer.py' voi cac tham so --input_path --output_root --threshold --min_length --min_interval --hop_size
    # TODO: kiem tra - duong dan that cua audio_slicer.py trong repo (co the la tools/slicer2.py).
    r = subprocess.run(f'python tools/slice_audio.py {RAW} {SLICED}', shell=True, cwd='/content/GPT-SoVITS', text=True, capture_output=True)
    print(r.stdout[-1500:], r.stderr[-1500:])
    # ASR ngon ngu khac tieng Trung (README): python ./tools/asr/fasterwhisper_asr.py -i <input> -o <output> -l <language> -p <precision>
    r = subprocess.run(f'python ./tools/asr/fasterwhisper_asr.py -i {SLICED} -o {ASR_OUT} -l en -p float16',
                       shell=True, cwd='/content/GPT-SoVITS', text=True, capture_output=True)
    print(r.stdout[-1500:], r.stderr[-1500:])
    # Sau do HAY HIEU DINH tay file .list trong ASR_OUT (README: buoc 5 'proofread ASR').
'''),
    md("## 5B. (Chỉ khi có >= ~1 phút giọng) Huấn luyện bằng WebUI\nREADME hướng dẫn fine-tune qua WebUI: `python webui.py <ngôn ngữ>` (cổng mặc định `webui_port_main = 9874` trong `config.py`). Trên Colab, cần đường hầm để mở giao diện.\nCác tab: `1-GPT-SoVITS-TTS` -> định dạng dữ liệu -> huấn luyện SoVITS -> huấn luyện GPT. Với T4, để batch size nhỏ."),
    code(r'''
# TODO: kiem tra - cach mo WebUI tu Colab. Phuong an: dung cloudflared de tao link cong khai tam thoi.
import subprocess, time
subprocess.run('wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared', shell=True)
webui = subprocess.Popen('python webui.py en', shell=True, cwd='/content/GPT-SoVITS')
time.sleep(25)
tunnel = subprocess.Popen('cloudflared tunnel --url http://localhost:9874', shell=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
import re
for _ in range(60):
    line = tunnel.stdout.readline()
    m = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', line or '')
    if m:
        print('MO WEBUI TAI:', m.group(0)); break
print('Huan luyen xong thi chay o 6 de xuat mo hinh. Dung WebUI: webui.terminate()')
'''),
    md("## 6. Xuất model (.ckpt / .pth) sang Drive/models\nTheo `config.py`: trọng số SoVITS lưu ở `SoVITS_weights*` (`.pth`), trọng số GPT ở `GPT_weights*` (`.ckpt`), tên thư mục phụ thuộc phiên bản (v1: `SoVITS_weights`/`GPT_weights`, v2: `..._v2`, v3: `..._v3`, v4: `..._v4`, v2Pro, v2ProPlus, v5dev, v5turbo)."),
    code(r'''
import glob, os, shutil
dst = f'{MODEL_DIR}/{EXP_NAME}'
os.makedirs(dst, exist_ok=True)
n = 0
for pat in ('SoVITS_weights*/*.pth', 'GPT_weights*/*.ckpt'):
    for f in glob.glob(f'/content/GPT-SoVITS/{pat}'):
        shutil.copy2(f, dst); n += 1
        print('DA LUU:', os.path.join(dst, os.path.basename(f)))
if n == 0:
    print('Chua co trong so da huan luyen (binh thuong neu ban chi dung zero-shot).')
'''),
    md("## 7. Suy luận zero-shot: tạo audio từ kịch bản\nChạy `api_v2.py` (repo có tệp này; cổng mặc định trong `config.py` là `api_port = 9880`) và gọi `/tts`. Tên trường JSON lấy theo hiểu biết về api_v2, **chưa xác minh** trong lượt đọc README -> `# TODO: kiểm tra`."),
    code(r'''
import subprocess, time, requests, os, pathlib, wave
api = subprocess.Popen('python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml',
                       shell=True, cwd='/content/GPT-SoVITS')  # TODO: kiem tra - co & tham so cua api_v2.py
time.sleep(40)

ref_audio = f'{IN_DIR}/{VOICE_DIR}/{REF_AUDIO}'
ref_text = pathlib.Path(f'{IN_DIR}/{VOICE_DIR}/{REF_TEXT_FILE}').read_text(encoding='utf-8').strip()
script = pathlib.Path(f'{IN_DIR}/{SCRIPT_FILE}').read_text(encoding='utf-8').strip()
payload = {
    'text': script, 'text_lang': TEXT_LANG,
    'ref_audio_path': ref_audio, 'prompt_text': ref_text, 'prompt_lang': REF_LANG,
    'text_split_method': 'cut5', 'batch_size': 1, 'media_type': 'wav', 'streaming_mode': False,
}  # TODO: kiem tra ten truong voi api_v2.py
try:
    r = requests.post('http://127.0.0.1:9880/tts', json=payload, timeout=1800)
    r.raise_for_status()
    out = f'{OUT_DIR}/{EXP_NAME}_voice.wav'
    open(out, 'wb').write(r.content)
    print('KET QUA:', out, f'({len(r.content)/1e6:.1f} MB)')
except Exception as e:
    print('LOI suy luan:', e)
    print('Neu loi, mo inference_webui.py (python GPT_SoVITS/inference_webui.py, cong 9872) thu cong.')
finally:
    api.terminate()
'''),
]

# ---------------------------------------------------------------- 3. LatentSync
nb3 = [
    md("""# LatentSync trên Colab (T4)

Repo: https://github.com/bytedance/LatentSync

## VRAM thật (theo README)
- **LatentSync 1.5: tối thiểu 8 GB** khi suy luận.
- **LatentSync 1.6: tối thiểu 18 GB** khi suy luận (huấn luyện ở 512x512).
- GPU T4 Colab có **16 GB** -> **bản 1.6 không đủ theo README, bản 1.5 chạy được.** Mặc định notebook dùng **1.5**.

## Cách giảm VRAM / thời gian khi cần
- Dùng bản 1.5 (khuyến nghị cho T4).
- Giảm `inference_steps` (README: 20-50; thấp hơn nhanh hơn, hình kém hơn) và để `guidance_scale` 1.0-3.0.
- Giữ cờ `--enable_deepcache` (có trong `inference.sh` chính thức).
- Cắt video thành đoạn ngắn (vài giây đến ~1 phút) rồi ghép lại bằng FFmpeg.
- Nguồn video rõ mặt, một người, mặt thấy rõ; hạ độ phân giải nếu nguồn rất lớn.
- Không có phần "giảm VRAM khi suy luận" riêng trong README; mục giảm VRAM của README chỉ dành cho huấn luyện.

""" + GPU_NOTE),
    md("## 1. Cấu hình"),
    code(r'''
#@title Tham số
VIDEO_FILE = "video.mp4"     #@param {type:"string"}
AUDIO_FILE = "audio.wav"     #@param {type:"string"}
OUT_NAME   = "video_lipsync.mp4"  #@param {type:"string"}
VERSION    = "1.5"           #@param ["1.5", "1.6"]
INFERENCE_STEPS = 20         #@param {type:"integer"}
GUIDANCE_SCALE  = 1.5        #@param {type:"number"}
ENABLE_DEEPCACHE = True      #@param {type:"boolean"}
LATENTSYNC_COMMIT = ""       #@param {type:"string"}
'''),
    md("## 2. Mount Drive và kiểm tra GPU"),
    code(MOUNT),
    code(GPU_CHECK),
    md("## 3. Cài đặt\n`setup_env.sh` của repo dùng conda + Python 3.10.13. Trên Colab ta chạy các lệnh tương đương không có conda: `pip install -r requirements.txt`, `apt install libgl1`, FFmpeg, rồi tải checkpoint từ Hugging Face."),
    code(r'''
import subprocess, os
def sh(cmd, cwd=None, check=True):
    print('$', cmd)
    r = subprocess.run(cmd, shell=True, cwd=cwd, text=True, capture_output=True)
    print(r.stdout[-2500:])
    if r.returncode != 0:
        print('LOI:', r.stderr[-2500:])
        if check:
            raise RuntimeError(f'Lenh that bai: {cmd}')
    return r

sh('python --version')  # setup_env.sh dung Python 3.10.13; Colab co the la ban khac. TODO: kiem tra tuong thich requirements.txt
sh('apt-get -y -qq install ffmpeg libgl1')
if not os.path.isdir('/content/LatentSync'):
    sh('git clone https://github.com/bytedance/LatentSync.git /content/LatentSync')
if LATENTSYNC_COMMIT:
    sh(f'git checkout {LATENTSYNC_COMMIT}', cwd='/content/LatentSync')
sh('git rev-parse HEAD', cwd='/content/LatentSync')
sh('pip install -q -r requirements.txt', cwd='/content/LatentSync')
'''),
    md("## 4. Tải checkpoint\nTheo `setup_env.sh`: `huggingface-cli download ByteDance/LatentSync-1.6 whisper/tiny.pt ...` và `latentsync_unet.pt`. Với bản 1.5 ta đổi repo thành `ByteDance/LatentSync-1.5` (tên repo này **chưa xác minh**)."),
    code(r'''
import subprocess, os
repo = 'ByteDance/LatentSync-1.5' if VERSION == '1.5' else 'ByteDance/LatentSync-1.6'
# TODO: kiem tra - ten repo HF cua ban 1.5 va ten tep trong do (README chi xac nhan repo 1.6).
ckpt_cache = f'{MODEL_DIR}/latentsync_{VERSION}'
os.makedirs(ckpt_cache, exist_ok=True)
for f in ('whisper/tiny.pt', 'latentsync_unet.pt'):
    cmd = f'huggingface-cli download {repo} {f} --local-dir /content/LatentSync/checkpoints'
    print('$', cmd)
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    print(r.stdout[-800:], r.stderr[-800:])
print(subprocess.run('ls -la /content/LatentSync/checkpoints /content/LatentSync/checkpoints/whisper', shell=True, text=True, capture_output=True).stdout)
'''),
    md("## 5. Chạy đồng bộ khẩu hình\nLệnh lấy từ `inference.sh` chính thức (có `--enable_deepcache`, 20 bước, guidance 1.5). Cấu hình UNet: bản 1.6 dùng `configs/unet/stage2_512.yaml`; bản 1.5 nhiều khả năng là `configs/unet/stage2.yaml` (**TODO: kiểm tra**)."),
    code(r'''
import subprocess, os, shutil
video = f'{IN_DIR}/{VIDEO_FILE}'; audio = f'{IN_DIR}/{AUDIO_FILE}'
for p in (video, audio):
    assert os.path.exists(p), f'Khong thay {p}. Hay dua len Drive/input.'
shutil.copy2(video, '/content/in_video.mp4'); shutil.copy2(audio, '/content/in_audio.wav')

unet_cfg = 'configs/unet/stage2_512.yaml' if VERSION == '1.6' else 'configs/unet/stage2.yaml'  # TODO: kiem tra
cmd = ['python', '-m', 'scripts.inference',
       '--unet_config_path', unet_cfg,
       '--inference_ckpt_path', 'checkpoints/latentsync_unet.pt',
       '--inference_steps', str(INFERENCE_STEPS),
       '--guidance_scale', str(GUIDANCE_SCALE),
       '--video_path', '/content/in_video.mp4',
       '--audio_path', '/content/in_audio.wav',
       '--video_out_path', '/content/out.mp4']
if ENABLE_DEEPCACHE:
    cmd.insert(-8, '--enable_deepcache')
print(' '.join(cmd))
r = subprocess.run(cmd, cwd='/content/LatentSync', text=True, capture_output=True)
print(r.stdout[-3000:])
if r.returncode != 0:
    print('LOI:', r.stderr[-4000:])
    if 'out of memory' in r.stderr.lower():
        print('>> Het VRAM: dung ban 1.5, giam INFERENCE_STEPS, hoac cat video ngan hon.')
else:
    dst = f'{OUT_DIR}/{OUT_NAME}'
    shutil.copy2('/content/out.mp4', dst)
    print('KET QUA:', dst, f'({os.path.getsize(dst)/1e6:.1f} MB)')
'''),
]

# ---------------------------------------------------------------- 4. Video2X
nb4 = [
    md("""# Video2X (upscale lên 4K) trên Colab (T4)

Repo: https://github.com/k4yt3x/video2x (bản 6.x, README nêu 6.4.0 là mới nhất lúc đọc).

## Điểm KHÔNG chắc chắn (nói thẳng)
- Video2X cần **Vulkan** (README: GPU phải hỗ trợ Vulkan). Ở Colab, driver NVIDIA thường **chỉ có CUDA**, **có thể thiếu Vulkan ICD** (`nvidia_icd.json`). Tôi **không thể xác minh** điều này từ máy Local, notebook sẽ **kiểm tra thật** ở ô 3.
- Docs Video2X nêu `vkEnumeratePhysicalDevices failed -3` thì thêm `--privileged` (chỉ áp dụng cho Docker, không dùng được trong Colab).
- Tên tệp AppImage trên trang Releases không đọc được tĩnh; notebook lấy danh sách asset qua GitHub API lúc chạy.
- Cú pháp CLI xác minh từ docs: `video2x -i in.mp4 -o out.mp4 -p realesrgan -s 4 --realesrgan-model realesr-animevideov3`; chọn GPU `-g`, liệt kê `--list-gpus`.

## Phương án dự phòng (tự động theo kết quả kiểm tra)
1. **Video2X AppImage** nếu có Vulkan.
2. **Real-ESRGAN bản PyTorch (CUDA, không cần Vulkan)** — chạy được trên T4. Chưa xác minh trọn vẹn trên Colab (`# TODO: kiểm tra`).
3. **FFmpeg lanczos** lên 3840x2160: luôn chạy được, nhưng không phải AI, chỉ phóng to.

""" + GPU_NOTE),
    md("## 1. Cấu hình"),
    code(r'''
#@title Tham số
VIDEO_FILE = "video_thap.mp4"  #@param {type:"string"}
OUT_NAME   = "video_4k.mp4"    #@param {type:"string"}
PROCESSOR  = "realesrgan"      #@param ["realesrgan", "libplacebo"]
REALESRGAN_MODEL = "realesr-animevideov3"  #@param ["realesr-animevideov3", "realesrgan-plus"]
SCALE = 4                      #@param {type:"integer"}
TARGET_W, TARGET_H = 3840, 2160
FORCE_METHOD = "auto"          #@param ["auto", "video2x", "realesrgan_pytorch", "ffmpeg_lanczos"]
'''),
    md("## 2. Mount Drive và kiểm tra GPU"),
    code(MOUNT),
    code(GPU_CHECK),
    md("## 3. Kiểm tra Vulkan thật trên Colab"),
    code(r'''
import subprocess, glob, os
def sh(cmd, check=False):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    return r

sh('apt-get -y -qq install libvulkan1 vulkan-tools mesa-vulkan-drivers ffmpeg')
icds = glob.glob('/usr/share/vulkan/icd.d/*.json') + glob.glob('/etc/vulkan/icd.d/*.json')
print('ICD tim thay:', icds)
has_nvidia_icd = any('nvidia' in p.lower() for p in icds)
r = sh('vulkaninfo --summary')
print(r.stdout[-2500:] or r.stderr[-1500:])
vk_gpu = ('NVIDIA' in r.stdout) and ('Tesla' in r.stdout or 'T4' in r.stdout or 'GPU' in r.stdout)
VULKAN_OK = r.returncode == 0 and 'NVIDIA' in r.stdout
print('\n>>> Vulkan tren GPU NVIDIA:', 'CO' if VULKAN_OK else 'KHONG (hoac chi co llvmpipe CPU)')
# TODO: kiem tra - thu tao ICD thu cong neu thieu: tao /etc/vulkan/icd.d/nvidia_icd.json tro toi libGLX_nvidia.so.0.
# Khong ep ghi o day vi chua xac minh tren Colab; neu can hay lam thu cong roi chay lai o nay.
'''),
    md("## 4A. Phương án chính: Video2X AppImage (nếu có Vulkan)"),
    code(r'''
import requests, os, subprocess, shutil
USE_V2X = (FORCE_METHOD == 'video2x') or (FORCE_METHOD == 'auto' and VULKAN_OK)
V2X = '/content/Video2X.AppImage'
if not USE_V2X:
    print('Bo qua Video2X (khong co Vulkan NVIDIA hoac FORCE_METHOD khac).')
else:
    try:
        rel = requests.get('https://api.github.com/repos/k4yt3x/video2x/releases/latest', timeout=30).json()
        print('Ban phat hanh:', rel.get('tag_name'))
        assets = [a for a in rel['assets'] if a['name'].lower().endswith('.appimage')]
        print('AppImage:', [a['name'] for a in assets])
        a = assets[0]
        with requests.get(a['browser_download_url'], stream=True, timeout=600) as rr:
            rr.raise_for_status()
            with open(V2X, 'wb') as f:
                shutil.copyfileobj(rr.raw, f)
        os.chmod(V2X, 0o755)
        print(subprocess.run([V2X, '--appimage-extract-and-run', '--help'], capture_output=True, text=True).stdout[:1500])
        # TODO: kiem tra - '--appimage-extract-and-run' (co the khong can FUSE tren Colab)
    except Exception as e:
        print('LOI tai/chay AppImage:', e)
        USE_V2X = False
'''),
    code(r'''
import subprocess, os, shutil
RESULT = None
src = f'{IN_DIR}/{VIDEO_FILE}'
assert os.path.exists(src), f'Khong thay {src}. Hay dua video len Drive/input.'
shutil.copy2(src, '/content/in.mp4')
tmp_out = '/content/out_v2x.mp4'
if USE_V2X:
    # Cu phap xac minh tu docs: video2x -i -o -p realesrgan -s 4 --realesrgan-model <ten> ; libplacebo dung -w -h
    if PROCESSOR == 'realesrgan':
        cmd = [V2X, '--appimage-extract-and-run', '-i', '/content/in.mp4', '-o', tmp_out,
               '-p', 'realesrgan', '-s', str(SCALE), '--realesrgan-model', REALESRGAN_MODEL]
    else:
        cmd = [V2X, '--appimage-extract-and-run', '-i', '/content/in.mp4', '-o', tmp_out,
               '-w', str(TARGET_W), '-h', str(TARGET_H), '-p', 'libplacebo',
               '--libplacebo-shader', 'anime4k-v4-a+a']
    print(' '.join(cmd))
    r = subprocess.run(cmd, text=True, capture_output=True)
    print(r.stdout[-2000:])
    if r.returncode == 0 and os.path.exists(tmp_out):
        RESULT = tmp_out
    else:
        print('LOI Video2X:', r.stderr[-3000:])
        print('>> Chuyen sang phuong an du phong o muc 4B.')
'''),
    md("## 4B. Dự phòng: Real-ESRGAN PyTorch (CUDA) rồi FFmpeg\nChạy khi Video2X không dùng được. Real-ESRGAN gốc: https://github.com/xinntao/Real-ESRGAN . Gói `basicsr` đôi khi lỗi với torchvision mới (**TODO: kiểm tra**, có thể phải vá `functional_tensor`)."),
    code(r'''
import subprocess, os, shutil
if RESULT is None and FORCE_METHOD in ('auto', 'realesrgan_pytorch'):
    def run(cmd, cwd=None):
        r = subprocess.run(cmd, shell=True, cwd=cwd, text=True, capture_output=True)
        print('$', cmd); print(r.stdout[-1200:]);
        if r.returncode: print('LOI:', r.stderr[-1500:])
        return r.returncode == 0
    ok = run('git clone https://github.com/xinntao/Real-ESRGAN.git /content/Real-ESRGAN') if not os.path.isdir('/content/Real-ESRGAN') else True
    ok = ok and run('pip install -q basicsr facexlib gfpgan', '/content/Real-ESRGAN')
    ok = ok and run('pip install -q -r requirements.txt', '/content/Real-ESRGAN')
    ok = ok and run('python setup.py develop', '/content/Real-ESRGAN')
    # TODO: kiem tra - ten co va mo hinh cua inference_realesrgan_video.py (-n, -s, --suffix, --fp32)
    ok = ok and run(f'python inference_realesrgan_video.py -n RealESRGAN_x4plus -i /content/in.mp4 -o /content/re_out -s {SCALE}', '/content/Real-ESRGAN')
    if ok:
        import glob
        outs = glob.glob('/content/re_out/*.mp4')
        RESULT = outs[0] if outs else None
    if RESULT is None:
        print('Real-ESRGAN PyTorch khong chay duoc -> dung FFmpeg lanczos o muc 4C.')
'''),
    md("## 4C. Cuối cùng: ép đúng 3840x2160 và lưu ra Drive/output\nNếu chưa có kết quả AI, bước này dùng FFmpeg lanczos (chỉ phóng to, không phải AI)."),
    code(r'''
import subprocess, os, shutil
src_for_final = RESULT or '/content/in.mp4'
if RESULT is None:
    print('CANH BAO: chua co ket qua AI, chi phong to bang lanczos.')
dst = f'{OUT_DIR}/{OUT_NAME}'
vf = (f'scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease:flags=lanczos,'
      f'pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2')
r = subprocess.run(['ffmpeg', '-y', '-i', src_for_final, '-i', '/content/in.mp4', '-map', '0:v:0', '-map', '1:a:0?',
                    '-vf', vf, '-c:v', 'libx264', '-crf', '18', '-preset', 'medium',
                    '-pix_fmt', 'yuv420p', '-c:a', 'copy', dst], text=True, capture_output=True)
if r.returncode != 0:
    print('LOI FFmpeg:', r.stderr[-3000:])
else:
    print('KET QUA:', dst, f'({os.path.getsize(dst)/1e6:.1f} MB)')
    print(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height', '-of', 'csv=p=0', dst], text=True, capture_output=True).stdout)
'''),
]

save("colab_openmontage.ipynb", nb1)
save("colab_gpt_sovits.ipynb", nb2)
save("colab_latentsync.ipynb", nb3)
save("colab_video2x.ipynb", nb4)