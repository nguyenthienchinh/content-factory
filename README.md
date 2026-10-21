# Content Factory

Ứng dụng Windows (1 file exe) điều phối: viết kịch bản qua proxy ClewdR, làm video trên Google Colab, đăng bài qua Postiz.

## Đóng exe trên GitHub
1. Tạo repo, đẩy toàn bộ thư mục này lên (không đẩy `vendor/`, `data/`, `config.json`; đã có trong `.gitignore`).
2. Vào tab Actions, chọn "build-exe", bấm Run workflow. Hoặc đẩy tag: `git tag v0.1.0 && git push --tags`.
3. Tải `ContentFactory.exe` ở mục Artifacts (hoặc Releases khi dùng tag).

## Dùng
1. Mở file exe ClewdR riêng của bạn, nạp cookie Claude.ai, lấy mật khẩu API.
2. Mở `ContentFactory.exe`; trình duyệt tự mở `http://127.0.0.1:8765`.
3. Mục Cài đặt: nhập địa chỉ proxy (`http://127.0.0.1:8484`), mật khẩu API, tên model, bấm Kiểm tra kết nối.
4. Mục 1 viết kịch bản, mục 2 đưa lên Drive và chạy notebook Colab, mục 3 đăng bài.

Dữ liệu (`data/`, `config.json`) nằm cạnh file exe. Mật khẩu lưu dạng chữ thường trong `config.json`, không chia sẻ tệp này.

## Postiz
Chạy riêng (Ubuntu/WSL bằng `setup_local.sh`, hoặc máy khác). Ứng dụng chỉ mở địa chỉ Postiz, không gọi API của nó.

## Lưu ý
- Windows SmartScreen có thể cảnh báo exe chưa ký số; chọn "More info" rồi "Run anyway".
- Chưa chạy thử exe và các notebook Colab trên môi trường thật.
- Dùng cookie Claude.ai qua proxy có thể vi phạm điều khoản dịch vụ; OpenMontage dùng giấy phép AGPL-3.0.