# Kỷ luật chung của vòng lặp — đọc khi có nghi ngờ

Hai vai dùng chung file này. Nó KHÔNG được nạp mỗi lượt: chỉ mở khi gặp đúng tình huống
bên dưới. Đọc nó mỗi lượt là trả lại đúng cái giá mà việc gom lô đang cắt đi.

File này là LUẬT. Nếu một sự cố đang xảy ra ngay lúc này, tra
[`runbook.md`](runbook.md) theo TRIỆU CHỨNG — đó mới là chỗ có lối ra.

| Nghi ngờ điều gì | Mục |
|---|---|
| Một câu trả lời có đáng tin không | §1 |
| Lệnh exit 0 nhưng đọc lại không thấy đổi | §2 |
| Sắp gõ một lệnh trông vô hại | §3 |
| Test đỏ — lỗi của PR hay của cách chạy? | §4 |
| Test này có thật sự canh cái gì không | §5 |
| Một mục MIỄN TRỪ / allowlist còn tác dụng không | §5.6 |
| Diff có test mới — nó vô nghĩa kiểu nào? | §6 |
| Sắp hoàn tác thứ vừa tiêm vào để thử chiều ngược | §7 |
| Một cổng chạy xong, xanh, mà không kiểm gì | §8 |
| Hook git đọc nhầm repo | §9 |

---

## 1. Đọc ngược lại, đừng tin

Lỗi đắt nhất của vòng lặp này không phải viết code sai. Là **làm lại việc đã có**, hoặc
**tưởng đã gửi thứ chưa gửi**. Cả hai đến từ việc tin một câu trả lời thay vì đọc lại nguồn.
Không ai nói dối — công cụ và trạng thái đều có thể lệch.

| Muốn biết | ĐỌC | KHÔNG tin |
|---|---|---|
| Việc này đã ai làm chưa | `git log --all --grep="#<N>"`, `git grep` trên `origin/<base>` | mô tả issue, comment "chưa làm" |
| Bản sửa đã tới base chưa | `git merge-base --is-ancestor <sha> origin/<base>` | comment nói "đã ship" kèm sha |
| Diff thật của PR | `gh pr diff <PR>` | phần "Đã làm" trong thân PR |
| PR đã review chưa | nhãn trên **issue neo** | nhãn trên PR — nó sống sót qua push mới |
| Lô mình đang giữ | `tal assert` | thẻ `.tal-lease.json` đọc bằng mắt |
| Issue nào trong lô đã có commit | `tal batch status` | trí nhớ của lượt trước |
| Ai đang giữ gì | `tal status` | phỏng đoán |

## 2. Khi công cụ nói dối

Dấu hiệu: lệnh exit 0 nhưng đọc lại thấy không đổi.

1. **Đừng chạy lại lệnh** — nó sẽ lại exit 0 và bạn mất thêm một vòng.
2. **Đi đường vòng bằng `gh`/`git` trực tiếp** để hoàn thành việc.
3. **Mở issue cho lỗi công cụ**, kèm lệnh tái hiện và đoạn code nghi ngờ.
4. **Nếu lỗi nằm ở file đang có người giữ lease** (`tal status`) → **đừng sửa**. Bàn phần
   mình đã kiểm vào comment issue của họ. Hai bản sửa song song vào cùng một file chính là
   vấn đề mà cả cái vòng lặp này đang chữa.

Ba thói quen đi kèm, cần cả khi công cụ đang lành:

- **Đọc lại từ NGUỒN sau mỗi lần đổi trạng thái** — nhãn của issue sau một `review-verdict`,
  thân PR sau một `tal pr`. Không phải đọc lại thứ mình vừa gõ.
- **Lệch so với kỳ vọng là một PHÁT HIỆN**, không phải một phiền toái. Mở issue kèm lệnh
  tái hiện.
- **Mọi bản vá cho chính công cụ đi MỘT đường.** Bốn PR song song vào cùng một file lớn là
  bốn conflict; điều đó đã xảy ra thật.

## 3. Tám cạm bẫy đã trả giá

Cả tám đến từ **một session** review 13 PR. Không cái nào là bất cẩn nhất thời — mỗi cái
là một lỗ mà skill lúc đó không phủ.

**1. `cd` không phải một rào.** `cd X && lệnh` mà `cd` **trượt** thì **lệnh vẫn chạy**, ở
thư mục cũ.

```sh
git -C "$WT" merge origin/<base>       # ĐÚNG — đường dẫn đi cùng lệnh
cd "$WT" && git merge origin/<base>    # SAI — cd trượt là merge vào chỗ khác
```

Hậu quả thật: một `git merge` chạy nhầm vào **worktree dùng chung đang giữ WIP chưa commit
của session khác**, phải `git merge --abort` để cứu. Xảy ra **hai lần trong một session** —
worktree vừa bị `tal gc` xoá, và một đăng ký worktree cũ, cả hai đều làm `cd` trượt.

**2. Số `0` là một khẳng định.** Một câu đếm trả `0` **một lần** chưa đủ để nói "không còn
gì". Đã báo "0 PR mở trên cả 8 repo" trong khi có **13** PR mở. Trước khi báo một số không,
hỏi lại bằng đường KHÁC (liệt kê thay vì đếm; `--state all` rồi lọc). Với hàng đợi của vòng
lặp thì `tal` đã tự phân biệt — xem [runbook §8](runbook.md).

**3. Chạy harness thiếu tham số → đỏ giả.** Xem §4.

**4. Grep nhầm cây.** Xem §4.

**5. Nhận một issue mà bản sửa đã nằm trong một PR đang mở.** Một PR cụm đóng nhiều issue,
nên N−1 issue còn lại **không bao giờ** được ghi nhãn và trông vẫn "rảnh". `tal queue` đã
đo và loại chúng (nó hỏi PR mở nào đóng issue nào). Cạm bẫy còn lại là **nhặt tay** một số
issue đọc được ở đâu đó, hoặc `tal claim --force`: cả hai đều đi vòng qua phép đo ấy.

**6. Gõ một sha bằng tay.** **Lấy sha từ git, đừng gõ, đừng cắt ngắn.**
`SHA=$(git rev-parse …)` rồi in ra trước khi dùng. Giá đã trả: một sha gõ tay truyền cho
`git update-index --cacheinfo` — lệnh ghi thẳng vào index và **không kiểm object có tồn
tại** — nên nó hỏng ở clone của người tiếp theo, không hỏng ở máy đã gõ.

**7. Merge PR của chính mình.** Năm lần trong một session. `tal` nay chặn ở cả cửa
`review-verdict` lẫn cửa merge, và cờ phá rào (`--allow-self`) ghi thẳng một comment
"TỰ MERGE — tách vai bị phá" lên PR. Nếu hoàn cảnh thật sự buộc phải làm (bản vá cho chính
công cụ đang hỏng): **nói to trong comment** rằng luật đã bị phá, vì sao, và chỗ nào đáng
được xem lại — để một session sau vẫn review được sau khi việc đã rồi. Đừng giấu.

**8. Sửa một file tracked trong worktree dùng chung để tự gỡ kẹt.** Nếu buộc phải: sửa nhỏ
nhất có thể, **khôi phục ngay** (theo cách ở §7, không phải `git checkout --`), và kiểm
`git status` sạch trước khi đi tiếp. Có session khác đang làm trong đúng cây đó.

## 4. Test đỏ ≠ PR sai

Loại trừ MÔI TRƯỜNG trước khi kết luận về PR. Ba dấu hiệu:

| Dấu hiệu | Gần như chắc chắn |
|---|---|
| Đỏ **tức thì** (< 1s), **0 assertion** | Ứng dụng chưa bao giờ khởi động: thiếu dependency, thiếu file môi trường, sai cwd |
| **Mọi** test đỏ với **cùng một** thông điệp | Môi trường (hoặc một bước migrate/bootstrap chết) |
| Lỗi nêu một đường dẫn **ngoài** cây đang test | Autoload/symlink trỏ nhầm cây |

Hai luật đi kèm:

- **Đọc dòng `Run:` của chính harness trước khi chạy nó.** Đã trả giá: một script test được
  gọi **thiếu đối số `$1`** → biến đường dẫn bên trong giải ra `/`, hai ca đỏ, và suýt bị
  báo thành lỗi của PR. Gọi đúng chữ ký, nó **xanh 5/5**.
- **Luôn đo baseline trước.** Chạy đúng bộ test ấy trên `origin/<base>` **chưa merge PR**.
  `27 passed` → `28 passed` là bằng chứng; `28 passed` đứng một mình không nói gì.

Và: **muốn kiểm một PR thì phải kiểm BÊN TRONG một cây đã merge PR đó.** `grep` ở worktree
chính là đang đọc base, **không phải** PR.

## 5. Rào rỗng — hình dạng lỗi mà vòng lặp này hay đẻ ra

Sáu ca độc lập trong **một ngày làm việc**. Bốn cái bị bắt ngay lúc viết, bằng nghi thức
chạy chiều ngược. Hai cái đã sống trong repo hàng tháng, vì **không ai chạy chiều ngược cho
một test ĐÃ CÓ**.

Một rào rỗng có tên đúng, có thông điệp lỗi soạn kỹ, trông như đang canh một bất biến —
trong khi phép đo của nó ĐÚNG bất kể code làm gì. Nó tệ hơn không có test: người đọc sau
tin rằng chỗ đó đã được phủ.

Năm khuôn, cả năm đều tái diễn:

1. **Baseline không phải số 0.** Nếu khung test bọc mỗi bài trong một transaction thì mức
   lồng transaction bắt đầu từ **1**, nên `lớn hơn 0` luôn đúng — kể cả khi thứ đang được
   canh đã bị lôi ra khỏi transaction. Chụp baseline **ngay trước** lời gọi và so **tương
   đối**; in cả hai số vào thông điệp lỗi.
2. **Fixture trùng kỳ vọng.** Gieo `(−400, −36)`, khẳng định `(−400, −36)` ⇒ "không ghi gì
   cả" cũng xanh. Fixture phải **khác** kết quả đúng.
3. **Đo sau một hàm tự chữa.** Một wrapper kết thúc bằng recalc/normalize nuốt mọi lỗi được
   tiêm. Gọi **thẳng** đơn vị đang kiểm.
4. **Quét văn bản thay vì hành vi.** `contains(mã_nguồn, "KindX")` xanh với mọi lần NHẮC
   tên — một nhánh `switch`, một bảng nhãn, một biến trung gian. Cắt lời gọi thật cuối cùng
   thì rào vẫn xanh. Khớp **lời gọi** (`Raise\(\s*KindX`), không khớp cái tên.
5. **Khẳng định trên một giá trị do chính test tự tính.** Test chép lại công thức bằng tay
   rồi khẳng định nó bằng một hằng số cũng do nó viết. Nó **không chạm dòng production
   nào** — xoá phần tính toán khỏi service, test vẫn xanh.

   Nó không phải bốn khuôn trên: baseline ổn, fixture khác kỳ vọng, không có gì tự chữa,
   không quét văn bản. Hình dạng riêng của nó là **trôi trong im lặng** — nó chỉ đo chính
   nó. VÍ DỤ đã đo ở một kho tiêu thụ: công thức thật mang **bảy** số hạng, test ghim
   **bốn**; ba số hạng chưa bao giờ được canh, hai trong số đó từng là lỗi thật. Ba lần
   tiêm vào công thức thật: test mới đỏ cả ba, **test cũ xanh cả ba**.

   Nhận ra nó: grep thân test tìm một tên class/service của production. Không có ⇒ nó không
   bao giờ gọi production. Sửa bằng cách gọi **thẳng** đơn vị thật và khẳng định trên thứ nó
   TRẢ VỀ — không bao giờ bằng cách chép công thức vào test. Cùng khuôn ấy còn một ca thứ
   hai đi bằng **đường khác** nên ba lần tiêm trên không chạm tới: **một hình dạng thường có
   nhiều hơn một con đường.**

6. **Rào chống rào rỗng tự nó có thể rỗng.** Bản đầu của rào canh khuôn 1 quét theo TỪNG
   DÒNG, nên trượt đúng ca nó sinh ra để bắt: giá trị được đưa vào một biến trung gian rồi
   so ở chỗ khác, và formatter cắt lời gọi ra làm hai dòng. Phát hiện bằng cách chạy chiều
   ngược — trả lại lỗi cũ, xem rào có im không. Đó là ca thứ **bảy**, do chính người đang
   sửa khuôn 1 tạo ra.

7. **Rào kêu oan bị TẮT, chứ không bị cãi.** Bản theo-từng-file gắn cờ sáu dòng chỉ vì
   chúng ở chung file với một phép đo. Siết bằng cách đòi **chủ ngữ** của khẳng định phải
   liên quan tới thứ đang được đo. Một rào báo động giả cỡ đó sẽ bị gỡ, và gỡ xong thì nó
   không còn cãi được nữa.

### 5.6. Mọi mục MIỄN TRỪ phải tự chứng minh còn TẢI LỰC

Một allowlist là chỗ rào tự đục lỗ vào mình, và cái lỗ ấy mục theo một con đường **không ai
canh**: file được miễn trừ thôi vi phạm (đổi tên, viết lại, bị xoá), mục vẫn nằm đó, và từ
đó trở đi nó chỉ là một dòng chữ. Rào vẫn xanh, danh sách vẫn đọc như "đang trong tầm kiểm
soát" — trong khi nó không miễn trừ cho ai, và lần vi phạm THẬT tiếp theo ở đúng file đó
được nó che.

Quy ước **không** phải một cái tag `@ratchet` cộng một lượt quét văn bản: quét văn bản
chính là **khuôn 4**, và nó chỉ ghi lại *lời khai* rằng ai đó đã chạy chiều ngược. Quy ước
là một phép đo CHẠY ĐƯỢC:

> **gỡ một mục miễn trừ ⇒ thứ nó che phải HIỆN RA**

Ba dạng đã dùng được, chọn một, đừng bịa dạng thứ tư:

| Dạng | Cách đo |
|---|---|
| Bỏ từng mục | Gỡ **từng** mục một, đòi kết quả phải ĐỔI |
| Quét ngược | Một mục không còn khớp thứ gì trong cây ⇒ ĐỎ |
| So hai chiều | Đối chiếu danh sách với thực tế theo **cả hai** chiều |

Ba thứ **không** cần rào loại này — đừng thêm: một allowlist **rỗng** (không mục nào để
mục), một danh sách **khẳng định** (file bắt buộc phải CHỨA gì đó — file bị xoá là test tự
đỏ), và một hằng số **không ai đọc** (nới nó ra chẳng đổi gì kiểm chứng được).

## 6. Bốn kiểu test vô nghĩa, và chỗ tiêm lỗi đúng

Nhận ra chúng trong diff nhanh hơn là chạy lại:

| Dấu hiệu | Vì sao vô nghĩa |
|---|---|
| Test đọc **mã nguồn** (đọc file, đếm chuỗi, regex trên file) | Ghim VỊ TRÍ của code, không ghim hành vi. Đỏ khi dời code đúng cách, xanh khi hành vi hỏng mà chuỗi vẫn còn |
| Test **mock** đúng class/method chứa thứ đang kiểm | Mock nuốt luôn cái rào |
| Tiêm lỗi bằng cách **đập môi trường** (xoá bảng, ngắt kết nối) | Lỗi rơi SỚM hơn chỗ đang đo |
| Đầu vào **không kích hoạt** nhánh đang kiểm | Gửi trùng giá trị đang có ⇒ rào "chỉ chạy khi ĐỔI" không chạy lần nào |

**Chỗ tiêm lỗi đúng nằm GIỮA hai thứ đang được buộc lại với nhau** (một model event, một
cổng được inject). Tiêm ở đó ghim **thuộc tính**; mock một service thường chỉ ghim **cách
cài đặt**.

Một luật chung nữa, rẻ và hay bị quên: **matcher biến thiên nào cũng nuốt đối số thêm** —
câu giải thích bạn định gửi kèm sẽ bị đọc thành một giá trị nữa để so, và test xanh vĩnh
viễn. Kiểm **chữ ký** của matcher trước khi truyền thông điệp cho nó.

## 7. Hoàn tác một thay đổi: dùng `cp`, KHÔNG dùng `git checkout --`

Nghi thức chiều ngược — gỡ bản sửa, xem test ĐỎ, đặt lại — là bắt buộc ở cả hai vai. Cách
hiển nhiên để đặt lại là cách sai.

`git checkout -- <path>` khôi phục từ **index**. Worktree của một lô mang việc chưa commit
từ lúc bắt đầu tới `tal pr`, nên lệnh đó vứt *toàn bộ* phần chưa commit trong file, không
chỉ dòng bạn vừa tiêm.

Đã trả giá hai lần trong một session. Lần đắt mất **cả một implementation chưa commit của
subagent** — một field, một vòng lặp được tách, và chỗ gọi — để lại bản build với chín lỗi
"chưa định nghĩa" và không còn bản nào trên đĩa; subagent phải dựng lại từ chính transcript
của nó.

```sh
cp <file> /tmp/x.good          # TRƯỚC khi tiêm
…tiêm, chạy test, thấy ĐỎ…
cp /tmp/x.good <file>          # đặt lại
diff -q <file> /tmp/x.good     # kiểm
```

Đo chứ không suy: với một dòng chưa commit nằm đó, `git checkout --` xoá nó; vòng `cp` giữ
được nó và vẫn dọn sạch dòng vừa tiêm.

Lớp phòng thủ thứ hai là một luật về THỨ TỰ, không phải một lời khuyên: **commit trước, soi
sau.** Một subagent trả về cả cây đầy việc chưa commit, nên commit trước khi kiểm biến kết
cục tệ nhất từ "code bốc hơi" thành "một commit cần amend".

## 8. Một cổng khoá theo HÌNH DẠNG là một cổng sắp im lặng

Đây là hạt nhân, và nó lặp lại ở mọi tầng.

Một cổng từng hỏi: *"đường dẫn nào vừa đổi mà LÀ một thư mục chứa file khai module?"* — tức
nó khoá vào **hình dạng đường dẫn** của một kiểu liên kết cụ thể. Khi cách tổ chức repo đổi,
một lần sửa bên trong sinh ra đường dẫn **của file**, không bao giờ sinh ra chính thư mục
ấy. Danh sách vì thế **luôn rỗng**, cổng trả về ngay lập tức. Xanh. Mỗi lần.

Không ai quyết định tắt nó. Nó chỉ **thôi khớp với thực tế**, và không test nào phát hiện
vì fixture của test cũng cho ăn đúng hình dạng cũ. Cổng chết cả một ngày; lượt chạy đầu tiên
sau khi phục hồi tìm thấy drift ngay trên base — đúng từ cái cửa sổ không ai canh.

Cùng lớp lỗi ấy đã cắn ở một chỗ khác của chính công cụ này: một hằng số ghim cứng tên hai
nhánh, nên rào chặn push-thẳng **im lặng không đóng** ở mọi repo đặt tên nhánh khác. Rào
đó nay được dựng từ CONFIG (`tal` đọc base/promotion từ `.claude/agent-loop.json`).

Ba luật rút ra:

- **Khoá vào QUAN HỆ, đừng khoá vào hình dạng.** "Đi ngược lên tổ tiên gần nhất có file
  khai module" sống sót qua việc đổi cách tổ chức; "là một thư mục chứa file khai module"
  thì không.
- **Một cổng chỉ trả rỗng phải NÓI là nó rỗng.** Không phân biệt được "không có gì để
  kiểm" với "không đo được" thì cổng đã là trang trí. So [runbook §8](runbook.md).
- **Fixture của test phải là hình dạng THẬT hôm nay**, không phải hình dạng lúc test được
  viết. Một fixture cũ làm cổng và test cùng chết mà vẫn cùng xanh.

Nói cách khác: **bản sửa đã tồn tại, đã merge, và vẫn không có tác dụng** là lớp hỏng tệ
nhất của một công cụ tự động.

## 9. `GIT_DIR` thắng cả `-C`

Git **xuất `GIT_DIR` cho hook**, và nó đè cả `-C` lẫn `cwd`. Nên `git -C <submodule> …`
viết trong một git hook KHÔNG chạy trong submodule. Ở worktree gốc `GIT_DIR` là `".git"`
tương đối nên tình cờ giải đúng; trong **worktree phụ** (vòng lặp luôn sống ở đó) nó là
đường dẫn tuyệt đối, nên mọi lookup rơi về repo chính và một pointer đã push đàng hoàng
vẫn bị báo dangling.

Cách sửa cho hook của repo:
`env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C "$path" …`.
Đừng "sửa" bằng `--no-verify` — cái hook đang kiểm là thứ có thật.

## 10. Ba ca đã cắn thật, đáng biết trước

- **#1335 — `tal pr` nuốt `--body-file` khi PR đã tồn tại mà vẫn exit 0.** Thân PR kẹt ở
  vòng 1, reviewer đọc mô tả sai và trả về một PR **đã sửa** — hai vòng liền trên #1318.
  *Đã sửa trong `tal` (cmd_pr giờ gọi `gh pr edit` thật).* Giữ lại ở đây làm ví dụ cho
  luật: **lỗi công cụ thì sửa công cụ, đừng dạy mọi skill một nghi thức né tránh.**
- **Nhãn `review-passed` sót trên PR** làm rào merge tưởng một bản chưa ai xem là đã xem.
  Vì thế căn cứ luôn là nhãn trên **issue neo**, không phải nhãn trên PR.
- **Một issue bị kết luận "còn lỗi"** trong khi code đã ship ba ngày trước — vì đọc mô tả
  issue thay vì đọc `origin/<base>`.

## 11. Không bao giờ

- **Không sửa gì trước khi `tal claim` / `tal batch claim` thành công.**
- **Không chạy full suite.** Rào cứng ở `hook-guard`. Vòng lặp chạy `tal tests --run`.
  Full suite chạy ở CI của PR vào nhánh promotion, hoặc do người gõ `tal fullsuite`.
- **Không push khi `tal assert` fail.** Lease đã cấp cho người khác thì commit của bạn là
  rác — DỪNG, báo lại, đừng biến xung đột thành hỏng dữ liệu.
- **Không `--no-verify`, `--force`, `--skip-*`** để vượt một cổng đang chặn. Cổng chặn vì
  có thứ thật cần xử lý.
- **Không commit WIP của người khác.** Stage đường dẫn tường minh, không `git add -A`.
- **Không đổi tên nhánh khỏi `issue-<số>`.** Cần một nhánh khác thì **mở sub-issue** và
  dùng số của nó.
- **Không gõ một sha bằng tay.** (§3.6)
- **Không viết lại một file mà một PR đang mở đã chạm.**
- **Không bịa vấn đề để tỏ ra đã làm việc.** Một kết quả âm có bằng chứng vẫn là kết quả.

---

## Nguồn — đoạn nào đến từ đâu

Toàn bộ nội dung mới ở đây được **lọc** (không chép) từ tài liệu vòng lặp đang sống trong
kho tiêu thụ `godx-jp/godx-tempo`, nhánh `dev`. Mọi giả định của riêng kho đó (tên thư mục,
tên framework test, tên engine CSDL, tên app, tên test cụ thể) đã bị nâng lên một bậc trừu
tượng hoặc gỡ bỏ. Bảng này để `godx-tempo#4147` biết cái gì đã sang plugin và có thể xoá ở
kho tiêu thụ.

| Mục ở đây | Nguồn |
|---|---|
| §2, ba thói quen đi kèm | `docs/guide/agent-loop-skills.md` §6 (L413–428) |
| §3 (tám cạm bẫy) | `docs/guide/agent-loop-skills.md` §4 (L247–309) |
| §4 | `docs/guide/agent-loop-skills.md` §3 (L176–197) |
| §5 (năm khuôn + rào-của-rào + rào kêu oan) | `docs/guide/agent-loop-skills.md` §6b (L429–527) |
| §5.6 (miễn trừ phải còn tải lực) | `docs/guide/agent-loop-skills.md` §6b, phần "Every EXEMPTION…" |
| §6 (bốn kiểu test vô nghĩa + chỗ tiêm + matcher biến thiên) | `.claude/agent-loop/test-policy.md` |
| §7 (`cp`, không `git checkout --`) | `docs/guide/agent-issue-loop.md` L522–551 |
| §8 (cổng khoá theo hình dạng) | `docs/guide/agent-issue-loop.md` L611–655 |
| §11, hai mục bổ sung (không đổi tên nhánh · không viết lại file PR đang mở) | `docs/guide/agent-loop-skills.md` §7 |

**Bằng chứng độc lập rằng §5 và §6 là luật CHUNG chứ không phải của một kho:**
`godx-jp/godx-task` — một kho khác stack, khác đội — tự viết ra cùng doctrine trong
`.ai/rules/tests.md` ("mutation-check every guard", "guard-on-guard", "exemptions get a rot
test") mà không chép từ đâu. Hai kho độc lập hội tụ vào cùng ba luật là đúng định nghĩa
"còn đúng ở một kho stack khác" ⇒ thuộc plugin.
