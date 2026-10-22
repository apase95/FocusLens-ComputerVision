# Roadmap — các cổng bắt buộc, không phải cam kết lịch

Tất cả cổng nhúng dưới đây **chưa được xác minh trên board**.
Thử nghiệm host 2026-10-22 đã export PIR→ONNX, đạt parity FP32 trên 4 TRAIN word,
build RKNN RV1106 INT8 với workaround và chạy PC simulator. Simulator khớp 4/4
chuỗi nhưng không đạt tolerance tensor FP32; calibration chỉ 16 TRAIN ảnh riêng.
**Cổng 2 chưa đạt**: chưa có parity/quality đủ rộng hoặc memory/latency board.
Xem [bằng chứng và lệnh tái lập](RKNN_CTC_FEASIBILITY.md).
Expanded trial: [500+500 TRAIN protocol](RKNN_DATASET_EVALUATION.md) selected
disjoint sets, but 10/500 FP32 comparisons failed the unchanged numerical gate.
Expanded INT8 remains blocked; no board or quality gate is cleared.

| Cổng | Bằng chứng để đi tiếp |
|---|---|
| 0. Chốt nền tảng | Đúng Pico Max/revision, BSP/toolchain ARM32 tái lập, license manifest và boot không mạng |
| 1. I/O | Camera CSI snapshot/focus ROI, display VI/IPA, nút và USB host/audio hoạt động; pinmux và nguồn đo được |
| 2. OCR feasibility | Export/convert recognizer ứng viên; operator/shape/INT8 hợp lệ; CTC charset/blank/normalization parity so với host trên tập calibration và tập kiểm tra riêng; đo memory/latency board |
| 3. Lookup/UI | Corpus EN–VI + IPA có quyền phân phối; SQLite lookup có test known/unknown, biến thể và nhiều nghĩa; không silent autocorrect |
| 4. Speech | Bản ghi hoặc engine+voice offline được cấp phép, ARM32 chạy được; English trước; missing audio rõ ràng, VI là gate riêng |
| 5. Standalone acceptance | Ngắt mạng và host, cold boot→capture→nghĩa/IPA→audio; đo stage RSS/PSS, peak hệ thống, p50/p95 end-to-end, storage/audio/power; thử timeout, mất SD, asset lỗi, watchdog và brownout |
| 6. Quality | Bộ ảnh độc lập do người audit, camera/ánh sáng/font thực tế; chốt ngưỡng chất lượng và ngân sách từ số đo, không dùng TEST đã xem để tuyên bố held-out |

Nếu recognizer v5 không đáp ứng, đánh giá model nhỏ khác theo cùng protocol,
không đổi nhãn baseline PC thành kết quả NPU. MVP chỉ một từ ROI; short line cần
đánh giá lại shape, CTC, UX và bộ nhớ. Detector/full page không phải yêu cầu MVP.

## Nhánh dịch câu: feasibility riêng

OPUS-MT/CTranslate2 host đã ghi peak RSS 332,1 MiB, lớn hơn tổng RAM 256 MB.
Chưa chứng minh SDK/ABI ARM32 tương thích; NPU không tự tăng tốc CT2/LLM.
Chỉ mở nhánh này sau khi có model/runtime/license và số đo phù hợp tài nguyên.
Tra từng từ không tạo thành dịch câu có ngữ cảnh. Không chuyển xử lý sang LAN/cloud
để gọi là standalone. Các [benchmark host](../README.md#bằng-chứng-thực-nghiệm-và-giới-hạn)
và phân tích lỗi v5 được bảo toàn như bằng chứng lịch sử.
