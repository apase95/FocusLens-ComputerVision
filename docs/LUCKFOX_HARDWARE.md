# Luckfox Pico Max — phần cứng và nguồn kiểm chứng

Chưa test hardware. Thông số vendor không phải số đo FocusLens:
**RV1106G3, một lõi Cortex-A7 32-bit, 256 MB DDR3L, NPU 1 TOPS,
256 MB SPI NAND, MIPI CSI**. Không coi đây là máy ARM64 hoặc máy PC chạy Python
nguyên trạng. 1 TOPS không xác định latency pipeline hay dung lượng model chạy được.

## Nguồn chính thức

- [Pico Pro/Max specifications](https://wiki.luckfox.com/Luckfox-Pico-Pro-Max)
- [CSI camera / Buildroot](https://wiki.luckfox.com/Luckfox-Pico-Pro-Max/CSI-Camera)
- [USB configuration](https://wiki.luckfox.com/Luckfox-Pico-Pro-Max/USB)
- [Luckfox RKNN guide](https://wiki.luckfox.com/Luckfox-Pico-RV1106/RKNN)
- [Rockchip RKNN Toolkit2](https://github.com/airockchip/rknn-toolkit2)
- [Luckfox BSP/SDK](https://github.com/LuckfoxTECH/luckfox-pico)

RKNN hỗ trợ RV1106 và board C API không đồng nghĩa Paddle recognizer v5 chuyển
được không sửa. Pin đúng phiên bản BSP/toolkit/runtime và kiểm tra ABI/operator,
INT8/static width, RAM và parity trên board trước khi kết luận hỗ trợ model.

## BOM: board xác định, ngoại vi còn là ứng viên

| Thành phần | Lựa chọn/phải xác minh trước khi mua hoặc nối |
|---|---|
| Compute | Luckfox Pico Max RV1106G3; kiểm tra đúng SKU/revision |
| Camera | Module sensor nằm trong danh sách vendor hỗ trợ cho CSI/Buildroot đã chọn; xác nhận connector, pinout, driver và lens/focus ở khoảng cách đọc |
| Display | SPI display ứng viên; kiểm tra driver, pinmux, refresh, buffer và glyph VI/IPA |
| Audio | USB DAC ứng viên; cấu hình USB host trong BSP, driver USB audio và nguồn; chọn line/headphone output phù hợp |
| Speaker | Cần amplifier phù hợp với loa thụ động; USB line-out không mặc nhiên kéo loa trực tiếp |
| Storage | SD cho DB/recordings/model nếu cần; xác nhận support, mount/read-only và lỗi mất thẻ |
| Controls | Nút chụp và UI tối thiểu; pinmux/điện áp/debounce theo schematic board |
| Power | Nguồn 5V được điều áp, pin có mạch bảo vệ/charger phù hợp; kiểm tra yêu cầu vendor, tải đỉnh camera/audio, brownout và shutdown |

Không tái sử dụng camera DVP ESP32 chỉ vì cáp trông giống nhau. Không đoán GPIO,
không khẳng định I2S bất khả dụng trước khi kiểm tra pinmux/schematic/BSP. USB
host role có thể ảnh hưởng provisioning/debug và phải nghiệm thu cấu hình thực.
Không ghi giá/BOM tổng hoặc số giờ pin chưa được kiểm chứng. Ngắt nguồn khi nối
ngoại vi; không dùng tài liệu pinout ESP32 cho Luckfox.

Điều kiện nghiệm thu: capture đúng focus, display đủ glyph, audio không clipping,
boot hoàn toàn offline và chạy ổn định đồng thời trong giới hạn nguồn/RAM. Xem
[roadmap](ROADMAP.md) trước khi đặt kỳ vọng hiệu năng.
