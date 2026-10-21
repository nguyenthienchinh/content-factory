# WORKFLOW: Local -> Colab -> Local

Luồng dữ liệu của Content Factory trên máy yếu (Surface 3 Pro, RAM 4GB, không GPU rời).
Nguyên tắc: máy Local chỉ làm việc nhẹ (viết kịch bản, đăng bài). Việc nặng chạy trên Google Colab.

## 1. Các thành phần

| Thành phần | Chạy ở đâu | Vai trò |
|---|---|---|
| ClewdR (exe riêng, không thuộc dự án) | Local | Proxy Claude, cung cấp API kiểu OpenAI tại http://127.0.0.1:8484 |
| ContentFactory.exe (app/main.py) | Local | Giao diện web tại http://127.0.0.1:8765: viết kịch bản, tải notebook, quản lý video |
| Postiz | Local (Ubuntu/WSL, PM2) hoặc máy khác | Đăng bài lên mạng xã hội |
| 4 notebook Colab | Google Colab (T4) | Giọng nói, dựng video, khớp khẩu hình, upscale |
| Google Drive | Đám mây | Cầu nối file giữa Local và Colab |

## 2. Sơ đồ

```
[LOCAL]                              [GOOGLE DRIVE]                    [COLAB T4]
1. Mở ClewdR (exe riêng)
2. Mở ContentFactory.exe
   - nhập chủ đề
   - gọi ClewdR 127.0.0.1:8484
   - áp quy tắc văn phong tự nhiên
   - lưu data/scripts/<slug>-<ts>.txt
3. Đưa .txt lên Drive/input  ------>                      ------>  4. colab_gpt_sovits   (giọng nói)
                                                                    5. colab_openmontage (dựng video)
                                                                    6. colab_latentsync  (khẩu hình, tùy chọn)
                                                                    7. colab_video2x     (upscale, tùy chọn)
                                     <------  8. Kết quả ghi vào Drive/output
9. Tải về data/drive_inbox
10. Đăng bài qua Postiz, rồi bấm "Đã đăng" trong ứng dụng
```

Cấu trúc thư mục trên Drive (các notebook dùng chung):

```
MyDrive/content-factory/
  input/    kịch bản .txt, video nguồn, audio nguồn
  output/   video/audio thành phẩm
  models/   model GPT-SoVITS đã train
```

Cấu trúc cạnh file exe (ứng dụng tự tạo):

```
ContentFactory.exe
config.json          địa chỉ proxy, mật khẩu API, model, rclone remote
data/scripts/        kịch bản .txt
data/drive_inbox/    video tải từ Drive về
data/published/      video đã đăng
```

## 3. Từng bước

### Bước 1. Chạy ClewdR
1. Mở file exe ClewdR. Mặc định nó nghe tại http://127.0.0.1:8484.
2. Mật khẩu API và mật khẩu admin được in ra console. Đây là hai mật khẩu riêng. Ứng dụng cần mật khẩu API.
3. Mở http://127.0.0.1:8484, đăng nhập bằng mật khẩu admin, vào Claude > Submit Cookie, dán cookie Claude.ai (mỗi dòng một cookie).
4. Giữ cửa sổ ClewdR mở suốt lúc dùng.

### Bước 2. Cài đặt ứng dụng
1. Mở ContentFactory.exe. Trình duyệt tự mở http://127.0.0.1:8765.
2. Vào mục Cài đặt, điền:
   - Địa chỉ proxy: http://127.0.0.1:8484
   - Mật khẩu API: mật khẩu API của ClewdR
   - Tên model: claude-sonnet-4-6 (danh sách thật xem tại http://127.0.0.1:8484/v1/models)
   - Rclone remote: gdrive:content-factory
3. Bấm Lưu, rồi Kiểm tra kết nối.

### Bước 3. Viết kịch bản
1. Mục Viết kịch bản: nhập chủ đề và yêu cầu thêm (không bắt buộc).
2. Bấm Viết kịch bản, chờ vài chục giây.
3. Kịch bản được lưu ở data/scripts/ cạnh file exe.

### Bước 4. Đưa kịch bản lên Drive
Chọn một trong hai cách:
- Thủ công: kéo thả tệp vào Drive/content-factory/input trên drive.google.com.
- rclone: chạy `rclone config` một lần để tạo remote `gdrive`, sau đó
  `rclone copy data\scripts gdrive:content-factory/input`

### Bước 5. Chạy notebook trên Colab
1. Mục Làm video (Colab) trong ứng dụng: tải 4 notebook về.
2. Vào colab.research.google.com, chọn Tệp > Tải notebook lên.
3. Chọn Thời gian chạy > Thay đổi loại thời gian chạy > T4 GPU.
4. Chạy từng ô từ trên xuống, cho phép truy cập Drive khi được hỏi.

| Notebook | Đầu vào (Drive/input) | Đầu ra |
|---|---|---|
| colab_gpt_sovits | mẫu giọng | model trong Drive/models, audio thử |
| colab_openmontage | kịch bản .txt | video trong Drive/output |
| colab_latentsync | video + audio | video khớp khẩu hình trong Drive/output |
| colab_video2x | video độ phân giải thấp | video 4K trong Drive/output |

Lưu ý:
- Phiên Colab miễn phí có giới hạn thời gian và có thể bị ngắt. Hãy lưu kết quả ra Drive sau mỗi bước.
- Mẫu giọng 5 giây chỉ đủ cho zero-shot. Fine-tune cần khoảng 1 phút trở lên. README của GPT-SoVITS không liệt kê tiếng Việt trong các ngôn ngữ hỗ trợ.
- LatentSync 1.5 mới vừa với T4 16GB (bản 1.6 cần khoảng 18GB).
- Video2X cần Vulkan. Chưa xác minh trên T4, notebook có phương án dự phòng.
- Các ô có TODO là chỗ chưa kiểm chứng. Nếu lỗi, ghi lại thông báo để sửa.

### Bước 6. Lấy video về
- Thủ công: tải từ Drive/content-factory/output về thư mục data\drive_inbox.
- rclone: `rclone copy gdrive:content-factory/output data\drive_inbox`
- Trong ứng dụng, nút Mở thư mục "Video về" mở nhanh thư mục này.

### Bước 7. Đăng bài qua Postiz
Ứng dụng chỉ mở giao diện Postiz, không gọi API của nó.
1. Cài Postiz một lần trên Ubuntu/WSL: chạy `bash setup_local.sh`, rồi làm theo phần hướng dẫn in ra cuối script (tạo database, điền .env của Postiz, `pnpm install`, `pnpm run build`, `pm2 start`).
2. Mục Đăng bài: nhập địa chỉ Postiz (mặc định http://localhost:5000), bấm Mở Postiz.
3. Trong Postiz: kết nối tài khoản mạng xã hội, tạo bài, đính kèm video từ drive_inbox, đăng hoặc lên lịch.
4. Quay lại ứng dụng, bấm Đã đăng cạnh video để chuyển sang data\published.

## 4. Mức tự động hóa thực tế

| Khâu | Mức độ |
|---|---|
| Viết kịch bản | Tự động (Local, qua ClewdR) |
| Chạy notebook Colab | Thủ công: Colab miễn phí không có API chính thức để kích hoạt từ xa |
| Đồng bộ file Local <-> Drive | Bán tự động nếu dùng rclone, hoặc thủ công |
| Đăng bài | Thủ công trong giao diện Postiz |

## 5. Lưu ý
- Postiz không nối được với ClewdR: client OpenAI của Postiz chỉ đọc OPENAI_API_KEY, không có base URL tùy chỉnh. Postiz vẫn đăng bài bình thường, chỉ tính năng AI của nó không dùng ClewdR.
- Mật khẩu API lưu dạng chữ thường trong config.json cạnh file exe. Không chia sẻ tệp này.
- Dùng cookie Claude.ai qua proxy có thể vi phạm điều khoản dịch vụ. OpenMontage dùng giấy phép AGPL-3.0.
- Chưa chạy thử exe và các notebook trên môi trường thật.

## 6. Mẹo cho RAM 4GB
- Postiz tốn RAM nhất. Bật swap 2GB (setup_local.sh hỏi xác nhận) và đóng chương trình khác khi build.
- Chạy Postiz ở chế độ production dưới PM2, đặt `NODE_OPTIONS=--max-old-space-size=1536`.
- Nếu quá chậm, chạy Postiz trên máy khác và chỉ sửa địa chỉ trong ô Mở Postiz.
- Không chạy mô hình AI nặng ở Local. Mọi suy luận nặng chạy trên Colab.

## 7. Xử lý sự cố nhanh

| Hiện tượng | Cách xử lý |
|---|---|
| Không kết nối được proxy | Mở exe ClewdR, kiểm tra địa chỉ và cổng trong Cài đặt |
| Proxy trả HTTP 401 | Đang dùng mật khẩu admin, phải nhập mật khẩu API |
| Trình duyệt không tự mở | Mở tay http://127.0.0.1:8765 |
| Cổng 8765 bị chiếm | Sửa "port" trong config.json, mở lại exe |
| Colab bị ngắt phiên | Chạy lại từ ô cuối đã lưu kết quả ra Drive |
| Không thấy video trên Local | Kiểm tra đã tải về data\drive_inbox, hoặc chạy lại rclone copy |