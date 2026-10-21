# content-factory: cấu trúc thư mục

```
content-factory/
  app/
    main.py                   ứng dụng cục bộ (máy chủ web 127.0.0.1 + tự mở trình duyệt)
    ui/index.html             giao diện: Viết kịch bản, Làm video, Đăng bài, Cài đặt
  config/
    humanizer_rules.md        quy tắc văn phong tự nhiên (rút gọn từ blader/humanizer, MIT)
  colab/                      4 notebook Colab (tải trực tiếp từ giao diện)
  tools/build_colab_notebooks.py
  docs/WORKFLOW.md            luồng Local -> Drive -> Colab -> Local -> Postiz
  setup_local.sh              chỉ cài Postiz, PostgreSQL, Redis (Ubuntu/WSL)
  .github/workflows/build-exe.yml   đóng ContentFactory.exe trên GitHub Actions
  data/                       tạo tự động cạnh file exe
    scripts/                  kịch bản .txt
    drive_inbox/              video tải về từ Drive
    published/                video đã đăng
  config.json                 tạo tự động cạnh file exe (địa chỉ proxy, mật khẩu, model)
```

ClewdR không nằm trong dự án: bạn chạy file exe ClewdR riêng. Ứng dụng chỉ gọi tới địa chỉ proxy tương thích OpenAI mà bạn nhập trong mục Cài đặt.