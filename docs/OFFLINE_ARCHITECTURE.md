# Kiến trúc offline — mục tiêu, chưa triển khai

## Ranh giới sản phẩm

Luckfox Pico Max RV1106G3 tự xử lý toàn bộ phiên sử dụng, kể cả boot không mạng.
Không cần PC/điện thoại/cloud/server LAN. Host chỉ phục vụ provisioning, export,
quantization, calibration, đóng gói asset và flash; runtime không tải tài nguyên.
MVP: người dùng căn **một từ tiếng Anh** trong ROI rồi nhấn chụp. Một dòng ngắn
là mở rộng cần đo lại; từ điển không phải máy dịch câu.

```text
Nút → CSI snapshot → ROI/resize/normalize
  → recognizer RKNN ứng viên → CTC decode CPU → từ OCR + trạng thái
  → SQLite EN–VI + IPA có giấy phép → UI tiếng Việt/IPA
  → bản ghi âm được cấp phép hoặc TTS offline nhẹ → audio output
```

Đây là thiết kế C/C++ dự kiến, không phải các module đang tồn tại.
Recognizer v5 hiện có là ứng viên, không bảo đảm chuyển đổi được. Phải kiểm tra
operator, shape/width tĩnh, input normalization, alphabet/blank token, INT8
calibration, bộ nhớ và parity CTC với host. NPU không phải bộ tăng tốc tổng quát
cho CTranslate2, LLM hoặc audio. Nguồn SDK nằm trong [tài liệu phần cứng](LUCKFOX_HARDWARE.md).

## Hợp đồng dữ liệu và trạng thái UI dự kiến

- Giữ nguyên chuỗi OCR hiển thị cùng crop; lookup có normalization được mô tả
  rõ và giữ liên kết tới entry gốc. Không âm thầm autocorrect từ không có trong DB.
- Entry gồm headword, nghĩa EN–VI, IPA (có thể thiếu), biến thể được khai báo,
  audio ID tùy chọn, nguồn/giấy phép/phiên bản. Nhiều nghĩa cần trình bày lựa chọn;
  lookup chính xác không bảo đảm OCR hay nghĩa theo ngữ cảnh chính xác 100%.
- Phân biệt `no_text`, `uncertain_ocr`, `unknown_word`, `missing_ipa`,
  `audio_missing`, `asset_error` và lỗi capture; có thể chụp lại, không bịa kết quả.
- Khi có entry, hiển thị từ + nghĩa + IPA; audio thiếu thì báo rõ, chỉ dùng TTS
  nếu engine/voice đã được cài và nghiệm thu, không fallback mạng.
- English speech trước; Vietnamese reading là gate engine/voice riêng.
  Font UI phải đủ dấu tiếng Việt và glyph IPA, kiểm tra shaping và bộ nhớ glyph cache.

## Bộ nhớ, độ bền và đo lường

256 MB là RAM tổng của board, không phải ngân sách riêng ứng dụng. Kernel, media
buffers, NPU runtime, display và audio cùng tiêu thụ RAM. Dùng snapshot/ROI và
buffer có giới hạn, xử lý tuần tự, giải phóng frame trung gian; thử unload model
trước audio nếu cần, đo cả chi phí reload. Không giả định allocator trả RAM ngay.
Chưa chốt budget số; chỉ chấp nhận sau đo RSS/PSS theo stage và peak toàn hệ thống.

Watchdog, timeout capture/inference/audio, nút có debounce, chống double-trigger,
asset manifest/hash và DB chỉ đọc là yêu cầu thiết kế. Ghi cấu hình theo cách atomic;
thử mất điện/brownout, boot phục hồi an toàn và trạng thái lỗi hiển thị được.
Đo cold boot offline, latency từng stage và camera→UI/âm thanh p50/p95, camera,
storage, audio và công suất toàn thiết bị. Không có cam kết 100 ms, thời lượng pin
hoặc độ chính xác khi chưa đo.

## Layout đề xuất (chưa tạo scaffold)

```text
embedded/                 # C/C++ runtime: capture, ROI, RKNN/CTC, lookup, UI, audio
tools/                    # host export/calibrate/package; phải tái lập được
assets/                   # manifest/license; payload chỉ khi có quyền phân phối
focuslens/                # Python host reference hiện có, giữ nguyên
scripts/                  # chuẩn bị host hiện có, giữ nguyên đường dẫn
tests/                    # host tests hiện có; embedded tests bổ sung khi port
docs/                     # kiến trúc, hardware, quyết định và acceptance gates
```

Không di chuyển code hiện tại trong đợt docs này. OPUS-MT/CTranslate2 vẫn là host
reference: peak RSS đã ghi **332,1 MiB > 256 MB RAM board**, chưa xác minh SDK
ARM32. Dịch câu phải qua feasibility độc lập với model/runtime phù hợp; không biến
dictionary MVP thành lời hứa dịch cả câu. Xem [roadmap](ROADMAP.md).
