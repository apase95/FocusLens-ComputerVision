# ESP32-CAM OV3660 — lịch sử và kiểm tra cục bộ

> Tài liệu legacy, giữ để tái lập thử nghiệm ESP32/host. Mục tiêu hiện tại là
> [Luckfox Pico Max với camera CSI cục bộ](docs/LUCKFOX_HARDWARE.md), không cần
> camera HTTP hoặc server LAN. Firmware/pinout ESP32 bên dưới không áp dụng cho
> Luckfox; chưa có kiểm tra phần cứng Luckfox trong dự án.

Chạy các lệnh từ thư mục gốc của repository.
Arduino CLI **1.5.1**: `.camera-tools/bin/arduino-cli`; core Espressif
**3.3.12**: `.camera-tools/data/packages/esp32/hardware/esp32/3.3.12`.
Config riêng: `arduino-cli.yaml` (đường dẫn tương đối với thư mục chạy lệnh).
Không cần cài thêm thư viện camera. Toolchain esp-x32 2601, esptool 5.3.1.

`CameraWebServer/` sao chép từ example của core này, không dùng master.
Giữ nguyên notices upstream. `app_httpd.cpp`, `camera_index.h`, `camera_pins.h`
giữ nguyên; đổi `board_config.h` chọn AI-Thinker và vô hiệu hóa LED PWM/HTTP.
Sketch thêm header riêng, chẩn đoán PSRAM/PID, STA timeout 30 giây và giữ GPIO4 LOW.
JPEG có fallback DRAM/SVGA khi không thấy PSRAM; khởi đầu stream QVGA.
Không thao tác SD hay kiểm tra GPIO ngoài. GPIO0 là XCLK khi chạy, không giữ IO0 khi reset để chạy sketch.

## Kết quả compile lịch sử (không phải kiểm tra hardware hiện tại)

- Biên dịch thật thành công với `esp32:esp32:esp32cam`, Huge APP 3MB mặc định.
- Flash 1,059,085 / 3,145,728 bytes (33%); RAM tĩnh 69,808 / 327,680 (21%).
- Chỉ dùng SSID giả ghi rõ COMPILE_ONLY; header đã xóa. **Không upload bản trong `build/compile-only`.**
- Các báo cáo lịch sử có ghi nhận OV3660, PSRAM và capture/stream JPEG hoạt động;
  đây không phải xác nhận phần cứng hiện tại và không được kiểm tra lại khi xuất bản.
- Không flash, không mở serial, không thay MicroPython hay `esp32cam_firmware.bin`.

## Cấu hình Wi-Fi tại terminal riêng

ESP32 cần Wi-Fi **2.4 GHz**. Không gửi mật khẩu vào chat hoặc dòng lệnh.
Chạy ở thư mục dự án:

```sh
python3 scripts/setup_wifi.py
```

Cả SSID và mật khẩu nhập ẩn qua getpass. Script tạo
`CameraWebServer/wifi_secrets.h` mode 0600, escape byte UTF-8 bằng octal C/C++.
Không ghi đè file đã tồn tại; nếu muốn đổi mạng, tự xóa header ở máy rồi chạy lại.
Header, tools và build được gitignore. Firmware/build thật vẫn chứa bí mật:
không chia sẻ header, binary, build hoặc log verbose. Header hiện có được giữ riêng;
task setup không đọc nội dung và không chạy compile smoke khi header tồn tại.

## Biên dịch và bước upload sau khi bạn đồng ý

```sh
.camera-tools/bin/arduino-cli version
.camera-tools/bin/arduino-cli --config-file arduino-cli.yaml core list
.camera-tools/bin/arduino-cli --config-file arduino-cli.yaml compile --fqbn esp32:esp32:esp32cam --build-path build/home CameraWebServer
```

**Dừng ở đây nếu chưa muốn ghi đè MicroPython.** Upload sau sẽ thay firmware
MicroPython hiện tại và có thể làm mất dữ liệu trên flash; sao lưu dữ liệu cần giữ trước.
Chỉ sau khi cấu hình Wi-Fi, compile lại thành công và đồng ý flash:
đóng mọi terminal/monitor đang giữ serial rồi mới chạy:

```sh
.camera-tools/bin/arduino-cli --config-file arduino-cli.yaml upload --fqbn esp32:esp32:esp32cam --port /dev/ttyUSB0 --input-dir build/home CameraWebServer
.camera-tools/bin/arduino-cli --config-file arduino-cli.yaml monitor --port /dev/ttyUSB0 --config baudrate=115200
```

Nhấn RST nếu cần đọc lại khởi động. Mở URL `http://<IP in trên serial>/`
trên máy cùng LAN, chọn **Start Stream**. Thoát monitor bằng Ctrl-C trước upload tiếp.
Web server mẫu không có xác thực/TLS: chỉ dùng mạng tin cậy, không mở port Internet.
Nếu Wi-Fi timeout sau 30s: kiểm tra cấu hình cục bộ, băng tần/router, rồi RST.

## Nguồn điện và lỗi camera

Cấp nguồn qua USB của ESP32-CAM-MB; nếu brownout dùng cáp data ngắn, tốt và
nguồn USB đủ dòng. Ngắt điện trước khi gắn lại cáp ribbon camera.
**Không bao giờ cấp 5V vào 3V3.** Không cần đấu dây thủ công cho bước này.
Pin layout AI-Thinker mới là giả định từ mô tả bo, chưa xác nhận trực quan.
Nếu `Camera init failed`/không thấy sensor: kiểm tra nguồn, cáp ribbon khi đã ngắt điện,
model camera và sơ đồ chân bo thực tế; không đổi model hoặc thử chân ngẫu nhiên.
Chỉ kết luận camera hoạt động khi hình/stream phần cứng thực sự chạy.

## Tái lập cài đặt và kiểm tra cô lập

CLI lấy từ release chính thức v1.5.1 Linux_64bit:
https://github.com/arduino/arduino-cli/releases/tag/v1.5.1
SHA256 archive: `28a8e119c498a25607821c36cb2dc49e8463941b261a0d99091baa7bc692dd2b`.
Core index chính thức nằm trong YAML; CLI kiểm tra checksum gói khi cài.

```sh
.camera-tools/bin/arduino-cli --config-file arduino-cli.yaml core update-index
.camera-tools/bin/arduino-cli --config-file arduino-cli.yaml core install esp32:esp32@3.3.12
python3 -m unittest tests/test_camera.py
python3 -m unittest tests/test_compile.py
```

Các lệnh unittest stdlib chỉ chạy hai file được chỉ định, không discovery suite. Hai test camera kiểm tra header
0600, escaping và từ chối ghi đè; RED thiếu module, sau đó GREEN 2 test/0.002s
(wall 0.052s). Compile smoke thật 17.72s, tự xóa header test trong finally;
từ chối nếu đã có header thật. Không chạy suite/integration hoặc hardware test.
