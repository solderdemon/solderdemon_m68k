# ATF1502AS на окремому PLCC-44 адаптері: прошивка через USB-Blaster

Це коротка інструкція для перевірки **ATF1502AS-10JU44** до встановлення в
SolderDemon m68k Classic r2.14. На платі стоять **два однакові за типом, але
різні за прошивкою** чіпи: IC2 — `bin/ic2_decoder.jed`, IC3 —
`bin/ic3_glue.jed`. Позначте запрограмовані мікросхеми, перш ніж виймати їх
з адаптера.

## Що під'єднати

PLCC-44 нумерується **за видом зверху**; знайдіть мітку піна 1 на корпусі й
на адаптері. Перед подачею живлення прозвоніть відповідність PLCC-падів і
виводів вашого конкретного адаптера PLCC→DIP: у різних адаптерів розводка DIP
різна. Під'єднуйтеся за **номерами PLCC**, а не за номерами DIP.

| Сигнал | Контакти PLCC-44 | Контакт 10-pin USB-Blaster |
|---|---:|---:|
| +5 V | 3, 15, 23, 35 — **усі чотири** | 4 — VCC target sense |
| GND | 10, 22, 30, 42 — **усі чотири** | 2 і 10 |
| TCK | 32 | 1 |
| TDO (вихід CPLD → програматор) | 38 | 3 |
| TMS | 13 | 5 |
| TDI (програматор → CPLD) | 7 | 9 |
| не підключати | решта PLCC | 6, 7, 8 |

На адаптері додайте керамічний **100 нФ між VCC і GND біля корпусу**; короткі
проводи JTAG полегшують перший запуск. Живіть мікросхему від **окремого
стабілізованого джерела 5 В** (5 V ±5% для цього варіанта); з'єднайте землю
джерела із землею Blaster. Контакт 4 кабелю — опорна напруга цілі для
програматора: подайте на нього ті самі +5 В, але **не вважайте USB-Blaster
джерелом живлення чіпа**. Перед вставлянням CPLD виміряйте 5 В і перевірте,
що VCC та GND не замкнені. Вставляйте/виймайте чіп лише без живлення.

Для 2×5 роз'єму з ключем перевірте мітку контакту 1 на **самому кабелі**:
вид з боку контактів легко сплутати з видом з боку дротів. Один чіп на
адаптері — **один JTAG-пристрій**, на відміну від ланцюга з двох на готовій
платі J9 (`TDI → IC2 → IC3 → TDO`).

## Чим прошивати

Файли `.jed` у `bin/` — вхід для програматора, але **OpenOCD не прошиває
ATF1502AS безпосередньо з JEDEC**. USB-Blaster можна використати як транспорт
JTAG для відтворення **SVF**, згенерованого Microchip **ATMISP** для одного
ATF1502AS. ATMISP 7 на Windows підтримує безпосередньо **ATDH1150USB**, а не
USB-Blaster; тому для Blaster потрібен крок `JED → SVF → OpenOCD`.

1. Встановіть [ATMISP](https://www.microchip.com/en-us/development-tool/atmisp)
   на Windows. Створіть ланцюг **з одного ATF1502AS** у PLCC-44, виберіть
   `Program/Verify` та відповідний `.jed` (`ic2_decoder` або `ic3_glue`).
   Не вмикайте security/JTAG-disable опції. За потреби спочатку згенеруйте
   окремий SVF для `Erase` / `Blank Check` / `Verify`.
2. У режимі **SVF output** задайте файл, запустіть операцію і закрийте ATMISP,
   щоб SVF було дописано. У старому посібнику ATMISP це
   `Process → Options → Write to SVF file → Yes`, SVF Rev. D, `Use STATE RESETS`
   → Yes, далі `Process → Run`; розташування пунктів у ATMISP 7 може
   відрізнятися. Переконайтеся, що SVF не порожній і що він створений для
   **одного** чіпа, а не для ланцюга J9.
3. Підключіть адаптер і окреме живлення. У терміналі з OpenOCD та
   конфігураційними файлами OpenOCD спершу перевірте, чи читається JTAG ID:

   На Ubuntu: `sudo apt update && sudo apt install openocd`.

   ```sh
   openocd -f interface/altera-usb-blaster.cfg \
     -c 'transport select jtag' \
     -c 'jtag newtap atf1502 tap -irlen 10' \
     -c 'init; scan_chain; shutdown'
   ```

   Назва `interface/altera-usb-blaster.cfg` залежить від пакета OpenOCD;
   перевірте її у вашому каталозі `scripts/interface/`. Має з'явитися
   **стабільний ненульовий IDCODE** для одного TAP. `0x00000000`,
   `0xffffffff`, помилка відкриття USB чи відсутність TAP — спершу перевірити
   живлення, нумерацію PLCC, TDI/TDO та драйвер програматора. Не запускайте
   SVF, поки читання ID нестабільне.
4. Відтворіть SVF, згенерований для вибраної прошивки:

   ```sh
   openocd -f interface/altera-usb-blaster.cfg \
     -c 'transport select jtag' \
     -c 'jtag newtap atf1502 tap -irlen 10' \
     -c 'init; svf /absolute/path/to/one_chip_program_verify.svf -progress; shutdown'
   ```

   У Windows використайте абсолютний шлях у форматі, який розуміє ваш
   OpenOCD, без пробілів або з належним екрануванням. Успішне завершення
   `Program/Verify` з **нульовою кількістю помилок порівняння TDO** —
   практична перевірка програмування. За бажанням вимкніть живлення,
   увімкніть знову та відтворіть окремий `Verify` SVF.

Якщо у вас **ATDH1150USB**, ATMISP може виконати `Program/Verify` напряму
без OpenOCD. TL866/minipro для ISP-програмування ATF1502AS тут не підходить.

## Нотатка про результат першої спроби

Заповніть після фізичної перевірки (цей репозиторій не може підтвердити стан
окремих отриманих чіпів):

| Дата / маркування чіпа | Прошивка | Програматор / ПЗ | IDCODE | Program/Verify | Повторна Verify |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## Джерела

- [Microchip ATF1502AS datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/ATF1502AS-ATF1502ASL-5V-32-Macrocell-CPLD-Data-Sheet-20006619A.pdf) — PLCC-44 pinout, живлення та JTAG.
- [Microchip ATMISP](https://www.microchip.com/en-us/development-tool/atmisp) і [ATF15xx ISP guide](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/UserGuides/Atmel-8968-CPLD-ATF-ISP-UserGuide.pdf) — генерація SVF.
- [Intel USB-Blaster user guide](https://www.intel.com/content/dam/support/us/en/programmable/support-resources/bulk-container/pdfs/literature/ug/archives/ug-usb-blstr-15.1.pdf) — 10-pin JTAG.
- [OpenOCD USB-Blaster](https://openocd.org/doc/html/Debug-Adapter-Configuration.html) і [SVF command](https://openocd.org/doc/html/Boundary-Scan-Commands.html).
