# FocusLens · Computer Vision

**ESP32-CAM → ảnh JPEG/PNG → OCR cục bộ trên CPU với PaddleOCR.**
FocusLens là nền tảng thử nghiệm thị giác máy tính theo mô-đun, hướng tới
thiết bị hỗ trợ đọc và tra cứu Anh–Việt. Hiện tại dự án chỉ triển khai capture,
kiểm tra ảnh và OCR; không cần dịch vụ AI trả phí.

[Cài đặt](#cài-đặt) · [Sử dụng](#sử-dụng) · [Kiểm thử](#kiểm-thử) · [Giấy phép](#giấy-phép)

## Kiến trúc và phạm vi

```text
ESP32-CAM /capture hoặc file JPEG/PNG
    → Python: kiểm tra định dạng, giải mã và giới hạn ảnh
    → PP-OCRv5_mobile_det → en_PP-OCRv4_mobile_rec (CPU)
    → JSON: text, confidence, polygon, thời gian xử lý
```

- Đã có: firmware CameraWebServer tùy chỉnh, helper Wi-Fi nhập ẩn,
  CLI capture/OCR, hợp đồng `Frame`/`TextLine`, batch OCR và 10 mẫu CORD.
- Runtime OCR: 2 CPU threads, MKLDNN tắt; orientation/unwarping tắt.
- Chưa triển khai: dịch Anh–Việt, TTS, từ điển, pipeline riêng cho chữ viết tay,
  giao diện ứng dụng và cloud backend. Chưa có benchmark CER/WER/accuracy.
- Không xác nhận lại phần cứng trong lần xuất bản này. QVGA mặc định của firmware
  chưa được đánh giá về chất lượng OCR; cần kiểm tra focus, ánh sáng và độ phân giải.

## Cài đặt

Môi trường đã dùng: Linux, CPython 3.12, PaddleOCR 3.3.2, PaddlePaddle CPU 3.2.2.
Cần Python 3.12 tương thích wheel Paddle và [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/apase95/FocusLens-ComputerVision.git
cd FocusLens-ComputerVision
uv venv --python python3.12 .venv
uv pip install --python .venv/bin/python -r requirements-ocr.lock.txt
```

`requirements-ocr.txt` ghim dependency trực tiếp; lock ghi 62 phiên bản, không có
hash artifact. Khả năng cài đặt mới còn phụ thuộc nền tảng và package index.
Trọng số tải khi chạy OCR lần đầu, không nằm trong repository; xem điều khoản
model ở [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Sử dụng

Chạy từ thư mục gốc dự án:

```sh
# Xác minh mẫu đã có, offline: 10 ảnh + hash và reference
.venv/bin/python retrieve_samples.py

# OCR file; stdout là JSON, không tự ghi đè ảnh
.venv/bin/python -m focuslens ocr samples/cord/test-000.png

# Batch thực sự chạy inference, ghi results/ocr-samples.json (gitignored)
.venv/bin/python ocr_samples.py
```

Batch giữ cache trong `.cache/`. Để CLI dùng chung model cache:

```sh
PADDLE_PDX_CACHE_HOME="$PWD/.cache/paddlex" .venv/bin/python -m focuslens ocr samples/cord/test-000.png
```

Tùy chọn, **chỉ khi chủ động thử camera trên LAN tin cậy**; thay `CAMERA_IP`:

```sh
.venv/bin/python -m focuslens capture http://CAMERA_IP/capture local.jpg
.venv/bin/python -m focuslens ocr local.jpg
```

Capture từ chối ghi đè file, giới hạn response mặc định 8 MB, ảnh 20 triệu pixel,
socket timeout 5 giây (không phải deadline tổng). URL có thể redirect theo urllib;
không dùng URL không tin cậy. Firmware mẫu không có xác thực/TLS: không mở port Internet.
Thiết lập Wi-Fi riêng bằng `python3 setup_wifi.py`; không đưa mật khẩu vào command,
chat hay git. Header và firmware đã compile có thể chứa bí mật, không chia sẻ chúng.

## Kiểm thử

```sh
python3 camera_smoke.py
.venv/bin/python focuslens_smoke.py
```

Hai runner cô lập, không discovery: 2 test helper Wi-Fi và 5 test capture/OCR
conversion/metadata mẫu; HTTP được giả lập bằng server loopback, không truy cập camera thật
hay tải model. Kiểm tra gồm đường thành công, từ chối ghi đè, HTTP lỗi, ảnh lỗi,
quá giới hạn byte, timeout và kết quả OCR rỗng.
Compile/flash là thao tác riêng, không thuộc smoke mặc định;
xem [README-camera.md](README-camera.md) trước khi thực hiện.

## Cấu trúc và tài liệu

```text
focuslens/           contracts, capture/validation, OCR adapter, CLI
CameraWebServer/     firmware nguồn từ Espressif (không kèm secrets)
samples/cord/        10 ảnh, annotations, text tham chiếu và manifest
retrieve_samples.py  tải mẫu khi thư mục trống hoặc xác minh offline
ocr_samples.py       batch inference và report cục bộ
setup_wifi.py        tạo header riêng, không ghi đè
```

- [OCR: cấu hình, lịch sử kiểm thử và giới hạn](README-ocr.md)
- [Camera: toolchain, Wi-Fi và cảnh báo flash](README-camera.md)
- [Nguồn mẫu và CC BY 4.0](samples/LICENSE-CORD.md)

CORD là receipt tiếng Indonesia từ NAVER CLOVA, không đại diện cho sách tiếng Anh
hoặc chữ viết tay. Annotation chỉ bao phủ một số vùng, không phải transcript toàn
trang. Ảnh/annotation gốc được giữ nguyên; text được ghép từ `valid_line`.
Manifest giữ nguồn ổn định và SHA256; endpoint chưa ghim revision nên hash xác
định snapshot. URL tải có chữ ký không được công bố. Không có tuyên bố accuracy.

## Giấy phép

[MIT](LICENSE) áp dụng cho phần mã/tài liệu gốc của FocusLens, © 2026 Ho Dang Thai Duy.
Không tái cấp phép toàn bộ repository thành MIT: mã Espressif theo Apache-2.0,
mẫu CORD theo CC BY 4.0; dependency và trọng số có điều khoản riêng.
Xem [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) và [LICENSE-APACHE-2.0](LICENSE-APACHE-2.0).
