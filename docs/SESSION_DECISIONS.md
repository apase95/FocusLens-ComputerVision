# Quyết định retarget — 2026-10-22

## Phạm vi nguồn thảo luận

Qua nội dung pane scout được đọc bằng Herdr, yêu cầu “last4” được đối chiếu với
bốn lượt user/request-response trong terminal scrollback, **không có bằng chứng
là bốn persisted agent sessions**. Bỏ lượt mới nhất về ESP32 RBMT theo câu;
ba lượt còn lại nói về từ điển/IPA/audio offline, MPU thay thế và BOM/pipeline
Luckfox Max. Tài liệu này ghi quyết định sản phẩm, không thay thế kiểm chứng phần cứng.

## Quyết định

- Target Pico Max RV1106G3 standalone; không bắt buộc PC/phone/cloud/LAN server.
- MVP một từ có guided ROI; SQLite EN–VI/IPA và audio/TTS offline là kế hoạch.
- Python hiện tại giữ nguyên như host reference; baseline/error-analysis v5 và
  các kết quả nghiên cứu trước đó được giữ, không tạo runtime nhúng giả hoặc scaffold rỗng.
- Không lặp lại các khẳng định chưa chứng minh: 100 ms đầu-cuối, guaranteed
  Paddle→RKNN, PC software chạy nguyên trạng ARM32, dictionary đúng 100%,
  Cambridge/Oxford audio miễn phí, hoặc USB line-out kéo loa thụ động trực tiếp.
- Chưa có số đo trực tiếp trên phần cứng Luckfox.

## Định vị metadata GitHub

Description tiếng Anh, dưới 200 ký tự:

> Fully offline OCR, English–Vietnamese lookup and speech for Luckfox Pico Max (RV1106G3). Embedded deployment in development; Python host reference and benchmarks included.

Topics đề xuất (mô tả **mục tiêu**, không xác nhận đã triển khai):

```text
offline-first luckfox-pico rv1106 embedded-linux edge-ai ocr
english-vietnamese text-to-speech computer-vision machine-translation rknn
```

Bỏ `esp32-s3` khỏi định vị chính; tài liệu ESP32 vẫn giữ lịch sử. Các nguồn và
cổng kiểm chứng nằm ở [hardware](LUCKFOX_HARDWARE.md) và [roadmap](ROADMAP.md).
